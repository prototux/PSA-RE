"""
A DBMUXEv repository: architectures, nodes, frames, cars and diagnostics,
with the variant inheritance (``parent``) resolved.

    >>> db = Database('path/to/PSA-RE')
    >>> bus = db['AEE2004.full']['LS.CONF']
    >>> frame = bus.frame(0x0F6)
    >>> print(frame.decode(bytes.fromhex('8E7F00000000A001')))

Files are loaded on first access. Objects keep the path they were loaded
from and can be saved back; :meth:`Database.save_all` writes every loaded
object that changed.
"""
import os
import re

from .architecture import Architectures, Car, NodeSet, Variant, merge_nodes
from .diag import DiagProtocol, EcuDiag
from .message import FRAME_FILE_RE, Message

__all__ = ['Database', 'BusView', 'find_root']

PROTOCOL_FRAME_TYPES = {'CAN': ('can', 'can-tp'), 'CAN-FD': ('can', 'can-tp'), 'VAN': ('van',), 'LIN': ('lin',)}


def is_repository(path):
    """True for a directory with an architectures.yml and data (not the commented examples of dbmuxev/doc/)"""
    return os.path.isfile(os.path.join(path, 'architectures.yml')) and \
        any(os.path.isdir(os.path.join(path, d)) for d in ('buses', 'nodes', 'cars'))


def find_root(root=None):
    """Repository root: ``root``, else the current directory or the directory containing this package
    (or one of their parents) holding an architectures.yml and data directories"""
    if root is not None:
        return os.path.abspath(root)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for start in (os.getcwd(), here):
        d = start
        while True:
            if is_repository(d):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    raise FileNotFoundError('no DBMUXEv repository (architectures.yml) found, give the root directory')


class BusView:
    """A bus as seen from an architecture variant: its definition and its frames, inherited ones included"""

    def __init__(self, db, variant, name):
        self.db = db
        self.variant = variant
        self.name = name

    def __repr__(self):
        return f'<BusView {self.variant.full_name}/{self.name}>'

    @property
    def definition(self):
        """Bus (protocol, bitrate...) from architectures.yml"""
        return self.db.buses(self.variant).get(self.name)

    @property
    def protocol(self):
        d = self.definition
        return d.protocol if d else None

    @property
    def bitrate(self):
        d = self.definition
        return d.bitrate if d else None

    @property
    def network(self):
        return self.name.split('.')[0]

    @property
    def frames(self):
        """{file key: Message}, own frames override the parent variant ones"""
        return self.db.frames(self.variant, self.name)

    @property
    def own_frames(self):
        return self.db.frames(self.variant, self.name, inherited=False)

    def __iter__(self):
        return iter(sorted(self.frames.values(), key=lambda m: (m.id, m.key)))

    def __len__(self):
        return len(self.frames)

    def __getitem__(self, ident):
        return self.frame(ident)

    def __contains__(self, ident):
        try:
            self.frame(ident)
            return True
        except KeyError:
            return False

    def frames_by_id(self, frame_id):
        """Frames sharing an ID (several files <ID>_<SUFFIX>.yml), the one without suffix first"""
        out = [m for m in self.frames.values() if m.id == frame_id]
        return sorted(out, key=lambda m: (m.suffix is not None, m.key))

    def frame(self, ident):
        """Frame by ID (int), file key ('0F6', '8EC_CD_CHANGER_COMMAND_TRACK'), name or alternative name"""
        frames = self.frames
        if isinstance(ident, int):
            found = self.frames_by_id(ident)
            if found:
                return found[0]
        else:
            if ident in frames:
                return frames[ident]
            if ident.upper() in frames:
                return frames[ident.upper()]
            for m in frames.values():
                if m.name == ident:
                    return m
            for m in frames.values():
                if ident in (m.alt_names or []):
                    return m
            if re.fullmatch(r'(0x)?[0-9A-Fa-f]{1,8}', ident):
                return self.frame(int(ident, 16))
        raise KeyError(f'{self.variant.full_name}/{self.name}: no frame {ident!r}')

    def identify(self, frame_id, data):
        """The frame that best matches a received frame, when several share its ID (None if unknown)"""
        candidates = self.frames_by_id(frame_id)
        if len(candidates) <= 1:
            return candidates[0] if candidates else None
        data = bytes(data)

        def score(m):
            s = 0
            if m.length == len(data):
                s += 2
            elif m.length is not None and (m.length_min or m.length) <= len(data) <= m.length:
                s += 1
            for sel in m.selectors:
                raw = sel.raw_from_payload(data)
                if raw is None:
                    continue
                if raw in m.mux_values(sel.name):
                    s += 3
                entry = (sel.values or {}).get(raw)
                if entry is not None and not entry.unused:
                    s += 1
            return s + (0.5 if m.suffix is None else 0)

        return max(candidates, key=score)

    def decode(self, frame_id, data, lang=None, include_unused=False):
        """DecodedFrame of a received frame (frame_id: int or hex string), KeyError if the ID is unknown"""
        if isinstance(frame_id, str):
            frame_id = int(frame_id, 16)
        msg = self.identify(frame_id, data)
        if msg is None:
            raise KeyError(f'{self.variant.full_name}/{self.name}: unknown frame ID 0x{frame_id:X}')
        return msg.decode(data, lang, include_unused)

    @property
    def nodes(self):
        """{name: Node} of the nodes connected to this bus"""
        return {n: node for n, node in self.db.nodes(self.variant).items() if self.name in node.bus}

    def new_frame(self, frame_id, name, frame_type=None, suffix=None, **kwargs):
        """Creates a frame in this variant (written by save() / Database.save_all())"""
        if frame_type is None:
            frame_type = PROTOCOL_FRAME_TYPES.get(self.protocol, ('can',))[0]
        msg = Message(id=frame_id, name=name, type=frame_type, **kwargs)
        if frame_type == 'can-tp' and msg.isotp is None:
            from .message import IsoTp
            msg.isotp = IsoTp(addressing='normal')
        if frame_type == 'van' and msg.van is None:
            from .message import Van
            msg.van = Van(access='write')
        msg.suffix = suffix
        self.db.add_frame(self.variant, self.name, msg)
        return msg

    def override(self, ident):
        """Copies an inherited frame into this variant, to describe what changed in it"""
        msg = self.frame(ident)
        if msg.variant == self.variant.full_name:
            return msg
        copy = msg.copy()
        copy.path = copy.link = None
        copy._source = None
        self.db.add_frame(self.variant, self.name, copy)
        return copy

    def link(self, msg):
        """Makes ``msg`` (a frame of another variant) also part of this bus, as a relative symlink"""
        return self.db.link_frame(msg, self.variant, self.name)

    def remove(self, ident, delete_file=True):
        msg = ident if isinstance(ident, Message) else self.frame(ident)
        self.db.remove_frame(msg, delete_file=delete_file)
        return msg

    def save(self):
        """Writes the modified frames of this variant's bus"""
        return [self.db.save_frame(m) for m in self.own_frames.values() if m.is_modified]


