"""
Diagnostics (KWP2000 / UDS): ``diag/protocols/<PROTOCOL>.yml`` and
``diag/<arch>.<variant>/<NODE>/`` (ecu.yml, dids/, lids/, dtcs.yml, routines/, ioctls/).

Besides the document objects, this module builds requests and decodes
responses of the identifiers it describes, encodes/decodes DTC codes and
implements the PSA seed/key algorithm documented in ``diag/protocols/UDS.yml``.
"""
import os
import re
from dataclasses import dataclass, field

from ._yaml import hexint
from .model import Document, Field, Model, hex_out, list_in, ml_in, ml_out
from .multilang import MultiLang
from .signal import ValueTable, decode_payload, dump_signals, encode_payload, load_signals

__all__ = ['DiagProtocol', 'Service', 'Algorithm', 'DiagEcu', 'Addressing', 'SecurityAccess', 'TesterPresent',
           'DiagData', 'Dtc', 'DtcTable', 'Routine', 'Ioctl', 'EcuDiag', 'NegativeResponse',
           'dtc_to_raw', 'raw_to_dtc', 'psa_seed_key', 'parse_hex', 'check_response']

UDS, KWP = 'UDS', 'KWP2000'
DTC_RE = re.compile(r'^([PCBU])([0-9A-F]{4})(?:-([0-9A-F]{2}))?$')


def parse_hex(data):
    """bytes from '22 F1 90', '22F190', a list of ints or bytes"""
    if isinstance(data, str):
        return bytes.fromhex(data.replace(':', ' ').replace('0x', ''))
    return bytes(data)


def _ml_map_in(d):
    return {k: MultiLang.of(v) for k, v in (d or {}).items()}


def _ml_map_out(d):
    return {hexint(k): dict(v) for k, v in d.items()}


class NegativeResponse(Exception):
    """A negative response (7F SID NRC)"""

    def __init__(self, sid, nrc, text=None):
        self.sid, self.nrc, self.text = sid, nrc, text
        super().__init__(f'negative response to 0x{sid:02X}: 0x{nrc:02X}' + (f' ({text})' if text else ''))


def check_response(request_sid, response, protocol=None):
    """Checks a response to a request (raises NegativeResponse), returns the response without its SID"""
    response = parse_hex(response)
    if response[:1] == b'\x7F':
        nrc = response[2] if len(response) > 2 else 0
        text = protocol.negative_responses.label(nrc) if protocol and protocol.negative_responses else None
        raise NegativeResponse(response[1] if len(response) > 1 else request_sid, nrc, text)
    if not response or response[0] != (request_sid + 0x40) & 0xFF:
        raise ValueError(f'unexpected response {response.hex(" ").upper()} to service 0x{request_sid:02X}')
    return response[1:]


# --------------------------------------------------------------------------
# Protocols
# --------------------------------------------------------------------------

@dataclass
class Service(Model):
    sid: int = 0
    name: str = ''
    display_name: MultiLang = None
    comment: MultiLang = None
    request: str = None
    response: str = None
    subfunctions: ValueTable = None

    FIELDS = (
        Field('name'),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
        Field('request'),
        Field('response'),
        Field('subfunctions', load=ValueTable.from_dict, dump=lambda t: t.to_dict()),
    )


@dataclass
class Algorithm(Model):
    name: str = ''
    comment: MultiLang = None
    pseudocode: str = None

    FIELDS = (
        Field('comment', load=ml_in, dump=ml_out),
        Field('pseudocode'),
    )


