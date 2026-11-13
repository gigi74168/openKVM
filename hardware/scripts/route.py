#!/usr/bin/env python3
"""Routage d'openKVM : regles JLCPCB, plans, export DSN, Freerouting, import, remplissage.

Etapes :  python3 route.py prepare   -> build/openkvm.dsn (carte placee + regles + plans)
          python3 route.py autoroute -> build/openkvm.ses (Freerouting, long)
          python3 route.py finish    -> openkvm.kicad_pcb (pistes importees, plans remplis)
Freerouting (GPL-3.0) n'est pas dans le depot : FREEROUTING_JAR doit pointer vers son .jar.
"""
import math
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
BUILD = os.path.join(HW, 'build')
SRC = os.path.join(BUILD, 'openkvm-place.kicad_pcb')
PRE = os.path.join(BUILD, 'openkvm-pre.kicad_pcb')
DSN = os.path.join(BUILD, 'openkvm.dsn')
SES = os.path.join(BUILD, 'openkvm.ses')
OUT = os.path.join(HW, 'openkvm.kicad_pcb')
W, H = 45.0, 45.0

# Capacites JLCPCB multicouche (page "PCB Capabilities", lue le 2026-11-12) :
# piste/isolement mini 0,09 mm ; via mini 0,15 / 0,25 mm ; trou de via a 0,2 mm au moins de tout autre cuivre.
# Le BGA au pas de 0,65 mm impose des trous de 0,2 mm (avec 0,3 mm le trou serait a 0,16 mm des billes).
# On prend donc partout un via 0,4 / 0,2 mm : couronne 0,1 + isolement 0,1 = 0,2 mm entre trou et cuivre voisin.
RULES = dict(min_clearance=0.10, min_track=0.10, min_via=0.4, min_drill=0.2, min_annular=0.1,
             edge_clearance=0.3, hole_clearance=0.2, hole_to_hole=0.25)
VIA = (0.4, 0.2)
# classe : (isolement, largeur de piste, diametre de via, percage)
CLASSES = {
    'Default': (0.10, 0.10, 0.40, 0.20),
    'Rapide': (0.10, 0.13, 0.40, 0.20),      # HDMI, CSI-2, USB, Ethernet : ~50 ohms en piste simple (0,15 ne sort pas du BGA)
    'Puissance': (0.10, 0.20, 0.40, 0.20),
}
BGA_FINE = ['TC_AVDD12', 'TC_AVDD25', 'TC_VDDC']
BGA_POWER = BGA_FINE + ['TC_AVDD33', 'TC_VDDMIPI', '3V3', 'GND']
POWER = ['3V3', 'TC_AVDD33', 'TC_VDDMIPI', '5V_SYS', 'VBUS_TGT', 'VBUS_EXT', '1V2', 'VDD_HP', 'SW_3V3', 'SW_1V2', 'SW_HP', 'SD_VDD',
         'VDDO_3', 'VDDO_4', 'VDDO_FLASH', 'VDDO_PSRAM', 'VDD_USBPHY', 'ETH_AVDD33', 'OSC27_VDD', 'HDMI_5V',
         'VDD_BAT', 'ETH_REGOUT']
FAST = ['HDMI_D0_P', 'HDMI_D0_N', 'HDMI_D1_P', 'HDMI_D1_N', 'HDMI_D2_P', 'HDMI_D2_N', 'HDMI_CK_P', 'HDMI_CK_N',
        'CSI_CLK_P', 'CSI_CLK_N', 'CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N',
        'USB_HS_DP', 'USB_HS_DM', 'USB_FS_DP', 'USB_FS_DM', 'USB_FS_CONN_DP', 'USB_FS_CONN_DM',
        'ETH_TX_P', 'ETH_TX_N', 'ETH_RX_P', 'ETH_RX_N']
EP_VIAS = [(dx, dy) for dx in (-2.4, 0.0, 2.4) for dy in (-2.4, 0.0, 2.4)]


def mm(v):
    return pcbnew.FromMM(v)


