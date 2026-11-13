#!/usr/bin/env python3
"""Cree hardware/build/openkvm-place.kicad_pcb : contour, empreintes, nets et placement complet.

Les connecteurs et les puces sont poses a la main (PLACE). Tout le reste est place
automatiquement par place.py, sur les deux faces. Le routage est fait ensuite par route.py.

Usage : python3 gen_pcb.py
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from place import Placer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
NS = uuid.UUID('6f70656e-4b56-4d00-8000-000000000001')
KICAD_FP = '/usr/share/kicad/footprints'
BOARD_W, BOARD_H = 45.0, 45.0
OUT = os.path.join(HW, 'build', 'openkvm-place.kicad_pcb')

# ref -> (x, y, rotation en degres), face superieure. Origine = coin arriere gauche, y vers l'avant.
PLACE = {
    'J4': (9.0, 13.0, 180),      # RJ45, face arriere
    'J3': (26.0, 6.3, 180),      # HDMI, face arriere
    'J1': (39.5, 5.2, 180),      # USB-C CIBLE, face arriere
    'J2': (5.2, 31.0, 270),      # USB-C EXT, face gauche
    'J5': (38.0, 19.4, 90),      # microSD, face droite
    'SW1': (43.7, 38.0, 270),    # bouton FN (unique), face droite
    'U10': (22.75, 12.5, 0),     # ESD HDMI : D2 et D1, traversees par les paires
    'U11': (25.75, 12.5, 0),     # ESD HDMI : D0 et horloge
    'U12': (29.2, 12.5, 0),      # ESD HDMI : DDC, HPD, CEC
    'U13': (39.5, 10.2, 0),      # ESD USB cible, entre J1 et la microSD
    'U14': (9.9, 31.0, 90),      # ESD USB EXT, devant J2
    'U8': (26.0, 18.5, 270),     # TC358743 : HDMI vers l'arriere, CSI vers le P4
    'Y2': (20.4, 18.5, 0),
    'U1': (26.5, 31.0, 180),     # ESP32-P4 : CSI et USB vers l'arriere, RMII a gauche
    'U7': (37.0, 33.0, 0),       # flash
    'Y1': (18.8, 32.8, 90),
    'U2': (33.5, 39.5, 0),       # DCDC coeur
    'L3': (37.6, 39.5, 0),
    'U9': (13.6, 25.2, 0),       # PHY
    'Y3': (18.6, 24.6, 90),
    'U5': (4.6, 38.3, 0),        # buck 3V3
    'L1': (8.6, 38.3, 0),
    'U6': (12.6, 38.3, 0),       # buck 1V2
    'L2': (16.6, 38.3, 0),
    'U3': (6.6, 42.3, 0),
    'U4': (10.2, 42.3, 0),
    'SW2': (23.6, 41.8, 0),      # BOOT (interne)
    'D4': (29.6, 43.7, 0),       # LED alim, bord avant
    'D3': (33.6, 43.7, 0),       # LED etat, bord avant
}
# Marge supplementaire (mm) laissee libre autour de certaines puces, pour sortir les pistes
MARGIN = {'U1': 1.2, 'U8': 0.9, 'U9': 0.7, 'J3': 0.3}
# Couloirs gardes libres sur le dessus pour les paires rapides : (x0, y0, x1, y1)
CORRIDORS = [(20.0, 10.4, 32.0, 15.4),     # HDMI : connecteur -> ESD -> TC358743
             (22.2, 21.6, 31.5, 26.2)]     # CSI-2 : TC358743 -> ESP32-P4
HOLES = [(2.5, 23.9), (2.5, 42.5), (40.6, 43.5)]
# Vias thermiques sous la pastille centrale de l'ESP32-P4 (decalages par rapport a son centre)
EP_VIAS = [(dx, dy) for dx in (-2.4, 0.0, 2.4) for dy in (-2.4, 0.0, 2.4)]
# Face inferieure : couronne laissee libre sous les rangees de broches (les vias de sortie y atterrissent).
# ref -> (demi-cote interieur, demi-cote exterieur) en mm
BOTTOM_RINGS = {'U1': (3.9, 5.7), 'U9': (1.45, 2.7)}
# Face inferieure : carre laisse libre sous le centre du BGA (vias de l'eventail), demi-cote en mm
BOTTOM_SQUARES = {'U8': 2.45}


def uid(*key):
    return str(uuid.uuid5(NS, '/'.join(str(k) for k in key)))


def mm(v):
    return pcbnew.FromMM(v)


def load(fp):
    lib, name = fp.split(':')
    path = os.path.join(HW, 'lib', 'openkvm.pretty') if lib == 'openkvm' else os.path.join(KICAD_FP, lib + '.pretty')
    f = pcbnew.FootprintLoad(path, name)
    if f is None:
        sys.exit(f'empreinte introuvable : {fp}')
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f


def kicad_nets():
    """Noms de nets tels que KiCad les deduit du schema (y compris les 'unconnected-...')."""
    out = os.path.join(tempfile.mkdtemp(), 'net.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', out,
                    os.path.join(HW, 'openkvm.kicad_sch')], check=True, capture_output=True)
    nets = {}
    for n in ET.parse(out).getroot().find('nets'):
        for node in n:
            name = n.get('name')
            if name.startswith('unconnected-'):
                name = name.replace('/', '{slash}')
            nets[(node.get('ref'), node.get('pin'))] = name
    return nets


def outline(board):
    r = 2.0
    for x1, y1, x2, y2 in [(r, 0, BOARD_W - r, 0), (BOARD_W, r, BOARD_W, BOARD_H - r),
                           (BOARD_W - r, BOARD_H, r, BOARD_H), (0, BOARD_H - r, 0, r)]:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)
    for cx, cy, sx, sy in ((r, r, 0, r), (BOARD_W - r, r, BOARD_W - r, 0),
                           (BOARD_W - r, BOARD_H - r, BOARD_W, BOARD_H - r), (r, BOARD_H - r, r, BOARD_H)):
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetCenter(pcbnew.VECTOR2I(mm(cx), mm(cy)))
        a.SetStart(pcbnew.VECTOR2I(mm(sx), mm(sy)))
        a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        a.SetLayer(pcbnew.Edge_Cuts)
        a.SetWidth(mm(0.1))
        board.Add(a)


def size_rank(part):
    fp = part['fp']
    for i, key in enumerate(('0805', 'SOD-123', 'SOT-23', 'USON', '0603', 'TestPoint', '0402')):
        if key in fp:
            return i
    return 0


def build():
    parts = json.load(open(os.path.join(HW, 'exports', 'design.json')))['parts']
    knet = kicad_nets()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    outline(board)
    pl = Placer(board, BOARD_W, BOARD_H, load)
    edge = 0.6
    for side in 'FB':
        pl.block(side, 0, 0, BOARD_W, edge)
        pl.block(side, 0, BOARD_H - edge, BOARD_W, BOARD_H)
        pl.block(side, 0, 0, edge, BOARD_H)
        pl.block(side, BOARD_W - edge, 0, BOARD_W, BOARD_H)
        for cx in (0, BOARD_W - 1.3):
            for cy in (0, BOARD_H - 1.3):
                pl.block(side, cx, cy, cx + 1.3, cy + 1.3)
    for i, (x, y) in enumerate(HOLES, 1):
        h = load('MountingHole:MountingHole_2.2mm_M2')
        h.SetReference(f'H{i}')
        h.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        board.Add(h)
        pl.block_circle('F', x, y, 2.5)
        pl.block_circle('B', x, y, 2.9)     # plot du boitier, diametre 5 mm
    ux, uy, _ = PLACE['U1']
    for dx, dy in EP_VIAS:
        pl.block('B', ux + dx - 0.45, uy + dy - 0.45, ux + dx + 0.45, uy + dy + 0.45)
    for ref, (a, b) in BOTTOM_RINGS.items():
        cx, cy, _ = PLACE[ref]
        pl.block('B', cx - b, cy - b, cx + b, cy - a)
        pl.block('B', cx - b, cy + a, cx + b, cy + b)
        pl.block('B', cx - b, cy - a, cx - a, cy + a)
        pl.block('B', cx + a, cy - a, cx + b, cy + a)
    for ref, a in BOTTOM_SQUARES.items():
        cx, cy, _ = PLACE[ref]
        pl.block('B', cx - a, cy - a, cx + a, cy + a)
    cx, cy, _ = PLACE['U9']          # via thermique au centre du PHY
    pl.block('B', cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5)

    sheet_uuid = {}
    fps = {}
    for p in parts:
        f = load(p['fp'])
        f.SetReference(p['ref'])
        f.SetValue(p['value'])
        sid = sheet_uuid.setdefault(p['sheet'], uid('sheet', p['sheet']))
        f.SetPath(pcbnew.KIID_PATH(f"/{sid}/{uid('sym', p['ref'])}"))
        for key in ('LCSC', 'MPN'):
            if p[key.lower()]:
                fld = pcbnew.PCB_FIELD(f, f.GetNextFieldId(), key)
                fld.SetText(p[key.lower()])
                fld.SetVisible(False)
                f.AddField(fld)
        if p['dnp']:
            f.SetDNP(True)
            f.SetExcludedFromBOM(True)
            f.SetExcludedFromPosFiles(True)
        for pad in f.Pads():
            n = knet.get((p['ref'], pad.GetNumber()))
            if n:
                pad.SetNet(net(n))
        f.Reference().SetVisible(False)      # serigraphie des references : trop dense pour etre lisible
        fps[p['ref']] = f

    # 1. composants fixes
    for p in parts:
        if p['ref'] in PLACE:
            x, y, rot = PLACE[p['ref']]
            f = fps[p['ref']]
            f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            f.SetOrientationDegrees(rot)
            board.Add(f)
            pl.commit(p, 'F', x, y, rot, f)
            m = MARGIN.get(p['ref'])
            if m:
                rect, _ = pl.geometry(p['fp'], rot, 'F')
                pl.block('F', x + rect[0] - m, y + rect[1] - m, x + rect[2] + m, y + rect[3] + m)
    for c in CORRIDORS:
        pl.block('F', *c)

    # 2. le reste, des plus gros aux plus petits, en plusieurs passes
    todo = sorted([p for p in parts if p['ref'] not in PLACE], key=size_rank)
    progress = True
    while todo and progress:
        progress = False
        for p in list(todo):
            f = fps[p['ref']]
            prefer = 'B' if 'TestPoint' in p['fp'] else None
            if pl.place(p, f, prefer):
                todo.remove(p)
                progress = True
    for p in todo:      # sans cible (ex. pastille de test GND) : pres du centre de son groupe
        mates = [pl.where[q['ref']] for q in parts if q['group'] == p['group'] and q['ref'] in pl.where]
        tx = sum(m[1] for m in mates) / len(mates)
        ty = sum(m[2] for m in mates) / len(mates)
        found = pl.search(p, 'B', tx, ty, {}, 20.0)
        if not found:
            sys.exit(f"placement impossible : {p['ref']}")
        f = fps[p['ref']]
        board.Add(f)
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(found[2])
        f.SetPosition(pcbnew.VECTOR2I(mm(found[0]), mm(found[1])))
        pl.commit(p, 'B', found[0], found[1], found[2], f)

    with open(os.path.join(HW, 'exports', 'placement.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['ref', 'face', 'x_mm', 'y_mm', 'rotation'])
        for ref, (side, x, y, rot) in sorted(pl.where.items()):
            w.writerow([ref, 'dessus' if side == 'F' else 'dessous', f'{x:.2f}', f'{y:.2f}', rot])
    return board, len(nets), pl


def main():
    board, nnets, pl = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pcbnew.SaveBoard(OUT, board)
    nb = sum(1 for v in pl.where.values() if v[0] == 'B')
    print(f'{OUT} : {len(board.GetFootprints())} empreintes, {nnets} nets, {nb} composants dessous')


if __name__ == '__main__':
    main()
