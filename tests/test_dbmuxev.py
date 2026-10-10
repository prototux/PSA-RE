"""
Tests of the dbmuxev library: python3 -m unittest discover -s tests

Most tests use small repositories written in a temporary directory; the
TestRepository tests run on the repository containing this file (skipped
when there is none).
"""
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from dbmuxev import (BitRange, Database, DiagData, Message, NegativeResponse, Signal, dtc_to_raw,  # noqa: E402
                     lin_checksum, lin_protected_id, psa_seed_key, raw_to_dtc, set_language)
from dbmuxev import _yaml, isotp  # noqa: E402
from dbmuxev.bits import be_to_le, extract, insert, le_to_be  # noqa: E402
from dbmuxev.diag import check_response  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(text).lstrip('\n'))
    return path


ARCHS = '''
# Architectures of the test repository
ARCH:
  full:
    comment:
      en: 'Full'
      fr: 'Complet'
    years: '2004-2010'
    networks:
      HS:
        IS:
          protocol: 'CAN'
          bitrate: 500
      LIN:
        LIN1:
          protocol: 'LIN'
          bitrate: 19.2

  # later evolution
  ev:
    parent: 'full'
    comment:
      en: 'Evolution'
    networks:
      HS:
        HYB:
          protocol: 'CAN'
          bitrate: 500
'''

NODES = '''
BSI:
  bus: ['HS.IS', 'LIN.LIN1']
  id:
    HS: 0x12
  name:
    en: 'Body control module'
    fr: 'Boitier de servitude intelligent'

CMM:
  bus: ['HS.IS']
  name:
    en: 'Engine ECU'
'''