def apply_rules(board):
    bds = board.GetDesignSettings()
    bds.m_MinClearance = mm(RULES['min_clearance'])
    bds.m_TrackMinWidth = mm(RULES['min_track'])
    bds.m_ViasMinSize = mm(RULES['min_via'])
    bds.m_MinThroughDrill = mm(RULES['min_drill'])
    bds.m_ViasMinAnnularWidth = mm(RULES['min_annular'])
    bds.m_CopperEdgeClearance = mm(RULES['edge_clearance'])
    bds.m_HoleClearance = mm(RULES['hole_clearance'])
    bds.m_HoleToHoleMin = mm(RULES['hole_to_hole'])
    bds.SetBoardThickness(mm(1.6))
    ns = bds.m_NetSettings
    fine = set(BGA_FINE)        # nets d'alimentation qui passent entre deux billes du BGA : piste fine
    for name, (cl, w, vd, dr) in CLASSES.items():
        nc = ns.GetDefaultNetclass() if name == 'Default' else pcbnew.NETCLASS(name)
        nc.SetClearance(mm(cl))
        nc.SetTrackWidth(mm(w))
        nc.SetViaDiameter(mm(vd))
        nc.SetViaDrill(mm(dr))
        if name != 'Default':
            ns.SetNetclass(name, nc)
    for n in POWER:
        if n not in fine:           # les nets qui sortent du BGA restent en piste fine
            ns.SetNetclassPatternAssignment(n, 'Puissance')
    for n in FAST:
        ns.SetNetclassPatternAssignment(n, 'Rapide')
    ns.RecomputeEffectiveNetclasses() if hasattr(ns, 'RecomputeEffectiveNetclasses') else None
    board.SynchronizeNetsAndNetClasses(True)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)      # plan de masse : aucun signal dessus
    board.SetLayerName(pcbnew.In1_Cu, 'GND')
    board.SetLayerName(pcbnew.In2_Cu, 'PWR')


def add_zone(board, layer, netname, clearance=0.15, priority=0, inset=0.0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(netname))
    pts = [(inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)]
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(mm(x), mm(y))
    z.SetLocalClearance(mm(clearance))
    z.SetMinThickness(mm(0.15))
    z.SetAssignedPriority(priority)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetThermalReliefGap(mm(0.2))
    z.SetThermalReliefSpokeWidth(mm(0.3))
    board.Add(z)
    return z


def add_via(board, x, y, net, dia=VIA[0], drill=VIA[1]):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(x, y))
    v.SetWidth(pcbnew.F_Cu, mm(dia))
    v.SetDrill(mm(drill))
    v.SetNet(net)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetLocked(True)
    board.Add(v)
    return v


def add_track(board, x1, y1, x2, y2, net, width, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(x1, y1))
    t.SetEnd(pcbnew.VECTOR2I(x2, y2))
    t.SetWidth(mm(width))
    t.SetLayer(layer)
    t.SetNet(net)
    t.SetLocked(True)
    board.Add(t)


def bga_fanout(board, ref='U8', pitch=0.65):
    """Eventail en os de chien : un via 0,4 / 0,3 mm en diagonale pour chaque bille des anneaux interieurs."""
    f = board.FindFootprintByReference(ref)
    c = f.GetPosition()
    done = set()
    for pad in f.Pads():
        dx, dy = pcbnew.ToMM(pad.GetPosition().x - c.x), pcbnew.ToMM(pad.GetPosition().y - c.y)
        ring = max(abs(dx), abs(dy))
        if pad.GetNetname().startswith('unconnected') or ring > 2.5 * pitch + 0.05:
            continue      # anneau exterieur : il sort en surface
        if ring > 1.5 * pitch + 0.05 and pad.GetNetname() not in BGA_POWER:
            continue      # 2e anneau : les signaux sortent entre deux billes, les alimentations par un via
        vx = pad.GetPosition().x + mm(pitch / 2 if dx > 0 else -pitch / 2)
        vy = pad.GetPosition().y + mm(pitch / 2 if dy > 0 else -pitch / 2)
        add_via(board, vx, vy, pad.GetNet())
        add_track(board, pad.GetPosition().x, pad.GetPosition().y, vx, vy, pad.GetNet(), 0.15)
        done.add((ref, pad.GetNumber()))
    return done


def rect_dist(r, x, y):
    """Distance d'un point au rectangle r = (x0, y0, x1, y1), 0 s'il est dedans."""
    dx = max(r[0] - x, 0, x - r[2])
    dy = max(r[1] - y, 0, y - r[3])
    return math.hypot(dx, dy)


