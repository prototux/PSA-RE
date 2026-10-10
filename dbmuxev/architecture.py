"""
Architectures (``architectures.yml``), nodes (``nodes/<arch>.<variant>.yml``) and cars (``cars/<project>.yml``)
"""
import re
from dataclasses import dataclass, field

from .model import Document, Field, Model, hex_out, list_in, ml_in, ml_out

__all__ = ['Bus', 'Variant', 'Architectures', 'Node', 'NodeDiag', 'NodeSet', 'Car', 'CarVersion', 'parse_years']

YEARS_RE = re.compile(r'^(\d{4})(?:-(\d{4})?)?$')


def parse_years(text):
    """'2004-2018' -> (2004, 2018), '2013-' -> (2013, None), '2010' -> (2010, 2010), None -> (None, None)"""
    if not text:
        return None, None
    m = YEARS_RE.match(str(text).strip())
    if not m:
        raise ValueError(f'invalid years {text!r}')
    start = int(m.group(1))
    if m.group(2):
        return start, int(m.group(2))
    return start, (None if '-' in str(text) else start)


def _in_years(text, year):
    start, end = parse_years(text)
    return start is None or (start <= year and (end is None or year <= end))


# --------------------------------------------------------------------------
# Architectures
# --------------------------------------------------------------------------

@dataclass
class Bus(Model):
    """A bus of a network: ``network`` 'HS' + ``name`` 'IS' is referenced as 'HS.IS'"""
    network: str = ''
    name: str = ''
    protocol: str = 'CAN'
    bitrate: float = None   # kbit/s
    display_name: object = None
    comment: object = None

    FIELDS = (
        Field('protocol'),
        Field('bitrate'),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
    )

    @property
    def full_name(self):
        return f'{self.network}.{self.name}'

    def __str__(self):
        return self.full_name


def _networks_in(d):
    return {net: {b: Bus.from_dict(bd, network=net, name=b) for b, bd in (buses or {}).items()}
            for net, buses in (d or {}).items()}


def _networks_out(nets):
    return {net: {b: bus.to_dict() for b, bus in buses.items()} for net, buses in nets.items()}


@dataclass
class Variant(Model):
    """An architecture variant, eg. AEE2004.full. A variant with a ``parent`` inherits its networks,
    nodes and frames (see Database for the merged views)"""
    arch: str = ''
    name: str = ''
    comment: object = None
    display_name: object = None
    parent: str = None
    years: str = None
    status: str = None
    networks: dict = None   # {network: {bus: Bus}}
    protocols: list = None

    FIELDS = (
        Field('comment', load=ml_in, dump=ml_out),
        Field('display_name', load=ml_in, dump=ml_out),
        Field('parent'),
        Field('years'),
        Field('status'),
        Field('networks', load=_networks_in, dump=_networks_out),
        Field('protocols', load=list_in),
    )

    @property
    def full_name(self):
        return f'{self.arch}.{self.name}'

    @property
    def parent_name(self):
        return f'{self.arch}.{self.parent}' if self.parent else None

    def own_buses(self):
        """{'HS.IS': Bus} defined by this variant (not the inherited ones)"""
        return {f'{net}.{b}': bus for net, buses in (self.networks or {}).items() for b, bus in buses.items()}

    # ---- views, for a variant obtained from a Database ----
    _db = None

    @property
    def db(self):
        if self._db is None:
            raise RuntimeError(f'{self.full_name} is not attached to a Database')
        return self._db

    def __getitem__(self, bus):
        """BusView of one of the variant's buses: ``db['AEE2004.full']['HS.IS']``"""
        return self.db.bus(self, bus)

    def buses(self):
        """{'HS.IS': Bus} with the inherited buses"""
        return self.db.buses(self)

    def bus_views(self):
        """{'HS.IS': BusView} of every bus defined or having frames"""
        names = dict.fromkeys(list(self.db.buses(self)) + self.db.frame_buses(self))
        return {b: self.db.bus(self, b) for b in names}

    def nodes(self, inherited=True):
        return self.db.nodes(self, inherited)

    def node(self, name):
        return self.db.node(self, name)

    def chain(self):
        return self.db.chain(self)

    def diag(self, node):
        return self.db.diag(self, node)

    def cars(self):
        return list(self.db.find_cars(architecture=self.full_name))

    def add_bus(self, network, name, protocol='CAN', bitrate=None, **kwargs):
        bus = Bus(network=network, name=name, protocol=protocol, bitrate=bitrate, **kwargs)
        self.networks = self.networks or {}
        self.networks.setdefault(network, {})[name] = bus
        return bus

    def __str__(self):
        return self.full_name