FRAME_208 = '''
id: 0x208
name: 'ENGINE_DATA'
type: 'can'
length: 8
comment:
  en: 'Engine data'
  fr: 'Données moteur'
periodicity: ['10ms', 'trigger']
senders: ['CMM']
receivers: ['BSI']

signals:
  ENGINE_RPM:
    bits: '1.7-2.0'
    factor: 0.125
    units: 'rpm'
    invalid: 0xFFFF
    default: 0x0000

  CRUISE_STATUS:
    bits: '3.7-3.6'
    type: 'enum'
    values:
      0x00:
        en: 'Off'
        fr: 'Arrêt'
      0x01:
        en: 'Active'
        fr: 'Actif'
      0x03:
        unused: true
    alternatives:
      - note:
          en: 'Single bit on old ECUs'
        bits: '3.7'

  RESERVED:
    bits: '3.5-3.0'
    unused: true

  SPEED_LE:
    bits: '4.7-5.0'
    byte_order: 'little_endian'
    factor: 0.01
    units: 'km/h'

  TEMPERATURE:
    bits: '6.7-6.0'
    type: 'sint'

  MODE:
    bits: '7.7-7.6'
    mux_selector: true
    default: 0x01
    values:
      0x00:
        en: 'Page 0'
      0x01:
        en: 'Page 1'

  PAGE0_VALUE:
    bits: '7.5-8.0'
    mux:
      selector: 'MODE'
      values: [0x00]

  PAGE1_FLAG:
    bits: '7.5'
    type: 'bool'
    mux:
      selector: 'MODE'
      values: [0x01]

alternatives:
  - note:
      en: 'Also seen with 7 bytes'
    length: 7
'''


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='dbmuxev-test-')
        write(self.root, 'architectures.yml', ARCHS)
        write(self.root, 'nodes/ARCH.full.yml', NODES)
        write(self.root, 'nodes/ARCH.ev.yml', '''
        BSI:
          bus: ['HS.HYB']
          name:
            en: 'Body control module (ev)'
        HCU:
          bus: ['HS.HYB']
          name:
            en: 'Hybrid control unit'
        ''')
        write(self.root, 'buses/ARCH.full/HS.IS/208.yml', FRAME_208)
        write(self.root, 'buses/ARCH.full/HS.IS/0F6.yml', '''
        id: 0x0F6
        name: 'BSI_SLOW_DATA'
        type: 'can'
        length: 2
        periodicity: ['500ms']
        senders: ['BSI']
        signals:
          COOLANT_TEMPERATURE:
            bits: '1.7-1.0'
            offset: -40
            units: 'degC'
          IGNITION:
            bits: '2.7'
            type: 'bool'
        ''')
        write(self.root, 'buses/ARCH.full/HS.IS/0F6_OTHER.yml', '''
        id: 0x0F6
        name: 'BSI_SLOW_DATA_OTHER'
        type: 'can'
        length: 3
        periodicity: ['500ms']
        senders: ['BSI']
        signals:
          VALUE:
            bits: '1.7-3.0'
        ''')
        write(self.root, 'buses/ARCH.full/LIN.LIN1/05.yml', '''
        id: 0x05
        name: 'RAIN_SENSOR'
        type: 'lin'
        length: 2
        periodicity: ['20ms']
        senders: ['CDPL']
        lin:
          protected_id: 0x85
          checksum: 'enhanced'
        signals:
          RAIN:
            bits: '1.7-1.4'
        ''')
        write(self.root, 'buses/ARCH.ev/HS.IS/0F6.yml', '''
        id: 0x0F6
        name: 'BSI_SLOW_DATA'
        type: 'can'
        length: 2
        periodicity: ['500ms']
        senders: ['BSI']
        signals:
          COOLANT_TEMPERATURE:
            bits: '1.7-1.0'
            offset: -39
            units: 'degC'
        ''')
        os.makedirs(os.path.join(self.root, 'buses/ARCH.ev/HS.HYB'))
        os.symlink('../../ARCH.full/HS.IS/208.yml', os.path.join(self.root, 'buses/ARCH.ev/HS.HYB/208.yml'))
        write(self.root, 'cars/X1.yml', '''
        codes:
          X11: 'test car'  # 5 doors
          X12: ['test car SW', 'test car estate']

        brand: ['peugeot']
        years: '2005-2012'

        versions:
          phase1:
            architecture: 'ARCH.full'
            years: '2005-2008'
            nodes:
              HS: ['BSI', 'CMM']
            optional_nodes: ['CMM']
          phase2:
            architecture: 'ARCH.ev'
            years: '2008-2012'
            codes: ['X12']
            nodes:
              HS: ['BSI', 'HCU']
        ''')
        write(self.root, 'diag/ARCH.full/BSI/ecu.yml', '''
        node: 'BSI'
        protocols: ['UDS']
        addressing:
          - transport: 'can-tp'
            bus: 'HS.IS'
            request_id: 0x752
            response_id: 0x652
        sessions:
          0x01:
            en: 'Default session'
        services: [0x10, 0x22, 0x27]
        security_access:
          - level: 0x03
            algorithm: 'PSA_SEED_KEY'
            key: 'B2B2'
        ''')
        write(self.root, 'diag/ARCH.full/BSI/dids/F190.yml', '''
        did: 0xF190
        name: 'VIN'
        kind: 'identification'
        access: 'read'
        length: 17
        params:
          VIN:
            bits: '1.7-17.0'
            type: 'str'
        ''')
        write(self.root, 'diag/ARCH.full/BSI/dtcs.yml', '''
        'B1003-00':
          raw: '900300'
          display_name:
            en: 'Secured coding fault'
        ''')
        write(self.root, 'diag/protocols/UDS.yml', '''
        protocol: 'UDS'
        services:
          0x22:
            name: 'READ_DATA_BY_IDENTIFIER'
        negative_responses:
          0x31:
            en: 'Request out of range'
        ''')
        self.db = Database(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)


