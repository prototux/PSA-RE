"""
YAML reading and writing in the DBMUXEv style.

Reading keeps integers written in hex as :class:`HexInt` (an ``int`` that
remembers it was hex and how many digits it had), so a file can be written
back without turning ``0x0F6`` into ``246``. :class:`Layout` records what a
YAML parser drops: the comments (file header, full lines and end of line),
blank lines and the style of the lists, by key path.

Writing replays the layout of the original file, so a file loaded then saved
unchanged is identical, and an edit only changes the lines it touches. New
documents get the repository style: 2 spaces indentation, single quoted
strings, flow style lists of scalars (``['BSI', 'CMM']``), hex integers,
literal blocks for multi-line texts and blank lines between signals.
"""
import json
import re

import yaml

try:  # libyaml is much faster on the ~5000 files of a full repository
    _BaseLoader = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    _BaseLoader = yaml.SafeLoader

__all__ = ['HexInt', 'hexint', 'load_file', 'loads', 'dumps', 'split_header', 'Layout']


class HexInt(int):
    """An integer written in hex (``0x1A``). ``digits`` is the minimum number of hex digits to write."""

    def __new__(cls, value, digits=None):
        obj = int.__new__(cls, value)
        obj.digits = digits
        return obj

    def __repr__(self):
        return f'0x{int(self):0{self.digits or 2}X}'

    def __reduce__(self):
        return HexInt, (int(self), self.digits)


def hexint(value, digits=2):
    """Marks an integer to be written in hex, keeping the digit count of a value read from a file"""
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        return value
    if isinstance(value, HexInt) and value.digits:
        return value
    return HexInt(value, digits)


class Loader(_BaseLoader):
    """Safe loader that keeps hex integers as HexInt"""


def _construct_int(loader, node):
    value = loader.construct_yaml_int(node)
    text = node.value.replace('_', '').lstrip('+-')
    if text[:2].lower() == '0x':
        return HexInt(value, len(text) - 2)
    return value


Loader.add_constructor('tag:yaml.org,2002:int', _construct_int)


def split_header(text):
    """Returns (header, body): the comment (and blank) lines at the top of a file, exactly as written, and the rest"""
    lines = text.splitlines(keepends=True)
    n = 0
    while n < len(lines) and (lines[n].lstrip().startswith('#') or not lines[n].strip()):
        n += 1
    header = ''.join(lines[:n])
    return (header if header.strip() else ''), ''.join(lines[n:])


def loads(text):
    return yaml.load(text, Loader=Loader)


def load_file(path):
    """Returns (data, header, layout)"""
    with open(path, encoding='utf-8-sig') as f:
        text = f.read()
    header, _ = split_header(text)
    return loads(text), header, Layout.parse(text)


# --------------------------------------------------------------------------
# Layout: what YAML parsers drop (comments, blank lines, list styles)
# --------------------------------------------------------------------------

_KEY_RE = re.compile(r"""^('(?:[^']|'')*'|"(?:[^"\\]|\\.)*"|[^\s'"#\[\]{},:-][^#:]*?|-[^\s#:][^#:]*?)\s*:(?:\s+(.*))?$""")
_ITEM_RE = re.compile(r'^-(?:\s+(.*))?$')


class _Entry:
    __slots__ = ('pre', 'inline', 'block', 'seq_indent')

    def __init__(self, pre):
        self.pre = pre          # comment and blank lines before the key / item, as written
        self.inline = None      # '  # comment' after the value
        self.block = False      # list written in block style
        self.seq_indent = 2     # indentation of the block list items relative to the key


def _split_comment(text):
    """(value, inline comment) of the end of a line, quotes aware"""
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                if quote == "'" and text[i + 1:i + 2] == "'":
                    i += 1
                else:
                    quote = None
            elif c == '\\' and quote == '"':
                i += 1
        elif c in '\'"' and (i == 0 or text[i - 1] in ' [,{:'):
            quote = c
        elif c == '#' and (i == 0 or text[i - 1] in ' \t'):
            j = i
            while j > 0 and text[j - 1] in ' \t':
                j -= 1
            # 'KEY: # comment': the spaces before '#' were taken by the key pattern, keep one
            return text[:j], text[j:] if j else ' ' + text
        i += 1
    return text, None


def _key_name(text):
    if text[:1] == "'":
        return text[1:-1].replace("''", "'")
    if text[:1] == '"':
        return json.loads(text)
    return text


