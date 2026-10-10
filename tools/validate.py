#!/usr/bin/env python3
"""
DBMUXEv repository validator.

Checks every YAML file of a DBMUXEv repository (architectures, nodes, cars,
bus frames, diagnostics) against schemas/dbmuxev.schema.json, then runs
semantic checks the schema cannot express (bit overlaps, bits outside of the
frame, unknown nodes/buses, file naming, translations...).

Usage:
    python3 tools/validate.py [ROOT] [--strict] [--quiet] [--json] [--langs]
                              [--only PATH_SUBSTRING] [--no-warnings]

Exit code is 1 if any error was found (or any warning with --strict).
Requires: pyyaml, jsonschema  (pip install -r tools/requirements.txt)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

try:
    import yaml
    import jsonschema
except ImportError:
    sys.stderr.write('Missing dependencies, run: pip install -r tools/requirements.txt\n')
    sys.exit(2)

SCHEMA_REL = os.path.join('schemas', 'dbmuxev.schema.json')
RECOMMENDED_LANGS = ['en', 'fr']
EXTRA_LANGS = ['es', 'de', 'it', 'pl', 'ru', 'zh', 'hu', 'pt']
BITS_RE = re.compile(r'^(\d+)\.([0-7])(?:-(?:(\d+)\.([0-7])|(n)))?$')
FRAME_FILE_RE = re.compile(r'^([0-9A-F]{2,8})(?:_([A-Z0-9_]+))?\.yml$')
DEPRECATED_TYPES = {'uint8', 'uint16', 'uint24', 'int8', 'int16', 'int24'}


# --------------------------------------------------------------------------
# Strict YAML loading: duplicate keys and binary/octal looking keys are errors
# --------------------------------------------------------------------------

class YamlIssue(Exception):
    pass


class StrictLoader(yaml.SafeLoader):
    issues = None


def _construct_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    seen = {}
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        raw = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
        line = key_node.start_mark.line + 1
        if raw is not None and re.fullmatch(r'0[0-9]+', raw) and key_node.style is None:
            loader.issues.append(('error', line,
                                  f"key '{raw}' has a leading zero: YAML reads it as octal/decimal "
                                  f"({key}), write it as hex (0x..) or plain decimal"))
        if raw is not None and re.fullmatch(r'0b[01_]+', raw) and key_node.style is None:
            loader.issues.append(('warning', line, f"key '{raw}' is binary, prefer hex (0x..)"))
        try:
            hash(key)
        except TypeError:
            loader.issues.append(('error', line, f'unhashable key {key!r}'))
            continue
        if key in seen:
            loader.issues.append(('error', line,
                                  f"duplicate key '{raw if raw is not None else key}' "
                                  f"(first defined line {seen[key]}), the first one is silently lost"))
        seen[key] = line
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml(path):
    """Returns (data, issues[(level, line, msg)])"""
    issues = []
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        issues.append(('error', raw[:e.start].count(b'\n') + 1, f'file is not valid UTF-8 ({e.reason} at byte {e.start})'))
        text = raw.decode('utf-8', errors='replace')
    if text.startswith('﻿'):
        issues.append(('warning', 1, 'file starts with a UTF-8 BOM'))
        text = text[1:]
    if '\t' in text:
        issues.append(('warning', text[:text.index('\t')].count('\n') + 1, 'tabulation found, use spaces'))
    try:
        loader = StrictLoader(text)
    except yaml.YAMLError as e:
        # non printable characters are refused before parsing
        pos = getattr(e, 'position', 0) or 0
        issues.append(('error', text[:pos].count('\n') + 1, f'YAML: {e}'))
        return None, issues
    loader.issues = issues
    try:
        data = loader.get_single_data()
    except yaml.YAMLError as e:
        issues.append(('error', getattr(getattr(e, 'problem_mark', None), 'line', -1) + 1, f'YAML syntax: {e}'))
        data = None
    finally:
        loader.dispose()
    return data, issues


def to_json_compatible(obj):
    """Convert YAML data (int keys, dates...) to what JSON schema expects"""
    if isinstance(obj, dict):
        return {str(k): to_json_compatible(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json_compatible(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

class Report:
    def __init__(self, root):
        self.root = root
        self.items = []

    def add(self, level, path, msg, line=None, where=None):
        self.items.append({
            'level': level,
            'file': os.path.relpath(path, self.root) if path else '',
            'line': line,
            'where': where,
            'message': msg,
        })

    def error(self, path, msg, **kw):
        self.add('error', path, msg, **kw)

    def warn(self, path, msg, **kw):
        self.add('warning', path, msg, **kw)

    def count(self, level):
        return sum(1 for i in self.items if i['level'] == level)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def parse_bits(bits, length=None):
    """Returns a list of absolute bit indexes (byte0*8 + (7-bit)) in transmission
    order, or None if invalid. 'n' ranges extend to length (or 1 byte)."""
    m = BITS_RE.match(str(bits))
    if not m:
        return None
    sbyte, sbit = int(m.group(1)), int(m.group(2))
    start = (sbyte - 1) * 8 + (7 - sbit)
    if m.group(5):  # '-n'
        end = (length * 8 - 1) if length else start + 7
        end = max(end, start)
    elif m.group(3):
        ebyte, ebit = int(m.group(3)), int(m.group(4))
        end = (ebyte - 1) * 8 + (7 - ebit)
    else:
        end = start
    if end < start:
        return None
    return list(range(start, end + 1))


def iter_langs(obj):
    if isinstance(obj, dict):
        return set(k for k in obj.keys() if isinstance(k, str) and re.fullmatch(r'[a-z]{2}(-[A-Z]{2})?', k))
    return set()


class LangStats:
    def __init__(self):
        self.total = 0
        self.per_lang = defaultdict(int)

    def add(self, ml):
        if not isinstance(ml, dict):
            return
        self.total += 1
        for lang in iter_langs(ml):
            self.per_lang[lang] += 1


# --------------------------------------------------------------------------
# Validator
# --------------------------------------------------------------------------

class Validator:
    def __init__(self, root, only=None, check_langs=True):
        self.root = os.path.abspath(root)
        self.only = only
        self.report = Report(self.root)
        self.check_langs = check_langs
        self.langs = LangStats()
        schema_path = os.path.join(self.root, SCHEMA_REL)
        if not os.path.isfile(schema_path):
            # Allow validating a data repository using the schema of this tool's repository
            schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', SCHEMA_REL)
        with open(schema_path, encoding='utf-8') as f:
            self.bundle = json.load(f)
        self.validators = {}
        self.archs = {}
        self.nodes = {}       # 'AEE2004.full' -> {node: data}
        self.frames_by_bus = defaultdict(list)

    # ---- schema ----
    def schema_validator(self, kind):
        if kind not in self.validators:
            schema = {'$ref': f'#/definitions/{kind}', 'definitions': self.bundle['definitions']}
            self.validators[kind] = jsonschema.Draft7Validator(schema)
        return self.validators[kind]

    def check_schema(self, kind, data, path):
        v = self.schema_validator(kind)
        for err in sorted(v.iter_errors(to_json_compatible(data)), key=lambda e: list(e.absolute_path)):
            where = '/'.join(str(p) for p in err.absolute_path) or '(root)'
            msg = err.message
            if len(msg) > 300:
                msg = msg[:300] + '...'
            self.report.error(path, f'schema: {msg}', where=where)

    def load(self, path):
        data, issues = load_yaml(path)
        for level, line, msg in issues:
            self.report.add(level, path, msg, line=line)
        return data

    def wanted(self, path):
        return self.only is None or self.only in os.path.relpath(path, self.root)

    # ---- multilang walk ----
    def walk_multilang(self, obj, path, where):
        """Checks every multilang dict found (comment, name, display_name...)"""
        ml_keys = ('comment', 'observations', 'name', 'display_name', 'note', 'clues')
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ml_keys and isinstance(v, dict) and iter_langs(v):
                    self.langs.add(v)
                    if self.check_langs:
                        for lang in RECOMMENDED_LANGS:
                            if lang not in v:
                                self.report.warn(path, f"missing '{lang}' translation", where=f'{where}/{k}')
                elif k == 'values' and isinstance(v, dict):
                    for raw, entry in v.items():
                        if isinstance(entry, dict) and iter_langs(entry):
                            self.langs.add(entry)
                            if self.check_langs and 'fr' not in entry and not entry.get('unused'):
                                self.report.warn(path, "missing 'fr' translation", where=f'{where}/values/{raw}')
                else:
                    self.walk_multilang(v, path, f'{where}/{k}')
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                self.walk_multilang(v, path, f'{where}/{i}')

    # ---- architectures ----
    def load_architectures(self):
        path = os.path.join(self.root, 'architectures.yml')
        if not os.path.isfile(path):
            self.report.error(path, 'architectures.yml not found')
            return
        data = self.load(path)
        if data is None:
            return
        self.check_schema('architectures', data, path)
        self.walk_multilang(data, path, '')
        if isinstance(data, dict):
            for arch, variants in data.items():
                if not isinstance(variants, dict):
                    continue
                for variant, vdata in variants.items():
                    if isinstance(vdata, dict):
                        self.archs[f'{arch}.{variant}'] = vdata
                        parent = vdata.get('parent')
                        if parent and parent not in variants:
                            self.report.error(path, f"parent variant '{parent}' not found", where=f'{arch}/{variant}')

    def arch_buses(self, archvar):
        """Returns {'NET.BUS': protocol} for an architecture variant, following parents"""
        out = {}
        seen = set()
        while archvar in self.archs and archvar not in seen:
            seen.add(archvar)
            v = self.archs[archvar]
            for net, buses in (v.get('networks') or {}).items():
                for bus, bdata in (buses or {}).items():
                    out.setdefault(f'{net}.{bus}', (bdata or {}).get('protocol'))
            parent = v.get('parent')
            if not parent:
                break
            archvar = archvar.split('.')[0] + '.' + parent
        return out

    def arch_nodes(self, archvar):
        """nodes of a variant and its parents; a node redefined in a variant keeps the buses of the parent's entry"""
        out = {}
        seen = set()
        while archvar and archvar not in seen:
            seen.add(archvar)
            for name, nd in (self.nodes.get(archvar) or {}).items():
                if not isinstance(nd, dict):
                    continue
                if name in out:
                    merged = dict(nd, **out[name])
                    merged['bus'] = list(dict.fromkeys((out[name].get('bus') or []) + (nd.get('bus') or [])))
                    out[name] = merged
                else:
                    out[name] = nd
            parent = (self.archs.get(archvar) or {}).get('parent')
            archvar = archvar.split('.')[0] + '.' + parent if parent else None
        return out

    # ---- nodes ----
    def load_nodes(self):
        ndir = os.path.join(self.root, 'nodes')
        if not os.path.isdir(ndir):
            return
        for fn in sorted(os.listdir(ndir)):
            if not fn.endswith('.yml'):
                continue
            path = os.path.join(ndir, fn)
            archvar = fn[:-4]
            data = self.load(path)
            if data is None:
                continue
            if archvar not in self.archs:
                self.report.error(path, f"architecture variant '{archvar}' not defined in architectures.yml")
            self.nodes[archvar] = data if isinstance(data, dict) else {}
            if not self.wanted(path):
                continue
            self.check_schema('nodes', data, path)
            self.walk_multilang(data, path, '')
            buses = self.arch_buses(archvar)
            nets = {b.split('.')[0] for b in buses}
            if isinstance(data, dict):
                for node, nd in data.items():
                    if not isinstance(nd, dict):
                        continue
                    for b in nd.get('bus') or []:
                        if buses and b not in buses:
                            self.report.error(path, f"bus '{b}' not defined in {archvar}", where=node)
                    for net in (nd.get('id') or {}):
                        if nets and net not in nets:
                            self.report.warn(path, f"id given for unknown network '{net}'", where=node)
                    for dep in ('diag_services', 'diag_sessions', 'diag_reset'):
                        if dep in nd:
                            self.report.warn(path, f"'{dep}' is deprecated, move it to diag/{archvar}/{node}/ecu.yml", where=node)

    # ---- cars ----
    def check_cars(self):
        cdir = os.path.join(self.root, 'cars')
        if not os.path.isdir(cdir):
            return
        all_codes = {}
        for fn in sorted(os.listdir(cdir)):
            if not fn.endswith('.yml'):
                continue
            path = os.path.join(cdir, fn)
            if not self.wanted(path):
                continue
            data = self.load(path)
            if data is None:
                continue
            self.check_schema('car', data, path)
            self.walk_multilang(data, path, '')
            if not isinstance(data, dict):
                continue
            for code in (data.get('codes') or {}):
                if code in all_codes:
                    self.report.warn(path, f"car code '{code}' also defined in {all_codes[code]}")
                all_codes[code] = fn
            for vname, v in (data.get('versions') or {}).items():
                if not isinstance(v, dict):
                    continue
                archvar = v.get('architecture')
                if archvar == 'none':
                    if v.get('nodes'):
                        self.report.warn(path, "a non multiplexed car ('none') should not list nodes", where=f'versions/{vname}')
                    continue
                if archvar not in self.archs:
                    self.report.error(path, f"architecture '{archvar}' not defined", where=f'versions/{vname}')
                    continue
                buses = self.arch_buses(archvar)
                nets = {b.split('.')[0] for b in buses}
                known = self.arch_nodes(archvar)
                for net, nlist in (v.get('nodes') or {}).items():
                    if net not in nets:
                        self.report.error(path, f"network '{net}' not defined in {archvar}", where=f'versions/{vname}/nodes')
                    for n in nlist or []:
                        if known and n not in known:
                            self.report.warn(path, f"node '{n}' not defined in nodes/{archvar}.yml", where=f'versions/{vname}/nodes/{net}')
                        elif known and net in nets:
                            nb = {b.split('.')[0] for b in known[n].get('bus', [])}
                            if net not in nb:
                                self.report.warn(path, f"node '{n}' is not on network '{net}' in nodes/{archvar}.yml", where=f'versions/{vname}/nodes/{net}')
                allnodes = {n for l in (v.get('nodes') or {}).values() for n in (l or [])}
                for n in v.get('optional_nodes') or []:
                    if n not in allnodes:
                        self.report.warn(path, f"optional node '{n}' is not listed in 'nodes'", where=f'versions/{vname}')
                year = int(archvar[3:7]) if re.match(r'AEE\d{4}', archvar) else 0
                if year >= 2004 and v.get('nodes'):
                    for must in ('CMM', 'BSI', 'BSM', 'HDC', 'CMB'):
                        if must == 'CMM' and archvar.endswith('.electric'):
                            continue  # no engine ECU on electric cars
                        if must not in allnodes:
                            self.report.warn(path, f"node '{must}' missing (expected on every {archvar.split('.')[0]} car)", where=f'versions/{vname}')

    # ---- frames ----
    def check_buses(self):
        bdir = os.path.join(self.root, 'buses')
        if not os.path.isdir(bdir):
            return
        for archvar in sorted(os.listdir(bdir)):
            apath = os.path.join(bdir, archvar)
            if not os.path.isdir(apath):
                continue
            if archvar not in self.archs:
                self.report.error(apath, f"directory name must be <arch>.<variant> defined in architectures.yml, got '{archvar}'")
            buses = self.arch_buses(archvar)
            for netbus in sorted(os.listdir(apath)):
                npath = os.path.join(apath, netbus)
                if not os.path.isdir(npath):
                    continue
                if buses and netbus not in buses:
                    self.report.error(npath, f"bus directory must be <network>.<bus> defined in {archvar}, got '{netbus}'")
                protocol = buses.get(netbus)
                for fn in sorted(os.listdir(npath)):
                    fpath = os.path.join(npath, fn)
                    if not fn.endswith('.yml'):
                        if not fn.lower().endswith(('.md', '.txt')):
                            self.report.warn(fpath, 'unexpected file in bus directory')
                        continue
                    if os.path.islink(fpath):
                        if not os.path.exists(fpath):
                            self.report.error(fpath, f'broken symlink to {os.readlink(fpath)}')
                            continue
                        if not self.wanted(fpath):
                            continue
                        # the target is validated at its own place, only check it matches the name
                        data, _ = load_yaml(fpath)
                        if isinstance(data, dict):
                            self.check_frame_filename(fpath, fn, data)
                            self.frames_by_bus[(archvar, netbus)].append((fpath, data))
                        continue
                    if not self.wanted(fpath):
                        continue
                    self.check_frame(fpath, fn, archvar, netbus, protocol)

    def check_frame_filename(self, path, fn, data):
        m = FRAME_FILE_RE.match(fn)
        if not m:
            self.report.error(path, 'file name must be <ID in uppercase hex>.yml or <ID>_<SUFFIX>.yml')
            return
        fid = data.get('id')
        if isinstance(fid, int) and int(m.group(1), 16) != fid:
            self.report.error(path, f'file name ID 0x{m.group(1)} does not match id 0x{fid:X}')

    def check_frame(self, path, fn, archvar, netbus, protocol):
        data = self.load(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self.report.error(path, 'frame file must be a mapping')
            return
        self.check_schema('message', data, path)
        self.walk_multilang(data, path, '')
        self.check_frame_filename(path, fn, data)
        self.frames_by_bus[(archvar, netbus)].append((path, data))

        ftype = data.get('type')
        expect = {'CAN': ('can', 'can-tp'), 'CAN-FD': ('can', 'can-tp'), 'VAN': ('van',), 'LIN': ('lin',)}.get(protocol)
        if expect and ftype not in expect:
            self.report.error(path, f"frame type '{ftype}' does not match bus protocol {protocol}")
        fid = data.get('id')
        if ftype == 'can' and isinstance(fid, int) and fid > 0x7FF and not data.get('extended'):
            self.report.error(path, f'id 0x{fid:X} needs 29 bits, set extended: true')

        known_nodes = self.arch_nodes(archvar)
        for key in ('senders', 'receivers'):
            for n in data.get(key) or []:
                if known_nodes and n not in known_nodes:
                    self.report.warn(path, f"{key[:-1]} '{n}' not defined in nodes/{archvar}.yml", where=key)
        if not data.get('senders'):
            self.report.warn(path, 'no senders')

        self.check_signals(path, data.get('signals') or {}, data.get('length'), ftype, 'signals')
        for i, alt in enumerate(data.get('alternatives') or []):
            if isinstance(alt, dict) and 'signals' in alt:
                self.check_signals(path, alt['signals'] or {}, alt.get('length', data.get('length')), ftype, f'alternatives/{i}/signals')

    def check_signals(self, path, signals, length, ftype, where):
        if not isinstance(signals, dict):
            return
        variable = ftype == 'can-tp'
        occupancy = defaultdict(list)  # bit -> [(signal, muxkey)]
        selectors = {n for n, s in signals.items() if isinstance(s, dict) and s.get('mux_selector')}
        for name, sig in signals.items():
            if not isinstance(sig, dict):
                continue
            w = f'{where}/{name}'
            bits = parse_bits(sig.get('bits', ''), length)
            if bits is None:
                if 'bits' in sig and BITS_RE.match(str(sig['bits'])):
                    self.report.error(path, f"bits '{sig['bits']}' end before they start (ranges are <start>-<end> in transmission order, eg. 1.7-2.0)", where=w)
                continue
            width = len(bits)
            if length is not None and not variable and bits[-1] >= length * 8:
                self.report.error(path, f"bits '{sig['bits']}' outside of the {length} bytes frame", where=w)
            # multiplexing
            mux = sig.get('mux')
            muxkey = None
            if isinstance(mux, dict):
                if mux.get('selector') not in selectors:
                    self.report.error(path, f"mux selector '{mux.get('selector')}' is not a signal with mux_selector: true", where=w)
                muxkey = (mux.get('selector'), tuple(mux.get('values') or []))
            for b in bits:
                occupancy[b].append((name, muxkey))
            # types / values
            stype = sig.get('type')
            if stype in DEPRECATED_TYPES:
                self.report.warn(path, f"type '{stype}' is deprecated, use uint/sint", where=w)
            if 'signed' in sig:
                self.report.warn(path, "'signed' is deprecated, use type: sint", where=w)
            if 'resolution' in sig:
                self.report.warn(path, "'resolution' is deprecated, use factor", where=w)
            if stype == 'bool' and width != 1:
                self.report.error(path, f'bool signal must be 1 bit wide, got {width}', where=w)
            values = sig.get('values')
            if isinstance(values, dict) and width < 64:
                for raw in values:
                    if isinstance(raw, int) and raw >= (1 << width):
                        self.report.error(path, f'value 0x{raw:X} does not fit in {width} bit(s)', where=f'{w}/values')
            for k in ('invalid', 'default'):
                v = sig.get(k)
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if isinstance(x, int) and width < 64 and x >= (1 << width):
                        self.report.error(path, f'{k} 0x{x:X} does not fit in {width} bit(s)', where=w)
            if isinstance(sig.get('min'), (int, float)) and isinstance(sig.get('max'), (int, float)) and sig['min'] > sig['max']:
                self.report.error(path, 'min > max', where=w)
            if sig.get('unused') and (values or sig.get('comment')):
                pass  # documented reserved bits are fine
        # overlaps
        reported = set()
        for b, users in occupancy.items():
            if len(users) < 2:
                continue
            for i in range(len(users)):
                for j in range(i + 1, len(users)):
                    (n1, m1), (n2, m2) = users[i], users[j]
                    if m1 and m2 and m1[0] == m2[0] and not set(m1[1]) & set(m2[1]):
                        continue  # exclusive multiplexed signals
                    pair = tuple(sorted((n1, n2)))
                    if pair not in reported:
                        reported.add(pair)
                        self.report.error(path, f"signals '{n1}' and '{n2}' overlap (byte {b // 8 + 1} bit {7 - b % 8})", where=where)

    def check_bus_uniqueness(self):
        for (archvar, netbus), frames in self.frames_by_bus.items():
            by_name = defaultdict(list)
            by_id = defaultdict(list)
            for path, data in frames:
                if isinstance(data.get('name'), str):
                    by_name[data['name']].append(path)
                if isinstance(data.get('id'), int):
                    by_id[data['id']].append(path)
            for name, paths in by_name.items():
                if len(paths) > 1:
                    for p in paths:
                        self.report.warn(p, f"frame name '{name}' used by {len(paths)} frames on {archvar}/{netbus}")
            for fid, paths in by_id.items():
                if len(paths) > 1 and not any('_' in os.path.basename(p) for p in paths):
                    for p in paths:
                        self.report.error(p, f'id 0x{fid:X} defined by {len(paths)} files, use <ID>_<SUFFIX>.yml names')

    # ---- diag ----
    def check_diag(self):
        ddir = os.path.join(self.root, 'diag')
        if not os.path.isdir(ddir):
            return
        ecu_variants = {}   # directory -> set of variant ids of its ecu.yml
        used_variants = []  # (path, directory, [variant ids or PREFIX_* patterns])
        for dirpath, dirnames, filenames in os.walk(ddir):
            dirnames.sort()
            for fn in sorted(filenames):
                path = os.path.join(dirpath, fn)
                if not fn.endswith('.yml') or not self.wanted(path):
                    continue
                rel = os.path.relpath(path, ddir).split(os.sep)
                if rel[0] == 'protocols':
                    kind = 'diag_protocol'
                elif fn == 'ecu.yml':
                    kind = 'diag_ecu'
                elif fn == 'dtcs.yml':
                    kind = 'diag_dtcs'
                elif len(rel) >= 2 and rel[-2] in ('dids', 'lids'):
                    kind = 'diag_data'
                elif len(rel) >= 2 and rel[-2] == 'routines':
                    kind = 'diag_routine'
                elif len(rel) >= 2 and rel[-2] == 'ioctls':
                    kind = 'diag_ioctl'
                else:
                    self.report.warn(path, 'unknown diag file, expected ecu.yml, dtcs.yml, dids/, lids/, routines/ or ioctls/')
                    continue
                data = self.load(path)
                if data is None:
                    continue
                self.check_schema(kind, data, path)
                self.walk_multilang(data, path, '')
                if isinstance(data, dict):
                    base = dirpath if kind in ('diag_ecu', 'diag_dtcs') else os.path.dirname(dirpath)
                    if kind == 'diag_ecu' and isinstance(data.get('variants'), dict):
                        ecu_variants[base] = set(data['variants'])
                    if kind in ('diag_data', 'diag_routine', 'diag_ioctl'):
                        vs = list(data.get('variants') or [])
                        for alt in data.get('alternatives') or []:
                            if isinstance(alt, dict):
                                vs += list(alt.get('variants') or [])
                        if vs:
                            used_variants.append((path, base, vs))
                if rel[0] != 'protocols':
                    archvar = rel[0]
                    if archvar not in self.archs:
                        self.report.error(path, f"'{archvar}' is not an architecture variant")
                    node = rel[1] if len(rel) > 2 else None
                    if node and self.arch_nodes(archvar) and node not in self.arch_nodes(archvar):
                        self.report.warn(path, f"node '{node}' not defined in nodes/{archvar}.yml")
                    if kind == 'diag_data' and isinstance(data, dict):
                        ident = data.get('did', data.get('lid'))
                        m = re.match(r'^([0-9A-F]+)(_[A-Z0-9_]+)?\.yml$', fn)
                        if not m or (isinstance(ident, int) and int(m.group(1), 16) != ident):
                            self.report.error(path, 'file name must be the identifier in uppercase hex')
                        if rel[-2] == 'dids' and 'did' not in data:
                            self.report.error(path, 'files in dids/ must define did')
                        if rel[-2] == 'lids' and 'lid' not in data:
                            self.report.error(path, 'files in lids/ must define lid')
                        if isinstance(data.get('params'), dict):
                            self.check_signals(path, data['params'], data.get('length'), 'can-tp', 'params')
                        for i, alt in enumerate(data.get('alternatives') or []):
                            if isinstance(alt, dict) and isinstance(alt.get('params'), dict):
                                self.check_signals(path, alt['params'], alt.get('length'), 'can-tp', f'alternatives/{i}/params')
        for path, base, vs in used_variants:
            known = ecu_variants.get(base)
            if known is None:
                continue  # free text sub-families, nothing to check against
            for v in vs:
                if not isinstance(v, str):
                    continue
                ok = any(k.startswith(v[:-1]) for k in known) if v.endswith('*') else v in known
                if not ok:
                    self.report.error(path, f"variant '{v}' is not defined in ecu.yml")

    def run(self):
        self.load_architectures()
        self.load_nodes()
        self.check_cars()
        self.check_buses()
        self.check_bus_uniqueness()
        self.check_diag()
        return self.report


def main():
    ap = argparse.ArgumentParser(description='Validate a DBMUXEv repository')
    ap.add_argument('root', nargs='?', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--strict', action='store_true', help='warnings are errors')
    ap.add_argument('--quiet', action='store_true', help='only print the summary')
    ap.add_argument('--no-warnings', action='store_true', help='do not print warnings')
    ap.add_argument('--no-lang-check', action='store_true', help='do not warn about missing fr translations')
    ap.add_argument('--json', action='store_true', help='JSON output')
    ap.add_argument('--langs', action='store_true', help='print translation coverage')
    ap.add_argument('--only', help='only check files whose path contains this string')
    args = ap.parse_args()

    v = Validator(args.root, only=args.only, check_langs=not args.no_lang_check)
    report = v.run()
    errors, warnings = report.count('error'), report.count('warning')

    if args.json:
        print(json.dumps({'errors': errors, 'warnings': warnings, 'items': report.items,
                          'languages': {'texts': v.langs.total, 'per_lang': dict(v.langs.per_lang)}}, indent=1))
    else:
        if not args.quiet:
            for it in report.items:
                if it['level'] == 'warning' and args.no_warnings:
                    continue
                loc = it['file'] + (f":{it['line']}" if it['line'] else '')
                where = f" [{it['where']}]" if it['where'] else ''
                print(f"{it['level'].upper():7} {loc}{where}: {it['message']}")
        if args.langs and v.langs.total:
            print(f'\nTranslation coverage ({v.langs.total} texts):')
            for lang in RECOMMENDED_LANGS + EXTRA_LANGS + sorted(set(v.langs.per_lang) - set(RECOMMENDED_LANGS + EXTRA_LANGS)):
                n = v.langs.per_lang.get(lang, 0)
                print(f'  {lang}: {n:7d} ({100.0 * n / v.langs.total:5.1f}%)')
        print(f'\n{errors} error(s), {warnings} warning(s)')

    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == '__main__':
    main()
