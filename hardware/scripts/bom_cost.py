#!/usr/bin/env python3
"""Chiffre la BOM openKVM : prix des composants (API JLCPCB) + frais d'assemblage (grille publiee).

Usage : python3 bom_cost.py [--refresh]
  Les prix sont lus dans fabrication/prix-composants.json (instantane date).
  --refresh interroge de nouveau l'API publique de JLCPCB et met l'instantane a jour.
Sortie : fabrication/openkvm-bom-chiffree.csv + resume sur la sortie standard.

Ce que ce script NE sait PAS chiffrer (voir docs/05) : le TC358743 (broker), le module d'ecran,
le PCB nu, le transport, les droits de douane. Ils sont reportes tels quels, jamais inventes.
"""
import csv
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
BOM = os.path.join(HW, 'fabrication', 'openkvm-bom-jlcpcb.csv')
SNAP = os.path.join(HW, 'fabrication', 'prix-composants.json')
OUT = os.path.join(HW, 'fabrication', 'openkvm-bom-chiffree.csv')
API = 'https://cart.jlcpcb.com/shoppingCart/smtGood/getComponentDetail?componentCode='
DATE = '2026-11-12'

# Grille JLCPCB "PCB Assembly Cost" (page d'aide mise a jour le 22 oct. 2026, lue le 2026-11-12), en USD.
FEES = {
    'setup': 25.56,            # Standard PCBA, une face
    'stencil': 8.21,           # Standard, une face
    'feeder_per_ref': 1.53,    # par reference distincte (Standard : toutes les pieces)
    'smt_per_joint': 0.0016,   # 1 a 50 000 soudures
    'manual_per_joint': 0.0164,
    'hand_labor': 3.58,        # par commande
    'confirm_placement': 0.45,
    'fixture': 16.42,          # 1 a 29 cartes : 2 gabarits a 8,21
    'packing': 0.50,           # + 0,00003 x surface en cm2 (negligeable)
}
XRAY = [(10, 1.64), (50, 0.82), (200, 0.49), (500, 0.33)]     # (jusqu'a n pieces, USD/piece)
SMT_JOINTS = 708          # compte sur openkvm.kicad_pcb : 686 plots CMS + 22 trous de blindage de connecteurs CMS
MANUAL_JOINTS = 16        # RJ45 HR911105A (seul composant traversant)
XRAY_PER_BOARD = {'bga_qfn': 3, 'avec_uson': 8}   # U8, U1, U9 | + 5 x TPD4E05U06 (USON sans broches visibles)


def fetch(code):
    for i in range(4):
        out = subprocess.run(['curl', '-sS', '-m', '40', API + code, '-H', 'User-Agent: Mozilla/5.0'],
                             capture_output=True, text=True).stdout
        try:
            d = json.loads(out)['data']
            return {'stock': d['stockCount'], 'lib': d['componentLibraryType'], 'least': d['leastNumber'],
                    'loss': d['lossNumber'], 'minbuy': d['minPurchaseNum'], 'process': d['assemblyProcess'],
                    'prices': [[p['startNumber'], p['productPrice']] for p in d['prices']], 'date': DATE}
        except Exception:
            time.sleep(2 * (i + 1))
    raise SystemExit(f'prix introuvable pour {code}')


def load_snapshot(codes, refresh):
    snap = json.load(open(SNAP)) if os.path.exists(SNAP) and not refresh else {}
    for c in codes:
        if c not in snap:
            snap[c] = fetch(c)
            time.sleep(0.3)
    json.dump(snap, open(SNAP, 'w'), indent=1, sort_keys=True)
    return snap


def unit_price(prices, qty):
    best = prices[0][1]
    for start, price in prices:
        if qty >= start:
            best = price
    return best


def xray_fee(n):
    for limit, p in XRAY:
        if n <= limit:
            return n * p
    return n * 0.33


def scenario(rows, snap, boards):
    parts_total, lines = 0.0, []
    for r in rows:
        c, q = r['LCSC Part #'], int(r['Qty'])
        if not c:
            lines.append((r, None, None, None))
            continue
        s = snap[c]
        need = q * boards
        qty = max(need + s['loss'], s['least'], s['minbuy'])
        up = unit_price(s['prices'], qty)
        cost = qty * up
        parts_total += cost
        lines.append((r, qty, up, cost))
    refs = len({r['LCSC Part #'] for r in rows if r['LCSC Part #']}) + 1   # + TC358743 (fournie, mais charge feeder)
    asm = {'setup': FEES['setup'], 'pochoir': FEES['stencil'], 'feeders': refs * FEES['feeder_per_ref'],
           'smt': SMT_JOINTS * boards * FEES['smt_per_joint'], 'manuel': MANUAL_JOINTS * boards * FEES['manual_per_joint'],
           'main-d-oeuvre': FEES['hand_labor'], 'confirmation': FEES['confirm_placement'],
           'gabarits': FEES['fixture'], 'emballage': FEES['packing']}
    base = sum(asm.values())
    xr = {k: xray_fee(v * boards) for k, v in XRAY_PER_BOARD.items()}
    return parts_total, lines, asm, base, xr


def main():
    rows = list(csv.DictReader(open(BOM)))
    snap = load_snapshot(sorted({r['LCSC Part #'] for r in rows if r['LCSC Part #']}), '--refresh' in sys.argv)
    res = {}
    for boards in (8, 20):
        parts, lines, asm, base, xr = scenario(rows, snap, boards)
        res[boards] = (parts, asm, base, xr)
        print(f'\n== {boards} cartes assemblees ==')
        print(f'composants (hors TC358743) : {parts:7.2f} $  -> {parts / boards:6.2f} $/carte')
        for k, v in asm.items():
            print(f'  assemblage {k:14s}: {v:7.2f} $')
        print(f'assemblage hors rayons X   : {base:7.2f} $  -> {base / boards:6.2f} $/carte')
        for k, v in xr.items():
            print(f'  rayons X ({k:9s})   : {v:7.2f} $  -> {v / boards:6.2f} $/carte')
        lo = (parts + base + xr['bga_qfn']) / boards
        hi = (parts + base + xr['avec_uson']) / boards
        print(f'TOTAL par carte, hors PCB nu / TC358743 / ecran / transport : {lo:.2f} a {hi:.2f} $')
        if boards == 8:
            with open(OUT, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['Comment', 'Designator', 'LCSC Part #', 'MPN', 'Qty/carte', 'Biblio JLCPCB', 'Stock JLCPCB',
                            f'Qte commandee ({boards} cartes)', 'Prix unitaire USD', 'Cout ligne USD', 'Cout/carte USD', 'Prix lu le'])
                for r, qty, up, cost in lines:
                    c = r['LCSC Part #']
                    if qty is None:
                        w.writerow([r['Comment'], r['Designator'], '', r['MPN'], r['Qty'], '', '', '', 'A DEVIS (broker)', '', '', ''])
                    else:
                        s = snap[c]
                        w.writerow([r['Comment'], r['Designator'], c, r['MPN'], r['Qty'], s['lib'], s['stock'], qty, up,
                                    f'{cost:.4f}', f'{cost / boards:.4f}', s['date']])
    print('\necrit', OUT)


if __name__ == '__main__':
    main()
