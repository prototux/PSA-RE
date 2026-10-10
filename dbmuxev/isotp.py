"""
ISO 15765-2 (ISO-TP / CAN-TP) segmentation and reassembly, for the ``can-tp``
frames and the diagnostic requests/responses.

Only the framing is handled (no timing): :func:`segment` splits a payload in
CAN frames, :class:`Reassembler` rebuilds payloads from received CAN frames.
"""

__all__ = ['segment', 'flow_control', 'Reassembler', 'IsoTpError',
           'SINGLE_FRAME', 'FIRST_FRAME', 'CONSECUTIVE_FRAME', 'FLOW_CONTROL']

SINGLE_FRAME, FIRST_FRAME, CONSECUTIVE_FRAME, FLOW_CONTROL = 0, 1, 2, 3


class IsoTpError(ValueError):
    pass


def _finish(frame, padding, size):
    if padding is not None and len(frame) < size:
        frame = frame + bytes([padding]) * (size - len(frame))
    return bytes(frame)


def segment(payload, padding=None, address=None, frame_size=8):
    """CAN frames (data fields) carrying ``payload``.

    padding: byte used to fill the frames to ``frame_size`` (None: no padding)
    address: first byte of every frame for extended/mixed addressing
    """
    payload = bytes(payload)
    prefix = bytes([address]) if address is not None else b''
    room = frame_size - len(prefix)
    if len(payload) > 4095:
        raise IsoTpError(f'payload of {len(payload)} bytes, ISO-TP (classic) is limited to 4095')
    if len(payload) <= room - 1:
        return [_finish(prefix + bytes([len(payload)]) + payload, padding, frame_size)]
    frames = [prefix + bytes([0x10 | (len(payload) >> 8), len(payload) & 0xFF]) + payload[:room - 2]]
    pos, sn = room - 2, 1
    while pos < len(payload):
        frames.append(_finish(prefix + bytes([0x20 | sn]) + payload[pos:pos + room - 1], padding, frame_size))
        pos += room - 1
        sn = (sn + 1) & 0x0F
    frames[0] = bytes(frames[0])
    return frames


def flow_control(status=0, block_size=0, st_min=0, padding=None, address=None, frame_size=8):
    """Flow control frame: status 0 = continue to send, 1 = wait, 2 = overflow"""
    prefix = bytes([address]) if address is not None else b''
    return _finish(prefix + bytes([0x30 | status, block_size, st_min]), padding, frame_size)


class Reassembler:
    """Rebuilds ISO-TP payloads: ``feed(frame)`` returns the payload once complete, else None.

    Flow control frames are ignored; a first frame restarts the transfer.
    """

    def __init__(self, address=None):
        self.address = address
        self.reset()

    def reset(self):
        self.buffer = bytearray()
        self.expected = 0
        self.next_sn = 1

    @property
    def in_progress(self):
        return self.expected > 0

    def feed(self, frame):
        frame = bytes(frame)
        if self.address is not None:
            if not frame or frame[0] != self.address:
                return None
            frame = frame[1:]
        if not frame:
            return None
        kind = frame[0] >> 4
        if kind == SINGLE_FRAME:
            n = frame[0] & 0x0F
            if n == 0 and len(frame) > 1:  # CAN-FD escape: length in the next byte
                n, data = frame[1], frame[2:]
            else:
                data = frame[1:]
            self.reset()
            if n > len(data):
                raise IsoTpError(f'single frame announces {n} bytes, has {len(data)}')
            return bytes(data[:n])
        if kind == FIRST_FRAME:
            self.reset()
            self.expected = ((frame[0] & 0x0F) << 8) | frame[1]
            self.buffer.extend(frame[2:])
            return None
        if kind == CONSECUTIVE_FRAME:
            if not self.in_progress:
                return None
            sn = frame[0] & 0x0F
            if sn != self.next_sn:
                self.reset()
                raise IsoTpError(f'consecutive frame {sn} received, expected {self.next_sn}')
            self.next_sn = (self.next_sn + 1) & 0x0F
            self.buffer.extend(frame[1:])
            if len(self.buffer) >= self.expected:
                data = bytes(self.buffer[:self.expected])
                self.reset()
                return data
            return None
        return None  # flow control
