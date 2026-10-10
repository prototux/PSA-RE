# Tools

Install the dependencies once: `pip install -r tools/requirements.txt` (pyyaml, jsonschema).

## validate.py — check the repository

```
python3 tools/validate.py              # validate the repository this script is in
python3 tools/validate.py ../other-repo --strict
```

It checks every YAML file (architectures, nodes, cars, bus frames, diagnostics) against
[`schemas/dbmuxev.schema.json`](../schemas/dbmuxev.schema.json), then runs the checks a schema cannot express:

* YAML traps: duplicate keys (the first one is silently lost), keys like `010:` or `01:` (read as octal/decimal by YAML, write them in hex), tabs, non UTF-8 files, BOM
* file names: `<ID>.yml` must match the frame `id`, several frames with the same ID must use `<ID>_<SUFFIX>.yml`, bus directories must be `<network>.<bus>` of `architectures.yml`, diag file names must match the identifier
* frames: bits inside the frame length, bit ranges in transmission order, overlapping signals (multiplexed signals with exclusive `mux` values are allowed to overlap), value tables that don't fit in the signal width, `invalid`/`default` values, `min > max`, `bool` signals wider than 1 bit, frame type vs bus protocol (a `van` frame on a CAN bus...), 29 bit IDs without `extended`
* references: senders/receivers/nodes defined in `nodes/<arch>.<variant>.yml` (following the variant `parent`), buses and networks of nodes and cars, `mux` selectors, symlinks
* cars: codes defined twice, and the nodes every AEE2004+ car should have (CMM, BSI, BSM, HDC, CMB)
* translations: warns when `fr` is missing (`--no-lang-check` to disable), `--langs` prints the coverage per language
* deprecated fields (`resolution`, `signed`, sized integer types, `diag_*` in nodes)

Options: `--strict` (warnings are errors), `--quiet`, `--no-warnings`, `--json` (machine readable report), `--only <path substring>`.
The exit code is 1 when there are errors, so it can be used in a CI job:

```yaml
# .github/workflows/validate.yml
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r tools/requirements.txt && python3 tools/validate.py --no-lang-check
```

## export_dbc.py — generate DBC files

```
python3 tools/export_dbc.py --arch AEE2004.full -o dbc/            # one DBC per CAN bus
python3 tools/export_dbc.py --arch AEE2010.full --bus HS.IS --lang fr
```

Frames inherited from a parent variant are included. VAN and LIN frames are skipped (DBC is CAN only),
can-tp frames are exported without signals (their payload is reassembled data). Comments and value
tables use the language given with `--lang` (english by default).

## dbmuxev — the Python library

The [`dbmuxev`](../dbmuxev) package loads a repository, resolves the variant inheritance (`parent`), decodes and
encodes payloads, and edits/saves every kind of file. Python 3.10+, needs `pyyaml` (`jsonschema` for
`dbmuxev.schema`). Use it from the repository root, or install it with `pip install -e .`.

```python
from dbmuxev import Database

db = Database()                                   # repository around the current directory (or Database('path'))
bus = db['AEE2004.full']['LS.CONF']               # a bus seen from a variant, inherited frames included
frame = bus.frame(0x0F6)                          # by ID, file key ('0F6_BSI_SLOW_DATA_ELECTRIC'), name or alt name

decoded = bus.decode(0x0F6, bytes.fromhex('8E7F00000000A001'))   # picks the right file when several share the ID
print(decoded)                                    # one line per signal, labels from the value tables
decoded['COOLANT_TEMPERATURE'].value              # 87 (physical), .raw, .label, .valid (not an 'invalid' value)

frame.encode({'COOLANT_TEMPERATURE': 90, 'MAIN_STATUS': 'Ignition on'})   # physical values or labels,
                                                                          # defaults for the others
```

* frames: `Message.decode/encode` handle every signal type (`uint`, `sint`, `bool`, `enum`, `bcd`, `str`, `bytes`,
  `float`), `factor`/`offset`, `byte_order: little_endian`, `invalid`, `default`, multiplexing (`mux_selector`/`mux`)
  and `-n` ranges; `with_alternative(i)` applies an `alternatives` entry; `check()` lists layout problems;
  can-tp frames are segmented/reassembled with `encode_frames()` / `msg.isotp.reassembler()`
* queries: `db.find_frames(name=, signal=, node=, frame_id=)`, `db.find_signals(regex)`, `db.nodes(variant)`,
  `db.car('T91')`, `db.find_cars(node='BSI')`, `db.find_dtc('B1003-00')`
* diagnostics: `ed = db.diag('AEE2010.full', 'BSI')` gives `ed.ecu`, `ed.dids`, `ed.lids`, `ed.dtcs`, `ed.routines`,
  `ed.ioctls`; identifiers build requests (`read_request()`, `write_request(values)`) and decode responses
  (`decode_response(bytes)`); `ed.ecu.security().key_request(seed)` computes the PSA seed/key answer
* languages: `set_language('fr')` (texts fall back to english), or `lang=` on the decoders

Editing: change the objects, then `frame.save()` / `db.save_all()` (only the modified files are written).
Files are written back with their comments, blank lines and list styles, so a change only touches its own
lines; loading then saving the whole repository gives identical files. Frames whose ID changes are renamed,
`bus.new_frame(...)` creates one, `bus.override(id)` copies an inherited frame into a later variant,
`bus.link(frame)` shares a frame of another variant as a relative symlink. Saving a symlinked frame writes the
shared file, `save(break_link=True)` replaces the link with a regular file.

```python
frame = db['AEE2010.full']['HS.IS'].new_frame(0x7AB, 'TEST_FRAME', length=2, periodicity=['100ms'],
                                              senders=['BSI'], comment={'en': 'Test', 'fr': 'Test'})
frame.add_signal('VALUE', '1.7-2.0', factor=0.5, units='km/h', comment={'en': 'Value', 'fr': 'Valeur'})
frame.save()                                      # buses/AEE2010.full/HS.IS/7AB.yml

from dbmuxev.schema import schema_errors          # validate an object before saving it (needs jsonschema)
schema_errors(frame)
```

Command line: `python3 -m dbmuxev --help` (`variants`, `buses`, `frames`, `show`, `decode`, `encode`, `find`, `car`,
`dtc`, `seedkey`), eg. `python3 -m dbmuxev decode AEE2004.full LS.CONF 0F6 8E7F00000000A001`.

Tests: `python3 -m unittest discover -s tests` (includes a check that every file of the repository loads and is
written back identical).