@dataclass
class DiagProtocol(Model, Document):
    """``diag/protocols/<PROTOCOL>.yml``"""
    protocol: str = UDS
    standard: str = None
    comment: MultiLang = None
    transport: list = None
    services: dict = field(default_factory=dict)       # sid -> Service
    negative_responses: ValueTable = None
    algorithms: dict = None                            # name -> Algorithm

    FIELDS = (
        Field('protocol'),
        Field('standard'),
        Field('comment', load=ml_in, dump=ml_out),
        Field('transport', load=list_in),
        Field('services', load=lambda d: {k: Service.from_dict(v, sid=k) for k, v in d.items()},
              dump=lambda d: {hexint(k): v.to_dict() for k, v in d.items()}),
        Field('negative_responses', load=ValueTable.from_dict, dump=lambda t: t.to_dict()),
        Field('algorithms', load=lambda d: {k: Algorithm.from_dict(v, name=k) for k, v in d.items()},
              dump=lambda d: {k: v.to_dict() for k, v in d.items()}),
    )

    def service(self, sid_or_name):
        if isinstance(sid_or_name, int):
            return self.services[sid_or_name]
        for s in self.services.values():
            if s.name == sid_or_name:
                return s
        raise KeyError(sid_or_name)

    def nrc_text(self, nrc, lang=None):
        return self.negative_responses.label(nrc, lang) if self.negative_responses else None


# --------------------------------------------------------------------------
# ECU
# --------------------------------------------------------------------------

@dataclass
class Addressing(Model):
    transport: str = 'can-tp'     # can-tp | k-line | doip
    bus: str = None
    request_id: int = None
    response_id: int = None
    functional_id: int = None
    kline_address: int = None
    kline_init: str = None
    bitrate: float = None
    protocol: str = None
    comment: MultiLang = None

    FIELDS = (
        Field('transport'),
        Field('bus'),
        Field('protocol'),
        Field('request_id', dump=hex_out(3)),
        Field('response_id', dump=hex_out(3)),
        Field('functional_id', dump=hex_out(3)),
        Field('kline_address', dump=hex_out()),
        Field('kline_init'),
        Field('bitrate'),
        Field('comment', load=ml_in, dump=ml_out),
    )


@dataclass
class SecurityAccess(Model):
    level: int = 0x01        # requestSeed sub-function, sendKey is level + 1
    algorithm: str = None
    key: str = None          # 16 bit constant, 4 hex digits
    comment: MultiLang = None

    FIELDS = (
        Field('level', dump=hex_out()),
        Field('algorithm'),
        Field('key'),
        Field('comment', load=ml_in, dump=ml_out),
    )

    def seed_request(self):
        return bytes([0x27, self.level])

    def key_request(self, seed):
        """27 <level + 1> <key> for a seed (bytes or hex); only the PSA_SEED_KEY algorithm is known"""
        if self.algorithm not in (None, 'PSA_SEED_KEY'):
            raise NotImplementedError(f'algorithm {self.algorithm}')
        return bytes([0x27, self.level + 1]) + psa_seed_key(parse_hex(seed), int(self.key, 16))


@dataclass
class TesterPresent(Model):
    request: str = '3E 00'
    period_ms: int = None

    FIELDS = (Field('request'), Field('period_ms'))


@dataclass
class DiagEcu(Model, Document):
    """``diag/<arch>.<variant>/<NODE>/ecu.yml``: how to talk to one ECU"""
    node: str = ''
    comment: MultiLang = None
    protocols: list = field(default_factory=list)
    addressing: list = None
    sessions: dict = None
    resets: dict = None
    services: list = None
    security_access: list = None
    tester_present: TesterPresent = None

    FIELDS = (
        Field('node'),
        Field('comment', load=ml_in, dump=ml_out),
        Field('protocols', load=list_in),
        Field('addressing', load=lambda l: [Addressing.from_dict(a) for a in l],
              dump=lambda l: [a.to_dict() for a in l]),
        Field('sessions', load=_ml_map_in, dump=_ml_map_out),
        Field('resets', load=_ml_map_in, dump=_ml_map_out),
        Field('services', load=list_in, dump=hex_out()),
        Field('security_access', load=lambda l: [SecurityAccess.from_dict(a) for a in l],
              dump=lambda l: [a.to_dict() for a in l]),
        Field('tester_present', load=TesterPresent.from_dict, dump=lambda t: t.to_dict()),
    )

    @property
    def uses_uds(self):
        return UDS in self.protocols or not any(p.startswith('KWP') for p in self.protocols)

    def address(self, protocol=None, bus=None):
        """First addressing entry matching a protocol and/or a bus"""
        for a in self.addressing or []:
            if (protocol is None or a.protocol in (None, protocol)) and (bus is None or a.bus in (None, bus)):
                return a
        return None

    def security(self, level=None):
        for s in self.security_access or []:
            if level is None or s.level == level:
                return s
        return None

    def session_request(self, session):
        return bytes([0x10, session])

    def reset_request(self, kind=0x01):
        return bytes([0x11, kind])


