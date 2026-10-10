# PSA-RE: the networks of Peugeot, Citroën and DS cars

PSA-RE documents the in-car networks of the PSA group cars (Peugeot, Citroën, DS, and the Opel/Vauxhall models built on
PSA platforms): which electronic architecture each car uses, the buses of each architecture, the ECUs connected to them,
and the frames they exchange, down to the meaning of every bit.

Everything is plain YAML in the [DBMUXEv format](dbmuxev/doc/README.md), checked by a JSON schema, and every text is
available in English and French (and most of it in Spanish, German, Italian, Polish, Russian, Chinese, Hungarian and
Portuguese). The goal is to let anybody understand their own car and build tools, dashboards, retrofits or DIY ECUs
on top of it.

**Browse it online: [explorer.openleo.org](https://explorer.openleo.org)**: search frames and signals, see which
ECUs and buses a car has, decode a capture log, export DBC files, all in the browser.

## What's inside

| Architecture | Cars | Networks | Frame files |
|---|---|---|---|
| `AEE2001` | VAN + CAN cars, late 90s to 2008 (206, early 307, Xsara Picasso...) | 1 CAN bus, VAN comfort/body buses | 132 |
| `AEE2004` | first "full CAN" cars, 2004 to 2018 (207, 308 I, C4 I, C5 II...) | HS and LS CAN, LIN | 849 |
| `AEE2010` | second generation, 2010 to the early 2020s (208 I/II, 308 II, 3008 II, C4 Picasso II, DS 7...) | up to 11 HS CAN buses, LS CAN, LIN | 1962 |
| `NEA2020` | 2021+ cars | not documented yet | - |

Each architecture has **variants** (`<architecture>.<variant>`):

* `full`: the reference variant
* `ev`: **evolution**, a later revision of the architecture (not "electric vehicle"); `AEE2004.ev` is used by cars
  designed from about 2007
* `eco`, `ev_eco`: the economy variant (low cost cars, fewer and merged buses)
* `hybrid`: HYbrid4 diesel hybrids (3008 HYbrid4, 508 RXH, DS5 HYbrid4)
* `electric`: plug-in hybrids and electric cars

A variant inherits everything from its `parent` (see [architectures.yml](architectures.yml)) and only contains
what is different or new.

The bus names follow the car's own naming: `HS` is high speed CAN (500 kbit/s), `LS` low speed CAN (125 kbit/s),
`IS` is the inter-systems bus (powertrain and chassis), `CONF` the comfort bus, `CAR` the body bus, `INFO-DIV` the
infotainment bus, `LAS` the steering/chassis sensors bus, `HYB` the hybrid/electric drivetrain bus, and so on.
Every bus is described in [architectures.yml](architectures.yml).

## Which architecture does my car use?

Look for your car in [`cars/`](cars): files are named after the PSA project code (`T9` is the 308 II, `P2` the
208 II / 2008 II, `T7` the 308 I...), and list the commercial names. Each car has one or more **versions**
(phases, engines, hybrid or electric versions): every version gives its architecture variant, the ECUs on each
network, the optional ones, and the buses actually fitted. The explorer has a car search that does the same.

## Repository layout

```
architectures.yml                     architectures, variants, networks and buses
cars/{project}.yml                    car codes, names, versions, architecture and ECUs of each version
nodes/{architecture}.{variant}.yml    ECUs (nodes): name, buses, network addresses, diagnostic addressing
buses/{architecture}.{variant}/{network}.{bus}/{ID}.yml
                                      one frame per file, ID in uppercase hex
buses/.../{ID}_{NAME}.yml             when several different frames use the same ID on a bus
diag/protocols/                       diagnostic protocols (KWP2000, KWP-PSA2000, UDS, EOBD)
schemas/dbmuxev.schema.json           JSON schema of every document
dbmuxev/                              Python library (load, decode, encode) and the format documentation (dbmuxev/doc)
tools/                                validator and DBC export
```

To get all the frames of a variant, start from its own directory and walk up its `parent` chain: a file in a child
variant replaces the file with the same path in its parents (`buses/AEE2004.ev/HS.IS/305.yml` replaces
`buses/AEE2004.full/HS.IS/305.yml` on the cars using `AEE2004.ev`).

## Reading a frame

Here is the steering wheel angle frame of AEE2004 (`buses/AEE2004.full/HS.IS/305.yml`), shortened:

```yaml
id: 0x305                       # CAN ID
name: 'STEERING_WHEEL_ANGLE'    # unique name in the architecture
alt_names: ['ANGLE_VOLANT', 'WHEEL_SENSOR']   # other names this frame is known by
type: 'can'                     # can, can-tp (ISO-TP transfer), van or lin
length: 7                       # payload length in bytes
comment:
  en: 'Steering-wheel angle, rotation speed and direction, sensor calibration/trim and fault status.'
  fr: 'Angle volant, vitesse et sens de rotation, calibration/trim du capteur et état de défaut.'
periodicity: ['10ms']           # or 'trigger' (sent on events), 'request', or both
senders: ['ABS', 'CAV', 'DAE']  # nodes defined in nodes/AEE2004.full.yml
receivers: ['CMM', 'BSI', 'BVA', ...]

signals:
  STEERING_WHEEL_ANGLE:
    bits: '1.7-2.0'             # byte 1 bit 7 (MSB) to byte 2 bit 0 (LSB): 16 bits
    type: 'sint'                # two's complement
    factor: 0.1
    min: -780
    max: 780
    units: '°'
    invalid: 0x7FFF             # raw value meaning "not available"
    default: 0x00

  STEERING_WHEEL_ROTATION_SPEED:
    bits: '3.7-3.0'
    type: 'uint'
    factor: 4
    units: '°/s'
    invalid: 0xFF

  STEERING_WHEEL_ROTATION_DIRECTION:
    bits: '4.7'                 # a single bit
    type: 'bool'
    values:
      0x00:
        en: 'Positive angle direction, wheel angle increasing (counter-clockwise)'
      0x01:
        en: 'Negative angle direction, steering wheel angle decreasing: clockwise'
  ...
```

### Bit notation

Bits are written `<byte>.<bit>`: bytes are numbered from 1 (the first byte on the bus), bits from 7 (most significant)
to 0. A range `<start>-<end>` is written in transmission order, so multi-byte values are **big endian**
("Motorola"): `1.7-2.0` is byte 1 (most significant) followed by byte 2.

```
        byte 1                  byte 2
 7  6  5  4  3  2  1  0  7  6  5  4  3  2  1  0
[1.7                  ][                    2.0]   bits: '1.7-2.0' (16 bits)
       [1.5-1.3]                                   bits: '1.5-1.3' (3 bits)
```

A few values are little endian: they have `byte_order: 'little_endian'`. Variable length payloads (CAN-TP transfers,
diagnostics) use `n` as the end: `3.7-n` is everything from byte 3. For a DBC file, the Motorola start bit of
`<byte>.<bit>` is `(byte - 1) * 8 + bit`.

### From raw bytes to values

The physical value is `raw * factor + offset` (factor 1 and offset 0 when they are not given). With the payload
`FF 9C 1C 00 A0 F0 00` on 0x305:

* `STEERING_WHEEL_ANGLE`, bits `1.7-2.0`: raw `0xFF9C`, signed on 16 bits = -100, x 0.1 = **-10.0 °**
* `STEERING_WHEEL_ROTATION_SPEED`, bits `3.7-3.0`: raw `0x1C` = 28, x 4 = **112 °/s**
* `STEERING_WHEEL_ROTATION_DIRECTION`, bit `4.7`: 0 = counter-clockwise

### Interpreting the fields

| Field | Meaning |
|---|---|
| `type` | `uint`, `sint`, `bool` (1 bit), `enum` (a value table, possibly with a scaling for the other values), `bcd`, `str` (ASCII), `bytes` (raw), `float` |
| `values` | labels of raw values (keys are hex). `unused: true` in a value table marks a reserved value |
| `invalid` | raw value sent when the data is not available or not valid: do not scale it |
| `default` | value sent before the data is known (start-up, sender absent) |
| `min` / `max` | physical range |
| `unused: true` | bits with no known meaning |
| `mux_selector` / `mux` | multiplexed frames: the selector signal tells which signals are present, each multiplexed signal lists the selector `values` it belongs to |
| `alternatives` | conflicting observations of the same frame or signal (another length, period, layout or scaling, seen on some cars or software versions): the main description is the most common one, each alternative has a `note` |
| `observations` | how and when the frame is sent, differences between car generations |
| `senders: []` | the sender is not known yet (marked `# TODO: find the sender(s)`) |
| `alt_names` | other names of the frame or signal, to help searching |
| `isotp` (can-tp) | ISO 15765-2 parameters: the signals describe the reassembled payload, not the CAN frames |
| `van` (van) | VAN access mode, acknowledge, reply (in-frame response) |

Node names (`BSI`, `CMM`, `ABS`, `BSM`...) are the usual PSA ECU names; their description is in
`nodes/{architecture}.{variant}.yml`: `BSI` is the body computer and main gateway, `CMM` the engine ECU, `BVA` the
automatic gearbox, `CMB` the instrument cluster, `BSM` the under-hood fuse box, and so on.

## Using the data

### In the browser

[explorer.openleo.org](https://explorer.openleo.org) loads this repository directly: browse the architectures, cars,
ECUs, frames and signals, decode a capture log, estimate the bus load, export DBC or JSON files. It can also load a
local copy or a fork, to check your own changes.

### With Python

The [`dbmuxev`](dbmuxev) package loads a repository, resolves the variant inheritance and decodes/encodes frames:

```python
from dbmuxev import Database

db = Database('.').load_all()
bus = db['AEE2004.full']['HS.IS']
decoded = bus.decode(0x305, bytes.fromhex('FF9C1C00A0F000'))
print(decoded)                                   # one line per signal, with units and value labels
decoded['STEERING_WHEEL_ANGLE'].value            # -10.0 (physical value); .raw, .label, .valid
```

From the command line: `python3 -m dbmuxev decode AEE2004.full HS.IS 305 FF9C1C00A0F000`, and
`python3 -m dbmuxev --help` for the other commands (`frames`, `show`, `find`, `car`...). See
[tools/README.md](tools/README.md) for the whole API.

DBC files (one per CAN bus, inherited frames included):

```
pip install -r tools/requirements.txt
python3 tools/export_dbc.py --arch AEE2004.full -o dbc/
```

### With your own parser

Any YAML parser works, but keep in mind:

* keys of value tables are hex numbers (`0x1A:`), read as integers by YAML 1.1 parsers (PyYAML, js-yaml); a YAML 1.2
  parser may keep them as strings
* resolve the `parent` chain of the variant (see above), and accept symlinks between architectures (identical
  frames can be shared that way)
* text fields are maps of language codes: fall back to `en` when a language is missing
* validate your understanding with [`schemas/dbmuxev.schema.json`](schemas/dbmuxev.schema.json), which describes
  every document type, and the commented examples in [`dbmuxev/doc`](dbmuxev/doc)

## Contributing

Corrections and new frames are welcome. Run the validator before opening a pull request:

```
pip install -r tools/requirements.txt
python3 tools/validate.py
```

It checks the schema, bit ranges, overlaps, value tables, node and bus references and the usual YAML traps.
The rules are in [dbmuxev/doc/README.md](dbmuxev/doc/README.md): names in English `UPPER_SNAKE_CASE`, every text
with at least `en` (and `fr` if you can), numbers in hex, and when two observations disagree, keep both (the most
common one as the main description, the other one in `alternatives` with a `note`).

Come and discuss on [the Discord server](https://discord.gg/DPthrN2cbS), and see the [wiki](https://github.com/prototux/PSA-RE/wiki).

## Warning

This is an unofficial project: the data may be incomplete or wrong. Any change you make to your car, even based on
this documentation, is your sole responsibility.

## Thanks

* Wouter Bokslag for his awesome work on the [reverse engineering of the immobilizer](https://fahrplan.events.ccc.de/congress/2019/Fahrplan/events/11020.html)
* Alexandre Blin for his [tools](https://github.com/alexandreblin?tab=repositories), work on his 207 and for being a huge inspiration for this
* Peter Pinter for his huge work on his own [FullCAN to VAN bridge](https://github.com/morcibacsi?tab=repositories)
* Lanchon for his reverse engineering of AEE2004's 0x60F
* All the people who leaked parts of PSA's designs all over the internet :)

## Licence

[Apache 2.0](LICENCE)
