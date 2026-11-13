#!/usr/bin/env python3
"""Fichiers de fabrication JLCPCB a partir de openkvm.kicad_pcb.

Sortie : fabrication/jlcpcb/
  openkvm-gerbers.zip        4 cuivres, masques, pates, serigraphies, contour + percages Excellon
  openkvm-bom-jlcpcb.csv     BOM (copie de fabrication/openkvm-bom-jlcpcb.csv)
  openkvm-cpl-jlcpcb.csv     placement : Designator, Val, Package, Mid X, Mid Y, Rotation, Layer

Conventions du CPL (celles du greffon kicad-jlcpcb-tools, MIT) : Y inverse par rapport a KiCad,
rotation KiCad telle quelle sur le dessus, (180 - rotation) mod 360 sur le dessous.
Les empreintes viennent de la bibliotheque JLCPCB/EasyEDA : pas de correction de rotation par piece
(verifie par check_orientation.py).
"""
import csv
import glob
import os
import shutil
import subprocess
import sys
import zipfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
PCB = os.path.join(HW, 'openkvm.kicad_pcb')
OUT = os.path.join(HW, 'fabrication', 'jlcpcb')
BOM = os.path.join(HW, 'fabrication', 'openkvm-bom-jlcpcb.csv')
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"echec : {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")


def gerbers():
    g = os.path.join(OUT, 'gerbers')
    shutil.rmtree(g, ignore_errors=True)
    os.makedirs(g)
    run('kicad-cli', 'pcb', 'export', 'gerbers', '-o', g + '/', '-l', LAYERS, '--no-x2', '--no-netlist',
        '--subtract-soldermask', PCB)
    run('kicad-cli', 'pcb', 'export', 'drill', '-o', g + '/', '--format', 'excellon', '--excellon-units', 'mm',
        '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate', '--excellon-separate-th',
        '--generate-map', '--map-format', 'gerberx2', PCB)
    for f in glob.glob(g + '/*.gbrjob'):
        os.remove(f)
    z = os.path.join(OUT, 'openkvm-gerbers.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(g)):
            zf.write(os.path.join(g, f), f)
    files = sorted(os.listdir(g))
    shutil.rmtree(g)
    return z, files


def cpl():
    board = pcbnew.LoadBoard(PCB)
    rows = []
    for f in board.GetFootprints():
        ref = f.GetReference()
        if f.IsDNP() or f.IsExcludedFromPosFiles() or ref.startswith('H'):
            continue
        bottom = f.IsFlipped()
        rot = f.GetOrientationDegrees() % 360
        if bottom:
            rot = (180 - rot) % 360
        p = f.GetPosition()
        rows.append([ref, f.GetValue(), str(f.GetFPID().GetLibItemName()), f'{pcbnew.ToMM(p.x):.4f}',
                     f'{-pcbnew.ToMM(p.y):.4f}', f'{rot:.0f}', 'bottom' if bottom else 'top'])
    rows.sort(key=lambda r: (r[0].rstrip('0123456789'), int(''.join(c for c in r[0] if c.isdigit()) or 0)))
    path = os.path.join(OUT, 'openkvm-cpl-jlcpcb.csv')
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Designator', 'Val', 'Package', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        w.writerows(rows)
    return path, rows


def check(rows):
    """Chaque reference de la BOM doit etre dans le CPL, et inversement."""
    bom = set()
    for r in csv.DictReader(open(BOM)):
        bom.update(x.strip() for x in r['Designator'].split(','))
    pos = {r[0] for r in rows}
    return sorted(bom - pos), sorted(pos - bom)


def main():
    os.makedirs(OUT, exist_ok=True)
    z, files = gerbers()
    path, rows = cpl()
    shutil.copy(BOM, os.path.join(OUT, 'openkvm-bom-jlcpcb.csv'))
    only_bom, only_cpl = check(rows)
    print(f'{z} : {len(files)} fichiers')
    for f in files:
        print('   ', f)
    top = sum(1 for r in rows if r[6] == 'top')
    print(f'{path} : {len(rows)} composants ({top} dessus, {len(rows) - top} dessous)')
    print('dans la BOM mais pas dans le CPL :', only_bom or 'aucun')
    print('dans le CPL mais pas dans la BOM :', only_cpl or 'aucun')
    if only_bom or only_cpl:
        sys.exit(1)


if __name__ == '__main__':
    main()
