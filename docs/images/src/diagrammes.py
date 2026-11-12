#!/usr/bin/env python3
"""Genere les diagrammes SVG du README (blocs + arbre d'alimentation).
Usage : python3 diagrammes.py  puis rsvg-convert -w 1600 x.svg -o x.png"""
import os

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, MUTED, LINE = '#1c2430', '#5b6675', '#7b8794'
FILL = {'soc': '#dbe8ff', 'video': '#ffe6cc', 'usb': '#e3f4e1', 'net': '#e8e0f7', 'pwr': '#fff3c4',
        'io': '#eef1f5', 'ext': '#ffffff'}
STROKE = {'soc': '#2f6fde', 'video': '#d9822b', 'usb': '#3d9a50', 'net': '#7a55c7', 'pwr': '#c79a00',
          'io': '#7b8794', 'ext': '#7b8794'}


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h = w, h
        self.el = [f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
                   f'<text x="32" y="46" font-size="26" font-weight="700" fill="{INK}">{title}</text>']

    def box(self, x, y, w, h, title, sub='', kind='io', dashed=False):
        dash = ' stroke-dasharray="7 5"' if dashed else ''
        self.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{FILL[kind]}" '
                       f'stroke="{STROKE[kind]}" stroke-width="2"{dash}/>')
        lines = sub.split('|') if sub else []
        ty = y + h / 2 - 9 * len(lines) + 6
        self.el.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="17" '
                       f'font-weight="700" fill="{INK}">{title}</text>')
        for i, s in enumerate(lines):
            self.el.append(f'<text x="{x + w / 2}" y="{ty + 20 + i * 17}" text-anchor="middle" '
                           f'font-size="13.5" fill="{MUTED}">{s}</text>')

    def link(self, pts, label='', both=False, lx=None, ly=None, color=LINE):
        d = 'M' + ' L'.join(f'{x},{y}' for x, y in pts)
        start = ' marker-start="url(#a)"' if both else ''
        self.el.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2" '
                       f'marker-end="url(#a)"{start}/>')
        if label:
            (x1, y1), (x2, y2) = pts[0], pts[1]
            lx = (x1 + x2) / 2 if lx is None else lx
            ly = (y1 + y2) / 2 - 7 if ly is None else ly
            self.el.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="13" fill="{INK}" '
                           f'paint-order="stroke" stroke="#ffffff" stroke-width="4">{label}</text>')

    def note(self, x, y, s, size=13):
        self.el.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{MUTED}">{s}</text>')

    def save(self, name):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'font-family="DejaVu Sans, Arial, sans-serif">'
                f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                f'fill="{LINE}"/></marker></defs>')
        open(os.path.join(OUT, name), 'w').write(head + ''.join(self.el) + '</svg>\n')


def blocs():
    s = Svg(1500, 800, 'openKVM v1 (sans ecran) - diagramme de blocs')
    s.box(30, 90, 200, 330, '', kind='ext', dashed=True)
    s.note(64, 116, 'Machine cible', 15)
    s.box(55, 150, 150, 70, 'Sortie HDMI', kind='video')
    s.box(55, 300, 150, 70, 'Port USB', kind='usb')
    s.box(300, 150, 150, 70, 'J3 HDMI A', '+ 3 x TPD4E05U06', 'video')
    s.box(520, 130, 190, 110, 'TC358743XBG', 'HDMI vers CSI-2|EDID emule|osc. 27 MHz', 'video')
    s.box(300, 300, 150, 70, 'J1 USB-C CIBLE', 'donnees + 5 V', 'usb')
    s.box(300, 470, 150, 70, 'J2 USB-C EXT', 'alim + debug', 'usb')
    s.box(790, 110, 300, 450, 'ESP32-P4NRW32X', 'RISC-V double coeur 400 MHz|32 Mo PSRAM integree|'
          'encodeur H.264 materiel|firmware : fork jetkvm/mini (MIT)', 'soc')
    s.box(1180, 100, 130, 70, 'IP101GRI', 'PHY 10/100', 'net')
    s.box(1350, 100, 120, 70, 'J4 RJ45', 'magnetiques', 'net')
    s.box(1180, 210, 290, 62, 'J5 microSD', 'slot SDMMC 0, UHS-I : images ISO', 'io')
    s.box(1180, 312, 290, 62, 'LED alim + LED etat', 'verte sur le 5 V ; jaune sur GPIO6', 'io')
    s.box(1180, 414, 290, 62, 'Bouton FN', '1 lateral ; BOOT interne ; pas d ecran', 'io')
    s.box(1180, 516, 290, 62, 'Flash SPI 16 Mo', 'GD25Q128E : firmware + OTA', 'io')
    s.link([(205, 185), (300, 185)], 'TMDS')
    s.link([(450, 185), (520, 185)])
    s.link([(710, 160), (790, 160)], 'CSI-2', lx=750, ly=150)
    s.link([(710, 215), (790, 215)], 'I2C', both=True, lx=750, ly=206)
    s.link([(205, 335), (300, 335)], 'USB', both=True)
    s.link([(450, 335), (790, 335)], 'USB 2.0 HS : clavier, souris, stockage, audio', both=True)
    s.link([(450, 505), (790, 505)], 'USB Full Speed : serie / JTAG, flashage', both=True)
    s.link([(1090, 135), (1180, 135)], 'RMII', both=True)
    s.link([(1310, 135), (1350, 135)], both=True)
    s.link([(1090, 241), (1180, 241)], 'SD 4 bits', both=True)
    s.link([(1090, 343), (1180, 343)], 'SPI')
    s.link([(1180, 445), (1090, 445)], 'GPIO')
    s.link([(1090, 547), (1180, 547)], 'QSPI', both=True)
    s.box(300, 640, 190, 80, 'OU ideal 5 V', '2 x LM66100|cible ou EXT', 'pwr')
    s.box(560, 640, 170, 80, 'Buck 3,3 V', 'TLV62569', 'pwr')
    s.box(800, 640, 170, 80, 'Buck coeur', 'TLV62569|pilote par le P4', 'pwr')
    s.box(1040, 640, 170, 80, 'Buck 1,2 V', 'TLV62569|TC358743', 'pwr')
    s.link([(300, 352), (268, 352), (268, 665), (300, 665)], '')
    s.link([(375, 540), (375, 640)], '')
    s.note(180, 600, 'VBUS 5 V')
    s.note(385, 600, 'VBUS 5 V')
    s.link([(490, 680), (560, 680)], '5V_SYS', ly=670)
    s.link([(730, 680), (800, 680)], '3V3', ly=670)
    s.link([(885, 640), (885, 560)], 'VDD_HP', lx=930, ly=606)
    s.link([(525, 680), (525, 760), (1125, 760), (1125, 720)], '5V_SYS', lx=825, ly=752)
    s.note(1230, 672, 'Tout le reste est en 3,3 V.')
    s.note(1230, 692, 'Budget estime : 0,52 a 0,57 A sous 5 V.')
    s.save('diagramme-blocs.svg')


