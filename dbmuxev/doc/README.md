# DBMUXEv format specs v0.2

## Intro

The DBMUXEv format describes multiple generations of automotive network designs (architectures), each made of several networks and buses (CAN, CAN-TP/ISO-TP, VAN, LIN, K-line), the nodes (ECUs) on them, the frames they exchange, and how to diagnose them (KWP2000 / UDS).
It was created because other formats (including Vector's DBC) didn't fit our needs: describing several generations of designs, each including multiple networks, in a readable and diffable way.

It's primarily used to describe the architectures from PSA (Peugeot/Citroen/DS), hence the name: "DBMUX" was the name of a tool used to describe multiplexed networks, and 'ev' ("évolution") is often used to describe an evolution of something.

The machine readable definition of every document is [`schemas/dbmuxev.schema.json`](../../schemas/dbmuxev.schema.json) (JSON schema, draft 07). The files in this directory are commented examples. Run `python3 tools/validate.py` to check the whole repository (see [tools/README.md](../../tools/README.md)).

## Terminology

* **architecture**: a name for a set of design templates (eg. AEE2004)
* **variant**: the architecture variant (derivative), eg. `full`, `eco`, or `ev` (evolution). A variant can have a `parent`
* **network**: a set of buses using the same kind of physical layer (eg. `HS` for high speed CAN, `LS` for low speed CAN, `VAN`, `LIN`)
* **bus**: a physical link between nodes (eg. `HS.IS`, `LS.CONF`, `VAN.CAR`, `LIN.LIN1`)
* **node**: a controller/ECU connected to one or more bus(es)
* **protocol**: the protocol used to send data on a bus (CAN, VAN, LIN, K-LINE) or on top of it (CAN-TP, KWP2000, UDS...)
* **message** / **frame**: a frame sent on a bus (eg. a CAN frame)
* **signal**: a data point sent in a message (eg. some bits of it)

## Directory structure

```
.
├── architectures.yml                       architectures, variants, networks and buses
├── schemas
│   └── dbmuxev.schema.json                 JSON schema of every document
├── cars
│   └── {project}.yml                       codes, names, and which architecture/nodes each car uses
├── nodes
│   └── {architecture}.{variant}.yml        nodes (ECUs) of an architecture variant
├── buses
│   └── {architecture}.{variant}
│       └── {network}.{bus}
│           └── {ID}.yml                    a frame (CAN, CAN-TP, VAN or LIN), ID in uppercase hex
│           └── {ID}_{SUFFIX}.yml           when several frames share the same ID
├── diag
│   ├── protocols
│   │   └── {protocol}.yml                  generic protocol definition (UDS, KWP2000, KWP-PSA2000, EOBD)
│   └── {architecture}.{variant}
│       └── {node}                          (optionally {node}/{model}/ when the node has several ECU models)
│           ├── ecu.yml                     addressing, sessions, services, security access, variants
│           ├── dids
│           │   └── {DID}.yml               UDS data identifiers (0x22 / 0x2E)
│           ├── lids
│           │   └── {LID}.yml               KWP2000 local identifiers (0x21 / 0x3B)
│           ├── dtcs.yml                    diagnostic trouble codes
│           ├── routines
│           │   └── {ID}.yml                routine control (0x31)
│           └── ioctls
│               └── {ID}.yml                input/output control (0x2F / 0x30)
└── tools
    └── validate.py                         validator
```

## Frame types

| type | what | `id` | `length` | extra block |
|---|---|---|---|---|
| `can` | classic CAN frame | 11 bits (29 with `extended: true`) | 0-8 | - |
| `can-tp` | ISO 15765-2 (ISO-TP) transfer, signals describe the reassembled payload | CAN ID of the data frames | max payload (4095) | `isotp` (flow control ID, padding...) |
| `van` | VAN frame (ISO 11519-3) | 12 bits | 0-28 | `van` (access, RAK, RTR, reply mode) |
| `lin` | LIN frame | 6 bits (0x00-0x3F) | 1-8 | `lin` (checksum, master) |

See [message_can.yml](message_can.yml), [message_cantp.yml](message_cantp.yml), [message_van.yml](message_van.yml) and [message_lin.yml](message_lin.yml).

## Bits notation

Bits are written `<byte>.<bit>`: bytes are numbered from 1 (first byte sent), bits from 7 (most significant, sent first) to 0.
A range is `<start>-<end>` in transmission order: `1.7-2.0` is a 16 bit value made of bytes 1 (MSB) and 2 (LSB), big endian ("Motorola").
For a DBC file, the Motorola start bit of `<byte>.<bit>` is `(byte - 1) * 8 + bit`.
Variable length payloads (can-tp, diagnostic data) can use `n` as end: `3.7-n` is everything from byte 3.
The physical value is `raw * factor + offset`. `sint` values are two's complement.

```
        byte 1                  byte 2
 7  6  5  4  3  2  1  0  7  6  5  4  3  2  1  0
[1.7                  ][                    2.0]   bits: '1.7-2.0' (16 bits)
       [1.5-1.3]                                   bits: '1.5-1.3' (3 bits)
```

## Conflicting observations

When two observations of the same frame disagree (other length, other period, other meaning for the same bits...), do not pick one silently: describe the most common one, and add the other one in `alternatives`, at the frame level (partial override of the frame, `signals` then replaces the whole signal map) or at the signal level (partial override of the signal). Every alternative has a `note` explaining where/when it was seen.

## Diagnostics with several ECU models

When the same node exists as several ECU models (eg. engine ECUs from different suppliers, each with its own identifiers),
each model gets its own directory: `diag/{architecture}.{variant}/{node}/{model}/` with the same content as a node directory.
Its `ecu.yml` then has a `model`, the `cars` it was seen on, how to read its part number (`identification`) and its
software `variants` (variant id -> part numbers and cars).

* `dids/`, `lids/`, `routines/`, `ioctls/` documents can have `variants`: the variant ids (of `ecu.yml`) they were seen on.
  A trailing `*` stands for every variant starting with that prefix (`A51_*`). Without `variants`, the document applies to every variant.
* When variants disagree on the layout of the same identifier, the most common layout is described and the others go in
  `alternatives` (each one with a `note`, its `variants`, and a complete `params` map). Two readings of the same bytes are given the same way.
* `mapped`: values without fixed position (the ECU sends its own parameter table), given with their `index` and `length` (bits).
* `lids/{LID}_IDENT.yml`: data read with KWP2000 ReadEcuIdentification (`service: 0x1A`); `routines/{ID}_LID.yml` and
  `ioctls/{ID}_LID.yml`: KWP2000 routines / input-output controls by local identifier (1 byte identifiers).
* routines and ioctls can list the actuator `tests` that use them; ioctls give their `controls` (control option values) and `results`.
* `dtcs.yml` entries can have `failure_types`: the failure type byte sent with 2 byte codes.

See [diag_ecu_model.yml](diag_ecu_model.yml).

## Rules

* IDs and unique names (frame names, signal names, node names...) are in english, `UPPER_SNAKE_CASE`
* Every text is translated (`multilang`): `en` is mandatory, `fr` strongly recommended; `es`, `de`, `it`, `pl`, `ru`, `zh`, `hu` are welcome (any ISO 639-1 code is accepted)
* Numbers are written in hex (`0x1A`) for identifiers, raw values and codes. Never write binary looking keys like `010:` (YAML reads them as decimal or octal!)
* If a message is identical between multiple architectures (and versions of architectures), describe it in the most relevant version of the first architecture implementing it, then create a (relative) symlink to it
* When a frame only differs in a later variant (eg. new signals in `AEE2004.ev`), describe it in both variants
* The dot `.` is used as a separator when needed (`AEE2004.full`, `HS.IS`)
* Senders and receivers must be nodes defined in the matching `nodes/{architecture}.{variant}.yml` (or its parents)

## Changes since v0.1

* JSON schema for every document, and a validator
* new frame types `can-tp`, `lin`; `van` got its own block (was `method`)
* `periodicity` is always a list (`['100ms']`, `['trigger']`, `['500ms', 'trigger']`, `['request']`)
* signal `type`: `uint`, `sint`, `bool`, `enum`, `bcd`, `str`, `bytes`, `float` (the sized types and `signed` are deprecated); `resolution` is deprecated in favour of `factor`; `unit` is `units`
* signal `byte_order` (little endian values do exist), `default`, `mux`/`mux_selector`, `receivers`
* `alternatives` for conflicting observations
* nodes: `diag` addressing summary, `released`
* architectures: `parent`, `years`, `status`; `ev` means evolution
* cars: `brand`, `years`, `platform`, `optional_nodes`, per version `years`/`codes`, `architecture: 'none'` for non multiplexed cars
* diagnostics: `ecu.yml`, `dids/`, `lids/` (KWP2000), `dtcs.yml`, `routines/`, `ioctls/`, `protocols/`
* diagnostics: ECU models (`{node}/{model}/`), `variants`, `identification`, `alternatives`, `mapped`, actuator `tests`, `failure_types`
