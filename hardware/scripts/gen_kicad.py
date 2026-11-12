#!/usr/bin/env python3
"""Genere le projet KiCad 9 d'openKVM a partir de design.py.

Sorties (dans hardware/) :
  openkvm.kicad_pro / openkvm.kicad_sch + une feuille par bloc
  lib/openkvm_sym.kicad_sym   symboles generes
  fabrication/openkvm-bom-jlcpcb.csv, exports/netlist.csv, exports/composants.csv

Le schema est en style "etiquettes" : chaque broche porte une etiquette globale
au nom de son net. Pas de fils a suivre, et le fichier reste reproductible.
"""
import csv
import json
import math
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexp import Sym as A, dumps, loads, find, first  # noqa: E402
import design  # noqa: E402

NS = uuid.UUID('6f70656e-4b56-4d00-8000-000000000001')
LIB = 'openkvm_sym'
ALIAS = {'HR911105A': 'HR911105A_C12074'}
TWO_PIN = {'R': ('1', '2'), 'C': ('1', '2'), 'FB': ('1', '2'), 'L': ('1', '2'),
           'TVS': ('2', '1'), 'LED': ('2', '1')}   # (broche gauche, broche droite)
PREFIX = {'R': 'R', 'C': 'C', 'FB': 'FB', 'L': 'L', 'TVS': 'D', 'LED': 'D'}
P = 2.54
LBL = 30.48          # place reservee a une etiquette
CELL_W, CELL_H = 68.58, 6.35
PAPERS = [('A3', 420, 297), ('A2', 594, 420), ('A1', 841, 594), ('A0', 1189, 841)]


def uid(*key):
    return str(uuid.uuid5(NS, '/'.join(str(k) for k in key)))


def n(x):
    return A(('%.4f' % x).rstrip('0').rstrip('.') if '.' in '%.4f' % x else '%d' % x)


def font(size=1.27, *extra):
    return [A('effects'), [A('font'), [A('size'), n(size), n(size)]], *extra]


def hide():
    return [A('hide'), A('yes')]


# --------------------------------------------------------------------------- symboles
def lcsc_pins():
    lib = loads(open(os.path.join(HW, 'lib', 'lcsc_symbols.kicad_sym')).read())

    def pins(sym):
        out = []
        for s in find(sym, 'symbol'):
            out += pins(s)
        for p in find(sym, 'pin'):
            out.append((first(p, 'number')[1], first(p, 'name')[1]))
        return out

    def key(x):
        return (len(x[0]), x[0])

    return {s[1]: sorted(pins(s), key=key) for s in find(lib, 'symbol')}


def stroke(w=0.254):
    return [A('stroke'), [A('width'), n(w)], [A('type'), A('default')]]


def poly(pts, fill='none'):
    return [A('polyline'), [A('pts')] + [[A('xy'), n(x), n(y)] for x, y in pts], stroke(),
            [A('fill'), [A('type'), A(fill)]]]


def rect(x1, y1, x2, y2, fill='background'):
    return [A('rectangle'), [A('start'), n(x1), n(y1)], [A('end'), n(x2), n(y2)], stroke(),
            [A('fill'), [A('type'), A(fill)]]]


def pin(num, name, x, y, ang, length=P):
    return [A('pin'), A('passive'), A('line'), [A('at'), n(x), n(y), n(ang)], [A('length'), n(length)],
            [A('name'), name, font(1.0)], [A('number'), num, font(1.0)]]


def sym_props(prefix):
    out = []
    for k, v in (('Reference', prefix), ('Value', ''), ('Footprint', ''), ('Datasheet', ''),
                 ('Description', '')):
        e = font(1.27) if k in ('Reference', 'Value') else font(1.27, hide())
        out.append([A('property'), k, v, [A('at'), n(0), n(0), n(0)], e])
    return out


