#!/usr/bin/env python3
"""Verifie l'orientation de chaque empreinte par rapport a celle de la bibliotheque JLCPCB/EasyEDA.

JLCPCB pose les composants selon l'empreinte de SA bibliotheque (celle d'EasyEDA). Pour chaque
reference LCSC de la BOM, on telecharge cette empreinte (easyeda2kicad) et on la compare, pastille
par pastille (meme numero), a la notre. On en deduit la correction de rotation et de position a
appliquer dans le fichier de placement (CPL).  Resultat : fabrication/corrections-cpl.json

Usage : python3 check_orientation.py [dossier_cache]
"""
import glob
import json
import math
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
KICAD_FP = '/usr/share/kicad/footprints'
OUT = os.path.join(HW, 'fabrication', 'corrections-cpl.json')


def load(fp):
    lib, name = fp.split(':')
    path = os.path.join(HW, 'lib', 'openkvm.pretty') if lib == 'openkvm' else os.path.join(KICAD_FP, lib + '.pretty')
    return pcbnew.FootprintLoad(path, name)


def pads(f, rot=0):
    f.SetOrientationDegrees(rot)
    out = {}
    for p in f.Pads():
        if not p.GetNumber():
            continue
        out.setdefault(p.GetNumber(), []).append((pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)))
    return {k: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v)) for k, v in out.items()}


def easyeda(code, cache):
    base = os.path.join(cache, code)
    if not glob.glob(base + '.pretty/*.kicad_mod'):
        subprocess.run(['easyeda2kicad', f'--lcsc_id={code}', '--footprint', '--output', base],
                       capture_output=True, text=True, timeout=120)
    files = glob.glob(base + '.pretty/*.kicad_mod')
    if not files:
        return None
    return pcbnew.FootprintLoad(os.path.dirname(files[0]), os.path.basename(files[0])[:-10])


def compare(ours, ref):
    """Renvoie (rotation a ajouter, decalage x, decalage y, erreur max en mm, pastilles comparees)."""
    r = pads(ref, 0)
    best = None
    for c in (0, 90, 180, 270):
        o = pads(ours, c)
        common = sorted(set(o) & set(r))
        if len(common) < 2:
            return None
        ox = sum(r[k][0] - o[k][0] for k in common) / len(common)
        oy = sum(r[k][1] - o[k][1] for k in common) / len(common)
        err = max(math.hypot(r[k][0] - o[k][0] - ox, r[k][1] - o[k][1] - oy) for k in common)
        if best is None or err < best[3] - 1e-6:
            best = ((-c) % 360, ox, oy, err, len(common))
    return best


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, 'build', 'easyeda')
    os.makedirs(cache, exist_ok=True)
    parts = json.load(open(os.path.join(HW, 'exports', 'design.json')))['parts']
    seen, res, bad = {}, {}, 0
    for p in parts:
        if p['dnp'] or not p['lcsc']:
            continue
        key = (p['fp'], p['lcsc'])
        seen.setdefault(key, []).append(p['ref'])
    print(f'{"empreinte":44s} {"LCSC":10s} rot    dx     dy    err  n  etat')
    for (fp, code), refs in sorted(seen.items()):
        ref = easyeda(code, cache)
        name = fp.split(':')[1]
        if ref is None:
            print(f'{name[:44]:44s} {code:10s}  ?     -      -      -   -  EMPREINTE JLCPCB INTROUVABLE ({",".join(refs)})')
            res[f'{fp}|{code}'] = {'rotation': None, 'refs': refs, 'etat': 'non verifie'}
            bad += 1
            continue
        c = compare(load(fp), ref)
        if c is None:
            print(f'{name[:44]:44s} {code:10s}  ?  numeros de pastilles differents ({",".join(refs)})')
            res[f'{fp}|{code}'] = {'rotation': None, 'refs': refs, 'etat': 'non verifie'}
            bad += 1
            continue
        rot, dx, dy, err, n = c
        sym = n == 2
        ok = err < 0.15
        etat = 'ok' if ok else 'GEOMETRIE DIFFERENTE'
        bad += 0 if ok else 1
        print(f'{name[:44]:44s} {code:10s} {rot:3d} {dx:6.2f} {dy:6.2f} {err:6.2f} {n:2d}  {etat}' + ('  (2 broches)' if sym else ''))
        res[f'{fp}|{code}'] = {'rotation': rot, 'dx': round(dx, 3), 'dy': round(dy, 3), 'erreur_mm': round(err, 3),
                               'pastilles': n, 'refs': refs, 'etat': etat}
    json.dump(res, open(OUT, 'w'), indent=1, sort_keys=True, ensure_ascii=False)
    print(f'\n{len(res)} couples empreinte/reference, {bad} a regarder. Ecrit : {OUT}')


if __name__ == '__main__':
    main()