class TestBits(unittest.TestCase):
    def test_parse_and_format(self):
        for text in ('1.7', '1.7-2.0', '1.5-1.3', '3.7-n', '8.0', '2.3-4.4'):
            self.assertEqual(str(BitRange.parse(text)), text)
        r = BitRange.parse('1.7-2.0')
        self.assertEqual((r.start, r.end, r.width()), (0, 15, 16))
        self.assertEqual(BitRange.parse('3.7-n').width(8), 48)
        self.assertEqual(r.dbc_start_bit(), 7)
        self.assertEqual(BitRange.from_dbc(7, 16), r)
        self.assertEqual(str(BitRange.from_size(2, 3, 4)), '2.3-2.0')
        with self.assertRaises(ValueError):
            BitRange.parse('2.0-1.7')
        with self.assertRaises(ValueError):
            BitRange.parse('0.7')

    def test_extract_insert(self):
        data = bytes.fromhex('A5C3')
        self.assertEqual(extract(data, 0, 16), 0xA5C3)
        self.assertEqual(extract(data, 2, 3), 0b100)
        buf = bytearray(2)
        insert(buf, 2, 3, 0b101)
        self.assertEqual(bytes(buf), bytes([0b00101000, 0]))
        with self.assertRaises(ValueError):
            insert(buf, 0, 3, 8)

    def test_little_endian(self):
        self.assertEqual(be_to_le(0x1234, 0, 16), 0x3412)
        self.assertEqual(le_to_be(0x3412, 0, 16), 0x1234)
        for v in (0, 1, 0x1FF, 0x2ABC):
            self.assertEqual(be_to_le(le_to_be(v, 3, 14), 3, 14), v)


class TestSignals(unittest.TestCase):
    def test_types(self):
        cases = [
            (Signal(name='U', bits='1.7-2.0', factor=0.125), bytes.fromhex('0100'), 32.0),
            (Signal(name='S', bits='1.7-1.0', type='sint'), b'\xfe', -2),
            (Signal(name='B', bits='1.7', type='bool'), b'\x80', True),
            (Signal(name='BCD', bits='1.7-2.0', type='bcd'), bytes.fromhex('1234'), 1234),
            (Signal(name='T', bits='1.7-4.0', type='str'), b'AB\x00\x00', 'AB'),
            (Signal(name='R', bits='1.7-2.0', type='bytes'), b'\x01\x02', b'\x01\x02'),
            (Signal(name='F', bits='1.7-4.0', type='float'), bytes.fromhex('3FC00000'), 1.5),
            (Signal(name='O', bits='1.7-1.0', offset=-40), b'\x82', 90),
            (Signal(name='LE', bits='1.7-2.0', byte_order='little_endian'), bytes.fromhex('3412'), 0x1234),
            (Signal(name='L', bits='1.4-1.0', type='uint8'), b'\x1f', 31),
            (Signal(name='SG', bits='1.7-1.0', signed=True), b'\xff', -1),
        ]
        for sig, data, expected in cases:
            with self.subTest(sig.name):
                v = sig.decode(data)
                self.assertEqual(v.value, expected)
                raw = sig.raw(v.value)
                if isinstance(raw, bytes):   # texts are padded with 0x00 when written
                    raw = raw.ljust(len(v.raw), b'\x00')
                self.assertEqual(raw, v.raw)

    def test_float_precision(self):
        sig = Signal(name='P', bits='1.7-1.0', factor=0.1)
        self.assertEqual(sig.physical(3), 0.3)
        self.assertEqual(sig.raw(0.3), 3)
        big = Signal(name='BIG', bits='1.7-7.0')
        self.assertEqual(big.raw(71723565653016761), 71723565653016761)

    def test_labels_and_invalid(self):
        sig = Signal(name='E', bits='1.7-1.6', type='enum', invalid=0x03,
                     values={0: {'en': 'Off', 'fr': 'Arrêt'}, 1: {'en': 'On'}})
        self.assertEqual(sig.decode(b'\x40').label, 'On')
        self.assertEqual(sig.decode(b'\x00').signal.label(0, 'fr'), 'Arrêt')
        self.assertFalse(sig.decode(b'\xc0').valid)
        self.assertEqual(sig.raw('arrêt'), 0)
        self.assertEqual(sig.raw('On'), 1)
        with self.assertRaises(ValueError):
            sig.raw('Unknown')
        with self.assertRaises(ValueError):
            sig.raw(4)
        self.assertEqual(sig.raw(4, strict=False), 3)


