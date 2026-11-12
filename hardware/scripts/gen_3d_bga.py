#!/usr/bin/env python3
"""Genere un modele 3D simple (VRML) du BGA-64 6x6 mm pas 0,65 du TC358743XBG.

Corps noir + 64 billes. Les cotes viennent de l'empreinte (billes a +/-2,275 mm,
pas 0,65 mm, diametre de pastille 0,3 mm). La hauteur du corps est une valeur
GENERIQUE a verifier avec le dessin mecanique de la fiche technique.
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'lib', 'openkvm.3dshapes', 'BGA-64_8x8_6.0x6.0mm.wrl')
BODY = 6.0          # mm, carre
BODY_H = 0.75       # mm, epaisseur du corps (valeur generique)
STAND = 0.20        # mm, garde au sol sous le corps (hauteur de bille apres refusion, generique)
PITCH = 0.65
BALL_D = 0.35
N = 8
K = 1 / 2.54      # KiCad lit le VRML en unites de 0,1 pouce : 1 unite = 2,54 mm


def sphere(cx, cy, cz, r, seg=10, ring=6):
    pts, idx = [], []
    for i in range(ring + 1):
        phi = math.pi * i / ring
        for j in range(seg):
            th = 2 * math.pi * j / seg
            pts.append((cx + r * math.sin(phi) * math.cos(th), cy + r * math.sin(phi) * math.sin(th), cz + r * math.cos(phi)))
    for i in range(ring):
        for j in range(seg):
            a = i * seg + j
            b = i * seg + (j + 1) % seg
            idx.append((a, b, b + seg, a + seg))
    return pts, idx


def shape(pts, idx, color, spec=0.1):
    p = ' '.join(f'{x * K:.5f} {y * K:.5f} {z * K:.5f},' for x, y, z in pts)
    f = ' '.join(f'{a} {b} {c} {d} -1,' if d is not None else f'{a} {b} {c} -1,' for a, b, c, d in idx)
    return (f'Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} specularColor {spec} {spec} {spec} '
            f'shininess 0.3 }} }} geometry IndexedFaceSet {{ coord Coordinate {{ point [ {p} ] }} coordIndex [ {f} ] '
            f'creaseAngle 0.5 solid FALSE }} }}\n')


def box(x0, y0, z0, x1, y1, z1):
    pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    idx = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return pts, idx


def main():
    h = BODY / 2
    z0, z1 = STAND, STAND + BODY_H
    s = '#VRML V2.0 utf8\n# openKVM : BGA-64 6x6 mm pas 0,65 (modele simplifie, hauteur generique)\n'
    pts, idx = box(-h, -h, z0, h, h, z1)
    # marque de la bille A1 : petit chanfrein visuel (cube sombre) en haut a gauche
    s += shape(pts, idx, '0.08 0.08 0.09')
    mp, mi = box(-h + 0.25, -h + 0.25, z1, -h + 0.65, -h + 0.65, z1 + 0.01)
    s += shape(mp, mi, '0.85 0.85 0.85')
    allp, alli = [], []
    for r in range(N):
        for c in range(N):
            x = (c - (N - 1) / 2) * PITCH
            y = (r - (N - 1) / 2) * PITCH
            sp, si = sphere(x, y, STAND, BALL_D / 2)
            base = len(allp)
            allp += sp
            alli += [(a + base, b + base, cc + base, d + base) for a, b, cc, d in si]
    s += shape(allp, alli, '0.75 0.75 0.78', 0.6)
    open(OUT, 'w').write(s)
    print('ecrit', OUT, os.path.getsize(OUT) // 1024, 'Ko')


if __name__ == '__main__':
    main()
