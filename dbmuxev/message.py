"""
Frames (messages): ``buses/<arch>.<variant>/<network>.<bus>/<ID>[_<SUFFIX>].yml``
"""
import re
from dataclasses import dataclass, field

from . import isotp as _isotp
from .bits import BitRange, bit_position
from .model import Document, Field, Model, hex_out, list_in, ml_in, ml_out
from .multilang import MultiLang
from .signal import Signal, check_signals, decode_payload, dump_signals, encode_payload, load_signals

__all__ = ['Message', 'MessageAlternative', 'IsoTp', 'Van', 'Lin', 'DecodedFrame', 'FRAME_TYPES',
           'lin_protected_id', 'lin_checksum', 'frame_file_key']

FRAME_TYPES = ('can', 'can-tp', 'van', 'lin')
MAX_LENGTH = {'can': 8, 'can-tp': 4095, 'van': 28, 'lin': 8}
FRAME_FILE_RE = re.compile(r'^([0-9A-F]{2,8})(?:_([A-Z0-9_]+))?\.yml$')
PERIOD_RE = re.compile(r'^(\d+)ms$')


def id_digits(frame_type, extended=False):
    if frame_type == 'lin':
        return 2
    return 8 if extended else 3


def frame_file_key(frame_id, frame_type='can', extended=False, suffix=None):
    """File name (without .yml) of a frame: ID in uppercase hex, optionally _SUFFIX"""
    key = f'{frame_id:0{id_digits(frame_type, extended)}X}'
    return f'{key}_{suffix}' if suffix else key


# --------------------------------------------------------------------------
# Protocol blocks
# --------------------------------------------------------------------------

@dataclass
class IsoTp(Model):
    """ISO-TP parameters of a can-tp frame"""
    flow_control_id: int = None
    addressing: str = None   # normal | extended | mixed
    address: int = None
    padding: int = None      # None and 'padding' in _nulls: frames are not padded
    block_size: int = None
    st_min: int = None
    functional: bool = None

    FIELDS = (
        Field('flow_control_id', dump=hex_out(3)),
        Field('addressing'),
        Field('address', dump=hex_out()),
        Field('padding', dump=hex_out()),
        Field('block_size'),
        Field('st_min'),
        Field('functional'),
    )

    def segment(self, payload):
        """CAN frames carrying ``payload``"""
        address = self.address if self.addressing in ('extended', 'mixed') else None
        return _isotp.segment(payload, padding=self.padding, address=address)

    def reassembler(self):
        return _isotp.Reassembler(self.address if self.addressing in ('extended', 'mixed') else None)


@dataclass
class Van(Model):
    """VAN specifics: access (write | read | read-write), RAK (ack), RTR, reply mode"""
    access: str = 'write'
    ack: bool = None
    rtr: bool = None
    reply: str = None   # none | in-frame | deferred
    requested_by: list = None

    FIELDS = (
        Field('access'),
        Field('ack'),
        Field('rtr'),
        Field('reply'),
        Field('requested_by', load=list_in),
    )

    @property
    def command(self):
        """4 bit VAN command field: EXT (always 1), RAK, R/W, RTR"""
        rw = self.access in ('read', 'read-write')
        return 0x8 | (0x4 if self.ack else 0) | (0x2 if rw else 0) | (0x1 if self.rtr else 0)


@dataclass
class Lin(Model):
    """LIN specifics"""
    protected_id: int = None
    checksum: str = None     # classic | enhanced
    frame_type: str = None   # unconditional | event_triggered | sporadic | diagnostic
    master: str = None

    FIELDS = (
        Field('protected_id', dump=hex_out()),
        Field('checksum'),
        Field('frame_type'),
        Field('master'),
    )


def lin_protected_id(frame_id):
    """LIN protected identifier: the 6 bit ID with its 2 parity bits"""
    b = [(frame_id >> i) & 1 for i in range(6)]
    p0 = b[0] ^ b[1] ^ b[2] ^ b[4]
    p1 = 1 ^ (b[1] ^ b[3] ^ b[4] ^ b[5])
    return (frame_id & 0x3F) | (p0 << 6) | (p1 << 7)