class Database:
    """A DBMUXEv repository. ``root`` defaults to the repository containing the current directory or this package"""

    def __init__(self, root=None):
        self.root = find_root(root)
        self.architectures = Architectures.load(self.path('architectures.yml'))
        self._nodes = {}
        self._frames = {}
        self._cars = None
        self._diag = {}
        self._protocols = None

    def __repr__(self):
        return f'<Database {self.root}>'

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    # ---- architectures ----
    @property
    def variants(self):
        """{'AEE2004.full': Variant}"""
        out = self.architectures.variants()
        for v in out.values():
            v._db = self
        return out

    def variant(self, name):
        if isinstance(name, Variant):
            return name
        variants = self.variants
        if name in variants:
            return variants[name]
        raise KeyError(f'unknown architecture variant {name!r}, known: {", ".join(variants)}')

    def __getitem__(self, name):
        return self.variant(name)

    def __iter__(self):
        return iter(self.variants.values())

    def chain(self, variant):
        """[variant, parent, grandparent...]"""
        v = self.variant(variant)
        out = []
        while v is not None and v not in out:
            out.append(v)
            v = self.variants.get(v.parent_name) if v.parent else None
        return out

    def children(self, variant):
        """Variants deriving (directly) from ``variant``"""
        v = self.variant(variant)
        return [c for c in self.variants.values() if c.parent_name == v.full_name]

    def buses(self, variant):
        """{'HS.IS': Bus} of a variant, inherited ones included"""
        out = {}
        for v in reversed(self.chain(variant)):
            out.update(v.own_buses())
        return out

    def bus(self, variant, bus):
        """BusView of a variant's bus ('HS.IS')"""
        v = self.variant(variant)
        if bus not in self.buses(v) and not os.path.isdir(self.path('buses', v.full_name, bus)):
            raise KeyError(f'{v.full_name}: no bus {bus!r}, known: {", ".join(self.buses(v))}')
        return BusView(self, v, bus)

    def add_variant(self, arch, name, comment, parent=None, **kwargs):
        """New architecture variant (written by save_architectures)"""
        return self.architectures.add_variant(arch, name, comment, parent=parent, **kwargs)

    def save_architectures(self):
        return self.architectures.save()

    # ---- nodes ----
    def nodeset(self, variant):
        """NodeSet of nodes/<variant>.yml (the variant's own nodes, empty if the file does not exist)"""
        name = self.variant(variant).full_name
        if name not in self._nodes:
            p = self.path('nodes', f'{name}.yml')
            if os.path.isfile(p):
                self._nodes[name] = NodeSet.load(p, variant=name)
            else:
                ns = NodeSet(variant=name)
                ns.path = p
                self._nodes[name] = ns
        return self._nodes[name]

    def nodes(self, variant, inherited=True):
        """{name: Node} of a variant; with ``inherited``, parent nodes are included (a node redefined in a
        variant keeps the buses of its parent's definition)"""
        if not inherited:
            return dict(self.nodeset(variant))
        return merge_nodes([self.nodeset(v) for v in self.chain(variant)])

    def node(self, variant, name):
        nodes = self.nodes(variant)
        if name in nodes:
            return nodes[name]
        for node in nodes.values():
            if node.matches(name):
                return node
        raise KeyError(f'{self.variant(variant).full_name}: no node {name!r}')

    # ---- frames ----
    def _load_frames(self, variant, bus):
        key = (variant, bus)
        if key in self._frames:
            return self._frames[key]
        frames = {}
        d = self.path('buses', variant, bus)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                p = os.path.join(d, fn)
                if not fn.endswith('.yml') or not os.path.isfile(p):
                    continue
                msg = Message.load(p)
                m = FRAME_FILE_RE.match(fn)
                msg.suffix = m.group(2) if m else (fn[:-4].split('_', 1)[1] if '_' in fn else None)
                msg.variant, msg.bus, msg._db = variant, bus, self
                msg.link = os.readlink(p) if os.path.islink(p) else None
                msg._file_key = fn[:-4]
                msg._loaded_key = msg.key
                frames[fn[:-4]] = msg
        self._frames[key] = frames
        return frames

    def frames(self, variant, bus, inherited=True):
        """{file key: Message} of a variant's bus; with ``inherited``, the frames of the parent variants
        that are not redefined are included"""
        chain = self.chain(variant) if inherited else [self.variant(variant)]
        out = {}
        for v in reversed(chain):
            out.update(self._load_frames(v.full_name, bus))
        return out

    def frame(self, variant, bus, ident):
        return self.bus(variant, bus).frame(ident)

    def frame_buses(self, variant, inherited=True):
        """Buses having frames in a variant (directories of buses/<variant>/)"""
        names = []
        chain = self.chain(variant) if inherited else [self.variant(variant)]
        for v in chain:
            d = self.path('buses', v.full_name)
            if os.path.isdir(d):
                names += [b for b in sorted(os.listdir(d)) if os.path.isdir(os.path.join(d, b))]
        return list(dict.fromkeys(names))

    def iter_frames(self, variants=None, buses=None, inherited=False):
        """Every frame (of the given variants / buses). Without ``inherited`` each file is seen once per variant
        directory it is in (symlinks included)"""
        variants = [self.variant(v) for v in (variants or self.variants.values())]
        if isinstance(buses, str):
            buses = [buses]
        for v in variants:
            for b in self.frame_buses(v, inherited):
                if buses and b not in buses:
                    continue
                yield from sorted(self.frames(v, b, inherited).values(), key=lambda m: (m.id, m.key))

    def find_frames(self, name=None, frame_id=None, signal=None, node=None, variants=None, buses=None,
                    inherited=False):
        """Frames matching all the given criteria. ``name`` and ``signal`` are regular expressions
        (case insensitive, matching names and alternative names); ``node`` is a sender or receiver"""
        rname = re.compile(name, re.I) if name else None
        rsig = re.compile(signal, re.I) if signal else None
        for m in self.iter_frames(variants, buses, inherited):
            if frame_id is not None and m.id != frame_id:
                continue
            if rname and not any(rname.search(n) for n in [m.name] + list(m.alt_names or [])):
                continue
            if rsig and not any(rsig.search(n) for s in m.signals.values() for n in [s.name] + list(s.alt_names or [])):
                continue
            if node and node not in (m.senders or []) + (m.receivers or []):
                continue
            yield m

    def find_signals(self, pattern, variants=None, buses=None, inherited=False):
        """(Message, Signal) whose signal name (or alternative name) matches a regular expression"""
        r = re.compile(pattern, re.I)
        for m in self.iter_frames(variants, buses, inherited):
            for s in m.signals.values():
                if any(r.search(n) for n in [s.name] + list(s.alt_names or [])):
                    yield m, s

    def decode(self, variant, bus, frame_id, data, lang=None):
        return self.bus(variant, bus).decode(frame_id, data, lang)

    def add_frame(self, variant, bus, msg):
        """Registers a new frame in a variant's bus (written by save_frame / save_all)"""
        v = self.variant(variant)
        frames = self._load_frames(v.full_name, bus)
        if msg.key in frames and frames[msg.key] is not msg:
            raise ValueError(f'{v.full_name}/{bus}: frame {msg.key} already exists'
                             + ('' if msg.suffix else ', give a suffix'))
        msg.variant, msg.bus, msg._db = v.full_name, bus, self
        frames[msg.key] = msg
        return msg

    def frame_path(self, msg):
        return self.path('buses', msg.variant, msg.bus, msg.filename)

    def save_frame(self, msg, break_link=False):
        """Writes a frame in buses/<variant>/<bus>/<ID>[_<SUFFIX>].yml. A frame whose ID/suffix changed is
        renamed. Through a symlink the shared target is written, unless ``break_link``"""
        if msg.variant is None or msg.bus is None:
            raise ValueError('frame not attached to a variant/bus, use BusView.new_frame or Database.add_frame')
        frames = self._load_frames(msg.variant, msg.bus)
        old_path = msg.path
        if old_path and getattr(msg, '_loaded_key', None) == msg.key:
            path = old_path   # keep the file name, even unusual ones
        else:
            path = self.frame_path(msg)
            other = frames.get(msg.key)
            if (other is not None and other is not msg) or (os.path.lexists(path) and path != old_path):
                raise FileExistsError(f'{path} already exists')
        if os.path.islink(path):
            if break_link:
                os.remove(path)
                msg.link = None
            else:
                _write_document(msg, os.path.realpath(path))
                msg.path = path
                self._rekey(frames, msg, old_path, path)
                return path
        _write_document(msg, path)
        if old_path and os.path.abspath(old_path) != os.path.abspath(path) and os.path.lexists(old_path):
            os.remove(old_path)
        msg.link = None if not os.path.islink(path) else msg.link
        self._rekey(frames, msg, old_path, path)
        return path

    def _rekey(self, frames, msg, old_path, path):
        for k, m in list(frames.items()):
            if m is msg:
                del frames[k]
        frames[os.path.basename(path)[:-4]] = msg
        msg._loaded_key = msg.key

    def remove_frame(self, msg, delete_file=True):
        frames = self._load_frames(msg.variant, msg.bus)
        for k, m in list(frames.items()):
            if m is msg:
                del frames[k]
        if delete_file and msg.path and os.path.lexists(msg.path):
            os.remove(msg.path)
        msg.path = None

    def link_frame(self, msg, variant, bus):
        """Adds a relative symlink to a frame file in another variant/bus (identical frames are shared)"""
        if not msg.path:
            raise ValueError('save the frame first')
        v = self.variant(variant)
        d = self.path('buses', v.full_name, bus)
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, os.path.basename(msg.path))
        if os.path.lexists(dest):
            raise FileExistsError(dest)
        target = os.path.relpath(os.path.realpath(msg.path), d)
        os.symlink(target, dest)
        self._frames.pop((v.full_name, bus), None)   # reload this bus on next access
        return self.bus(v, bus).frame(os.path.basename(dest)[:-4])

    # ---- cars ----
    @property
    def cars(self):
        """{project: Car}"""
        if self._cars is None:
            self._cars = {}
            d = self.path('cars')
            if os.path.isdir(d):
                for fn in sorted(os.listdir(d)):
                    if fn.endswith('.yml'):
                        self._cars[fn[:-4]] = Car.load(os.path.join(d, fn), project=fn[:-4])
        return self._cars

    def car(self, ident):
        """Car by project (file name), project/silhouette code or commercial name (case insensitive)"""
        cars = self.cars
        if ident in cars:
            return cars[ident]
        for car in cars.values():
            if ident in car.codes:
                return car
        low = ident.casefold()
        for car in cars.values():
            if low == car.project.casefold() or any(low == c.casefold() for c in car.codes) or \
                    any(low == n.casefold() for n in car.all_names):
                return car
        raise KeyError(f'no car {ident!r}')

    def find_cars(self, text=None, architecture=None, node=None, year=None):
        """Cars whose names/codes contain ``text`` and/or using an architecture variant / a node / built in a year"""
        low = text.casefold() if text else None
        for car in self.cars.values():
            if low and not (low in car.project.casefold() or any(low in c.casefold() for c in car.codes)
                            or any(low in n.casefold() for n in car.all_names)):
                continue
            versions = car.versions_for(year=year, architecture=architecture)
            if node:
                versions = [v for v in versions if v.has_node(node)]
            if (architecture or node or year) and not versions:
                continue
            yield car

    def add_car(self, project, codes, **kwargs):
        car = Car(project=project, codes=dict(codes), **kwargs)
        car.path = self.path('cars', f'{project}.yml')
        self.cars[project] = car
        return car

    # ---- diagnostics ----
    @property
    def protocols(self):
        """{name: DiagProtocol} of diag/protocols/"""
        if self._protocols is None:
            self._protocols = {}
            d = self.path('diag', 'protocols')
            if os.path.isdir(d):
                for fn in sorted(os.listdir(d)):
                    if fn.endswith('.yml'):
                        p = DiagProtocol.load(os.path.join(d, fn))
                        self._protocols[p.protocol or fn[:-4]] = p
        return self._protocols

    def protocol(self, name):
        return self.protocols[name]

    def diag_nodes(self, variant, inherited=True):
        """Nodes with a diagnostic directory in diag/<variant>/ (and the parent variants)"""
        names = []
        chain = self.chain(variant) if inherited else [self.variant(variant)]
        for v in chain:
            d = self.path('diag', v.full_name)
            if os.path.isdir(d):
                names += [n for n in sorted(os.listdir(d)) if os.path.isdir(os.path.join(d, n))]
        return list(dict.fromkeys(names))

    def diag(self, variant, node, inherited=True):
        """EcuDiag of diag/<variant>/<node>/ (the first one found following the parents with ``inherited``)"""
        chain = self.chain(variant) if inherited else [self.variant(variant)]
        node = node.name if hasattr(node, 'name') and not isinstance(node, str) else node
        for v in chain:
            p = self.path('diag', v.full_name, node)
            if os.path.isdir(p):
                break
        else:
            v = chain[0]
            p = self.path('diag', v.full_name, node)
        key = (v.full_name, node)
        if key not in self._diag:
            self._diag[key] = EcuDiag(p, node=node, variant=v.full_name, db=self)
        return self._diag[key]

    def find_dtc(self, code, variant=None):
        """(EcuDiag, Dtc) of every ECU knowing a DTC code ('B1003-00') or raw value"""
        variants = [self.variant(variant)] if variant else list(self.variants.values())
        for v in variants:
            for node in self.diag_nodes(v, inherited=False):
                ed = self.diag(v, node, inherited=False)
                d = ed.dtcs.lookup(code)
                if d is not None:
                    yield ed, d

    # ---- bulk ----
    def load_all(self):
        """Loads every file (useful before iterating many times, or to check that everything loads)"""
        for v in self.variants.values():
            self.nodeset(v)
            for b in self.frame_buses(v, inherited=False):
                self._load_frames(v.full_name, b)
            for n in self.diag_nodes(v, inherited=False):
                ed = self.diag(v, n, inherited=False)
                ed.ecu, ed.dids, ed.lids, ed.dtcs, ed.routines, ed.ioctls  # noqa: B018 (loads them)
        self.cars, self.protocols  # noqa: B018
        return self

    def loaded_documents(self):
        """Every object loaded (or created) so far"""
        yield self.architectures
        yield from self._nodes.values()
        seen = set()
        for frames in self._frames.values():
            for m in frames.values():
                if id(m) not in seen:
                    seen.add(id(m))
                    yield m
        yield from (self._cars or {}).values()
        yield from (self._protocols or {}).values()
        for ed in self._diag.values():
            for name in ('ecu', 'dtcs'):
                if ed._cache.get(name) is not None:
                    yield ed._cache[name]
            for name in ('dids', 'lids', 'routines', 'ioctls'):
                yield from (ed._cache.get(name) or {}).values()

    def modified(self):
        """Loaded objects that differ from their file"""
        return [doc for doc in self.loaded_documents() if doc.is_modified]

    def save_all(self):
        """Writes every modified object, returns the paths written"""
        written = []
        for doc in self.modified():
            if isinstance(doc, Message):
                written.append(self.save_frame(doc))
            elif doc.path:
                written.append(doc.save())
            elif isinstance(doc, NodeSet):
                written.append(doc.save(self.path('nodes', f'{doc.variant}.yml')))
            else:
                raise ValueError(f'no path to save {doc!r}')
        for ed in self._diag.values():
            for name in ('dids', 'lids', 'routines', 'ioctls'):
                for obj in (ed._cache.get(name) or {}).values():
                    if obj.path is None:
                        from .diag import _filename
                        written.append(obj.save(os.path.join(ed.path, name, _filename(obj))))
        return written


def _write_document(doc, path):
    from .model import Document
    return Document.save(doc, path)

