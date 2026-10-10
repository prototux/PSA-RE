"""
The DBMUXEv bit notation.

``<byte>.<bit>``: bytes are numbered from 1 (first byte sent), bits from 7
(most significant, sent first) to 0. A range ``<start>-<end>`` is given in
transmission order, so ``1.7-2.0`` is a 16 bit big endian value made of
bytes 1 (MSB) and 2 (LSB). ``3.7-n`` goes until the end of the payload.

Internally a bit position is an absolute index in transmission order:
``(byte - 1) * 8 + (7 - bit)``, so byte 1 bit 7 is 0 and byte 2 bit 0 is 15.
"""
import re
from dataclasses import dataclass

__all__ = ['BitRange', 'extract', 'insert', 'le_to_be', 'be_to_le', 'bit_index', 'bit_position']

BITS_RE = re.compile(r'^\s*([1-9][0-9]*)\.([0-7])(?:\s*-\s*(?:([1-9][0-9]*)\.([0-7])|(n)))?\s*$')


def bit_index(byte, bit):
    """Absolute index (transmission order) of <byte>.<bit>"""
    return (byte - 1) * 8 + (7 - bit)


def bit_position(index):
    """(byte, bit) of an absolute index"""
    return index // 8 + 1, 7 - index % 8


@dataclass(frozen=True)
class BitRange:
    """A position in a payload: ``start`` and ``end`` are absolute indexes, ``end`` is None for '-n' ranges"""
    start: int
    end: int = None
    to_end: bool = False

    @classmethod
    def parse(cls, text):
        if isinstance(text, BitRange):
            return text
        m = BITS_RE.match(str(text))
        if not m:
            raise ValueError(f"invalid bits {text!r}, expected '<byte>.<bit>' or '<byte>.<bit>-<byte>.<bit>'")
        start = bit_index(int(m.group(1)), int(m.group(2)))
        if m.group(5):
            return cls(start, None, True)
        end = bit_index(int(m.group(3)), int(m.group(4))) if m.group(3) else start
        if end < start:
            raise ValueError(f"bits {text!r} end before they start (ranges are in transmission order, eg. '1.7-2.0')")
        return cls(start, end)

    @classmethod
    def from_size(cls, start_byte, start_bit, size):
        """Range of ``size`` bits starting at <start_byte>.<start_bit>"""
        start = bit_index(start_byte, start_bit)
        return cls(start, start + size - 1)

    @classmethod
    def from_dbc(cls, start_bit, size, little_endian=False):
        """Range from a DBC signal definition (start bit numbering of Vector DBC files).

        Motorola (big endian): the start bit is the MSB, ``(byte - 1) * 8 + bit``.
        Intel (little endian): the start bit is the LSB; only byte aligned or single byte values map
        to the DBMUXEv notation, use ``byte_order: little_endian`` with the result.
        """
        byte, bit = start_bit // 8 + 1, start_bit % 8
        if not little_endian:
            return cls.from_size(byte, bit, size)
        if bit + size <= 8:  # inside one byte
            return cls.from_size(byte, bit + size - 1, size)
        if bit != 0 or size % 8:
            raise ValueError('little endian DBC signals must be byte aligned to be converted')
        return cls.from_size(byte, 7, size)

    def __str__(self):
        sbyte, sbit = bit_position(self.start)
        if self.to_end:
            return f'{sbyte}.{sbit}-n'
        if self.end == self.start:
            return f'{sbyte}.{sbit}'
        ebyte, ebit = bit_position(self.end)
        return f'{sbyte}.{sbit}-{ebyte}.{ebit}'

    def __repr__(self):
        return f"BitRange('{self}')"

    @property
    def start_byte(self):
        return self.start // 8 + 1

    @property
    def start_bit(self):
        return 7 - self.start % 8

    def last(self, length=None):
        """Absolute index of the last bit. For '-n' ranges, length (bytes) is needed"""
        if not self.to_end:
            return self.end
        if length is None:
            raise ValueError(f"the end of '{self}' depends on the payload length")
        return max(length * 8 - 1, self.start)

    def width(self, length=None):
        return self.last(length) - self.start + 1

    def byte_length(self, length=None):
        """Number of bytes needed to hold this range (1 based end byte)"""
        return self.last(length) // 8 + 1

    def indexes(self, length=None):
        return range(self.start, self.last(length) + 1)

    def overlaps(self, other, length=None):
        return self.start <= other.last(length) and other.start <= self.last(length)

    def fits(self, length):
        """True if the range is inside a payload of ``length`` bytes"""
        return self.start < length * 8 and (self.to_end or self.end < length * 8)

    def is_byte_aligned(self, length=None):
        return self.start % 8 == 0 and (self.last(length) + 1) % 8 == 0

    def dbc_start_bit(self, little_endian=False, length=None):
        """Start bit in the Vector DBC numbering (MSB for Motorola, LSB for Intel)"""
        if not little_endian:
            return (self.start_byte - 1) * 8 + self.start_bit
        last = self.last(length)
        if self.start // 8 == last // 8:
            return (self.start_byte - 1) * 8 + (7 - last % 8)
        return (self.start_byte - 1) * 8


def extract(data, start, width):
    """Unsigned value of ``width`` bits starting at absolute index ``start`` (big endian, MSB first)"""
    total = len(data) * 8
    if width <= 0 or start + width > total:
        raise ValueError(f'bits {start}..{start + width - 1} outside of a {len(data)} byte payload')
    return (int.from_bytes(data, 'big') >> (total - start - width)) & ((1 << width) - 1)


def insert(buf, start, width, value):
    """Writes ``value`` on ``width`` bits at absolute index ``start`` of the bytearray ``buf``"""
    total = len(buf) * 8
    if width <= 0 or start + width > total:
        raise ValueError(f'bits {start}..{start + width - 1} outside of a {len(buf)} byte payload')
    if value < 0 or value >> width:
        raise ValueError(f'value {value} does not fit in {width} bits')
    shift = total - start - width
    mask = ((1 << width) - 1) << shift
    whole = (int.from_bytes(buf, 'big') & ~mask) | (value << shift)
    buf[:] = whole.to_bytes(len(buf), 'big')


def _groups(start, width):
    """Sizes of the pieces of a range split at byte boundaries, in transmission order"""
    sizes = []
    pos, end = start, start + width
    while pos < end:
        nxt = min(end, (pos // 8 + 1) * 8)
        sizes.append(nxt - pos)
        pos = nxt
    return sizes


def be_to_le(raw, start, width):
    """Value of a little endian field from its bits read in transmission order (first byte is the least significant)"""
    sizes = _groups(start, width)
    value, shift, remaining = 0, 0, width
    for size in sizes:
        remaining -= size
        value |= ((raw >> remaining) & ((1 << size) - 1)) << shift
        shift += size
    return value


def le_to_be(value, start, width):
    """Inverse of :func:`be_to_le`: bits to write in transmission order for a little endian value"""
    sizes = _groups(start, width)
    raw, shift = 0, 0
    for size in sizes:
        raw = (raw << size) | ((value >> shift) & ((1 << size) - 1))
        shift += size
    return raw