def seg_rect_dist(r, x1, y1, x2, y2, n=12):
    return min(rect_dist(r, x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n + 1))


def ground_vias(board, skip, netname='GND', dia=VIA[0], drill=VIA[1], clr=0.10):
    """Pose un via de masse a cote de chaque pastille CMS de masse, avant l'autoroutage.

    Le plan de masse (couche 2) relie ensuite tous ces vias. Chaque via est verifie contre les
    pastilles des deux faces (il traverse la carte), les autres vias, les trous et le bord.
    Renvoie (nombre de vias poses, liste des pastilles restees sans via).
    """
    net = board.FindNet(netname)
    pads, holes = [], []
    for f in board.GetFootprints():
        fc = f.GetPosition()
        for p in f.Pads():
            bb = p.GetBoundingBox()
            r = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
            tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            pads.append(dict(r=r, net=p.GetNetname(), ref=f.GetReference(), num=p.GetNumber(), tht=tht,
                             top=tht or p.IsOnLayer(pcbnew.F_Cu), c=(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)),
                             fc=(pcbnew.ToMM(fc.x), pcbnew.ToMM(fc.y)), smd=not tht and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD))
            if tht:
                holes.append(r)
    vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y), v.GetNetname())
            for v in board.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    rad = dia / 2
    todo = [p for p in pads if p['net'] == netname and p['smd'] and (p['ref'], p['num']) not in skip]
    # d'abord les pastilles les plus contraintes (puces et connecteurs), puis les passifs
    todo.sort(key=lambda p: (p['ref'][0] in 'RCLDF', p['ref'], p['num']))
    done, failed = 0, []
    for p in todo:
        r = p['r']
        cx, cy = p['c']
        if any(n == netname and rect_dist(r, vx, vy) <= rad + 0.02 for vx, vy, n in vias):
            continue          # deja un via de masse dans ou contre la pastille (pastille centrale, eventail BGA)
        hx, hy = (r[2] - r[0]) / 2, (r[3] - r[1]) / 2
        ox, oy = cx - p['fc'][0], cy - p['fc'][1]          # vers l'exterieur du composant
        inward = p['ref'][0] == 'J'                         # connecteurs : via sous le corps, pas dans le couloir
        cands = []
        for d in (0.27, 0.4, 0.6, 0.85, 1.15, 1.5, 1.9):
            for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                vx = cx + ux * (hx + d) if ux else cx
                vy = cy + uy * (hy + d) if uy else cy
                dot = ux * ox + uy * oy
                along = (abs(ux) == 1 and uy == 0 and hx >= hy) or (abs(uy) == 1 and ux == 0 and hy >= hx)
                score = d + (0 if along else 0.25) + (0.5 if (dot < 0) != inward and (ox or oy) else 0) + (0.3 if ux and uy else 0)
                cands.append((score, vx, vy))
        best = None
        for score, vx, vy in sorted(cands):
            if not (0.6 <= vx <= W - 0.6 and 0.6 <= vy <= H - 0.6):
                continue
            ok = True
            for q in pads:
                if q is p:
                    continue
                dq = rect_dist(q['r'], vx, vy)
                if q['net'] == netname:
                    if q['tht'] and dq < rad + 0.25:
                        ok = False
                        break
                    continue
                if dq < max(rad + clr, drill / 2 + 0.2) + 0.02 + (0.15 if q['tht'] else 0):
                    ok = False
                    break
                # le bout de piste ne doit pas frotter une pastille voisine de la meme face
                if q['top'] == p['top'] or q['tht']:
                    if seg_rect_dist(q['r'], cx, cy, vx, vy) < 0.1 + clr:
                        ok = False
                        break
            if not ok:
                continue
            if any(math.hypot(vx - ax, vy - ay) < (drill + 0.27 if n == netname else dia + clr + 0.02) for ax, ay, n in vias):
                continue
            best = (vx, vy)
            break
        if best is None:
            failed.append(f"{p['ref']}-{p['num']}")
            continue
        vx, vy = best
        add_via(board, mm(vx), mm(vy), net, dia, drill)
        add_track(board, mm(cx), mm(cy), mm(vx), mm(vy), net, 0.2 if min(hx, hy) >= 0.1 else 0.15,
                  pcbnew.F_Cu if p['top'] else pcbnew.B_Cu)
        vias.append((vx, vy, netname))
        done += 1
    return done, failed