def lin_checksum(data, protected_id=None, enhanced=True):
    """LIN checksum (classic: data only, enhanced: data and protected ID)"""
    total = protected_id if (enhanced and protected_id is not None) else 0
    for byte in bytes(data):
        total += byte
        if total > 0xFF:
            total -= 0xFF
    return (~total) & 0xFF


# --------------------------------------------------------------------------
# Message
# --------------------------------------------------------------------------

def _signals_out(signals):
    return dump_signals(signals)


@dataclass
class MessageAlternative(Model):
    """A conflicting observation of a whole frame: ``note`` explains it, the other fields override the frame's.
    ``signals``, when given, replaces the whole signal map"""
    note: MultiLang = None
    length: int = None
    length_min: int = None
    comment: MultiLang = None
    periodicity: list = None
    senders: list = None
    receivers: list = None
    signals: dict = None

    FIELDS = (
        Field('note', load=ml_in, dump=ml_out),
        Field('length'),
        Field('length_min'),
        Field('comment', load=ml_in, dump=ml_out),
        Field('periodicity', load=list_in),
        Field('senders', load=list_in),
        Field('receivers', load=list_in),
        Field('signals', load=load_signals, dump=_signals_out),
    )


@dataclass
class Message(Model, Document):
    """A frame on a bus (can, can-tp, van or lin).

    Context attributes set by the Database: ``variant`` ('AEE2004.full'), ``bus`` ('HS.IS'),
    ``suffix`` (file name suffix when several frames share the ID), ``path``, ``link`` (symlink target).
    """
    id: int = 0
    name: str = ''
    type: str = 'can'
    alt_names: list = None
    extended: bool = None
    length: int = None
    length_min: int = None
    comment: MultiLang = None
    observations: MultiLang = None
    periodicity: list = None
    senders: list = None
    receivers: list = None
    isotp: IsoTp = None
    van: Van = None
    lin: Lin = None
    signals: dict = field(default_factory=dict)
    alternatives: list = None

    FIELDS = (
        Field('id', dump=None),  # formatted in to_dict
        Field('name'),
        Field('alt_names', load=list_in),
        Field('type'),
        Field('extended'),
        Field('length'),
        Field('length_min'),
        Field('comment', load=ml_in, dump=ml_out),
        Field('observations', load=ml_in, dump=ml_out),
        Field('periodicity', load=list_in),
        Field('senders', load=list_in),
        Field('receivers', load=list_in),
        Field('isotp', load=IsoTp.from_dict, dump=lambda b: b.to_dict()),
        Field('van', load=Van.from_dict, dump=lambda b: b.to_dict()),
        Field('lin', load=Lin.from_dict, dump=lambda b: b.to_dict()),
        Field('signals', load=load_signals, dump=_signals_out),
        Field('alternatives', load=lambda l: [MessageAlternative.from_dict(a) for a in l],
              dump=lambda l: [a.to_dict() for a in l]),
    )

    # context
    variant = None
    bus = None
    suffix = None
    link = None
    _db = None

    def __post_init__(self):
        if self.comment is not None and not isinstance(self.comment, MultiLang):
            self.comment = MultiLang.of(self.comment)
        if self.signals and not all(isinstance(s, Signal) for s in self.signals.values()):
            self.signals = load_signals(self.signals)

    def to_dict(self):
        out = super().to_dict()
        if 'signals' not in out:
            out['signals'] = {}
        out['id'] = hex_out(id_digits(self.type, self.extended))(self.id)
        return out

    def __repr__(self):
        where = f' {self.variant}/{self.bus}' if self.variant else ''
        return f'<Message {self.id_hex} {self.name} ({self.type}, {len(self.signals)} signals){where}>'

    # ---- identity / file ----
    @property
    def key(self):
        """File name without extension: '0F6', or '8EC_CD_CHANGER_COMMAND_TRACK'"""
        return frame_file_key(self.id, self.type, self.extended, self.suffix)

    @property
    def filename(self):
        return self.key + '.yml'

    @property
    def id_hex(self):
        return f'0x{self.id:0{id_digits(self.type, self.extended)}X}'

    @property
    def is_link(self):
        return self.link is not None

    @property
    def max_length(self):
        return MAX_LENGTH.get(self.type, 8)

    # ---- timing ----
    @property
    def periods_ms(self):
        return [int(m.group(1)) for p in (self.periodicity or []) for m in [PERIOD_RE.match(str(p))] if m]

    @property
    def period_ms(self):
        """Smallest period in ms, None if the frame is not periodic"""
        periods = self.periods_ms
        return min(periods) if periods else None

    @property
    def is_triggered(self):
        return 'trigger' in (self.periodicity or [])

    @property
    def is_on_request(self):
        return 'request' in (self.periodicity or [])

    # ---- signals ----
    def signal(self, name):
        """Signal by name or alternative name"""
        if name in self.signals:
            return self.signals[name]
        for s in self.signals.values():
            if name in (s.alt_names or []):
                return s
        raise KeyError(f'{self.name}: no signal {name!r}')

    def __getitem__(self, name):
        return self.signal(name)

    def __contains__(self, name):
        return name in self.signals

    def __iter__(self):
        return iter(self.signals.values())

    def add_signal(self, name, bits, replace=False, **kwargs):
        """Adds a signal: ``msg.add_signal('SPEED', '1.7-2.0', factor=0.01, units='km/h')``"""
        if name in self.signals and not replace:
            raise ValueError(f'{self.name}: signal {name} already exists')
        sig = Signal(name=name, bits=BitRange.parse(bits), **kwargs)
        self.signals[name] = sig
        return sig

    def remove_signal(self, name):
        return self.signals.pop(name)

    def rename_signal(self, old, new):
        """Renames a signal, keeping its position in the file and updating the mux references"""
        if new in self.signals:
            raise ValueError(f'{self.name}: signal {new} already exists')
        self.signals = {(new if k == old else k): v for k, v in self.signals.items()}
        self.signals[new].name = new
        for s in self.signals.values():
            if s.mux and s.mux.selector == old:
                s.mux.selector = new

    def sort_signals(self):
        """Orders the signals by position"""
        self.signals = dict(sorted(self.signals.items(), key=lambda kv: (kv[1].bits.start, kv[0])))

    @property
    def selectors(self):
        """Multiplexer selector signals"""
        return [s for s in self.signals.values() if s.mux_selector]

    def mux_values(self, selector=None):
        """Raw selector values used by the multiplexed signals"""
        out = []
        for s in self.signals.values():
            if s.mux and (selector is None or s.mux.selector == selector):
                out.extend(v for v in s.mux.values if v not in out)
        return sorted(out)

    def free_bits(self, length=None):
        """Bit ranges not used by any signal (multiplexed signals count as used)"""
        length = length or self.length or 8
        used = set()
        for s in self.signals.values():
            used.update(s.bits.indexes(length))
        out, start = [], None
        for i in range(length * 8 + 1):
            if i < length * 8 and i not in used:
                start = i if start is None else start
            elif start is not None:
                out.append(BitRange(start, i - 1))
                start = None
        return out

    def bit_map(self, length=None, selector_raws=None):
        """Grid of signal names: one row per byte, bits 7..0"""
        length = length or self.length or 8
        rows = [[None] * 8 for _ in range(length)]
        for name, s in self.signals.items():
            if s.mux and selector_raws is not None and selector_raws.get(s.mux.selector) not in s.mux.values:
                continue
            for i in s.bits.indexes(length):
                if i < length * 8:
                    byte, bit = bit_position(i)
                    cell = rows[byte - 1][7 - bit]
                    rows[byte - 1][7 - bit] = name if cell is None else f'{cell}|{name}'
        return rows

    # ---- alternatives ----
    def with_alternative(self, index):
        """Copy of the frame with the overrides of ``alternatives[index]`` applied"""
        alt = self.alternatives[index]
        d = self.to_dict()
        d.pop('alternatives', None)
        over = alt.to_dict()
        over.pop('note', None)
        d.update(over)
        m = Message.from_dict(d)
        m.variant, m.bus, m.suffix = self.variant, self.bus, self.suffix
        return m

    # ---- decoding / encoding ----
    def decode(self, data, lang=None, include_unused=False, all_mux=False):
        """Decodes a payload (for can-tp: the reassembled payload). Returns a DecodedFrame"""
        return DecodedFrame(self, bytes(data), decode_payload(self.signals, data, lang, include_unused, all_mux))

    def encode(self, values=None, raw=False, defaults=True, strict=True, length=None, base=None):
        """Builds a payload from {signal: physical value} (or raw values with ``raw=True``).

        Signals that are not given take their ``default`` raw value (or 0). The length is the frame
        length, except for can-tp frames where it is computed from the signals.
        """
        if length is None and base is None and self.type != 'can-tp':
            length = self.length if self.length is not None else None
        return encode_payload(self.signals, values, length=length, raw=raw, defaults=defaults, strict=strict,
                              base=base)

    def encode_frames(self, values=None, **kwargs):
        """can-tp frames: the ISO-TP CAN frames carrying the encoded payload"""
        payload = self.encode(values, **kwargs)
        if self.type != 'can-tp':
            return [payload]
        return (self.isotp or IsoTp()).segment(payload)

    # ---- checks ----
    def check(self):
        """Problems found in the frame definition (messages), see tools/validate.py for the full check"""
        problems = []
        if self.type not in FRAME_TYPES:
            problems.append(f"unknown frame type '{self.type}'")
        if self.length is not None and self.length > self.max_length:
            problems.append(f'length {self.length} > {self.max_length} for a {self.type} frame')
        if self.type == 'can' and self.id > 0x7FF and not self.extended:
            problems.append(f'id {self.id_hex} needs 29 bits, set extended: true')
        if self.type == 'lin' and self.id > 0x3F:
            problems.append('LIN ids are 6 bits')
        if self.type == 'van' and self.id > 0xFFF:
            problems.append('VAN ids are 12 bits')
        if self.type == 'can-tp' and self.isotp is None:
            problems.append('can-tp frames need an isotp block')
        if not self.senders:
            problems.append('no senders')
        length = self.length if self.type != 'can-tp' else None
        problems += [msg for _, msg in check_signals(self.signals, length, variable=self.type == 'can-tp')]
        for i, alt in enumerate(self.alternatives or []):
            if alt.signals:
                problems += [f'alternatives/{i}: {msg}' for _, msg in
                             check_signals(alt.signals, alt.length or length, variable=self.type == 'can-tp')]
        return problems

    # ---- persistence ----
    def save(self, path=None, break_link=False):
        """Writes the frame. Through a symlink the shared target is written, unless ``break_link``
        (the link is then replaced by a regular file)"""
        if self._db is not None and path is None:
            return self._db.save_frame(self, break_link=break_link)
        return Document.save(self, path)


