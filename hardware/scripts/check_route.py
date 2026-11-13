#!/usr/bin/env python3
"""Controle du routage : DRC KiCad resume, connexions manquantes, longueur des paires rapides.

Usage : python3 check_route.py [carte.kicad_pcb]
"""
import collections
import json
import os
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
PAIRS = [('HDMI_D0_P', 'HDMI_D0_N'), ('HDMI_D1_P', 'HDMI_D1_N'), ('HDMI_D2_P', 'HDMI_D2_N'), ('HDMI_CK_P', 'HDMI_CK_N'),
         ('CSI_CLK_P', 'CSI_CLK_N'), ('CSI_D0_P', 'CSI_D0_N'), ('CSI_D1_P', 'CSI_D1_N'),
         ('USB_HS_DP', 'USB_HS_DM'), ('USB_FS_DP', 'USB_FS_DM'), ('USB_FS_CONN_DP', 'USB_FS_CONN_DM'),
         ('ETH_TX_P', 'ETH_TX_N'), ('ETH_RX_P', 'ETH_RX_N')]
SERIOUS = ('shorting_items', 'clearance', 'tracks_crossing', 'hole_clearance', 'copper_edge_clearance',
           'track_width', 'annular_width', 'via_diameter', 'drill_out_of_range', 'courtyards_overlap',
           'hole_to_hole', 'solder_mask_bridge', 'unconnected_items')


def main():
    pcb = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, 'openkvm.kicad_pcb')
    out = os.path.join(tempfile.mkdtemp(), 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--schematic-parity', '-o', out, pcb],
                   capture_output=True)
    d = json.load(open(out))
    cnt = collections.Counter(v['type'] for v in d.get('violations', []))
    unc = d.get('unconnected_items', [])
    par = d.get('schematic_parity', [])
    print('DRC :', dict(cnt))
    print('connexions manquantes :', len(unc), '| ecarts schema/carte :', len(par))
    by_net = collections.Counter()
    for u in unc:
        for it in u['items'][:1]:
            desc = it['description']
            net = desc[desc.find('[') + 1:desc.find(']')] if '[' in desc else '?'
            by_net[net] += 1
    if unc:
        print('   par net :', dict(by_net.most_common(40)))
    for v in d.get('violations', []):
        if v['type'] in ('shorting_items', 'tracks_crossing'):
            print('  ', v['type'], '|', ' / '.join(i['description'][:70] for i in v['items']))
    board = pcbnew.LoadBoard(pcb)
    length = collections.Counter()
    vias = collections.Counter()
    layers = collections.Counter()
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias[t.GetNetname()] += 1
        else:
            length[t.GetNetname()] += pcbnew.ToMM(t.GetLength())
            layers[board.GetLayerName(t.GetLayer())] += pcbnew.ToMM(t.GetLength())
    print('longueur de pistes par couche (mm) :', {k: round(v) for k, v in layers.items()}, '| vias :', sum(vias.values()))
    print('paires rapides (longueur en mm, vias) :')
    for a, b in PAIRS:
        print(f'   {a:16s} {length[a]:6.2f} ({vias[a]})   {b:16s} {length[b]:6.2f} ({vias[b]})   ecart {abs(length[a] - length[b]):5.2f}')
    bad = sum(cnt[k] for k in SERIOUS) + len(unc)
    print('TOTAL des points serieux :', bad)
    return bad


if __name__ == '__main__':
    main()