class TestMessage(RepoTestCase):
    def test_decode(self):
        m = self.db['ARCH.full']['HS.IS'].frame(0x208)
        d = m.decode(bytes.fromhex('1F40' '40' '3412' 'FE' '00' '2A'))
        self.assertEqual(d['ENGINE_RPM'].value, 1000.0)
        self.assertEqual(d['CRUISE_STATUS'].label, 'Active')
        self.assertEqual(d['SPEED_LE'].value, 46.6)
        self.assertEqual(d['TEMPERATURE'].value, -2)
        self.assertNotIn('RESERVED', d)
        self.assertIn('PAGE0_VALUE', d)
        self.assertNotIn('PAGE1_FLAG', d)
        self.assertEqual(d['PAGE0_VALUE'].value, 0x2A)
        d = m.decode(bytes.fromhex('FFFF00000000' '60' '00'))
        self.assertFalse(d['ENGINE_RPM'].valid)
        self.assertTrue(d['PAGE1_FLAG'].value)
        self.assertNotIn('PAGE0_VALUE', d)
        self.assertIn('ENGINE_RPM', str(d))

    def test_encode(self):
        m = self.db['ARCH.full']['HS.IS'].frame('ENGINE_DATA')
        data = m.encode({'ENGINE_RPM': 1000, 'CRUISE_STATUS': 'Active', 'SPEED_LE': 46.6, 'TEMPERATURE': -2})
        self.assertEqual(data, bytes.fromhex('1F40' '40' '3412' 'FE' '40' '00'))   # MODE defaults to 1
        data = m.encode({'PAGE0_VALUE': 0x2A})                                      # selects MODE 0
        self.assertEqual(data[6:], bytes.fromhex('002A'))
        with self.assertRaises(ValueError):
            m.encode({'MODE': 1, 'PAGE0_VALUE': 1})
        with self.assertRaises(KeyError):
            m.encode({'NOPE': 1})
        self.assertEqual(m.encode({'ENGINE_RPM': 0x1F40}, raw=True)[:2], bytes.fromhex('1F40'))
        base = bytes.fromhex('0000000000000000')
        self.assertEqual(m.encode({'TEMPERATURE': 1}, base=base)[5], 1)

    def test_can_tp(self):
        m = Message(id=0x0A4, name='RADIO_TEXT', type='can-tp', length=64, isotp={'padding': 0},
                    signals={'KIND': {'bits': '1.7-1.0'}, 'TEXT': {'bits': '2.7-n', 'type': 'str'}})
        from dbmuxev.message import IsoTp
        m.isotp = IsoTp.from_dict({'padding': 0, 'addressing': 'normal'})
        payload = m.encode({'KIND': 1, 'TEXT': 'HELLO WORLD'})
        self.assertEqual(payload, b'\x01HELLO WORLD')
        self.assertEqual(m.decode(payload)['TEXT'].value, 'HELLO WORLD')
        frames = m.encode_frames({'KIND': 1, 'TEXT': 'HELLO WORLD'})
        self.assertEqual(frames[0][:2], bytes([0x10, 12]))
        r = m.isotp.reassembler()
        out = [r.feed(f) for f in frames]
        self.assertEqual(out[-1], payload)

    def test_alternatives_and_check(self):
        m = self.db['ARCH.full']['HS.IS'].frame(0x208)
        self.assertEqual(m.with_alternative(0).length, 7)
        self.assertEqual(str(m['CRUISE_STATUS'].with_alternative(0).bits), '3.7')
        self.assertEqual(m.check(), [])
        m.add_signal('OVERLAP', '1.0-2.7')
        m.add_signal('OUTSIDE', '9.7')
        problems = ' '.join(m.check())
        self.assertIn('overlap', problems)
        self.assertIn('outside', problems)

    def test_edit_signals(self):
        m = self.db['ARCH.full']['HS.IS'].frame(0x208)
        m.rename_signal('MODE', 'PAGE')
        self.assertEqual(m['PAGE0_VALUE'].mux.selector, 'PAGE')
        self.assertEqual(list(m.signals).index('PAGE'), 5)
        self.assertEqual(m.mux_values(), [0, 1])
        self.assertEqual(m.free_bits(), [])
        m.remove_signal('TEMPERATURE')
        self.assertEqual([str(r) for r in m.free_bits()], ['6.7-6.0'])
        self.assertEqual(m.bit_map()[0][0], 'ENGINE_RPM')
        self.assertEqual(m.period_ms, 10)
        self.assertTrue(m.is_triggered)


