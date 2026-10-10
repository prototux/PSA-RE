"""
Base classes of the document objects.

Every object is a dataclass loaded from / saved to a YAML mapping. The
fields a schema defines are attributes; anything else is kept in ``extra``
so loading then saving a file never loses data. Keys explicitly set to
``null`` stay ``null``, and the original key order is kept.
"""
import copy
import os
from dataclasses import dataclass, field

from . import _yaml
from .multilang import MultiLang

__all__ = ['Model', 'Document', 'Field', 'ml_in', 'ml_out', 'hex_out', 'list_in']


class Field:
    """Maps a YAML key to an attribute. ``load``/``dump`` convert the value (None = as is)"""
    __slots__ = ('key', 'attr', 'load', 'dump')

    def __init__(self, key, attr=None, load=None, dump=None):
        self.key = key
        self.attr = attr or key.replace('-', '_')
        self.load = load
        self.dump = dump


def ml_in(v):
    return MultiLang.of(v)


def ml_out(v):
    return dict(v)


def hex_out(digits=2):
    def dump(v):
        if isinstance(v, (list, tuple)):
            return [_yaml.hexint(x, digits) for x in v]
        return _yaml.hexint(v, digits)
    return dump


def list_in(v):
    return list(v) if isinstance(v, (list, tuple)) else [v]


@dataclass
class Model:
    """Base of every object read from a YAML mapping"""
    extra: dict = field(default_factory=dict, repr=False, compare=False, kw_only=True)
    _order: list = field(default_factory=list, repr=False, compare=False, kw_only=True)
    _nulls: set = field(default_factory=set, repr=False, compare=False, kw_only=True)

    FIELDS = ()

    @classmethod
    def from_dict(cls, data, **kwargs):
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise TypeError(f'{cls.__name__}: expected a mapping, got {type(data).__name__}')
        data = dict(data)
        order = list(data)
        loaded = {}
        nulls = set()
        for f in cls.FIELDS:
            if f.key not in data:
                continue
            v = data.pop(f.key)
            if v is None:
                nulls.add(f.key)
                continue
            loaded[f.attr] = f.load(v) if f.load else v
        loaded.update(kwargs)
        obj = cls(**loaded)
        obj.extra = data
        obj._order = order
        obj._nulls = nulls
        return obj

    def to_dict(self):
        out = {}
        for f in self.FIELDS:
            v = getattr(self, f.attr, None)
            if v is None:
                if f.key in self._nulls:
                    out[f.key] = None
                continue
            out[f.key] = f.dump(v) if f.dump else v
        out.update(self.extra)
        return _reorder(out, self._order)

    def copy(self):
        """Deep copy (the Database the object is attached to is shared, not copied)"""
        memo = {}
        db = getattr(self, '_db', None)
        if db is not None:
            memo[id(db)] = db
        return copy.deepcopy(self, memo)

    def set(self, **kwargs):
        """Sets several attributes, returns self"""
        for k, v in kwargs.items():
            if not hasattr(self, k):
                raise AttributeError(f'{type(self).__name__} has no attribute {k!r}')
            setattr(self, k, v)
        return self


def _reorder(out, order):
    """Keeps the keys of the original file in their original order, new keys after the canonical previous one"""
    if not order:
        return out
    keys = [k for k in order if k in out]
    canonical = list(out)
    for i, k in enumerate(canonical):
        if k in keys:
            continue
        prev = next((p for p in reversed(canonical[:i]) if p in keys), None)
        keys.insert(keys.index(prev) + 1 if prev is not None else 0, k)
    return {k: out[k] for k in keys}


class Document:
    """Mixin of the objects stored in their own file"""
    SPACED_TOP = False
    QUOTE_KEYS = False

    path = None
    header = ''

    _layout = None

    def to_yaml(self):
        return _yaml.dumps(self.to_dict(), header=self.header or '', spaced_top=self.SPACED_TOP,
                           quote_keys=self.QUOTE_KEYS, layout=self._layout)

    def save(self, path=None):
        """Writes the file (to ``path``, or where it was loaded from). Returns the path"""
        path = path or self.path
        if not path:
            raise ValueError(f'{type(self).__name__}: no path to save to')
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        text = self.to_yaml()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        self.path = path
        self._source = text
        return path

    @property
    def is_modified(self):
        """True if the object differs from the file it was loaded from; an object that was not loaded from a file
        is modified once it has content"""
        source = getattr(self, '_source', None)
        if source is None:
            return bool(self.to_dict())
        return source != self.to_yaml()

    @classmethod
    def load(cls, path, **kwargs):
        with open(path, encoding='utf-8-sig') as f:
            text = f.read()
        header, _ = _yaml.split_header(text)
        obj = cls.from_dict(_yaml.loads(text), **kwargs)
        obj.path = path
        obj.header = header
        obj._layout = _yaml.Layout.parse(text)
        obj._source = text
        return obj
