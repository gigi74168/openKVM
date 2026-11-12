#!/bin/sh
# Regenere tout le materiel depuis scripts/design.py. Necessite KiCad 9 (kicad-cli + python3-pcbnew).
set -e
cd "$(dirname "$0")"
python3 scripts/gen_kicad.py
python3 scripts/verify_netlist.py
python3 scripts/gen_pcb.py
kicad-cli sch export pdf -o exports/openkvm-schema.pdf openkvm.kicad_sch
echo "OK : schema, netlist verifiee, PCB pre-place et PDF regeneres."