class TestDatabase(RepoTestCase):
    def test_inheritance(self):
        ev = self.db['ARCH.ev']
        self.assertEqual(set(ev.buses()), {'HS.IS', 'LIN.LIN1', 'HS.HYB'})
        nodes = ev.nodes()
        self.assertEqual(set(nodes), {'BSI', 'CMM', 'HCU'})
        self.assertEqual(nodes['BSI'].bus, ['HS.HYB', 'HS.IS', 'LIN.LIN1'])
        self.assertEqual(str(nodes['BSI'].display_name), 'Body control module (ev)')
        self.assertEqual(nodes['BSI'].unit_code('HS'), 0x12)   # inherited
        is_frames = ev['HS.IS'].frames
        self.assertEqual(is_frames['0F6'].variant, 'ARCH.ev')     # redefined
        self.assertEqual(is_frames['208'].variant, 'ARCH.full')   # inherited
        self.assertEqual(ev['HS.IS'].decode(0x0F6, b'\x80\x00')['COOLANT_TEMPERATURE'].value, 89)
        self.assertEqual(self.db['ARCH.full']['HS.IS'].decode(0x0F6, b'\x80\x00')['COOLANT_TEMPERATURE'].value, 88)
        self.assertEqual([v.full_name for v in ev.chain()], ['ARCH.ev', 'ARCH.full'])
        self.assertEqual(set(ev['HS.IS'].nodes), {'BSI', 'CMM'})

    def test_frame_lookup(self):
        bus = self.db['ARCH.full']['HS.IS']
        self.assertEqual(bus.frame('0F6_OTHER').name, 'BSI_SLOW_DATA_OTHER')
        self.assertEqual(bus.frame(0x0F6).suffix, None)
        self.assertEqual(len(bus.frames_by_id(0x0F6)), 2)
        self.assertEqual(bus.identify(0x0F6, b'\x00\x00\x00').name, 'BSI_SLOW_DATA_OTHER')
        self.assertEqual(bus.identify(0x0F6, b'\x00\x00').name, 'BSI_SLOW_DATA')
        self.assertEqual(bus['0x208'].name, 'ENGINE_DATA')
        self.assertIn('ENGINE_DATA', bus)
        self.assertEqual(self.db['ARCH.full']['LIN.LIN1'].frame(5).key, '05')
        with self.assertRaises(KeyError):
            bus.frame(0x123)
        with self.assertRaises(KeyError):
            self.db['ARCH.full']['HS.NOPE']
        found = list(self.db.find_signals('rpm'))
        self.assertEqual({(m.variant, s.name) for m, s in found}, {('ARCH.full', 'ENGINE_RPM'), ('ARCH.ev', 'ENGINE_RPM')})
        self.assertEqual([m.name for m in self.db.find_frames(node='CMM', variants=['ARCH.full'])], ['ENGINE_DATA'])

    def test_symlink(self):
        m = self.db['ARCH.ev']['HS.HYB'].frame(0x208)
        self.assertTrue(m.is_link)
        m.comment['en'] = 'Shared'
        m.save()
        self.assertTrue(os.path.islink(m.path))
        self.assertEqual(Database(self.root)['ARCH.full']['HS.IS'].frame(0x208).comment['en'], 'Shared')
        m.comment['en'] = 'Own copy'
        m.save(break_link=True)
        self.assertFalse(os.path.islink(m.path))
        db = Database(self.root)
        self.assertEqual(db['ARCH.full']['HS.IS'].frame(0x208).comment['en'], 'Shared')
        self.assertEqual(db['ARCH.ev']['HS.HYB'].frame(0x208).comment['en'], 'Own copy')
        linked = db['ARCH.ev']['HS.HYB'].link(db['ARCH.full']['HS.IS'].frame('0F6_OTHER'))
        self.assertTrue(linked.is_link)

    def test_create_save_rename_remove(self):
        bus = self.db['ARCH.ev']['HS.HYB']
        m = bus.new_frame(0x3A0, 'HYBRID_STATUS', length=1, periodicity=['100ms'], senders=['HCU'],
                          comment={'en': 'Hybrid status', 'fr': 'Etat hybride'})
        m.add_signal('READY', '1.7', type='bool', comment={'en': 'Ready', 'fr': 'Prêt'})
        self.assertEqual(self.db.save_all(), [os.path.join(self.root, 'buses/ARCH.ev/HS.HYB/3A0.yml')])
        self.assertEqual(self.db.save_all(), [])   # nothing modified anymore
        with open(m.path, encoding='utf-8') as f:
            text = f.read()
        self.assertIn("id: 0x3A0\nname: 'HYBRID_STATUS'", text)
        self.assertIn('\nsignals:\n  READY:\n', text)
        m2 = Database(self.root)['ARCH.ev']['HS.HYB'].frame(0x3A0)
        self.assertEqual(m2.decode(b'\x80')['READY'].value, True)
        m.id = 0x3A1
        m.save()
        self.assertFalse(os.path.exists(os.path.join(self.root, 'buses/ARCH.ev/HS.HYB/3A0.yml')))
        self.assertTrue(os.path.exists(os.path.join(self.root, 'buses/ARCH.ev/HS.HYB/3A1.yml')))
        bus.remove(0x3A1)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'buses/ARCH.ev/HS.HYB/3A1.yml')))
        with self.assertRaises(ValueError):
            bus.new_frame(0x208, 'DUPLICATE')     # 208 exists (symlink) in this bus

    def test_override(self):
        bus = self.db['ARCH.ev']['HS.IS']
        m = bus.override(0x208)
        self.assertEqual(m.variant, 'ARCH.ev')
        m['ENGINE_RPM'].factor = 0.25
        m.save()
        db = Database(self.root)
        self.assertEqual(db['ARCH.ev']['HS.IS'].frame(0x208)['ENGINE_RPM'].factor, 0.25)
        self.assertEqual(db['ARCH.full']['HS.IS'].frame(0x208)['ENGINE_RPM'].factor, 0.125)

    def test_roundtrip_and_minimal_diff(self):
        for doc in Database(self.root).load_all().loaded_documents():
            self.assertFalse(doc.is_modified, doc.path)
        arch = self.db.architectures
        self.db['ARCH.full'].years = '2004-2011'
        text = arch.to_yaml()
        self.assertIn('# Architectures of the test repository\nARCH:', text)
        self.assertIn('\n  # later evolution\n  ev:', text)
        with open(arch.path, encoding='utf-8') as f:
            before = f.read().splitlines()
        changed = [(a, b) for a, b in zip(before, text.splitlines()) if a != b]
        self.assertEqual(changed, [("    years: '2004-2010'", "    years: '2004-2011'")])

    def test_cars(self):
        car = self.db.car('X12')
        self.assertEqual(car.project, 'X1')
        self.assertEqual(car.names_of('X12'), ['test car SW', 'test car estate'])
        self.assertEqual([v.name for v in car.versions_for(code='X11')], ['phase1'])
        self.assertEqual([v.name for v in car.versions_for(year=2010)], ['phase2'])
        self.assertEqual(car.versions['phase1'].mandatory_nodes, ['BSI'])
        self.assertEqual([c.project for c in self.db.find_cars(node='HCU')], ['X1'])
        self.assertEqual(self.db.car('test car estate'), car)
        car.platform = 'PF1'
        car.save()
        with open(car.path, encoding='utf-8') as f:
            self.assertIn("X11: 'test car'  # 5 doors", f.read())

    def test_nodes_edit(self):
        ns = self.db.nodeset('ARCH.full')
        ns.add('ABS', ['HS.IS'], {'en': 'Brakes', 'fr': 'Freins'}, id={'HS': 0x0D})
        ns.save()
        with open(ns.path, encoding='utf-8') as f:
            text = f.read()
        self.assertTrue(text.endswith("\nABS:\n  bus: ['HS.IS']\n  id:\n    HS: 0x0D\n  name:\n    en: 'Brakes'\n"
                                      "    fr: 'Freins'\n"), text)
        self.assertEqual(Database(self.root).node('ARCH.ev', 'ABS').bus, ['HS.IS'])