# --------------------------------------------------------------------------
# Identifiers, routines, IO controls
# --------------------------------------------------------------------------

def _params_out(signals):
    return dump_signals(signals)


class _ParamsMixin:
    """Converts params/results given as plain dicts when an object is built in code"""

    def __post_init__(self):
        for attr in ('params', 'results'):
            v = getattr(self, attr, None)
            if v and not all(hasattr(s, 'bits') for s in v.values()):
                setattr(self, attr, load_signals(v))


@dataclass
class DiagData(_ParamsMixin, Model, Document):
    """A UDS data identifier (``did``, dids/<DID>.yml) or a KWP2000 local identifier (``lid``, lids/<LID>.yml).
    ``params`` are signals, byte 1 being the first data byte after the identifier"""
    did: int = None
    lid: int = None
    name: str = ''
    alt_names: list = None
    display_name: MultiLang = None
    comment: MultiLang = None
    kind: str = None             # live | config | identification | counter | other
    access: str = None           # read | write | read-write
    session: int = None
    security_level: int = None
    length: int = None           # None with 'length' in _nulls: variable length
    variants: list = None
    params: dict = None

    FIELDS = (
        Field('did', dump=hex_out(4)),
        Field('lid', dump=hex_out(2)),
        Field('name'),
        Field('alt_names', load=list_in),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
        Field('kind'),
        Field('access'),
        Field('session', dump=hex_out()),
        Field('security_level', dump=hex_out()),
        Field('length'),
        Field('variants', load=list_in),
        Field('params', load=load_signals, dump=_params_out),
    )

    @property
    def identifier(self):
        return self.did if self.did is not None else self.lid

    @property
    def is_uds(self):
        return self.did is not None

    @property
    def readable(self):
        return self.access in (None, 'read', 'read-write')

    @property
    def writable(self):
        return self.access in ('write', 'read-write')

    @property
    def filename(self):
        return f'{self.did:04X}.yml' if self.is_uds else f'{self.lid:02X}.yml'

    def _id_bytes(self):
        return self.did.to_bytes(2, 'big') if self.is_uds else bytes([self.lid])

    def read_request(self):
        """22 DID_HI DID_LO (UDS) or 21 LID (KWP2000)"""
        return bytes([0x22 if self.is_uds else 0x21]) + self._id_bytes()

    def write_request(self, values=None, raw=False, data=None, base=None):
        """2E DID_HI DID_LO DATA (UDS) or 3B LID DATA (KWP2000); data built from {param: value} or given"""
        if data is None:
            data = self.encode(values, raw=raw, base=base)
        return bytes([0x2E if self.is_uds else 0x3B]) + self._id_bytes() + parse_hex(data)

    def encode(self, values=None, raw=False, base=None, strict=True):
        return encode_payload(self.params or {}, values, length=self.length, raw=raw, strict=strict, base=base)

    def decode(self, data, lang=None, include_unused=False):
        """{param: SignalValue} of the data (after the identifier)"""
        return decode_payload(self.params or {}, parse_hex(data), lang, include_unused)

    def decode_response(self, response, lang=None):
        """Decodes a positive response (62 DID_HI DID_LO DATA / 61 LID DATA)"""
        body = check_response(self.read_request()[0], response)
        ident = self._id_bytes()
        if body[:len(ident)] != ident:
            raise ValueError(f'response for identifier {body[:len(ident)].hex().upper()}, expected {ident.hex().upper()}')
        return self.decode(body[len(ident):], lang)