def two_pin_symbol(name):
    left, right = TWO_PIN[name]
    g = []
    lead = 1.27
    if name == 'R':
        g = [rect(-2.54, -1.016, 2.54, 1.016, 'none')]
    elif name == 'L':
        g = [rect(-2.54, -1.016, 2.54, 1.016, 'outline')]
    elif name == 'FB':
        g = [rect(-2.54, -1.016, 2.54, 1.016, 'none'), poly([(-1.5, -1.6), (1.5, 1.6)])]
    elif name == 'C':
        g = [poly([(-0.508, -1.778), (-0.508, 1.778)]), poly([(0.508, -1.778), (0.508, 1.778)])]
        lead = 3.302
    else:  # diode : anode a gauche, cathode a droite
        g = [poly([(-1.27, 1.27), (-1.27, -1.27), (1.27, 0), (-1.27, 1.27)]),
             poly([(1.27, 1.27), (1.27, -1.27)])]
        lead = 2.54
        if name == 'LED':
            g += [poly([(0.2, 1.9), (1.2, 2.9)]), poly([(1.2, 1.9), (2.2, 2.9)])]
    body = [A('symbol'), f'{name}_0_1'] + g
    pins = [A('symbol'), f'{name}_1_1', pin(left, '~', -3.81, 0, 0, lead), pin(right, '~', 3.81, 0, 180, lead)]
    return [A('symbol'), name, [A('pin_numbers'), hide()], [A('pin_names'), [A('offset'), n(0)], hide()],
            [A('exclude_from_sim'), A('no')], [A('in_bom'), A('yes')], [A('on_board'), A('yes')],
            *sym_props(PREFIX[name]), body, pins]


def box_geometry(pins):
    left = [p for p in pins if p[2] == 'L']
    right = [p for p in pins if p[2] == 'R']
    rows = max(len(left), len(right))
    wl = max([len(p[1]) for p in left] + [1])
    wr = max([len(p[1]) for p in right] + [1])
    half = math.ceil(((wl + wr) * 1.0 + 6) / 2 / P) * P
    half = max(half, 3 * P)
    top = math.floor(rows / 2) * P
    pos = {}
    for i, p in enumerate(left):
        pos[p[0]] = (-(half + P), top - i * P, 'L')
    for i, p in enumerate(right):
        pos[p[0]] = ((half + P), top - i * P, 'R')
    return dict(half=half, top=top, bottom=top - (rows - 1) * P, pos=pos, rows=rows)


def box_symbol(name, pins, prefix):
    g = box_geometry(pins)
    body = [A('symbol'), f'{name}_0_1', rect(-g['half'], g['top'] + P, g['half'], g['bottom'] - P)]
    ps = [A('symbol'), f'{name}_1_1']
    for num, nm, side in pins:
        x, y, _ = g['pos'][num]
        ps.append(pin(num, nm, x, y, 0 if side == 'L' else 180))
    return [A('symbol'), name, [A('pin_names'), [A('offset'), n(0.762)]],
            [A('exclude_from_sim'), A('no')], [A('in_bom'), A('yes')], [A('on_board'), A('yes')],
            *sym_props(prefix), body, ps]


