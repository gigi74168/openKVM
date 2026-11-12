#!/usr/bin/env python3
"""Verifie que le schema KiCad genere porte exactement la netlist de design.py.

KiCad relit les .kicad_sch, en extrait sa propre netlist, et on la compare
broche par broche a la source. Toute difference fait echouer le script.
"""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import design  # noqa: E402

out = os.path.join(tempfile.mkdtemp(), 'net.xml')
subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', out,
                os.path.join(HW, 'openkvm.kicad_sch')], check=True, capture_output=True)
root = ET.parse(out).getroot()
kicad = {}
for net in root.find('nets'):
    name = net.get('name').lstrip('/')
    for node in net:
        kicad[(node.get('ref'), node.get('pin'))] = 'NC' if name.startswith('unconnected-') else name
comps = {c.get('ref'): (c.findtext('value'), c.findtext('footprint')) for c in root.find('components')}

d = design.build()
want = {(p['ref'], num): net for p in d.parts for num, net in p['pins'].items()}
bad = 0
for key in sorted(set(want) | set(kicad)):
    a, b = want.get(key), kicad.get(key)
    if a != b:
        bad += 1
        print(f'DIFF {key[0]}.{key[1]}: design={a} kicad={b}')
for p in d.parts:
    if p['ref'] not in comps:
        bad += 1
        print('composant absent du schema :', p['ref'])
    elif comps[p['ref']] != (p['value'], p['fp']):
        bad += 1
        print('valeur/empreinte differente :', p['ref'], comps[p['ref']])
print(f'{len(comps)} composants, {len(want)} broches comparees, {bad} difference(s)')
sys.exit(1 if bad else 0)