def dtc_to_raw(code):
    """'B1003-00' -> b'\\x90\\x03\\x00' (2 bytes without failure type)"""
    m = DTC_RE.match(code.strip().upper())
    if not m:
        raise ValueError(f'invalid DTC {code!r}, expected P/C/B/U + 4 hex digits [-XX]')
    value = ('PCBU'.index(m.group(1)) << 14) | int(m.group(2), 16)
    if value >> 14 != 'PCBU'.index(m.group(1)) or int(m.group(2)[0], 16) > 3:
        raise ValueError(f'invalid DTC {code!r}: the first digit must be 0-3')
    raw = value.to_bytes(2, 'big')
    return raw + bytes([int(m.group(3), 16)]) if m.group(3) else raw


def raw_to_dtc(raw):
    """b'\\x90\\x03\\x00' or '900300' -> 'B1003-00' (2 bytes: 'B1003')"""
    raw = parse_hex(raw)
    value = int.from_bytes(raw[:2], 'big')
    code = f'{"PCBU"[value >> 14]}{value & 0x3FFF:04X}'
    return f'{code}-{raw[2]:02X}' if len(raw) >= 3 else code


@dataclass
class Dtc(Model):
    code: str = ''
    raw: str = None
    display_name: MultiLang = None
    comment: MultiLang = None
    clues: MultiLang = None
    variants: list = None

    FIELDS = (
        Field('raw'),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
        Field('clues', load=ml_in, dump=ml_out),
        Field('variants', load=list_in),
    )

    @property
    def raw_bytes(self):
        return parse_hex(self.raw) if self.raw else dtc_to_raw(self.code)

    def __str__(self):
        return f'{self.code} {self.display_name or ""}'.strip()


class DtcTable(Document, dict):
    """``dtcs.yml``: {code: Dtc}"""
    SPACED_TOP = False
    QUOTE_KEYS = True

    def __init__(self, dtcs=None):
        dict.__init__(self, dtcs or {})
        self.path = None
        self.header = ''

    @classmethod
    def from_dict(cls, data, **kwargs):
        return cls({str(code): Dtc.from_dict(d, code=str(code)) for code, d in (data or {}).items()})

    def to_dict(self):
        return {code: d.to_dict() for code, d in self.items()}

    def lookup(self, code):
        """Dtc from a code ('B1003-00', 'B1003') or raw bytes/hex ('900300'); falls back to the code without failure type"""
        if isinstance(code, str) and DTC_RE.match(code.strip().upper()):
            code = code.strip().upper()
        else:
            raw = parse_hex(code)
            for d in self.values():
                if d.raw and parse_hex(d.raw) == raw:
                    return d
            code = raw_to_dtc(raw)
        if code in self:
            return self[code]
        base = code.split('-')[0]
        return self.get(base) or next((d for c, d in self.items() if c.split('-')[0] == base), None)

    def add(self, code, display_name, **kwargs):
        d = Dtc(code=code, display_name=MultiLang.of(display_name), **kwargs)
        self[code] = d
        return d


@dataclass
class Routine(_ParamsMixin, Model, Document):
    """``routines/<ID>.yml``: UDS RoutineControl (31 01/02/03 ID) or KWP2000 31/32/33 LID"""
    routine: int = 0
    name: str = ''
    alt_names: list = None
    display_name: MultiLang = None
    comment: MultiLang = None
    session: int = None
    security_level: int = None
    control: list = None        # start | stop | results
    params: dict = None         # option record sent with start
    results: dict = None        # returned by results
    return_values: ValueTable = None

    FIELDS = (
        Field('routine', dump=hex_out(4)),
        Field('name'),
        Field('alt_names', load=list_in),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
        Field('session', dump=hex_out()),
        Field('security_level', dump=hex_out()),
        Field('control', load=list_in),
        Field('params', load=load_signals, dump=_params_out),
        Field('results', load=load_signals, dump=_params_out),
        Field('return_values', load=ValueTable.from_dict, dump=lambda t: t.to_dict()),
    )

    def request(self, control='start', values=None, uds=True, raw=False):
        """Request bytes: UDS 31 <01|02|03> ID_HI ID_LO [params], KWP2000 <31|32|33> LID [params]"""
        index = ('start', 'stop', 'results').index(control)
        data = encode_payload(self.params, values, raw=raw) if (control == 'start' and self.params) else b''
        if uds:
            return bytes([0x31, index + 1]) + self.routine.to_bytes(2, 'big') + data
        return bytes([0x31 + index, self.routine & 0xFF]) + data

    def decode_results(self, data, lang=None):
        """{result: SignalValue} of the results record (after the routine identifier)"""
        return decode_payload(self.results or {}, parse_hex(data), lang)