class Layout:
    """Comments, blank lines and list styles of a YAML file, by key path ('signals', 'SPEED', 'values', '0x01')"""

    def __init__(self):
        self.entries = {}
        self.tail = []

    def get(self, path):
        return self.entries.get(path)

    def has_children(self, path):
        n = len(path)
        return any(len(p) == n + 1 and p[:n] == path for p in self.entries)

    def siblings_spaced(self, parent):
        """True if the entries of a mapping are separated by blank lines"""
        n = len(parent)
        kids = [e for p, e in self.entries.items() if len(p) == n + 1 and p[:n] == parent]
        return any('' in e.pre for e in kids[1:])

    @classmethod
    def parse(cls, text):
        layout = cls()
        _, body = split_header(text)
        stack = []             # (indent, path, is_item)
        counters = {}
        pending = []
        block_scalar = None    # indent of the key owning a literal/folded block
        flow_depth = 0
        for raw in body.splitlines():
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(' '))
            if block_scalar is not None:
                if not stripped or indent > block_scalar:
                    continue
                block_scalar = None
            if flow_depth > 0:  # inside a multi-line flow collection
                flow_depth += raw.count('[') + raw.count('{') - raw.count(']') - raw.count('}')
                continue
            if not stripped:
                pending.append('')
                continue
            if stripped.startswith('#'):
                pending.append(raw.rstrip())
                continue
            col, line = indent, stripped
            while True:
                item = _ITEM_RE.match(line)
                if item:
                    while stack and (stack[-1][0] > col or (stack[-1][0] == col and stack[-1][2])):
                        stack.pop()
                    parent = stack[-1][1] if stack else ()
                    pe = layout.entries.get(parent)
                    if pe is not None and not pe.block:
                        pe.block = True
                        pe.seq_indent = col - stack[-1][0]
                    idx = counters.get(parent, 0)
                    counters[parent] = idx + 1
                    path = parent + (idx,)
                    entry = layout.entries[path] = _Entry(pending)
                    pending = []
                    rest = item.group(1) or ''
                    stack.append((col, path, True))
                    if _KEY_RE.match(rest) and not rest.startswith(("'", '"')) or \
                            (rest[:1] in '\'"' and _KEY_RE.match(rest) and ':' in _split_comment(rest)[0][2:]):
                        col = col + (len(line) - len(rest))
                        line = rest
                        pending = []
                        continue
                    value, entry.inline = _split_comment(rest)
                    value = value.strip()
                    if value.startswith(('|', '>')):
                        block_scalar = col
                    elif value.startswith(('[', '{')):
                        flow_depth = max(0, value.count('[') + value.count('{') - value.count(']') - value.count('}'))
                    break
                key = _KEY_RE.match(line)
                if not key:
                    break  # continuation of a multi-line scalar
                while stack and stack[-1][0] >= col and not (stack[-1][2] and stack[-1][0] < col):
                    if stack[-1][2] and stack[-1][0] < col:
                        break
                    stack.pop()
                parent = stack[-1][1] if stack else ()
                path = parent + (_key_name(key.group(1)),)
                entry = layout.entries[path] = _Entry(pending)
                pending = []
                value, entry.inline = _split_comment(key.group(2) or '')
                value = value.strip()
                if value.startswith(('|', '>')):
                    block_scalar = col
                elif value.startswith(('[', '{')):
                    flow_depth = max(0, value.count('[') + value.count('{') - value.count(']') - value.count('}'))
                stack.append((col, path, False))
                break
        layout.tail = pending
        return layout


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

_PLAIN_KEY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')
_resolver = yaml.resolver.Resolver()

# keys whose mapping gets a blank line between its entries (new documents)
SPACED_KEYS = frozenset({'signals', 'params', 'results'})
# top level keys preceded by a blank line (new documents)
BLANK_BEFORE = frozenset({'signals', 'alternatives', 'params', 'results', 'return_values', 'versions',
                          'addressing', 'sessions', 'resets', 'services', 'security_access', 'tester_present',
                          'negative_responses', 'algorithms'})
FLOW_WIDTH = 120   # lists of scalars longer than this are written in block style


def _resolves_to_str(text):
    return _resolver.resolve(yaml.ScalarNode, text, (True, False)) == 'tag:yaml.org,2002:str'


def _format_float(v):
    if v != v:
        return '.nan'
    if v in (float('inf'), float('-inf')):
        return '.inf' if v > 0 else '-.inf'
    text = repr(v)
    if 'e' in text:
        mantissa, exp = text.split('e')
        if '.' not in mantissa:
            mantissa += '.0'  # YAML 1.1 (PyYAML) needs a dot to read 1e-05 as a float
        if exp[0] not in '+-':
            exp = '+' + exp
        text = f'{mantissa}e{exp}'
    return text


def _quote(s):
    if any(ord(c) < 0x20 and c not in '\n' or c in '\x7f﻿' for c in s):
        return json.dumps(s, ensure_ascii=False)
    return "'" + s.replace("'", "''") + "'"


def scalar(v):
    """YAML text of a scalar"""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, HexInt):
        return repr(v) if v >= 0 else str(int(v))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return _format_float(v)
    if isinstance(v, (bytes, bytearray)):
        return _quote(bytes(v).hex().upper())
    return _quote(str(v))


def key_text(k, quote=False):
    if isinstance(k, (int, float, bool)) or k is None:
        return scalar(k)
    k = str(k)
    if not quote and _PLAIN_KEY_RE.match(k) and _resolves_to_str(k):
        return k
    return _quote(k)


def _path_key(k):
    """Key as found in the layout of the original text"""
    if isinstance(k, (int, float, bool)) or k is None:
        return scalar(k)
    return str(k)


