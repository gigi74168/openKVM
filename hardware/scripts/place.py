#!/usr/bin/env python3
"""Placement automatique des composants non fixes d'openKVM, sur les deux faces.

Principe : chaque composant vise les pastilles deja placees qui partagent ses nets
(les decouplages visent une broche d'alimentation precise de leur puce), puis on
cherche l'emplacement libre le plus proche sur une grille d'occupation.
Les passifs des puces a pas fin (U1, U8, U9) vont dessous, sous la puce.
"""
import math

import numpy as np
import pcbnew

RES = 0.05                       # mm par cellule de la grille d'occupation
GAP = 0.12                       # marge ajoutee autour de chaque zone de garde
POWER = {'GND', '3V3', '5V_SYS', '1V2'}
UNDER = {'U1', 'U8', 'U9'}       # puces dont les passifs vont sur la face inferieure
ALIAS = {'Decouplage P4 (au plus pres des broches)': 'ESP32-P4', 'Reset, boot, bouton, LED': 'ESP32-P4'}
ROTS = (0, 90, 180, 270)


def mm(v):
    return pcbnew.ToMM(v)


class Placer:
    def __init__(self, board, w, h, loader):
        self.b, self.w, self.h, self.load = board, w, h, loader
        n = (int(round(h / RES)), int(round(w / RES)))
        self.occ = {'F': np.zeros(n, bool), 'B': np.zeros(n, bool)}
        self.pads = {}            # net -> liste (x, y, ref, groupe)
        self.claims = {}          # (ref, x, y) -> nombre de composants qui visent cette pastille
        self.geo = {}             # (fp, rot, face) -> (rect, {pad: (dx, dy)})
        self.where = {}           # ref -> (face, x, y, rot)
        self.scratch = pcbnew.BOARD()   # Flip() exige une empreinte rattachee a une carte
        self.scratch.SetCopperLayerCount(4)

    # ------------------------------------------------------------ occupation
    def block(self, side, x0, y0, x1, y1):
        a = self.occ[side]
        i0, i1 = max(0, int(math.floor(y0 / RES))), min(a.shape[0], int(math.ceil(y1 / RES)))
        j0, j1 = max(0, int(math.floor(x0 / RES))), min(a.shape[1], int(math.ceil(x1 / RES)))
        if i1 > i0 and j1 > j0:
            a[i0:i1, j0:j1] = True

    def block_circle(self, side, cx, cy, r):
        a = self.occ[side]
        yy, xx = np.ogrid[:a.shape[0], :a.shape[1]]
        a[(xx * RES - cx) ** 2 + (yy * RES - cy) ** 2 <= r * r] = True

    def free(self, side, x0, y0, x1, y1):
        if x0 < 0 or y0 < 0 or x1 > self.w or y1 > self.h:
            return False
        a = self.occ[side]
        return not a[int(math.floor(y0 / RES)):int(math.ceil(y1 / RES)),
                     int(math.floor(x0 / RES)):int(math.ceil(x1 / RES))].any()

    # -------------------------------------------------------------- geometrie
    def geometry(self, fp, rot, side):
        key = (fp, rot, side)
        if key not in self.geo:
            f = self.load(fp)
            self.scratch.Add(f)
            f.SetPosition(pcbnew.VECTOR2I(0, 0))
            if side == 'B':
                f.Flip(pcbnew.VECTOR2I(0, 0), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            f.SetOrientationDegrees(rot)
            f.BuildCourtyardCaches()
            cy = f.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
            bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
            for p in f.Pads():          # les pastilles debordent parfois de la zone de garde
                bb.Merge(p.GetBoundingBox())
            rect = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
            pads = {}
            for p in f.Pads():
                pads.setdefault(p.GetNumber(), (mm(p.GetPosition().x), mm(p.GetPosition().y)))
            self.geo[key] = (rect, pads)
        return self.geo[key]

    def commit(self, part, side, x, y, rot, f):
        """Enregistre un composant pose : occupation, pastilles disponibles comme cibles."""
        rect, _ = self.geometry(part['fp'], rot, side)
        self.block(side, x + rect[0] - GAP, y + rect[1] - GAP, x + rect[2] + GAP, y + rect[3] + GAP)
        group = ALIAS.get(part['group'], part['group'])
        for p in f.Pads():
            px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
            net = part['pins'].get(p.GetNumber())
            if net and net != 'NC':
                self.pads.setdefault(net, []).append((px, py, part['ref'], group))
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = p.GetBoundingBox()   # un trou traverse : il gene aussi l'autre face
                other = 'B' if side == 'F' else 'F'
                self.block(other, mm(bb.GetLeft()) - 0.45, mm(bb.GetTop()) - 0.45, mm(bb.GetRight()) + 0.45, mm(bb.GetBottom()) + 0.45)
        self.where[part['ref']] = (side, x, y, rot)

    # ------------------------------------------------------------------ cibles
    def targets(self, part):
        """Pour chaque broche : la pastille deja posee a viser. Renvoie {broche: (x, y, ref)}."""
        group = ALIAS.get(part['group'], part['group'])
        out = {}
        for pin, net in part['pins'].items():
            if net in ('NC', 'GND'):
                continue
            cands = self.pads.get(net, [])
            if net in POWER:
                cands = [c for c in cands if c[3] == group]
            if not cands:
                continue
            others = [v for v in out.values()]
            def score(c):
                d = min((math.hypot(c[0] - o[0], c[1] - o[1]) for o in others), default=0)
                return (self.claims.get((c[2], c[0], c[1]), 0), d)
            best = min(cands, key=score)
            out[pin] = (best[0], best[1], best[2])
        return out

    def place(self, part, f, prefer=None, radius=14.0):
        tg = self.targets(part)
        if not tg:
            return False
        tx = sum(t[0] for t in tg.values()) / len(tg)
        ty = sum(t[1] for t in tg.values()) / len(tg)
        under = any(t[2] in UNDER for t in tg.values())
        sides = [prefer] if prefer else (['B'] if under else ['F', 'B'])
        best = None
        for si, side in enumerate(sides):
            limit = radius if (si == len(sides) - 1) else 3.5
            found = self.search(part, side, tx, ty, tg, limit)
            if found:
                best = (side,) + found
                break
        if not best:
            return False
        side, x, y, rot = best
        self.b.Add(f)
        if side == 'B':
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        for t in tg.values():
            k = (t[2], t[0], t[1])
            self.claims[k] = self.claims.get(k, 0) + 1
        self.commit(part, side, x, y, rot, f)
        return True

    def search(self, part, side, tx, ty, tg, limit):
        step = 0.2
        geos = [(r,) + self.geometry(part['fp'], r, side) for r in ROTS]
        best, d_stop = None, None
        nmax = int(limit / step)
        cells = sorted(((math.hypot(i, j) * step, i, j) for i in range(-nmax, nmax + 1) for j in range(-nmax, nmax + 1)
                        if math.hypot(i, j) <= nmax), key=lambda c: c[0])
        gx, gy = round(tx / step) * step, round(ty / step) * step
        for d, i, j in cells:
            if d_stop is not None and d > d_stop:
                break
            x, y = gx + i * step, gy + j * step
            for rot, rect, pads in geos:
                if not self.free(side, x + rect[0] - GAP, y + rect[1] - GAP, x + rect[2] + GAP, y + rect[3] + GAP):
                    continue
                cost = sum(math.hypot(x + pads[p][0] - t[0], y + pads[p][1] - t[1]) for p, t in tg.items() if p in pads)
                if best is None or cost < best[0]:
                    best = (cost, x, y, rot)
                if d_stop is None:
                    d_stop = d + 0.8
        return best[1:] if best else None
