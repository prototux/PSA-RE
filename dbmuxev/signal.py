"""
Signals: a value carried in a frame (or in a diagnostic payload), and the
functions decoding/encoding a whole payload from a signal map.
"""
import math
import struct
from dataclasses import dataclass, field

from . import bits as _bits
from .bits import BitRange
from ._yaml import hexint as _bits_hex
from .model import Field, Model, hex_out, ml_in, ml_out, list_in
from .multilang import MultiLang

__all__ = ['Signal', 'SignalAlternative', 'ValueEntry', 'ValueTable', 'Mux', 'SignalValue',
           'SIGNAL_TYPES', 'decode_payload', 'encode_payload', 'active_signals', 'check_signals',
           'load_signals', 'dump_signals']

SIGNAL_TYPES = ('uint', 'sint', 'bool', 'enum', 'bcd', 'str', 'bytes', 'float')
LEGACY_TYPES = {'uint8': 'uint', 'uint16': 'uint', 'uint24': 'uint', 'int8': 'sint', 'int16': 'sint', 'int24': 'sint'}
STRING_ENCODING = 'latin-1'  # texts are ASCII / ISO-8859-1


# --------------------------------------------------------------------------
# Value tables
# --------------------------------------------------------------------------

@dataclass
class ValueEntry(Model):
    """Meaning of one raw value: a translated text and/or ``unused`` (reserved, never observed)"""
    text: MultiLang = None
    unused: bool = None

    @classmethod
    def from_dict(cls, data, **kwargs):
        if isinstance(data, str):
            data = {'en': data}
        data = dict(data or {})
        unused = data.pop('unused', None)
        text = MultiLang({k: v for k, v in data.items() if isinstance(k, str)}) or None
        return cls(text=text, unused=unused)

    def to_dict(self):
        out = dict(self.text or {})
        if self.unused is not None:
            out['unused'] = self.unused
        return out

    def label(self, lang=None):
        return self.text.get_text(lang) if self.text else None

    def __str__(self):
        return self.label() or ('(unused)' if self.unused else '')


class ValueTable(dict):
    """Raw value (int) -> ValueEntry"""

    @classmethod
    def from_dict(cls, data):
        table = cls()
        for k, v in (data or {}).items():
            table[_int_key(k)] = v if isinstance(v, ValueEntry) else ValueEntry.from_dict(v)
        return table

    def to_dict(self, digits=2):
        return {_bits_hex(k, digits): v.to_dict() for k, v in self.items()}

    def label(self, raw, lang=None):
        """Text of a raw value, None if unknown or unused"""
        e = self.get(raw)
        return e.label(lang) if e else None

    def raw_of(self, label):
        """Raw value whose text (any language, case insensitive) is ``label``"""
        for raw, e in self.items():
            if e.text and e.text.matches(label):
                return raw
        raise KeyError(f'no value named {label!r}')

    def add(self, raw, text=None, unused=None, **langs):
        """Adds/replaces a value: ``add(0x01, 'On', fr='Marche')``"""
        ml = MultiLang.of(text) if text is not None else MultiLang()
        ml = MultiLang(ml, **langs) if langs else ml
        self[raw] = ValueEntry(text=ml or None, unused=unused)
        return self[raw]

    def used(self):
        return {k: v for k, v in self.items() if not v.unused}


def _int_key(k):
    if isinstance(k, int) and not isinstance(k, bool):
        return k
    s = str(k).strip()
    return int(s, 16) if s.lower().startswith('0x') else int(s)


# --------------------------------------------------------------------------
# Signal
# --------------------------------------------------------------------------

@dataclass
class Mux:
    """The signal is only present when the raw value of ``selector`` is one of ``values``"""
    selector: str
    values: list

    @classmethod
    def from_dict(cls, d):
        if isinstance(d, Mux):
            return d
        return cls(selector=d['selector'], values=list_in(d['values']))

    def to_dict(self):
        return {'selector': self.selector, 'values': hex_out()(self.values)}