def _is_scalar(v):
    return not isinstance(v, (dict, list, tuple))


def _needs_block(v):
    return isinstance(v, str) and '\n' in v.rstrip('\n') and not any(
        ord(c) < 0x20 and c != '\n' for c in v) and not v.startswith((' ', '\t'))


class _Emitter:
    def __init__(self, layout=None, spaced_top=False, quote_keys=False):
        self.layout = layout
        self.spaced_top = spaced_top
        self.quote_keys = quote_keys
        self.lines = []

    def entry(self, path):
        return self.layout.get(path) if self.layout else None

    def known(self, path):
        return self.layout is not None and (path == () or path in self.layout.entries)

    def pre(self, path, first, default_blank):
        """Comment/blank lines before a key or item"""
        e = self.entry(path)
        if e is not None:
            pre = e.pre
            if first:
                while pre and pre[0] == '':
                    pre = pre[1:]
            self.lines.extend(pre)
        elif default_blank and not first and self.lines and self.lines[-1] != '':
            self.lines.append('')

    def inline(self, path):
        e = self.entry(path)
        return e.inline if e is not None and e.inline else ''

    def mapping(self, d, indent, path, spaced=False):
        parent_known = self.known(path)
        sibling_spaced = parent_known and self.layout.siblings_spaced(path)
        for i, (k, v) in enumerate(d.items()):
            kpath = path + (_path_key(k),)
            if parent_known:
                blank = (k in BLANK_BEFORE if not path else sibling_spaced) or (not path and self.spaced_top)
            else:
                blank = spaced or (not path and k in BLANK_BEFORE)
            self.pre(kpath, i == 0, blank)
            self.value(f'{key_text(k, self.quote_keys and not path)}:', v, indent, kpath)

    def value(self, prefix, v, indent, path):
        pad = ' ' * indent
        name = path[-1] if path else None
        if isinstance(v, dict):
            if not v:
                self.lines.append(f'{pad}{prefix} {{}}{self.inline(path)}')
                return
            self.lines.append(f'{pad}{prefix}{self.inline(path)}')
            self.mapping(v, indent + 2, path, spaced=name in SPACED_KEYS)
        elif isinstance(v, (list, tuple)):
            e = self.entry(path)
            flow = None
            if all(_is_scalar(x) and not _needs_block(x) for x in v):
                flow = f'{pad}{prefix} [' + ', '.join(scalar(x) for x in v) + ']'
                block = e.block if e is not None else len(flow) > FLOW_WIDTH
                if not v or not block:
                    self.lines.append(flow + self.inline(path))
                    return
            self.lines.append(f'{pad}{prefix}{self.inline(path)}')
            self.sequence(v, indent + (e.seq_indent if e is not None else 2), path)
        elif _needs_block(v):
            chomp = '' if v.endswith('\n') and not v.endswith('\n\n') else '-'
            body = v[:-1] if chomp == '' else v
            self.lines.append(f'{pad}{prefix} |{chomp}{self.inline(path)}')
            inner = ' ' * (indent + 2)
            self.lines.extend(inner + line if line else '' for line in body.split('\n'))
        else:
            self.lines.append(f'{pad}{prefix} {scalar(v)}{self.inline(path)}')

    def sequence(self, seq, indent, path):
        pad = ' ' * indent
        for i, item in enumerate(seq):
            ipath = path + (i,)
            self.pre(ipath, i == 0, False)
            if isinstance(item, dict) and item:
                start = len(self.lines)
                self.mapping(item, indent + 2, ipath)
                # first key on the '- ' line (after the comments of the first key, if any)
                j = next(n for n in range(start, len(self.lines)) if self.lines[n].startswith(' ' * (indent + 2))
                         and self.lines[n].strip() and not self.lines[n].lstrip().startswith('#'))
                self.lines[j] = pad + '- ' + self.lines[j][indent + 2:]
            elif isinstance(item, (list, tuple)) and item:
                start = len(self.lines)
                self.sequence(item, indent + 2, ipath)
                self.lines[start] = pad + '- ' + self.lines[start][indent + 2:]
            else:
                self.value('-', item, indent, ipath)


def dumps(data, header='', spaced_top=False, quote_keys=False, layout=None):
    """YAML text of a document.

    header: comment block written first (as is)
    spaced_top: blank line between the top level entries (nodes files)
    quote_keys: quote the top level keys (DTC codes)
    layout: Layout of the original text, to keep its comments, blank lines and list styles
    """
    em = _Emitter(layout, spaced_top, quote_keys)
    if isinstance(data, dict):
        em.mapping(data, 0, ())
    elif isinstance(data, (list, tuple)):
        em.sequence(data, 0, ())
    else:
        em.lines.append(scalar(data))
    if layout is not None and layout.tail:
        em.lines.extend(layout.tail)
    text = '\n'.join(em.lines).rstrip('\n') + '\n'
    if header:
        text = header + ('' if header.endswith('\n\n') or layout is not None else
                         '\n' if header.endswith('\n') else '\n\n') + text
    return text