def prepare():
    os.makedirs(BUILD, exist_ok=True)
    board = pcbnew.LoadBoard(SRC)
    apply_rules(board)
    gnd = board.FindNet('GND')
    u1 = board.FindFootprintByReference('U1')
    for dx, dy in EP_VIAS:       # vias thermiques sous l'ESP32-P4, vers le plan de masse
        add_via(board, u1.GetPosition().x + mm(dx), u1.GetPosition().y + mm(dy), gnd, 0.5, 0.3)
    u9 = board.FindFootprintByReference('U9')
    add_via(board, u9.GetPosition().x, u9.GetPosition().y, gnd, 0.5, 0.3)
    fanned = bga_fanout(board)
    print('eventail BGA :', len(fanned), 'vias')
    n, failed = ground_vias(board, fanned | {('U1', '105'), ('U9', '33')})
    print('vias de masse :', n, '| pastilles sans via :', failed)
    add_zone(board, pcbnew.In1_Cu, 'GND')
    # Le 3V3 est route en pistes : un plan declare a l'autorouteur se ferait decouper par les signaux
    # de la couche 3 sans qu'il s'en apercoive. Le plan 3V3 est ajoute apres coup, en renfort (finish).
    pcbnew.SaveBoard(PRE, board)
    if os.path.exists(DSN):
        os.remove(DSN)
    ok = pcbnew.ExportSpecctraDSN(board, DSN)
    print('DSN', ok, os.path.getsize(DSN) if os.path.exists(DSN) else 0)


def autoroute(passes='60'):
    jar = os.environ.get('FREEROUTING_JAR')
    java = os.environ.get('FREEROUTING_JAVA', 'java')
    if not jar:
        sys.exit('FREEROUTING_JAR non defini')
    if os.path.exists(SES):
        os.remove(SES)
    env = dict(os.environ, JAVA_TOOL_OPTIONS='')
    # Pas de statistiques d'usage envoyees ; pas de retrecissement automatique des pistes (il descend sous
    # le minimum JLCPCB) ; pas d'etape "fanout" (elle impose 2,5 mm de piste avant chaque via).
    opts = ['--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true',
            '--router.automatic_neckdown=false', '--router.fanout.enabled=false',
            f'--router.autorouter.max_passes={passes}'] + sys.argv[3:]
    subprocess.run([java, '-Djava.awt.headless=true', '-jar', jar, *opts, '-de', DSN, '-do', SES], check=False, env=env)
    print('SES', os.path.exists(SES))


def finish():
    board = pcbnew.LoadBoard(PRE)
    apply_rules(board)
    if not pcbnew.ImportSpecctraSES(board, SES):
        sys.exit('import SES impossible')
    add_zone(board, pcbnew.In2_Cu, '3V3')
    add_zone(board, pcbnew.F_Cu, 'GND', clearance=0.2, inset=0.0)
    add_zone(board, pcbnew.B_Cu, 'GND', clearance=0.2, inset=0.0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    # Les regles et classes de nets vivent dans le .kicad_pro : on les recopie dans celui du projet.
    import json
    pre = json.load(open(PRE.replace('.kicad_pcb', '.kicad_pro')))
    pro_path = OUT.replace('.kicad_pcb', '.kicad_pro')
    pro = json.load(open(pro_path))
    pro['board'] = pre['board']
    pro['net_settings'] = pre['net_settings']
    json.dump(pro, open(pro_path, 'w'), indent=2)
    tracks = [t for t in board.GetTracks()]
    print(f'{OUT} : {sum(1 for t in tracks if t.Type() == pcbnew.PCB_TRACE_T)} segments, '
          f'{sum(1 for t in tracks if t.Type() == pcbnew.PCB_VIA_T)} vias')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'prepare':
        prepare()
    elif cmd == 'autoroute':
        autoroute(*sys.argv[2:3])
    elif cmd == 'finish':
        finish()
    else:
        sys.exit(__doc__)
