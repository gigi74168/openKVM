#!/usr/bin/env python3
"""Routage d'openKVM : regles JLCPCB, plans, export DSN, Freerouting, import, remplissage.

Etapes :  python3 route.py prepare   -> build/openkvm.dsn (carte placee + regles + plans)
          python3 route.py autoroute -> build/openkvm.ses (Freerouting, long)
          python3 route.py finish    -> openkvm.kicad_pcb (pistes importees, plans remplis)
Freerouting (GPL-3.0) n'est pas dans le depot : FREEROUTING_JAR doit pointer vers son .jar.
"""
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
# piste/isolement mini 0,09 mm ; via standard 0,3 mm perce, pastille 0,4 ou 0,45 mm.
RULES = dict(min_clearance=0.09, min_track=0.09, min_via=0.4, min_drill=0.3, min_annular=0.05,
             edge_clearance=0.3, hole_clearance=0.2, hole_to_hole=0.25)
# classe : (isolement, largeur de piste, diametre de via, percage)
CLASSES = {
    'Default': (0.09, 0.10, 0.40, 0.30),
    'Rapide': (0.09, 0.13, 0.40, 0.30),      # HDMI, CSI-2, USB, Ethernet : ~50 ohms en piste simple (0,15 ne sort pas du BGA)
    'Puissance': (0.09, 0.20, 0.40, 0.30),
}
POWER = ['3V3', '5V_SYS', 'VBUS_TGT', 'VBUS_EXT', '1V2', 'VDD_HP', 'SW_3V3', 'SW_1V2', 'SW_HP', 'SD_VDD',
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
    fine = set()
    u8 = board.FindFootprintByReference('U8')
    for pad in u8.Pads():
        n = pad.GetNetname()
        if n and not n.startswith('unconnected') and n != 'GND':
            fine.add(n)
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


def add_via(board, x, y, net, dia=0.4, drill=0.3):
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
    n = 0
    for pad in f.Pads():
        dx, dy = pcbnew.ToMM(pad.GetPosition().x - c.x), pcbnew.ToMM(pad.GetPosition().y - c.y)
        if max(abs(dx), abs(dy)) > 1.5 * pitch + 0.05 or pad.GetNetname().startswith('unconnected'):
            continue      # anneaux exterieurs : ils sortent en surface
        vx = pad.GetPosition().x + mm(pitch / 2 if dx > 0 else -pitch / 2)
        vy = pad.GetPosition().y + mm(pitch / 2 if dy > 0 else -pitch / 2)
        add_via(board, vx, vy, pad.GetNet())
        add_track(board, pad.GetPosition().x, pad.GetPosition().y, vx, vy, pad.GetNet(), 0.15)
        n += 1
    return n


def prepare():
    os.makedirs(BUILD, exist_ok=True)
    board = pcbnew.LoadBoard(SRC)
    apply_rules(board)
    gnd = board.FindNet('GND')
    u1 = board.FindFootprintByReference('U1')
    for dx, dy in EP_VIAS:       # vias thermiques sous l'ESP32-P4, vers le plan de masse
        add_via(board, u1.GetPosition().x + mm(dx), u1.GetPosition().y + mm(dy), gnd, 0.5)
    u9 = board.FindFootprintByReference('U9')
    add_via(board, u9.GetPosition().x, u9.GetPosition().y, gnd, 0.5)
    print('eventail BGA :', bga_fanout(board), 'vias')
    add_zone(board, pcbnew.In1_Cu, 'GND')
    add_zone(board, pcbnew.In2_Cu, '3V3')
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