class TestDiag(RepoTestCase):
    def test_ecu(self):
        ed = self.db.diag('ARCH.ev', 'BSI')     # found in the parent variant
        self.assertEqual(ed.variant, 'ARCH.full')
        self.assertEqual(ed.ecu.address(bus='HS.IS').request_id, 0x752)
        vin = ed.data(0xF190)
        self.assertEqual(vin.read_request(), bytes.fromhex('22F190'))
        decoded = vin.decode_response(bytes.fromhex('62F190') + b'VF3ABCDEFGH123456')
        self.assertEqual(decoded['VIN'].value, 'VF3ABCDEFGH123456')
        self.assertEqual(vin.write_request({'VIN': 'VF3ABCDEFGH123456'})[:3], bytes.fromhex('2EF190'))
        with self.assertRaises(NegativeResponse) as cm:
            check_response(0x22, '7F 22 31', self.db.protocol('UDS'))
        self.assertEqual(cm.exception.text, 'Request out of range')
        self.assertEqual(ed.dtcs.lookup('900300').code, 'B1003-00')
        self.assertEqual(ed.dtcs.lookup('B1003').code, 'B1003-00')
        sa = ed.ecu.security(0x03)
        self.assertEqual(sa.key_request('11223344'), bytes.fromhex('2704') + psa_seed_key('11223344', 'B2B2'))

    def test_kwp(self):
        lid = DiagData(lid=0x80, name='IDENT', params={'CODE': {'bits': '1.7-2.0'}})
        self.assertEqual(lid.read_request(), b'\x21\x80')
        self.assertEqual(lid.write_request({'CODE': 0x1234}), bytes.fromhex('3B801234'))
        self.assertEqual(lid.decode_response('61 80 12 34')['CODE'].value, 0x1234)

    def test_dtc_codes(self):
        self.assertEqual(dtc_to_raw('B1003-00'), bytes.fromhex('900300'))
        self.assertEqual(dtc_to_raw('P0420'), bytes.fromhex('0420'))
        self.assertEqual(dtc_to_raw('U3FFF-FF'), bytes.fromhex('FFFFFF'))
        self.assertEqual(raw_to_dtc('900300'), 'B1003-00')
        self.assertEqual(raw_to_dtc(b'\x44\x20'), 'C0420')
        with self.assertRaises(ValueError):
            dtc_to_raw('B4003')

    def test_seed_key(self):
        key = psa_seed_key(bytes.fromhex('11223344'), 0xB2B2)
        self.assertEqual(len(key), 4)
        self.assertEqual(key, psa_seed_key('11 22 33 44', 'B2B2'))
        self.assertNotEqual(key, psa_seed_key('11223345', 'B2B2'))