@dataclass
class SignalAlternative(Model):
    """A conflicting observation of a signal: ``note`` explains it, the other fields override the signal's"""
    note: MultiLang = None
    overrides: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data, **kwargs):
        data = dict(data or {})
        note = MultiLang.of(data.pop('note', None))
        return cls(note=note, overrides=data)

    def to_dict(self):
        out = {'note': dict(self.note)} if self.note else {}
        for k, v in self.overrides.items():
            if isinstance(v, (BitRange, MultiLang, ValueTable)):
                v = str(v) if isinstance(v, BitRange) else v.to_dict()
            out[k] = v
        return out


def _values_out(table):
    return table.to_dict()


def _bits_out(v):
    return str(v)


@dataclass
class Signal(Model):
    """A value carried in a frame. ``name`` is the key of the signal in its frame.

    Decoding: ``physical = raw * factor + offset``; ``values`` gives the meaning of raw values.
    """
    name: str = ''
    bits: BitRange = None
    unused: bool = None
    alt_names: list = None
    comment: MultiLang = None
    type: str = None
    factor: float = None
    offset: float = None
    min: float = None
    max: float = None
    units: str = None
    invalid: object = None   # int, list of ints, or None
    default: int = None
    values: ValueTable = None
    mux_selector: bool = None
    mux: Mux = None
    alternatives: list = None
    receivers: list = None
    byte_order: str = None
    # deprecated, read for compatibility
    signed: bool = None
    resolution: float = None

    FIELDS = (
        Field('bits', load=BitRange.parse, dump=_bits_out),
        Field('unused'),
        Field('alt_names', load=list_in),
        Field('comment', load=ml_in, dump=ml_out),
        Field('type'),
        Field('signed'),
        Field('factor'),
        Field('resolution'),
        Field('offset'),
        Field('min'),
        Field('max'),
        Field('units'),
        Field('invalid', dump=hex_out()),
        Field('default', dump=hex_out()),
        Field('byte_order'),
        Field('receivers', load=list_in),
        Field('mux_selector'),
        Field('mux', load=Mux.from_dict, dump=lambda m: m.to_dict()),
        Field('values', load=ValueTable.from_dict, dump=_values_out),
        Field('alternatives', load=lambda l: [SignalAlternative.from_dict(a) for a in l],
              dump=lambda l: [a.to_dict() for a in l]),
    )

    def __post_init__(self):
        if self.bits is not None and not isinstance(self.bits, BitRange):
            self.bits = BitRange.parse(self.bits)
        if self.comment is not None and not isinstance(self.comment, MultiLang):
            self.comment = MultiLang.of(self.comment)
        if isinstance(self.values, dict) and not isinstance(self.values, ValueTable):
            self.values = ValueTable.from_dict(self.values)
        if isinstance(self.mux, dict):
            self.mux = Mux.from_dict(self.mux)

    def to_dict(self):
        out = super().to_dict()
        if self.bits is not None and not self.bits.to_end:
            digits = max(2, (self.width() + 3) // 4)
            if self.default is not None:
                out['default'] = _bits_hex(self.default, digits)
            if self.invalid is not None:
                out['invalid'] = ([_bits_hex(v, digits) for v in self.invalid] if isinstance(self.invalid, (list, tuple))
                                  else _bits_hex(self.invalid, digits))
        return out

    def __repr__(self):
        extra = ''.join(f', {k}={getattr(self, k)!r}' for k in ('factor', 'offset', 'units') if getattr(self, k) is not None)
        mux = f', mux={self.mux.selector}{[hex(v) for v in self.mux.values]}' if self.mux else ''
        return f"<Signal {self.name} '{self.bits}' {self.kind}{extra}{mux}{' unused' if self.unused else ''}>"

    # ---- properties ----
    @property
    def kind(self):
        """Effective type: uint, sint, bool, enum, bcd, str, bytes or float"""
        t = LEGACY_TYPES.get(self.type, self.type)
        if t in (None, 'uint') and self.signed:
            return 'sint'
        return t or 'uint'

    @property
    def scale(self):
        """Effective factor (the deprecated 'resolution' is used when 'factor' is missing)"""
        f = self.factor if self.factor is not None else self.resolution
        return 1 if f is None else f

    @property
    def shift(self):
        return 0 if self.offset is None else self.offset

    @property
    def is_little_endian(self):
        return self.byte_order == 'little_endian'

    @property
    def is_multiplexed(self):
        return self.mux is not None

    @property
    def is_signed(self):
        return self.kind == 'sint'

    @property
    def invalid_values(self):
        if self.invalid is None:
            return []
        return list(self.invalid) if isinstance(self.invalid, (list, tuple)) else [self.invalid]

    def width(self, length=None):
        return self.bits.width(length)

    def label(self, raw, lang=None):
        return self.values.label(raw, lang) if self.values else None

    def text(self, lang=None):
        return self.comment.get_text(lang) if self.comment else ''

    # ---- alternatives ----
    def with_alternative(self, index):
        """Copy of the signal with the overrides of ``alternatives[index]`` applied"""
        alt = self.alternatives[index]
        d = self.to_dict()
        d.pop('alternatives', None)
        d.update(alt.to_dict())
        d.pop('note', None)
        return Signal.from_dict(d, name=self.name)

    # ---- raw <-> physical ----
    def raw_from_payload(self, data):
        """Raw value read from a payload: int for numeric types, bytes for str/bytes. None if the payload is too short"""
        length = len(data)
        if not self.bits.fits(length):
            return None
        width = self.bits.width(length)
        if self.bits.last(length) >= length * 8:
            return None
        raw = _bits.extract(data, self.bits.start, width)
        if self.is_little_endian:
            raw = _bits.be_to_le(raw, self.bits.start, width)
        if self.kind in ('str', 'bytes'):
            return raw.to_bytes((width + 7) // 8, 'big')
        return raw

    def write_raw(self, buf, raw):
        """Writes a raw value (int, or bytes for str/bytes) in the bytearray ``buf``"""
        length = len(buf)
        width = self.bits.width(length)
        if isinstance(raw, (bytes, bytearray)):
            # texts/bytes fill the field from its first byte (padded with 0x00, truncated when too long);
            # a field that is not a whole number of bytes holds the value right aligned, as it is read
            nbytes = (width + 7) // 8
            raw = int.from_bytes(bytes(raw)[:nbytes].ljust(nbytes, b'\x00'), 'big') & ((1 << width) - 1)
        if self.is_little_endian:
            raw = _bits.le_to_be(raw, self.bits.start, width)
        _bits.insert(buf, self.bits.start, width, raw)

    def physical(self, raw, width=None):
        """Physical value of a raw value"""
        kind = self.kind
        if raw is None:
            return None
        if kind == 'str':
            return bytes(raw).decode(STRING_ENCODING).rstrip('\x00')
        if kind == 'bytes':
            return bytes(raw)
        width = width or self.width()
        if kind == 'bool':
            return bool(raw)
        if kind == 'float':
            fmt = {16: '>e', 32: '>f', 64: '>d'}.get(width)
            if not fmt:
                raise ValueError(f'{self.name}: float signals must be 16, 32 or 64 bits wide, got {width}')
            value = struct.unpack(fmt, raw.to_bytes(width // 8, 'big'))[0]
        elif kind == 'sint':
            value = raw - (1 << width) if raw >> (width - 1) else raw
        elif kind == 'bcd':
            digits = f'{raw:0{(width + 3) // 4}X}'
            if any(c not in '0123456789' for c in digits):
                return None
            value = int(digits)
        else:
            value = raw
        return _scale(value, self.scale, self.shift)

    def raw(self, value, width=None, strict=True):
        """Raw value of a physical value (number, bool, value label for enums, str/bytes for texts)"""
        kind = self.kind
        if kind == 'str':
            return value.encode(STRING_ENCODING) if isinstance(value, str) else bytes(value)
        if kind == 'bytes':
            return bytes.fromhex(value) if isinstance(value, str) else bytes(value)
        if width is None and not self.bits.to_end:
            width = self.width()
        if isinstance(value, str):
            if self.values:
                try:
                    return self.values.raw_of(value)
                except KeyError:
                    pass
            try:
                value = float(value) if any(c in value for c in '.eE') and not value.lower().startswith('0x') \
                    else int(value, 0)
            except ValueError:
                raise ValueError(f'{self.name}: unknown value {value!r}'
                                 + (f", expected one of {[str(v) for v in self.values.values() if v.text]}"
                                    if self.values else '')) from None
        if isinstance(value, bool):
            value = int(value)
            if kind == 'bool':
                return value
        if kind == 'float':
            fmt = {16: '>e', 32: '>f', 64: '>d'}.get(width)
            if not fmt:
                raise ValueError(f'{self.name}: float signals must be 16, 32 or 64 bits wide, got {width}')
            value = (value - self.shift) / self.scale
            return int.from_bytes(struct.pack(fmt, value), 'big')
        number, scale = value - self.shift, self.scale
        if isinstance(number, int) and isinstance(scale, int) and number % scale == 0:
            raw = number // scale  # exact, even for values wider than a float mantissa
        else:
            raw = int(round(number / scale))  # nearest raw value when not a multiple of the factor
        if width is None:  # '-n' range, the payload length is not known yet
            if raw < 0 or kind == 'sint':
                raise ValueError(f'{self.name}: give the payload length to encode a signed value in {self.bits}')
            return int(str(raw), 16) if kind == 'bcd' else raw
        if kind == 'bcd':
            if raw < 0:
                raise ValueError(f'{self.name}: negative BCD value')
            ndigits = (width + 3) // 4
            if len(str(raw)) > ndigits and strict:
                raise ValueError(f'{self.name}: {value} needs more than {ndigits} BCD digits')
            raw = int(str(raw)[-ndigits:], 16)
        elif kind == 'sint':
            lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
            if not lo <= raw <= hi:
                if strict:
                    raise ValueError(f'{self.name}: {value} out of range (raw {raw} not in {lo}..{hi})')
                raw = max(lo, min(hi, raw))
            raw &= (1 << width) - 1
        else:
            if not 0 <= raw < (1 << width):
                if strict:
                    raise ValueError(f'{self.name}: {value} out of range (raw {raw} not in 0..{(1 << width) - 1})')
                raw = max(0, min((1 << width) - 1, raw))
        return raw

    def decode(self, data, lang=None):
        """SignalValue of this signal in ``data`` (None if the payload is too short)"""
        raw = self.raw_from_payload(data)
        if raw is None:
            return None
        width = self.bits.width(len(data))
        return SignalValue(self, raw, self.physical(raw, width),
                           self.label(raw, lang) if isinstance(raw, int) else None,
                           not (isinstance(raw, int) and raw in self.invalid_values))

    def physical_range(self, length=None):
        """(min, max) physical values: the documented ones, else computed from the width"""
        if self.min is not None and self.max is not None:
            return self.min, self.max
        if self.kind in ('str', 'bytes', 'float') or (self.bits.to_end and length is None):
            return self.min, self.max
        w = self.width(length)
        lo, hi = (-(1 << (w - 1)), (1 << (w - 1)) - 1) if self.is_signed else (0, (1 << w) - 1)
        if self.kind == 'bcd':
            lo, hi = 0, 10 ** ((w + 3) // 4) - 1
        a, b = _scale(lo, self.scale, self.shift), _scale(hi, self.scale, self.shift)
        a, b = min(a, b), max(a, b)
        return (self.min if self.min is not None else a), (self.max if self.max is not None else b)


def _scale(value, factor, offset):
    if factor == 1 and offset == 0:
        return value
    result = value * factor + offset
    if isinstance(result, float) and math.isfinite(result):
        result = float(f'{result:.15g}')  # 3 * 0.1 is 0.3, not 0.30000000000000004
    return result


@dataclass
class SignalValue:
    """A decoded signal: raw value, physical value, label of the raw value (from 'values') and validity"""
    signal: Signal
    raw: object
    value: object
    label: str = None
    valid: bool = True

    @property
    def name(self):
        return self.signal.name

    @property
    def units(self):
        return self.signal.units

    def __repr__(self):
        raw = self.raw.hex().upper() if isinstance(self.raw, bytes) else f'0x{self.raw:X}'
        return f'<SignalValue {self.name}={self.value!r} raw={raw}{" " + repr(self.label) if self.label else ""}' \
               f'{"" if self.valid else " invalid"}>'

    @property
    def in_range(self):
        lo, hi = self.signal.min, self.signal.max
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            return True
        return (lo is None or self.value >= lo) and (hi is None or self.value <= hi)

    def __str__(self):
        if not self.valid:
            return f'invalid (0x{self.raw:X})' + (f' {self.label}' if self.label else '')
        if self.label:
            return self.label
        if isinstance(self.value, bytes):
            return self.value.hex(' ').upper()
        if self.value is None and isinstance(self.raw, int):
            return f'0x{self.raw:X}'
        return f'{self.value} {self.units}' if self.units else str(self.value)


# --------------------------------------------------------------------------
# Signal maps (frame signals, diag params)
# --------------------------------------------------------------------------

def load_signals(d):
    return {name: (s if isinstance(s, Signal) else Signal.from_dict(s, name=name)) for name, s in (d or {}).items()}


def dump_signals(signals):
    return {name: s.to_dict() for name, s in signals.items()}


def _selector_names(signals):
    names = {n for n, s in signals.items() if s.mux_selector}
    names.update(s.mux.selector for s in signals.values() if s.mux and s.mux.selector in signals)
    return names


def active_signals(signals, selector_raws):
    """Names of the signals present for the given raw values of the mux selectors ({selector: raw})"""
    memo = {}

    def active(name, stack=()):
        if name in memo:
            return memo[name]
        sig = signals[name]
        if not sig.mux:
            res = True
        else:
            sel = sig.mux.selector
            if sel not in signals or sel in stack:
                res = False
            else:
                res = active(sel, stack + (name,)) and selector_raws.get(sel) in sig.mux.values
        memo[name] = res
        return res

    return [n for n in signals if active(n)]


def decode_payload(signals, data, lang=None, include_unused=False, all_mux=False):
    """Decodes ``data`` with a signal map: {name: SignalValue}.

    Multiplexed signals are only decoded when their selector has one of their values
    (all of them with ``all_mux``). Signals outside of a short payload are skipped.
    """
    data = bytes(data)
    selectors = {}
    for name in _selector_names(signals):
        raw = signals[name].raw_from_payload(data)
        if raw is not None:
            selectors[name] = raw
    names = list(signals) if all_mux else active_signals(signals, selectors)
    out = {}
    for name in names:
        sig = signals[name]
        if sig.unused and not include_unused:
            continue
        v = sig.decode(data, lang)
        if v is not None:
            out[name] = v
    return out


def encode_payload(signals, values=None, length=None, raw=False, defaults=True, strict=True, base=None):
    """Builds a payload from {signal: value}.

    values: physical values (numbers, bools, value labels, texts), or raw values with ``raw=True``
    length: payload length in bytes; computed from the signals when None
    defaults: use the ``default`` raw value of the signals that are not given
    base: initial payload (bytes) to modify instead of zeros
    """
    values = dict(values or {})
    unknown = [n for n in values if n not in signals]
    if unknown:
        raise KeyError(f'unknown signal(s): {", ".join(unknown)}')

    # selectors: given, else implied by a given multiplexed signal, else their default
    selectors = _selector_names(signals)
    selector_raws = {}
    for name in selectors:
        if name in values:
            selector_raws[name] = values[name] if raw else signals[name].raw(values[name], strict=strict)
    for name in values:
        sig = signals[name]
        if sig.mux and sig.mux.selector not in selector_raws:
            selector_raws[sig.mux.selector] = sig.mux.values[0]
    for name in selectors:
        if name not in selector_raws and base is not None:
            r = signals[name].raw_from_payload(bytes(base))
            if r is not None:
                selector_raws[name] = r
        if name not in selector_raws and signals[name].default is not None:
            selector_raws[name] = signals[name].default
    active = active_signals(signals, selector_raws)
    inactive = [n for n in values if n not in active]
    if inactive and strict:
        raise ValueError(f'signal(s) {", ".join(inactive)} not present with the selected multiplexer values')

    # raw values
    raws = {}
    for name in active:
        sig = signals[name]
        if name in values:
            v = values[name]
            if raw:
                raws[name] = bytes(v) if isinstance(v, (bytes, bytearray)) else v
            else:
                width = sig.bits.width(length) if (sig.bits.to_end and length) else None
                raws[name] = sig.raw(v, width=width, strict=strict)
        elif name in selector_raws:
            raws[name] = selector_raws[name]
        elif defaults and sig.default is not None:
            raws[name] = sig.default

    # length
    if length is None:
        if base is not None:
            length = len(base)
        else:
            length = 0
            for name in active:
                sig = signals[name]
                if sig.bits.to_end:
                    r = raws.get(name)
                    if isinstance(r, (bytes, bytearray)):
                        need = sig.bits.start // 8 + len(r)
                    elif isinstance(r, int):
                        need = sig.bits.start // 8 + max(1, (r.bit_length() + 7) // 8)
                    else:
                        need = sig.bits.start // 8 + 1
                    length = max(length, need)
                else:
                    length = max(length, sig.bits.byte_length())
    buf = bytearray(base) if base is not None else bytearray(length)
    if len(buf) < length:
        buf.extend(bytes(length - len(buf)))

    for name, r in raws.items():
        sig = signals[name]
        if not sig.bits.fits(len(buf)) or sig.bits.last(len(buf)) >= len(buf) * 8:
            if strict and name in values:
                raise ValueError(f'{name}: bits {sig.bits} outside of a {len(buf)} byte payload')
            continue
        if isinstance(r, int) and sig.bits.to_end:
            width = sig.bits.width(len(buf))
            if r >> width:
                raise ValueError(f'{name}: value does not fit in the payload')
        sig.write_raw(buf, r)
    return bytes(buf)


def check_signals(signals, length=None, variable=False):
    """Layout problems of a signal map: [(signal names, message)]"""
    problems = []
    occupancy = {}
    for name, sig in signals.items():
        if sig.bits is None:
            problems.append(((name,), 'no bits'))
            continue
        last = sig.bits.last(length) if (length or not sig.bits.to_end) else sig.bits.start
        if length is not None and not variable and last >= length * 8:
            problems.append(((name,), f"bits '{sig.bits}' outside of the {length} byte(s) frame"))
        width = last - sig.bits.start + 1
        if sig.kind == 'bool' and width != 1:
            problems.append(((name,), f'bool signal is {width} bits wide'))
        if sig.kind == 'float' and width not in (16, 32, 64) and not sig.bits.to_end:
            problems.append(((name,), f'float signal is {width} bits wide'))
        if sig.mux and (sig.mux.selector not in signals or not signals[sig.mux.selector].mux_selector):
            problems.append(((name,), f"mux selector '{sig.mux.selector}' is not a signal with mux_selector: true"))
        if width < 64:
            for raw in list((sig.values or {}).keys()) + sig.invalid_values + (
                    [sig.default] if sig.default is not None else []):
                if raw >= (1 << width):
                    problems.append(((name,), f'value 0x{raw:X} does not fit in {width} bit(s)'))
        if sig.min is not None and sig.max is not None and sig.min > sig.max:
            problems.append(((name,), 'min > max'))
        muxkey = (sig.mux.selector, frozenset(sig.mux.values)) if sig.mux else None
        for b in range(sig.bits.start, last + 1):
            occupancy.setdefault(b, []).append((name, muxkey))
    reported = set()
    for b, users in sorted(occupancy.items()):
        for i in range(len(users)):
            for j in range(i + 1, len(users)):
                (n1, m1), (n2, m2) = users[i], users[j]
                if m1 and m2 and m1[0] == m2[0] and not m1[1] & m2[1]:
                    continue
                pair = (n1, n2)
                if pair not in reported:
                    reported.add(pair)
                    byte, bit = _bits.bit_position(b)
                    problems.append((pair, f"signals '{n1}' and '{n2}' overlap (byte {byte} bit {bit})"))
    return problems