def alim():
    s = Svg(1500, 560, "openKVM v1 - arbre d'alimentation")
    s.box(40, 110, 200, 70, 'J1 USB-C CIBLE', 'VBUS 5 V, Rd 5,1 k', 'usb')
    s.box(40, 250, 200, 70, 'J2 USB-C EXT', 'VBUS 5 V, Rd 5,1 k', 'usb')
    s.box(320, 110, 170, 70, 'U3 LM66100', 'diode ideale', 'pwr')
    s.box(320, 250, 170, 70, 'U4 LM66100', 'diode ideale', 'pwr')
    s.box(570, 180, 150, 70, '5V_SYS', 'TVS en amont', 'io')
    s.box(800, 90, 190, 70, 'U5 TLV62569', '3,3 V : 100k / 22k', 'pwr')
    s.box(1070, 90, 190, 70, 'U2 TLV62569', 'VDD_HP ~1,1 V|EN et FB : P4', 'pwr')
    s.box(1320, 90, 150, 70, 'Coeur P4', 'VDD_HP_0..3', 'soc')
    s.box(800, 215, 300, 90, 'Rail 3V3', 'P4 (E/S, LDO, USB PHY)|TC358743 (AVDD33, VDDIO)|'
          'IP101GRI, microSD, oscillateur', 'io')
    s.box(1160, 215, 310, 90, 'LDO internes du P4', 'VDDO_FLASH 3,3 V  -  VDDO_PSRAM 1,9 V|'
          'VDDO_3 2,5 V : MIPI + AVDD25|VDDO_4 3,3 / 1,8 V : E/S microSD', 'soc')
    s.box(800, 400, 190, 70, 'U6 TLV62569', '1,2 V : 100k / 100k', 'pwr')
    s.box(1070, 400, 400, 70, 'TC358743 : VDDC, VDD_MIPI, AVDD12', 'via 3 ferrites 600 ohms, ~0,18 A', 'video')
    s.link([(240, 145), (320, 145)])
    s.link([(240, 285), (320, 285)])
    s.link([(490, 145), (530, 145), (530, 205), (570, 205)])
    s.link([(490, 285), (530, 285), (530, 228), (570, 228)])
    s.link([(720, 205), (760, 205), (760, 125), (800, 125)])
    s.link([(720, 228), (760, 228), (760, 435), (800, 435)])
    s.link([(990, 125), (1070, 125)], '3V3')
    s.link([(1260, 125), (1320, 125)])
    s.link([(895, 160), (895, 215)])
    s.link([(1100, 260), (1160, 260)])
    s.link([(990, 435), (1070, 435)], '1V2')
    s.note(40, 400, 'Les deux LM66100 ont leur broche CE croisee :')
    s.note(40, 420, "la source la plus haute alimente, l'autre est isolee")
    s.note(40, 440, '(pas de retour de courant vers la machine cible).')
    s.note(40, 490, 'Le buck 1,2 V est valide par le 3,3 V : il demarre apres lui.')
    s.save('arbre-alimentation.svg')

blocs()
alim()
