# Rules specific for PSA

* Names (frames, signals) are in english; other known names (eg. the french mnemonics seen in tools or dumps) go in `alt_names`
* Node names are the acronyms shown by the diagnostic tools (BSI, CMM, BSM, HDC, CMB, EMF...), see `nodes/`
* Architectures: `AEE2001` (VAN+CAN), `AEE2004` (full CAN, `ev` = 2007 evolution), `AEE2010` (`eco`, `ev`, `ev_eco` variants), `NEA2020` (not documented yet)
* The BSI is the gateway: a frame forwarded by the BSI on another bus is described on each bus, with the BSI as sender
* Node unit codes: `LS` codes are also the low byte of the node's wakeup (0x4xx), fault event (0x48x), supervision (0x5xx) and version (0x5Cx-0x5Fx) frames; `HS` codes are the 7 bit codes of the IS version frames (0x100 + code)
* Diagnostic CAN IDs follow the unit code: `0x740 + code` / `0x640 + code` on the low speed buses, `0x6A8`/`0x688` style on the IS bus (see `nodes/*.yml` `diag` and `diag/`)