@dataclass
class DecodedFrame:
    """Result of Message.decode: the signals present in the payload"""
    message: Message
    data: bytes
    signals: dict

    def __getitem__(self, name):
        return self.signals[name]

    def __contains__(self, name):
        return name in self.signals

    def __iter__(self):
        return iter(self.signals.values())

    def __repr__(self):
        return f'<DecodedFrame {self.message.id_hex} {self.message.name} {self.labels()}>'

    def __len__(self):
        return len(self.signals)

    def get(self, name, default=None):
        v = self.signals.get(name)
        return v.value if v is not None else default

    def values(self):
        """{signal: physical value}"""
        return {n: v.value for n, v in self.signals.items()}

    def raw_values(self):
        return {n: v.raw for n, v in self.signals.items()}

    def labels(self):
        """{signal: label or physical value}"""
        return {n: (v.label if v.label is not None else v.value) for n, v in self.signals.items()}

    def to_dict(self):
        return {n: {'raw': v.raw.hex() if isinstance(v.raw, bytes) else v.raw,
                    'value': v.value.hex() if isinstance(v.value, bytes) else v.value,
                    'label': v.label, 'units': v.units, 'valid': v.valid}
                for n, v in self.signals.items()}

    def __str__(self):
        m = self.message
        lines = [f'{m.id_hex} {m.name} [{self.data.hex(" ").upper()}]']
        width = max((len(n) for n in self.signals), default=0)
        for n, v in self.signals.items():
            lines.append(f'  {n:<{width}}  {v}')
        return '\n'.join(lines)
