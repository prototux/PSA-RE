#!/usr/bin/env python3
"""
Export the CAN frames of a DBMUXEv repository to Vector DBC files.

Usage:
    python3 tools/export_dbc.py [ROOT] --arch AEE2004.full [--bus HS.IS] [--lang en] [-o OUTDIR]

One DBC file is written per bus (<arch>.<variant>_<bus>.dbc). Variants with a
'parent' include the frames inherited from their parent. VAN and LIN frames are
skipped (DBC is CAN only); can-tp frames are exported as their raw 8 byte
transport frames without signals.
Requires: pyyaml
"""
import argparse
import os
import re
import sys

import yaml

BITS_RE = re.compile(r'^(\d+)\.([0-7])(?:-(?:(\d+)\.([0-7])|(n)))?$')


def load(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def variant_chain(archs, archvar):
    chain = []
    while archvar and archvar not in chain:
        chain.append(archvar)
        arch, var = archvar.split('.')
        parent = ((archs.get(arch) or {}).get(var) or {}).get('parent')
        archvar = f'{arch}.{parent}' if parent else None
    return chain


def frames_of(root, archs, archvar, bus):
    """frames of a variant (own files override the parent's), {filename: data}"""
    out = {}
    for av in reversed(variant_chain(archs, archvar)):
        d = os.path.join(root, 'buses', av, bus)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.yml') and os.path.exists(os.path.join(d, fn)):
                out[fn] = load(os.path.join(d, fn))
    return out


def buses_of(archs, archvar):
    buses = {}
    for av in reversed(variant_chain(archs, archvar)):
        arch, var = av.split('.')
        for net, bl in (((archs.get(arch) or {}).get(var) or {}).get('networks') or {}).items():
            for b, bd in (bl or {}).items():
                buses[f'{net}.{b}'] = bd or {}
    return buses


DBC_KEYWORDS = {'VERSION', 'NS_', 'BS_', 'BU_', 'BO_', 'SG_', 'EV_', 'CM_', 'BA_', 'BA_DEF_', 'BA_DEF_DEF_', 'VAL_',
                'VAL_TABLE_', 'SIG_GROUP_', 'SIG_VALTYPE_', 'BO_TX_BU_', 'SG_MUL_VAL_', 'CAT_', 'FILTER', 'ENVVAR_DATA_'}


def dbc_name(s):
    s = re.sub(r'[^A-Za-z0-9_]', '_', str(s))
    s = s if s and not s[0].isdigit() else '_' + s
    return s + '_' if s in DBC_KEYWORDS else s


def text(ml, lang):
    if not isinstance(ml, dict):
        return ''
    t = ml.get(lang) or ml.get('en') or next(iter(ml.values()), '')
    return str(t).replace('"', "'").replace('\n', ' ')


def motorola(bits, length):
    """PSA bits -> (DBC Motorola start bit, size) or None"""
    m = BITS_RE.match(str(bits))
    if not m or m.group(5):
        return None
    sb, sbit = int(m.group(1)), int(m.group(2))
    start = (sb - 1) * 8 + (7 - sbit)
    if m.group(3):
        end = (int(m.group(3)) - 1) * 8 + (7 - int(m.group(4)))
    else:
        end = start
    size = end - start + 1
    if size <= 0 or (length and end >= length * 8):
        return None
    return (sb - 1) * 8 + sbit, size, start, end


def intel(bits, length):
    """little endian: LSB is in the first covered byte (bits are whole bytes in practice)"""
    m = motorola(bits, length)
    if not m:
        return None
    _, size, start, end = m
    first_byte = start // 8
    lsb_in_byte = 7 - (end % 8) if start // 8 == end // 8 else 0
    return first_byte * 8 + lsb_in_byte, size


def export(root, archvar, bus, lang, outdir):
    archs = load(os.path.join(root, 'architectures.yml'))
    frames = frames_of(root, archs, archvar, bus)
    nodes = set()
    lines_bo, lines_cm, lines_ba, lines_val = [], [], [], []
    for fn, f in sorted(frames.items(), key=lambda kv: kv[1].get('id', 0)):
        if not isinstance(f, dict) or f.get('type') not in ('can', 'can-tp'):
            continue
        fid = f['id'] | (0x80000000 if f.get('extended') or f['id'] > 0x7FF else 0)
        length = f.get('length') or 8
        if f['type'] == 'can-tp':
            length = 8
        senders = f.get('senders') or []
        sender = dbc_name(senders[0]) if senders else 'Vector__XXX'
        nodes.update(dbc_name(n) for n in senders + (f.get('receivers') or []))
        mname = dbc_name(f.get('name') or f'FRAME_{f["id"]:X}')
        if '_' in fn.split('.')[0]:
            mname = f'{mname}_{fn.split(".")[0].split("_")[0]}'
        lines_bo.append(f'BO_ {fid} {mname}: {min(length, 8)} {sender}')
        if f.get('comment'):
            lines_cm.append(f'CM_ BO_ {fid} "{text(f["comment"], lang)}";')
        per = [p for p in (f.get('periodicity') or []) if str(p).endswith('ms')]
        if per:
            lines_ba.append(f'BA_ "GenMsgCycleTime" BO_ {fid} {int(per[0][:-2])};')
        if f['type'] == 'can-tp':
            continue
        selector = next((n for n, s in (f.get('signals') or {}).items() if s.get('mux_selector')), None)
        rcv = ','.join(dbc_name(n) for n in (f.get('receivers') or [])) or 'Vector__XXX'
        for sname, s in (f.get('signals') or {}).items():
            if s.get('unused'):
                continue
            le = s.get('byte_order') == 'little_endian'
            pos = intel(s['bits'], length) if le else motorola(s['bits'], length)
            if not pos:
                continue
            start, size = pos[0], pos[1]
            signed = '-' if s.get('type') == 'sint' else '+'
            factor = s.get('factor', 1) or 1
            offset = s.get('offset', 0) or 0
            mn = s.get('min', 0 if not s.get('values') else 0)
            mx = s.get('max', (2 ** size - 1) * factor + offset if signed == '+' else (2 ** (size - 1) - 1) * factor + offset)
            unit = str(s.get('units') or '').replace('"', "'")
            mux = ''
            if sname == selector:
                mux = ' M'
            elif s.get('mux') and s['mux']['selector'] == selector and len(s['mux']['values']) == 1:
                mux = f' m{s["mux"]["values"][0]}'
            srcv = ','.join(dbc_name(n) for n in s['receivers']) if s.get('receivers') else rcv
            lines_bo.append(f' SG_ {dbc_name(sname)}{mux} : {start}|{size}@{1 if le else 0}{signed} ({factor},{offset}) [{mn}|{mx}] "{unit}" {srcv}')
            if s.get('comment'):
                lines_cm.append(f'CM_ SG_ {fid} {dbc_name(sname)} "{text(s["comment"], lang)}";')
            vals = s.get('values') or {}
            pairs = [f'{int(k)} "{text(v, lang)}"' for k, v in sorted(vals.items(), key=lambda kv: int(kv[0]))
                     if isinstance(v, dict) and not (set(v) == {'unused'})]
            if pairs:
                lines_val.append(f'VAL_ {fid} {dbc_name(sname)} ' + ' '.join(pairs) + ' ;')
        lines_bo.append('')
    bd = buses_of(archs, archvar).get(bus, {})
    out = ['VERSION ""', '', 'NS_ :', '    CM_', '    BA_DEF_', '    BA_', '    VAL_', '    SG_MUL_VAL_', '',
           f'BS_:', '', 'BU_: ' + ' '.join(sorted(nodes - {'Vector__XXX'})), '', ''] + lines_bo + [''] + lines_cm + [
        'BA_DEF_ BO_ "GenMsgCycleTime" INT 0 65535;', 'BA_DEF_ "BusType" STRING;', 'BA_DEF_DEF_ "GenMsgCycleTime" 0;',
        'BA_DEF_DEF_ "BusType" "CAN";', f'BA_ "BusType" "CAN";'] + lines_ba + lines_val
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f'{archvar}_{bus}.dbc')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')
    comment = f" ({bd.get('bitrate')} kbit/s)" if bd.get('bitrate') else ''
    print(f'{path}: {sum(1 for l in lines_bo if l.startswith("BO_"))} frames{comment}')


def main():
    ap = argparse.ArgumentParser(description='Export DBMUXEv CAN frames to DBC')
    ap.add_argument('root', nargs='?', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--arch', required=True, help='architecture variant, eg. AEE2004.full')
    ap.add_argument('--bus', help='<network>.<bus>, eg. HS.IS (default: every CAN bus)')
    ap.add_argument('--lang', default='en', help='language of comments and value tables')
    ap.add_argument('-o', '--out', default='dbc', help='output directory')
    args = ap.parse_args()
    archs = load(os.path.join(args.root, 'architectures.yml'))
    buses = [args.bus] if args.bus else [b for b, d in buses_of(archs, args.arch).items() if str(d.get('protocol', '')).startswith('CAN')]
    if not buses:
        sys.exit(f'no CAN bus found for {args.arch}')
    for b in buses:
        export(args.root, args.arch, b, args.lang, args.out)


if __name__ == '__main__':
    main()
