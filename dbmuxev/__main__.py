"""
Command line access to a DBMUXEv repository.

    python3 -m dbmuxev variants
    python3 -m dbmuxev buses AEE2004.full
    python3 -m dbmuxev frames AEE2004.full LS.CONF
    python3 -m dbmuxev show AEE2004.full LS.CONF 0F6
    python3 -m dbmuxev decode AEE2004.full LS.CONF 0F6 8E7F00000000A001
    python3 -m dbmuxev encode AEE2004.full LS.CONF 0F6 COOLANT_TEMPERATURE=90 MAIN_STATUS='Ignition on'
    python3 -m dbmuxev find --signal SPEED --variant AEE2010.full
    python3 -m dbmuxev car T91
    python3 -m dbmuxev dtc B1003-00
    python3 -m dbmuxev seedkey 11223344 B2B2
"""
import argparse
import json
import sys

from . import Database, set_language
from .diag import psa_seed_key


def _frame_id(text):
    return int(text, 16) if all(c in '0123456789abcdefABCDEFx' for c in text) else text


def cmd_variants(db, args):
    for v in db.variants.values():
        parent = f' (parent: {v.parent})' if v.parent else ''
        years = f' {v.years}' if v.years else ''
        print(f'{v.full_name:<18}{years:<11} {v.status or "":<11} {v.comment or ""}{parent}')


def cmd_buses(db, args):
    v = db.variant(args.variant)
    for name, view in v.bus_views().items():
        d = view.definition
        rate = f'{d.bitrate:g} kbit/s' if d and d.bitrate else ''
        print(f'{name:<14} {(d.protocol if d else "?"):<7} {rate:<12} {len(view.frames):>4} frames  '
              f'{(d.display_name or "") if d else ""}')


def cmd_frames(db, args):
    for m in db.bus(args.variant, args.bus):
        period = '/'.join(m.periodicity or [])
        inherited = '' if m.variant == db.variant(args.variant).full_name else f' [{m.variant}]'
        print(f'{m.id_hex:<6} {m.key:<36} {m.name:<44} {period:<16} {",".join(m.senders or [])}{inherited}')


def cmd_show(db, args):
    m = db.bus(args.variant, args.bus).frame(_frame_id(args.frame))
    print(f'{m.id_hex} {m.name} ({m.type}, {m.length} bytes) {"/".join(m.periodicity or [])}')
    print(f'  file: {m.path}' + (f' -> {m.link}' if m.link else ''))
    if m.comment:
        print(f'  {m.comment}')
    print(f'  senders: {", ".join(m.senders or [])}')
    print(f'  receivers: {", ".join(m.receivers or [])}')
    for s in m.signals.values():
        flags = ' (unused)' if s.unused else ''
        if s.mux_selector:
            flags += ' (mux selector)'
        if s.mux:
            flags += f' (when {s.mux.selector} in {", ".join(hex(v) for v in s.mux.values)})'
        scale = f' x{s.scale:g}' if s.scale != 1 else ''
        scale += f' {s.shift:+g}' if s.shift else ''
        print(f'  {str(s.bits):<10} {s.name:<40} {s.kind:<5}{scale} {s.units or ""}{flags}')
        if s.values and args.values:
            for raw, e in s.values.items():
                print(f'{"":<14}0x{raw:02X} {e}')
    if args.map and m.type != 'can-tp':
        print()
        for i, row in enumerate(m.bit_map()):
            print(f'  {i + 1:>2} ' + ' '.join(f'{(c or "-")[:10]:<10}' for c in row))


def cmd_decode(db, args):
    bus = db.bus(args.variant, args.bus)
    d = bus.decode(int(args.frame, 16), bytes.fromhex(args.data), include_unused=args.all)
    if args.json:
        print(json.dumps(d.to_dict(), indent=1, ensure_ascii=False))
    else:
        print(d)


def cmd_encode(db, args):
    m = db.bus(args.variant, args.bus).frame(_frame_id(args.frame))
    values = {}
    for item in args.values:
        name, _, value = item.partition('=')
        sig = m.signal(name)
        if sig.kind in ('str', 'bytes'):
            values[sig.name] = value
        else:
            try:
                values[sig.name] = int(value, 0) if args.raw else float(value) if any(c in value for c in '.eE') \
                    and not value.lower().startswith('0x') else int(value, 0)
            except ValueError:
                values[sig.name] = value  # value label
    payload = m.encode(values, raw=args.raw)
    if m.type == 'can-tp' and args.frames:
        for f in m.encode_frames(values, raw=args.raw):
            print(f'{m.id:03X}#{f.hex().upper()}')
    else:
        print(payload.hex().upper())