class Architectures(Document):
    """``architectures.yml``: {arch: {variant: Variant}}"""

    def __init__(self, archs=None):
        self.archs = archs or {}
        self.path = None
        self.header = ''

    @classmethod
    def from_dict(cls, data, **kwargs):
        archs = {}
        for arch, variants in (data or {}).items():
            archs[arch] = {v: Variant.from_dict(vd, arch=arch, name=v) for v, vd in (variants or {}).items()}
        return cls(archs)

    def to_dict(self):
        return {arch: {v: var.to_dict() for v, var in variants.items()} for arch, variants in self.archs.items()}

    def variants(self):
        """{'AEE2004.full': Variant}"""
        return {var.full_name: var for variants in self.archs.values() for var in variants.values()}

    def add_variant(self, arch, name, comment, **kwargs):
        from .multilang import MultiLang
        var = Variant(arch=arch, name=name, comment=MultiLang.of(comment), **kwargs)
        self.archs.setdefault(arch, {})[name] = var
        return var


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------

@dataclass
class NodeDiag(Model):
    """Short diagnostic addressing summary of a node (details in diag/<arch>.<variant>/<node>/ecu.yml)"""
    protocols: list = None
    bus: str = None
    request_id: int = None
    response_id: int = None
    kline_address: int = None
    obd_request_id: int = None
    obd_response_id: int = None

    FIELDS = (
        Field('protocols', load=list_in),
        Field('bus'),
        Field('request_id', dump=hex_out(3)),
        Field('response_id', dump=hex_out(3)),
        Field('obd_request_id', dump=hex_out(3)),
        Field('obd_response_id', dump=hex_out(3)),
        Field('kline_address', dump=hex_out()),
    )


@dataclass
class Node(Model):
    """A node (ECU). ``name`` is its identifier (BSI, CMM...); the translated description
    (the 'name' key of the file) is ``display_name``"""
    name: str = ''
    bus: list = field(default_factory=list)   # ['HS.IS', 'LS.CONF']
    id: dict = None                           # unit code per network {'HS': 0x12, 'LS': 0x12}
    alt: list = None
    display_name: object = None
    comment: object = None
    released: bool = None
    diag: NodeDiag = None

    FIELDS = (
        Field('bus', load=list_in),
        Field('id', dump=lambda d: {k: hex_out()(v) for k, v in d.items()}),
        Field('alt', load=list_in),
        Field('name', 'display_name', load=ml_in, dump=ml_out),
        Field('comment', load=ml_in, dump=ml_out),
        Field('released'),
        Field('diag', load=NodeDiag.from_dict, dump=lambda d: d.to_dict()),
    )

    @property
    def networks(self):
        return list(dict.fromkeys(b.split('.')[0] for b in self.bus))

    def on_bus(self, bus):
        return bus in self.bus

    def on_network(self, network):
        return network in self.networks

    def unit_code(self, network):
        return (self.id or {}).get(network)

    def matches(self, name):
        """True if ``name`` is the node name or one of its other names (case insensitive)"""
        n = name.casefold()
        return n == self.name.casefold() or any(n == a.casefold() for a in (self.alt or []))

    def __str__(self):
        return self.name


class NodeSet(Document, dict):
    """``nodes/<arch>.<variant>.yml``: {name: Node}"""
    SPACED_TOP = True

    def __init__(self, nodes=None, variant=None):
        dict.__init__(self, nodes or {})
        self.variant = variant
        self.path = None
        self.header = ''

    @classmethod
    def from_dict(cls, data, variant=None):
        return cls({n: Node.from_dict(nd, name=n) for n, nd in (data or {}).items()}, variant=variant)

    def to_dict(self):
        return {n: node.to_dict() for n, node in self.items()}

    def add(self, name, bus, display_name=None, **kwargs):
        from .multilang import MultiLang
        node = Node(name=name, bus=list_in(bus), display_name=MultiLang.of(display_name), **kwargs)
        self[name] = node
        return node

    def find(self, name):
        """Node by name or other name (alt), case insensitive"""
        if name in self:
            return self[name]
        for node in self.values():
            if node.matches(name):
                return node
        return None

    def __repr__(self):
        return f'<NodeSet {self.variant}: {len(self)} nodes>'