class TestProtocols(unittest.TestCase):
    def test_isotp(self):
        payload = bytes(range(18))
        frames = isotp.segment(payload, padding=0xAA)
        self.assertEqual([len(f) for f in frames], [8, 8, 8])
        self.assertEqual(frames[0][:2], b'\x10\x12')
        self.assertEqual(frames[1][0], 0x21)
        self.assertEqual(frames[2][-1], 0xAA)
        r = isotp.Reassembler()
        self.assertEqual([r.feed(f) for f in frames][-1], payload)
        self.assertEqual(isotp.segment(b'\x22\xF1\x90'), [b'\x03\x22\xF1\x90'])
        self.assertEqual(isotp.Reassembler().feed(b'\x03\x62\xF1\x90'), b'\x62\xF1\x90')
        self.assertEqual(isotp.flow_control(padding=0), bytes([0x30, 0, 0, 0, 0, 0, 0, 0]))
        ext = isotp.segment(payload, address=0xF1)
        self.assertTrue(all(f[0] == 0xF1 for f in ext))
        r = isotp.Reassembler(address=0xF1)
        self.assertEqual([r.feed(f) for f in ext][-1], payload)

    def test_lin(self):
        self.assertEqual(lin_protected_id(0x05), 0x85)
        self.assertEqual(lin_protected_id(0x3C), 0x3C)
        self.assertEqual(lin_protected_id(0x3D), 0x7D)
        self.assertEqual(lin_checksum(b'\x01'), 0xFE)
        self.assertEqual(lin_checksum(b'\xFF\x01', 0x85), (~((0xFF + 0x01 - 0xFF + 0x85) & 0xFF)) & 0xFF)