# --------------------------------------------------------------------------- feuilles
class Sheet:
    def __init__(self, key, title, descr, page, root_uuid):
        self.key, self.title, self.descr, self.page = key, title, descr, page
        self.uuid = uid('sheet', key)
        self.path = f'/{root_uuid}/{self.uuid}'
        self.items = []
        self.used = set()

    def label(self, net, x, y, side):
        rot, just = (180, 'right') if side == 'L' else (0, 'left')
        k = uid(self.key, 'lbl', net, x, y)
        self.items.append(
            [A('global_label'), net, [A('shape'), A('passive')], [A('at'), n(x), n(y), n(rot)],
             font(1.27, [A('justify'), A(just)]), [A('uuid'), k],
             [A('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [A('at'), n(0), n(0), n(0)],
              font(1.27, hide())]])

    def nc(self, x, y):
        self.items.append([A('no_connect'), [A('at'), n(x), n(y)], [A('uuid'), uid(self.key, 'nc', x, y)]])

    def text(self, s, x, y, size=1.27, bold=False):
        f = [A('font'), [A('size'), n(size), n(size)]]
        if bold:
            f.append([A('bold'), A('yes')])
        self.items.append([A('text'), s, [A('exclude_from_sim'), A('no')], [A('at'), n(x), n(y), n(0)],
                           [A('effects'), f, [A('justify'), A('left'), A('bottom')]],
                           [A('uuid'), uid(self.key, 'txt', s, x, y)]])

    def place(self, part, x, y, ref_at, val_at, small):
        self.used.add(part['sym'])
        size = 1.0 if small else 1.27
        props = [
            [A('property'), 'Reference', part['ref'], [A('at'), n(ref_at[0]), n(ref_at[1]), n(0)],
             font(size, [A('justify'), A(ref_at[2])])],
            [A('property'), 'Value', part['value'], [A('at'), n(val_at[0]), n(val_at[1]), n(0)],
             font(size, [A('justify'), A(val_at[2])])],
            [A('property'), 'Footprint', part['fp'], [A('at'), n(x), n(y), n(0)], font(1.27, hide())],
            [A('property'), 'Datasheet', '', [A('at'), n(x), n(y), n(0)], font(1.27, hide())],
            [A('property'), 'Description', part['note'], [A('at'), n(x), n(y), n(0)], font(1.27, hide())],
            [A('property'), 'LCSC', part['lcsc'], [A('at'), n(x), n(y), n(0)], font(1.27, hide())],
            [A('property'), 'MPN', part['mpn'], [A('at'), n(x), n(y), n(0)], font(1.27, hide())],
        ]
        k = uid('sym', part['ref'])
        self.items.append(
            [A('symbol'), [A('lib_id'), f"{LIB}:{part['sym']}"], [A('at'), n(x), n(y), n(0)], [A('unit'), n(1)],
             [A('exclude_from_sim'), A('no')], [A('in_bom'), A('yes')], [A('on_board'), A('yes')],
             [A('dnp'), A('yes' if part['dnp'] else 'no')], [A('uuid'), k], *props,
             *[[A('pin'), num, [A('uuid'), uid('pin', part['ref'], num)]] for num in part['pins']],
             [A('instances'), [A('project'), 'openkvm',
                               [A('path'), self.path, [A('reference'), part['ref']], [A('unit'), n(1)]]]]])


def snap(v):
    return round(v / P) * P


def layout_sheet(sh, parts, syms, symdefs):
    groups = []
    for p in parts:
        hit = [g for g in groups if g[0] == p['group']]
        if hit:
            hit[0][1].append(p)
        else:
            groups.append((p['group'], [p]))
    blocks = []
    for title, ps in groups:
        ics = [p for p in ps if p['sym'] not in TWO_PIN]
        small = [p for p in ps if p['sym'] in TWO_PIN]
        geo = [box_geometry(syms[p['sym']]) for p in ics]
        ic_w = [2 * (g['half'] + P + LBL) for g in geo]
        ic_h = [(g['rows'] + 1) * P + 4 * P for g in geo]
        rows = min(len(small), 26) or 0
        cols = math.ceil(len(small) / 26) if small else 0
        w = max(sum(ic_w), cols * CELL_W, 60)
        h = 10 + (max(ic_h) if ic_h else 0) + rows * CELL_H + 8
        blocks.append(dict(title=title, ics=ics, small=small, geo=geo, ic_w=ic_w, ic_h=ic_h,
                           rows=rows, cols=cols, w=snap(w) + P, h=snap(h) + P))
    for name, pw, ph in PAPERS:
        x, y, rowh, ok = 15.24, 20.32, 0, True
        for b in blocks:
            if x + b['w'] > pw - 12 and x > 15.24:
                x, y, rowh = 15.24, y + rowh + 5.08, 0
            if x + b['w'] > pw - 10 or y + b['h'] > ph - 30:
                ok = False
                break
            b['x'], b['y'] = snap(x), snap(y)
            x += b['w'] + 7.62
            rowh = max(rowh, b['h'])
        if ok:
            break
    for b in blocks:
        bx, by = b['x'], b['y']
        sh.text(b['title'], bx, by, 2.2, True)
        cx = bx
        ich = max(b['ic_h']) if b['ic_h'] else 0
        for p, g, w in zip(b['ics'], b['geo'], b['ic_w']):
            X = snap(cx + w / 2)
            Y = snap(by + 3 * P + P + g['top'] + P)
            sh.place(p, X, Y, (X - g['half'], Y - g['top'] - P - 1.0, 'left'),
                     (X - g['half'], Y - g['bottom'] + P + 2.2, 'left'), False)
            if p['note']:
                sh.text(p['note'], X - g['half'], Y - g['bottom'] + P + 5.4, 1.0)
            for num, net in p['pins'].items():
                px, py, side = g['pos'][num]
                ex, ey = X + px, Y - py
                if net == 'NC':
                    sh.nc(ex, ey)
                else:
                    sh.label(net, ex, ey, side)
            cx += w
        y0 = snap(by + 10 + ich + 2 * P)
        for i, p in enumerate(b['small']):
            col, row = divmod(i, 26)
            X = snap(bx + col * CELL_W + CELL_W / 2)
            Y = round((y0 + row * CELL_H) / 1.27) * 1.27
            sh.place(p, X, Y, (X - 0.6, Y - 1.9, 'right'), (X + 0.6, Y - 1.9, 'left'), True)
            left, right = TWO_PIN[p['sym']]
            sh.label(p['pins'][left], X - 3.81, Y, 'L')
            sh.label(p['pins'][right], X + 3.81, Y, 'R')
    return name


def write_sheet(path, sh, paper, symdefs, extra=None, root=False, title=''):
    lib_syms = [A('lib_symbols')]
    for name in sorted(sh.used):
        s = [x for x in symdefs[name]]
        s[1] = f'{LIB}:{name}'
        lib_syms.append(s)
    doc = [A('kicad_sch'), [A('version'), A('20250114')], [A('generator'), 'openkvm_gen'],
           [A('generator_version'), '9.0'],
           [A('uuid'), sh if isinstance(sh, str) else (sh.uuid if not root else uid('root'))],
           [A('paper'), paper],
           [A('title_block'), [A('title'), title], [A('date'), '2026-11-12'], [A('rev'), '0.1'],
            [A('company'), 'openKVM - CERN-OHL-S-2.0'],
            [A('comment'), n(1), 'Schema preliminaire : revue humaine obligatoire avant fabrication'],
            [A('comment'), n(2), 'Genere par hardware/scripts/gen_kicad.py depuis design.py']],
           lib_syms, *sh.items, *(extra or [])]
    if root:
        doc.append([A('sheet_instances'), [A('path'), '/', [A('page'), '1']]])
    doc.append([A('embedded_fonts'), A('no')])
    open(path, 'w').write(dumps(doc) + '\n')


def main():
    lib_pins = lcsc_pins()
    for a, b in ALIAS.items():
        lib_pins[a] = lib_pins[b]
    syms = design.symbol_pins(lib_pins)
    d = design.build()

    # coherence : chaque broche du symbole est affectee, et inversement
    errors = []
    for p in d.parts:
        if p['sym'] in TWO_PIN:
            continue
        want = {x[0] for x in syms[p['sym']]}
        got = set(p['pins'])
        if want != got:
            errors.append(f"{p['ref']} ({p['sym']}): manquantes={sorted(want - got)} en trop={sorted(got - want)}")
    refs = [p['ref'] for p in d.parts]
    errors += [f'reference en double : {r}' for r in set(refs) if refs.count(r) > 1]
    if errors:
        sys.exit('\n'.join(errors))

    symdefs = {}
    for name in TWO_PIN:
        symdefs[name] = two_pin_symbol(name)
    for p in d.parts:
        if p['sym'] not in symdefs:
            symdefs[p['sym']] = box_symbol(p['sym'], syms[p['sym']], ''.join(c for c in p['ref'] if c.isalpha()))
    libdoc = [A('kicad_symbol_lib'), [A('version'), A('20241209')], [A('generator'), 'openkvm_gen'],
              [A('generator_version'), '9.0']] + [symdefs[k] for k in sorted(symdefs)]
    open(os.path.join(HW, 'lib', f'{LIB}.kicad_sym'), 'w').write(dumps(libdoc) + '\n')

    root_uuid = uid('root')
    root = Sheet('root', 'openKVM', '', 1, root_uuid)
    root.uuid = root_uuid
    extra = []
    root.text('openKVM v1 - KVM-over-IP ESP32-P4', 20.32, 22.86, 4, True)
    root.text('Schema preliminaire rev 0.1 - revue humaine obligatoire avant fabrication.', 20.32, 30.48, 2)
    root.text('Chaque net est porte par une etiquette globale : memes noms = meme connexion.', 20.32, 35.56, 2)
    for i, (key, title, descr) in enumerate(design.SHEETS):
        sh = Sheet(key, title, descr, i + 2, root_uuid)
        parts = [p for p in d.parts if p['sheet'] == key]
        paper = layout_sheet(sh, parts, syms, symdefs)
        write_sheet(os.path.join(HW, f'{key}.kicad_sch'), sh, paper, symdefs, title=f'openKVM - {title}')
        x, y = 25.4 + (i % 3) * 76.2, 50.8 + (i // 3) * 45.72
        extra.append(
            [A('sheet'), [A('at'), n(x), n(y)], [A('size'), n(60.96), n(25.4)],
             [A('exclude_from_sim'), A('no')], [A('in_bom'), A('yes')], [A('on_board'), A('yes')],
             [A('dnp'), A('no')], [A('stroke'), [A('width'), n(0.1524)], [A('type'), A('solid')]],
             [A('fill'), [A('color'), n(0), n(0), n(0), A('0.0000')]], [A('uuid'), sh.uuid],
             [A('property'), 'Sheetname', title, [A('at'), n(x), n(y - 0.8), n(0)],
              font(1.6, [A('justify'), A('left'), A('bottom')])],
             [A('property'), 'Sheetfile', f'{key}.kicad_sch', [A('at'), n(x), n(y + 26.4), n(0)],
              font(1.27, [A('justify'), A('left'), A('top')])],
             [A('instances'), [A('project'), 'openkvm',
                               [A('path'), f'/{root_uuid}', [A('page'), str(i + 2)]]]]])
        root.text(descr, x + 2.54, y + 12.7, 1.4)
    write_sheet(os.path.join(HW, 'openkvm.kicad_sch'), root, 'A4', symdefs, extra, root=True,
                title='openKVM v1 - vue d ensemble')

    pro = {'meta': {'filename': 'openkvm.kicad_pro', 'version': 3},
           'schematic': {'legacy_lib_dir': '', 'legacy_lib_list': []}, 'sheets': [], 'text_variables': {}}
    open(os.path.join(HW, 'openkvm.kicad_pro'), 'w').write(json.dumps(pro, indent=2) + '\n')
    open(os.path.join(HW, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{LIB}.kicad_sym")(options "")(descr "Symboles generes openKVM"))\n'
        '  (lib (name "lcsc_symbols")(type "KiCad")(uri "${KIPRJMOD}/lib/lcsc_symbols.kicad_sym")(options "")(descr "Symboles LCSC/EasyEDA d origine"))\n)\n')
    open(os.path.join(HW, 'fp-lib-table'), 'w').write(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "openkvm")(type "KiCad")(uri "${KIPRJMOD}/lib/openkvm.pretty")(options "")(descr "Empreintes openKVM"))\n)\n')

    # --- exports tabulaires
    os.makedirs(os.path.join(HW, 'fabrication'), exist_ok=True)
    os.makedirs(os.path.join(HW, 'exports'), exist_ok=True)
    groups = {}
    for p in d.parts:
        if p['dnp']:
            continue
        groups.setdefault((p['value'], p['fp'], p['lcsc'], p['mpn']), []).append(p['ref'])

    def refkey(r):
        a = ''.join(c for c in r if c.isalpha())
        return (a, int(''.join(c for c in r if c.isdigit())))

    with open(os.path.join(HW, 'fabrication', 'openkvm-bom-jlcpcb.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'MPN', 'Qty'])
        for (val, fp, lcsc, mpn), rs in sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1], key=refkey)[0])):
            rs = sorted(rs, key=refkey)
            w.writerow([val, ','.join(rs), fp.split(':')[1], lcsc, mpn, len(rs)])
    with open(os.path.join(HW, 'exports', 'composants.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Ref', 'Valeur', 'Feuille', 'Bloc', 'Empreinte', 'LCSC', 'MPN', 'Monte', 'Note'])
        for p in sorted(d.parts, key=lambda p: refkey(p['ref'])):
            w.writerow([p['ref'], p['value'], p['sheet'], p['group'], p['fp'], p['lcsc'], p['mpn'],
                        'non' if p['dnp'] else 'oui', p['note']])
    nets = {}
    for p in d.parts:
        for num, net in p['pins'].items():
            if net != 'NC':
                nets.setdefault(net, []).append(f"{p['ref']}.{num}")
    with open(os.path.join(HW, 'exports', 'netlist.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Net', 'Nb', 'Broches'])
        for net in sorted(nets):
            w.writerow([net, len(nets[net]), ' '.join(nets[net])])
    single = sorted(k for k, v in nets.items() if len(v) < 2)
    print(f'{len(d.parts)} composants, {len(nets)} nets, {len(groups)} lignes de BOM')
    if single:
        print('ATTENTION nets a une seule broche :', single)
    json.dump({'parts': d.parts}, open(os.path.join(HW, 'exports', 'design.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