def merge_nodes(nodesets):
    """Merges node sets, the first one wins; a node redefined keeps the buses of the others"""
    out = {}
    for nodes in nodesets:
        for name, nd in nodes.items():
            if name not in out:
                out[name] = nd
            else:
                merged = out[name].copy()
                merged.bus = list(dict.fromkeys(merged.bus + nd.bus))
                for attr in ('id', 'alt', 'display_name', 'comment', 'released', 'diag'):
                    if getattr(merged, attr) is None:
                        setattr(merged, attr, getattr(nd, attr))
                out[name] = merged
    return out


# --------------------------------------------------------------------------
# Cars
# --------------------------------------------------------------------------

@dataclass
class CarVersion(Model):
    """One architecture generation of a car project"""
    name: str = ''
    architecture: str = 'none'
    years: str = None
    codes: list = None
    comment: object = None
    nodes: dict = None            # {network: [node, ...]}
    optional_nodes: list = None

    FIELDS = (
        Field('architecture'),
        Field('years'),
        Field('codes', load=list_in),
        Field('comment', load=ml_in, dump=ml_out),
        Field('nodes', load=lambda d: {k: list_in(v or []) for k, v in d.items()}),
        Field('optional_nodes', load=list_in),
    )

    @property
    def is_multiplexed(self):
        return self.architecture != 'none'

    @property
    def all_nodes(self):
        """Every node fitted (mandatory and optional), without duplicates"""
        return list(dict.fromkeys(n for nodes in (self.nodes or {}).values() for n in nodes))

    @property
    def mandatory_nodes(self):
        optional = set(self.optional_nodes or [])
        return [n for n in self.all_nodes if n not in optional]

    def has_node(self, name):
        return name in self.all_nodes

    def in_years(self, year):
        return _in_years(self.years, year)


def _codes_in(d):
    return {code: v for code, v in (d or {}).items()}


@dataclass
class Car(Model, Document):
    """A car project (``cars/<project>.yml``). ``project`` is the file name"""
    project: str = ''
    codes: dict = field(default_factory=dict)   # code -> name or [names]
    brand: list = None
    names: list = None
    platform: str = None
    years: str = None
    comment: object = None
    versions: dict = field(default_factory=dict)

    FIELDS = (
        Field('codes', load=_codes_in),
        Field('brand', load=list_in),
        Field('names', load=list_in),
        Field('platform'),
        Field('years'),
        Field('comment', load=ml_in, dump=ml_out),
        Field('versions', load=lambda d: {k: CarVersion.from_dict(v, name=k) for k, v in d.items()},
              dump=lambda d: {k: v.to_dict() for k, v in d.items()}),
    )

    def __repr__(self):
        return f'<Car {self.project} {list(self.codes)}>'

    def names_of(self, code):
        """Commercial names of a project/silhouette code"""
        v = self.codes.get(code)
        return [] if v is None else list_in(v)

    @property
    def all_names(self):
        out = [n for c in self.codes for n in self.names_of(c)] + list(self.names or [])
        return list(dict.fromkeys(out))

    @property
    def architectures(self):
        return list(dict.fromkeys(v.architecture for v in self.versions.values()))

    def versions_for(self, code=None, year=None, architecture=None):
        """Versions matching a code, a production year and/or an architecture variant"""
        out = []
        for v in self.versions.values():
            if code is not None and v.codes and code not in v.codes:
                continue
            if year is not None and not v.in_years(year):
                continue
            if architecture is not None and v.architecture != architecture:
                continue
            out.append(v)
        return out

    def add_version(self, name, architecture, **kwargs):
        v = CarVersion(name=name, architecture=architecture, **kwargs)
        self.versions[name] = v
        return v