@dataclass
class Ioctl(_ParamsMixin, Model, Document):
    """``ioctls/<ID>.yml``: UDS 2F ID_HI ID_LO <control> [state] or KWP2000 30 LID <control> [state]"""
    ioctl: int = 0
    name: str = ''
    display_name: MultiLang = None
    comment: MultiLang = None
    session: int = None
    params: dict = None

    FIELDS = (
        Field('ioctl', dump=hex_out(4)),
        Field('name'),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
        Field('session', dump=hex_out()),
        Field('params', load=load_signals, dump=_params_out),
    )

    # control parameters (UDS): 0 return control to ECU, 1 reset to default, 2 freeze, 3 short term adjustment
    RETURN_CONTROL, RESET_TO_DEFAULT, FREEZE, ADJUST = 0x00, 0x01, 0x02, 0x03

    def request(self, control=0x03, values=None, uds=True, raw=False):
        data = encode_payload(self.params, values, raw=raw) if (values is not None and self.params) else b''
        if uds:
            return bytes([0x2F]) + self.ioctl.to_bytes(2, 'big') + bytes([control]) + data
        return bytes([0x30, self.ioctl & 0xFF, control]) + data


# --------------------------------------------------------------------------
# One ECU's diagnostic directory
# --------------------------------------------------------------------------

def _load_dir(path, cls):
    out = {}
    if not os.path.isdir(path):
        return out
    for fn in sorted(os.listdir(path)):
        if fn.endswith('.yml'):
            obj = cls.load(os.path.join(path, fn))
            key = getattr(obj, 'identifier', None)
            if key is None:
                key = getattr(obj, 'routine', None) if cls is Routine else getattr(obj, 'ioctl', None)
            out[key if key is not None else fn[:-4]] = obj
    return out