class TestYaml(unittest.TestCase):
    def test_hex_and_layout(self):
        text = textwrap.dedent('''\
            # header

            id: 0x0F6
            values:
              0x01:
                en: 'One'  # inline
              0x0A:
                en: 'Ten'
            list: ['a', 'b']
            block:
              - 'a'
              - 'b'
            text: |
              line 1
              # not a comment
            float: 1.0e-05
            ''')
        data = _yaml.loads(text)
        self.assertEqual(repr(data['id']), '0x0F6')
        self.assertEqual(data['values'][1]['en'], 'One')
        self.assertEqual(data['float'], 1e-05)
        layout = _yaml.Layout.parse(text)
        header, _ = _yaml.split_header(text)
        self.assertEqual(_yaml.dumps(data, header=header, layout=layout), text)
        self.assertEqual(_yaml.loads(_yaml.dumps({'f': 1e-05, 'q': "it's", 'n': None, 'b': True})),
                         {'f': 1e-05, 'q': "it's", 'n': None, 'b': True})
        self.assertEqual(_yaml.dumps({'yes': 1, 'B1003-00': 2, 'x': {}}), "'yes': 1\nB1003-00: 2\nx: {}\n")


class TestLanguage(RepoTestCase):
    def test_language(self):
        m = self.db['ARCH.full']['HS.IS'].frame(0x208)
        try:
            set_language('fr')
            self.assertEqual(str(m.comment), 'Données moteur')
            self.assertEqual(m.decode(bytes.fromhex('0000400000000000'))['CRUISE_STATUS'].label, 'Actif')
            self.assertEqual(str(self.db['ARCH.ev'].comment), 'Evolution')     # english fallback
        finally:
            set_language('en')
        self.assertEqual(m.decode(bytes(8), lang='fr')['CRUISE_STATUS'].label, 'Arrêt')


class TestSchema(RepoTestCase):
    def test_schema_errors(self):
        import importlib.util
        if importlib.util.find_spec('jsonschema') is None:
            self.skipTest('jsonschema not installed')
        from dbmuxev.schema import schema_errors
        path = os.path.join(ROOT, 'schemas', 'dbmuxev.schema.json')
        if not os.path.isfile(path):
            self.skipTest('no schema')
        m = self.db['ARCH.full']['HS.IS'].frame(0x208)
        self.assertEqual(schema_errors(m, schema_path=path), [])
        m.name = 'bad name'
        m['ENGINE_RPM'].type = 'number'
        self.assertEqual(len(schema_errors(m, schema_path=path)), 2)


@unittest.skipUnless(os.path.isfile(os.path.join(ROOT, 'architectures.yml')) and os.path.isdir(os.path.join(ROOT, 'buses')),
                     'no repository around the tests')
class TestRepository(unittest.TestCase):
    """Runs on the real repository: every file loads and is written back identical"""

    @classmethod
    def setUpClass(cls):
        cls.db = Database(ROOT).load_all()

    def test_roundtrip(self):
        modified = [d.path for d in self.db.loaded_documents() if d.is_modified]
        self.assertEqual(modified, [])

    def test_frames_decode_encode(self):
        for m in self.db.iter_frames():
            length = m.length or 8 if m.type != 'can-tp' else 16
            data = bytes((i * 37 + m.id) & 0xFF for i in range(length))
            d = m.decode(data)
            again = m.decode(m.encode(d.raw_values(), raw=True, defaults=False, length=length))
            self.assertEqual(again.raw_values(), d.raw_values(), m.path)


if __name__ == '__main__':
    unittest.main()
