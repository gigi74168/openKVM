#!/usr/bin/env python3
"""Cree hardware/openkvm.kicad_pcb : contour, empreintes, nets, pre-placement.

Ce n'est PAS un routage. Les connecteurs et les puces principales sont poses a
leur place prevue ; les passifs sont ranges par bloc sous la carte, a deplacer
pendant le layout. Tous les nets sont charges (chevelu complet).

Usage : python3 gen_pcb.py [--preview chemin.kicad_pcb]
  --preview ecrit aussi une copie sans les composants hors carte (pour les rendus).
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
NS = uuid.UUID('6f70656e-4b56-4d00-8000-000000000001')
KICAD_FP = '/usr/share/kicad/footprints'
BOARD_W, BOARD_H = 45.0, 45.0

# ref -> (x, y, rotation en degres). Origine = coin arriere gauche, y vers l'avant.
PLACE = {
    'J4': (9.0, 13.0, 180),      # RJ45, face arriere
    'J3': (26.0, 6.3, 180),      # HDMI, face arriere
    'J1': (39.5, 5.2, 180),      # USB-C CIBLE, face arriere
    'J2': (5.2, 31.0, 270),      # USB-C EXT, face gauche
    'J5': (38.0, 19.4, 90),      # microSD, face droite
    'SW1': (43.7, 32.1, 270),    # bouton NAV, face droite
    'SW2': (43.7, 40.6, 270),    # bouton MODE, face droite
    'U8': (26.0, 18.5, 270),     # TC358743 : HDMI vers l'arriere, CSI vers le P4
    'Y2': (20.4, 18.5, 0),
    'U1': (26.5, 31.0, 180),     # ESP32-P4 : CSI et USB vers l'arriere, RMII a gauche
    'U7': (37.0, 33.0, 0),      # flash
    'Y1': (18.8, 32.8, 90),
    'U2': (35.0, 40.0, 0),       # DCDC coeur
    'L3': (39.3, 40.0, 0),
    'U9': (13.6, 25.2, 0),       # PHY
    'Y3': (18.6, 24.6, 90),
    'U5': (4.6, 38.3, 0),        # buck 3V3
    'L1': (8.6, 38.3, 0),
    'U6': (12.6, 38.3, 0),       # buck 1V2
    'L2': (16.6, 38.3, 0),
    'U3': (6.6, 42.3, 0),
    'U4': (10.2, 42.3, 0),
    'J7': (27.6, 41.9, 0),       # connecteur ecran
    'SW3': (18.0, 42.4, 0),      # BOOT
}
HOLES = [(2.5, 23.9), (2.5, 42.5), (40.6, 43.5)]


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


def build(with_offboard=True):
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

    # contour, coins arrondis r = 2 mm
    r = 2.0
    pts = [(r, 0, BOARD_W - r, 0), (BOARD_W, r, BOARD_W, BOARD_H - r),
           (BOARD_W - r, BOARD_H, r, BOARD_H), (0, BOARD_H - r, 0, r)]
    for x1, y1, x2, y2 in pts:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)
    for cx, cy, sx, sy, ex, ey in ((r, r, 0, r, r, 0), (BOARD_W - r, r, BOARD_W - r, 0, BOARD_W, r),
                                   (BOARD_W - r, BOARD_H - r, BOARD_W, BOARD_H - r, BOARD_W - r, BOARD_H),
                                   (r, BOARD_H - r, r, BOARD_H, 0, BOARD_H - r)):
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetCenter(pcbnew.VECTOR2I(mm(cx), mm(cy)))
        a.SetStart(pcbnew.VECTOR2I(mm(sx), mm(sy)))
        a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        a.SetLayer(pcbnew.Edge_Cuts)
        a.SetWidth(mm(0.1))
        board.Add(a)

    for i, (x, y) in enumerate(HOLES, 1):
        h = load('MountingHole:MountingHole_2.2mm_M2')
        h.SetReference(f'H{i}')
        h.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        board.Add(h)

    sheet_uuid = {}
    cursor = {}
    order = ['power', 'mcu', 'hdmi', 'eth', 'periph']
    for p in parts:
        on_board = p['ref'] in PLACE
        if not on_board and not with_offboard:
            continue
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
        for pad in f.Pads():
            n = knet.get((p['ref'], pad.GetNumber()))
            if n:
                pad.SetNet(net(n))
        if on_board:
            x, y, rot = PLACE[p['ref']]
        else:
            col = order.index(p['sheet'])
            k = cursor.get(col, 0)
            cursor[col] = k + 1
            x = 2.0 + col * 34.0 + (k % 5) * 6.0
            y = BOARD_H + 12.0 + (k // 5) * 5.0
            rot = 0
        f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        f.SetOrientationDegrees(rot)
        board.Add(f)

    if with_offboard:
        titles = {'power': 'Alimentation', 'mcu': 'ESP32-P4', 'hdmi': 'Capture HDMI', 'eth': 'Ethernet',
                  'periph': 'Peripheriques'}
        for col, key in enumerate(order):
            t = pcbnew.PCB_TEXT(board)
            t.SetText(f'{titles[key]} : a placer')
            t.SetLayer(pcbnew.Cmts_User)
            t.SetPosition(pcbnew.VECTOR2I(mm(2.0 + col * 34.0 + 12), mm(BOARD_H + 7.0)))
            t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
            board.Add(t)
        t = pcbnew.PCB_TEXT(board)
        t.SetText('openKVM v1 rev 0.1 - PRE-PLACEMENT NON ROUTE - revue humaine obligatoire')
        t.SetLayer(pcbnew.Cmts_User)
        t.SetPosition(pcbnew.VECTOR2I(mm(BOARD_W / 2), mm(-4.0)))
        t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
        board.Add(t)
    return board, len(nets)


def main():
    board, nnets = build(True)
    out = os.path.join(HW, 'openkvm.kicad_pcb')
    pcbnew.SaveBoard(out, board)
    print(f'{out} : {len(board.GetFootprints())} empreintes, {nnets} nets')
    if '--preview' in sys.argv:
        prev, _ = build(False)
        path = sys.argv[sys.argv.index('--preview') + 1]
        pcbnew.SaveBoard(path, prev)
        print('apercu :', path)


if __name__ == '__main__':
    main()