class EcuDiag:
    """Everything known about the diagnostics of one node: ``diag/<arch>.<variant>/<NODE>/``.
    Sub-directories are loaded on first access."""

    def __init__(self, path, node=None, variant=None, db=None):
        self.path = path
        self.node = node or os.path.basename(path)
        self.variant = variant
        self._db = db
        self._cache = {}

    def __repr__(self):
        return f'<EcuDiag {self.variant}/{self.node}>'

    def _get(self, name, loader):
        if name not in self._cache:
            self._cache[name] = loader()
        return self._cache[name]

    @property
    def ecu(self):
        """DiagEcu (ecu.yml), None if missing"""
        p = os.path.join(self.path, 'ecu.yml')
        return self._get('ecu', lambda: DiagEcu.load(p) if os.path.isfile(p) else None)

    @ecu.setter
    def ecu(self, value):
        self._cache['ecu'] = value

    @property
    def dids(self):
        """{did: DiagData}"""
        return self._get('dids', lambda: _load_dir(os.path.join(self.path, 'dids'), DiagData))

    @property
    def lids(self):
        """{lid: DiagData}"""
        return self._get('lids', lambda: _load_dir(os.path.join(self.path, 'lids'), DiagData))

    @property
    def dtcs(self):
        p = os.path.join(self.path, 'dtcs.yml')
        return self._get('dtcs', lambda: DtcTable.load(p) if os.path.isfile(p) else DtcTable())

    @property
    def routines(self):
        return self._get('routines', lambda: _load_dir(os.path.join(self.path, 'routines'), Routine))

    @property
    def ioctls(self):
        return self._get('ioctls', lambda: _load_dir(os.path.join(self.path, 'ioctls'), Ioctl))

    @property
    def uses_uds(self):
        return self.ecu.uses_uds if self.ecu else bool(self.dids)

    def data(self, ident):
        """DID/LID by identifier or name"""
        if isinstance(ident, int):
            table = self.dids if self.uses_uds or ident > 0xFF else self.lids
            if ident in table:
                return table[ident]
            other = self.lids if table is self.dids else self.dids
            if ident in other:
                return other[ident]
            raise KeyError(f'{self.node}: no identifier 0x{ident:X}')
        for d in list(self.dids.values()) + list(self.lids.values()):
            if d.name == ident or ident in (d.alt_names or []):
                return d
        raise KeyError(f'{self.node}: no identifier {ident!r}')

    def routine(self, ident):
        return _by_id_or_name(self.routines, ident, self.node)

    def ioctl(self, ident):
        return _by_id_or_name(self.ioctls, ident, self.node)

    def save(self):
        """Writes every loaded file"""
        written = []
        ecu = self._cache.get('ecu')
        if ecu is not None:
            written.append(ecu.save(ecu.path or os.path.join(self.path, 'ecu.yml')))
        dtcs = self._cache.get('dtcs')
        if dtcs is not None and (dtcs.path or len(dtcs)):
            written.append(dtcs.save(dtcs.path or os.path.join(self.path, 'dtcs.yml')))
        for sub in ('dids', 'lids', 'routines', 'ioctls'):
            for obj in (self._cache.get(sub) or {}).values():
                written.append(obj.save(obj.path or os.path.join(self.path, sub, _filename(obj))))
        return written

    def add_data(self, ident, name, uds=None, **kwargs):
        """New DID (uds) or LID; registered here, written by save()"""
        uds = self.uses_uds if uds is None else uds
        d = DiagData(did=ident if uds else None, lid=None if uds else ident, name=name, **kwargs)
        (self.dids if uds else self.lids)[ident] = d
        return d


def _filename(obj):
    if isinstance(obj, DiagData):
        return obj.filename
    if isinstance(obj, Routine):
        return f'{obj.routine:04X}.yml' if obj.routine > 0xFF else f'{obj.routine:02X}.yml'
    return f'{obj.ioctl:04X}.yml' if obj.ioctl > 0xFF else f'{obj.ioctl:02X}.yml'


def _by_id_or_name(table, ident, node):
    if isinstance(ident, int):
        return table[ident]
    for obj in table.values():
        if obj.name == ident or ident in (getattr(obj, 'alt_names', None) or []):
            return obj
    raise KeyError(f'{node}: {ident!r} not found')


# --------------------------------------------------------------------------
# PSA seed/key (diag/protocols/UDS.yml, algorithms/PSA_SEED_KEY)
# --------------------------------------------------------------------------

_SEC1 = (0xB2, 0x3F, 0xAA)
_SEC2 = (0xB1, 0x02, 0xAB)


def _cdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _transform(data16, sec):
    data = data16 - 0x10000 if data16 & 0x8000 else data16
    rem = data - _cdiv(data, sec[0]) * sec[0]       # C '%': sign of the dividend
    result = rem * sec[2] - _cdiv(data, sec[0]) * sec[1]
    if result < 0:
        result += sec[0] * sec[2] + sec[1]
    return result & 0xFFFF


def psa_seed_key(seed, constant):
    """4 byte key answering a 4 byte seed, for the 16 bit ECU constant (the 'key' of security_access)"""
    seed = parse_hex(seed)
    if len(seed) != 4:
        raise ValueError('the seed is 4 bytes')
    if isinstance(constant, str):
        constant = int(constant, 16)
    msb = _transform(constant, _SEC1) | _transform((seed[0] << 8) | seed[3], _SEC2)
    lsb = _transform((seed[1] << 8) | seed[2], _SEC1) | _transform(msb, _SEC2)
    return bytes([msb >> 8, msb & 0xFF, lsb >> 8, lsb & 0xFF])