def cmd_find(db, args):
    variants = [args.variant] if args.variant else None
    if args.signal and not args.name:
        for m, s in db.find_signals(args.signal, variants, args.bus):
            print(f'{m.variant:<16} {m.bus:<12} {m.id_hex:<6} {m.name:<40} {s.name} ({s.bits})')
        return
    for m in db.find_frames(name=args.name, signal=args.signal, node=args.node, variants=variants, buses=args.bus,
                            frame_id=int(args.id, 16) if args.id else None):
        print(f'{m.variant:<16} {m.bus:<12} {m.id_hex:<6} {m.name}')


def cmd_car(db, args):
    cars = [db.car(args.car)] if not args.search else list(db.find_cars(args.car))
    for car in cars:
        print(f'{car.project}: {", ".join(car.all_names)}  {car.platform or ""} {car.years or ""}')
        for code in car.codes:
            print(f'  {code:<8} {", ".join(car.names_of(code))}')
        for v in car.versions.values():
            print(f'  {v.name}: {v.architecture} {v.years or ""}')
            for net, nodes in (v.nodes or {}).items():
                print(f'    {net}: {", ".join(n + ("?" if n in (v.optional_nodes or []) else "") for n in nodes)}')


def cmd_dtc(db, args):
    found = False
    for ed, d in db.find_dtc(args.code, args.variant):
        found = True
        print(f'{ed.variant} {ed.node}: {d.code} {d.display_name}' + (f' ({d.raw})' if d.raw else ''))
        if d.comment:
            print(f'    {d.comment}')
    if not found:
        sys.exit(f'{args.code}: not found')


def cmd_seedkey(db, args):
    print(psa_seed_key(bytes.fromhex(args.seed), int(args.key, 16)).hex().upper())


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python3 -m dbmuxev', description='Query a DBMUXEv repository')
    ap.add_argument('-r', '--root', help='repository root (default: found from the current directory)')
    ap.add_argument('-l', '--lang', default='en', help='language of the texts (en, fr...)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('variants', help='architecture variants')
    p = sub.add_parser('buses', help='buses of a variant')
    p.add_argument('variant')
    p = sub.add_parser('frames', help='frames of a bus')
    p.add_argument('variant')
    p.add_argument('bus')
    p = sub.add_parser('show', help='one frame and its signals')
    p.add_argument('variant')
    p.add_argument('bus')
    p.add_argument('frame', help='ID (hex), file key or name')
    p.add_argument('--values', action='store_true', help='print the value tables')
    p.add_argument('--map', action='store_true', help='print the bit map')
    p = sub.add_parser('decode', help='decode a payload')
    p.add_argument('variant')
    p.add_argument('bus')
    p.add_argument('frame', help='ID (hex)')
    p.add_argument('data', help='payload in hex')
    p.add_argument('--all', action='store_true', help='include the unused signals')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('encode', help='build a payload from SIGNAL=VALUE (physical value or label)')
    p.add_argument('variant')
    p.add_argument('bus')
    p.add_argument('frame', help='ID (hex), file key or name')
    p.add_argument('values', nargs='*')
    p.add_argument('--raw', action='store_true', help='values are raw values')
    p.add_argument('--frames', action='store_true', help='can-tp: print the ISO-TP CAN frames')
    p = sub.add_parser('find', help='search frames and signals')
    p.add_argument('--name', help='frame name regex')
    p.add_argument('--signal', help='signal name regex')
    p.add_argument('--node', help='sender or receiver')
    p.add_argument('--id', help='frame ID (hex)')
    p.add_argument('--variant')
    p.add_argument('--bus')
    p = sub.add_parser('car', help='a car project (by project, code or name)')
    p.add_argument('car')
    p.add_argument('--search', action='store_true', help='every car whose name/code contains the text')
    p = sub.add_parser('dtc', help='look up a trouble code (B1003-00, or raw hex 900300)')
    p.add_argument('code')
    p.add_argument('--variant')
    p = sub.add_parser('seedkey', help='PSA security access key of a seed')
    p.add_argument('seed', help='4 byte seed in hex')
    p.add_argument('key', help='16 bit ECU constant in hex (security_access key)')

    args = ap.parse_args(argv)
    set_language(args.lang)
    db = None if args.cmd == 'seedkey' else Database(args.root)
    try:
        globals()['cmd_' + args.cmd](db, args)
    except (KeyError, ValueError) as e:
        sys.exit(f'error: {e.args[0] if e.args else e}')
    except BrokenPipeError:  # pragma: no cover
        pass


if __name__ == '__main__':
    main()
