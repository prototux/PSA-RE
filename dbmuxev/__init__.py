"""
dbmuxev: load, query, decode/encode and edit DBMUXEv repositories.

DBMUXEv describes automotive network architectures (CAN, CAN-TP, VAN, LIN),
their nodes, frames, cars and diagnostics in YAML; the format is documented
in ``dbmuxev/doc/`` and ``schemas/dbmuxev.schema.json``.

Quick start::

    from dbmuxev import Database

    db = Database()                               # repository containing the current directory
    bus = db['AEE2004.full']['LS.CONF']           # a bus of an architecture variant
    frame = bus.frame(0x0F6)                      # by ID, file key, name or alt name
    decoded = frame.decode(bytes.fromhex('8E7F00000000A001'))
    print(decoded)                                # one line per signal
    decoded['COOLANT_TEMPERATURE'].value          # physical value

    payload = frame.encode({'COOLANT_TEMPERATURE': 90})

    sig = frame.add_signal('NEW_SIGNAL', '8.7-8.0', type='uint', comment={'en': '...', 'fr': '...'})
    frame.save()                                  # or db.save_all()

See the class documentation of :class:`Database`, :class:`Message`,
:class:`Signal` and the ``diag`` module.
"""
from ._yaml import HexInt, hexint
from .architecture import Architectures, Bus, Car, CarVersion, Node, NodeDiag, NodeSet, Variant, parse_years
from .bits import BitRange
from .database import BusView, Database, find_root
from .diag import (Addressing, DiagData, DiagEcu, DiagProtocol, Dtc, DtcTable, EcuDiag, Ioctl, NegativeResponse,
                   Routine, SecurityAccess, dtc_to_raw, psa_seed_key, raw_to_dtc)
from .message import DecodedFrame, IsoTp, Lin, Message, MessageAlternative, Van, lin_checksum, lin_protected_id
from .multilang import MultiLang, get_language, set_language
from .signal import (Mux, Signal, SignalAlternative, SignalValue, ValueEntry, ValueTable, decode_payload,
                     encode_payload)

__version__ = '0.2.0'
FORMAT_VERSION = '0.2'

__all__ = [
    'Database', 'BusView', 'find_root',
    'Architectures', 'Variant', 'Bus', 'NodeSet', 'Node', 'NodeDiag', 'Car', 'CarVersion', 'parse_years',
    'Message', 'MessageAlternative', 'IsoTp', 'Van', 'Lin', 'DecodedFrame', 'lin_protected_id', 'lin_checksum',
    'Signal', 'SignalAlternative', 'SignalValue', 'ValueTable', 'ValueEntry', 'Mux', 'decode_payload',
    'encode_payload', 'BitRange',
    'DiagProtocol', 'DiagEcu', 'Addressing', 'SecurityAccess', 'DiagData', 'Dtc', 'DtcTable', 'Routine', 'Ioctl',
    'EcuDiag', 'NegativeResponse', 'dtc_to_raw', 'raw_to_dtc', 'psa_seed_key',
    'MultiLang', 'set_language', 'get_language', 'HexInt', 'hexint',
]
