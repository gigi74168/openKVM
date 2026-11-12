"""openKVM v1 - source de verite du schema (netlist logique).

Chaque composant, chaque broche et chaque net est decrit ici. `gen_kicad.py`
en derive le schema KiCad, la BOM JLCPCB et les tableaux de documentation.

Sources des circuits :
- coeur ESP32-P4 : Espressif, "ESP32-P4 Hardware Design Guidelines", fig. 1 et 5
- pont HDMI TC358743 : Antmicro hdmi-mipi-bridge (Apache-2.0), feuille "Channel 1"
- brochage P4 : firmware jetkvm/mini (MIT), docs/hardware-variants.md
- PHY IP101GRI et prise HR911105A : fiches techniques constructeur
"""

FP_R = 'Resistor_SMD:R_0402_1005Metric'
FP_C = {'0402': 'Capacitor_SMD:C_0402_1005Metric',
        '0603': 'Capacitor_SMD:C_0603_1608Metric',
        '0805': 'Capacitor_SMD:C_0805_2012Metric'}
FP_FB = 'Inductor_SMD:L_0603_1608Metric'
FP_LED = 'LED_SMD:LED_0603_1608Metric'

# Valeur -> (reference fabricant, code LCSC verifie le 2026-11-12). '' = a choisir au livrable 5.
R_PARTS = {
    '0R': ('0402WGF0000TCE', 'C17168'), '22R': ('0402WGF220JTCE', 'C25092'),
    '33R': ('0402WGF330JTCE', 'C25105'), '470R': ('0402WGF4700TCE', 'C25117'),
    '1k': ('0402WGF1001TCE', 'C11702'), '2k': ('0402WGF2001TCE', 'C4109'),
    '4.7k': ('0402WGF4701TCE', 'C25900'), '5.1k': ('0402WGF5101TCE', 'C25905'),
    '10k': ('0402WGJ0103TCE', 'C25531'), '22k': ('0402WGF2202TCE', 'C25768'),
    '47k': ('0402WGF4702TCE', 'C25792'), '100k': ('0402WGF1003TCE', 'C25741'),
    '4.02k 1%': ('', ''), '6.19k 1%': ('', ''), '499k 1%': ('', ''),
}
C_PARTS = {
    ('18pF', '0402'): ('0402CG180J500NT', 'C1549'), ('22pF', '0402'): ('0402CG220J500NT', 'C1555'),
    ('10nF', '0402'): ('CL05B103KB5NNNC', 'C15195'), ('100nF', '0402'): ('CL05B104KO5NNNC', 'C1525'),
    ('1uF', '0402'): ('CL05A105KA5NQNC', 'C52923'), ('10uF', '0402'): ('CL05A106MQ5NUNC', 'C15525'),
    ('4.7uF', '0603'): ('CL10A475KO8NNNC', 'C19666'), ('10uF', '0603'): ('CL10A106KP8NNNC', 'C19702'),
    ('22uF', '0805'): ('CL21A226MAQNNNE', 'C45783'),
}

SHEETS = [
    ('power', 'Alimentation', 'USB-C, OU ideal 5 V, buck 3,3 V, buck 1,2 V'),
    ('mcu', 'ESP32-P4', 'SoC, flash, quartz, DCDC coeur, boutons, LED, debug'),
    ('hdmi', 'Capture HDMI', 'Connecteur HDMI, ESD, TC358743, oscillateur 27 MHz'),
    ('eth', 'Ethernet', 'PHY IP101GRI, quartz 25 MHz, RJ45 a magnetiques integres'),
    ('periph', 'Peripheriques', 'microSD (UHS-I), ecran SPI, ESD USB'),
]


class Design:
    def __init__(self):
        self.parts = []
        self.count = {}

    def ref(self, prefix):
        self.count[prefix] = self.count.get(prefix, 0) + 1
        return f'{prefix}{self.count[prefix]}'

    def part(self, ref, sym, value, fp, sheet, group, pins, lcsc='', mpn='', dnp=False, note=''):
        self.parts.append(dict(ref=ref, sym=sym, value=value, fp=fp, sheet=sheet, group=group,
                               pins={str(k): v for k, v in pins.items()}, lcsc=lcsc, mpn=mpn,
                               dnp=dnp, note=note))
        return ref

    def R(self, a, b, value, sheet, group, dnp=False, note=''):
        mpn, lcsc = R_PARTS[value]
        return self.part(self.ref('R'), 'R', value, FP_R, sheet, group, {1: a, 2: b}, lcsc, mpn, dnp, note)

    def C(self, a, value, sheet, group, pkg='0402', b='GND', dnp=False, note=''):
        mpn, lcsc = C_PARTS[(value, pkg)]
        return self.part(self.ref('C'), 'C', value, FP_C[pkg], sheet, group, {1: a, 2: b}, lcsc, mpn, dnp, note)

    def FB(self, a, b, sheet, group):
        return self.part(self.ref('FB'), 'FB', '600R@100MHz', FP_FB, sheet, group, {1: a, 2: b},
                         'C85833', 'BLM18KG601SN1D')

    def L(self, a, b, sheet, group):
        return self.part(self.ref('L'), 'L', '2.2uH 2A', 'openkvm:IND-SMD_L3.0-W3.0', sheet, group,
                         {1: a, 2: b}, 'C43389', 'SWPA3015S2R2MT')

    def decap(self, net, values, sheet, group):
        for v in values:
            pkg = '0402'
            if v in ('4.7uF',):
                pkg = '0603'
            if v == '22uF':
                pkg = '0805'
            if v == '10uF*':
                v, pkg = '10uF', '0603'
            self.C(net, v, sheet, group, pkg)


def build():
    d = Design()
    NC = 'NC'

    # ------------------------------------------------------------------ power
    S = 'power'
    for ref, name, vbus, dp, dm in (('J1', 'USB-C CIBLE', 'VBUS_TGT', 'USB_HS_DP', 'USB_HS_DM'),
                                    ('J2', 'USB-C EXT', 'VBUS_EXT', 'USB_FS_CONN_DP', 'USB_FS_CONN_DM')):
        cc1, cc2 = f'{ref}_CC1', f'{ref}_CC2'
        d.part(ref, 'TYPE-C-31-M-12', name, 'openkvm:USB-C_SMD-TYPE-C-31-M-12_1', S, name,
               {'A4B9': vbus, 'B4A9': vbus, 'A1B12': 'GND', 'B1A12': 'GND', 'A5': cc1, 'B5': cc2,
                'A6': dp, 'B6': dp, 'A7': dm, 'B7': dm, 'A8': NC, 'B8': NC,
                '1': 'GND', '2': 'GND', '3': 'GND', '4': 'GND'},
               'C165948', 'TYPE-C-31-M-12')
        d.R(cc1, 'GND', '5.1k', S, name, note='Rd : annonce un peripherique (UFP), 5 V par defaut')
        d.R(cc2, 'GND', '5.1k', S, name)
        d.part(d.ref('D'), 'TVS', 'SMF5.0A', 'openkvm:SOD-123FL_L2.7-W1.8-LS3.8-RD', S, name,
               {1: vbus, 2: 'GND'}, 'C19077497', 'SMF5.0A', note='1 = cathode')
        d.C(vbus, '100nF', S, name)

    G = 'OU ideal 5 V'
    d.part('U3', 'LM66100DCKR', 'LM66100DCKR', 'openkvm:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL', S, G,
           {1: 'VBUS_TGT', 2: 'GND', 3: 'VBUS_EXT', 4: NC, 5: NC, 6: '5V_SYS'},
           'C2869734', 'LM66100DCKR', note='CE croisee : la source la plus haute alimente, l autre est bloquee')
    d.part('U4', 'LM66100DCKR', 'LM66100DCKR', 'openkvm:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL', S, G,
           {1: 'VBUS_EXT', 2: 'GND', 3: 'VBUS_TGT', 4: NC, 5: NC, 6: '5V_SYS'},
           'C2869734', 'LM66100DCKR')
    d.decap('5V_SYS', ['22uF', '100nF'], S, G)

    G = 'Buck 3,3 V'
    d.part('U5', 'TLV62569DBVR', 'TLV62569DBVR', 'openkvm:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR', S, G,
           {1: 'EN_3V3', 2: 'GND', 3: 'SW_3V3', 4: '5V_SYS', 5: 'FB_3V3'}, 'C141836', 'TLV62569DBVR')
    d.R('5V_SYS', 'EN_3V3', '100k', S, G)
    d.L('SW_3V3', '3V3', S, G)
    d.R('3V3', 'FB_3V3', '100k', S, G, note='Vout = 0,6 x (1 + 100k/22k) = 3,33 V')
    d.R('FB_3V3', 'GND', '22k', S, G)
    d.C('3V3', '22pF', S, G, b='FB_3V3', note='avance de phase')
    d.decap('5V_SYS', ['10uF*'], S, G)
    d.decap('3V3', ['22uF', '22uF', '100nF'], S, G)

    G = 'Buck 1,2 V (TC358743)'
    d.part('U6', 'TLV62569DBVR', 'TLV62569DBVR', 'openkvm:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR', S, G,
           {1: 'EN_1V2', 2: 'GND', 3: 'SW_1V2', 4: '5V_SYS', 5: 'FB_1V2'}, 'C141836', 'TLV62569DBVR')
    d.R('3V3', 'EN_1V2', '100k', S, G, note='le 1,2 V demarre apres le 3,3 V')
    d.L('SW_1V2', '1V2', S, G)
    d.R('1V2', 'FB_1V2', '100k', S, G, note='Vout = 0,6 x (1 + 100k/100k) = 1,2 V')
    d.R('FB_1V2', 'GND', '100k', S, G)
    d.C('1V2', '22pF', S, G, b='FB_1V2')
    d.decap('5V_SYS', ['10uF*'], S, G)
    d.decap('1V2', ['22uF', '100nF'], S, G)

    # -------------------------------------------------------------------- mcu
    S = 'mcu'
    G = 'ESP32-P4'
    p4 = {
        1: NC, 2: 'I2C_SDA', 3: 'LCD_MOSI', 4: 'LCD_BL', 5: 'I2C_SCL', 6: 'LED_DBG', 7: 'SD_CD',
        8: 'SD_PWR_EN_N', 9: '3V3', 10: NC, 11: NC, 12: NC, 13: NC, 14: 'LCD_SCLK', 15: NC, 16: NC,
        17: NC, 18: NC, 19: NC, 20: NC, 21: '3V3', 22: 'LCD_DC', 23: 'LCD_RST', 24: 'LCD_CS',
        25: 'BTN_MODE', 26: 'VDD_HP', 27: 'FLASH_CS', 28: 'FLASH_Q', 29: 'FLASH_WP',
        30: 'VDDO_FLASH', 31: 'FLASH_HOLD', 32: 'FLASH_CK', 33: 'FLASH_D', 34: 'DSI_REXT',
        35: NC, 36: NC, 37: NC, 38: NC, 39: NC, 40: NC, 41: 'VDDO_3',
        42: 'CSI_D0_N', 43: 'CSI_D0_P', 44: 'CSI_CLK_P', 45: 'CSI_CLK_N', 46: 'CSI_D1_N',
        47: 'CSI_D1_P', 48: 'CSI_REXT', 49: 'USB_HS_DM', 50: 'USB_HS_DP', 51: 'VDD_USBPHY',
        52: 'USB_FS_DM', 53: 'USB_FS_DP', 54: 'VDD_HP', 55: NC, 56: NC, 57: 'RMII_CRS_DV',
        58: 'RMII_RXD0', 59: 'VDDO_PSRAM', 60: 'RMII_RXD1', 61: 'RMII_MDC', 62: '3V3',
        63: 'TC_RESETN', 64: 'TC_INT', 65: 'RMII_TXD0', 66: 'RMII_TXD1_BOOT', 67: 'VDDO_PSRAM',
        68: NC, 69: 'UART0_TX', 70: 'UART0_RX', 71: 'VDDO_FLASH', 72: 'VDDO_PSRAM', 73: 'VDDO_3',
        74: 'VDDO_4', 75: '3V3', 76: 'VDD_HP', 77: '3V3', 78: 'FB_DCDC', 79: 'EN_DCDC',
        80: 'SD_D0', 81: 'SD_D1', 82: 'SD_D2', 83: 'SD_D3', 84: 'SD_CLK', 85: 'VDDO_4',
        86: 'SD_CMD', 87: NC, 88: NC, 89: 'BTN_NAV', 90: NC, 91: 'VDD_HP', 92: 'RMII_TX_EN',
        93: 'RMII_REF_CLK', 94: 'PHY_RST', 95: 'RMII_MDIO', 96: '3V3', 97: NC, 98: NC,
        99: 'XTAL_N', 100: 'XTAL_P', 101: '3V3', 102: 'VDD_BAT', 103: 'CHIP_PU', 104: NC, 105: 'GND',
    }
    d.part('U1', 'ESP32-P4NRW32X', 'ESP32-P4NRW32X', 'openkvm:QFN-104_L10.0-W10.0-P0.35-TL-EP7.5',
           S, G, p4, 'C54540373', 'ESP32-P4NRW32X', note='revision de puce >= 3.x obligatoire')

    G = 'Decouplage P4 (au plus pres des broches)'
    d.decap('3V3', ['10uF*', '100nF'], S, G)             # VDD_LP (9)
    d.decap('3V3', ['100nF'], S, G)                      # VDD_IO_0 (21)
    d.decap('3V3', ['100nF'], S, G)                      # VDD_IO_4 (62)
    d.decap('3V3', ['100nF'], S, G)                      # VDD_IO_6 (96)
    d.decap('3V3', ['100nF'], S, G)                      # VDD_ANA (101)
    d.decap('3V3', ['10uF*', '100nF'], S, G)             # VDD_LDO (75) + VDD_DCDCC (77)
    d.R('3V3', 'VDD_BAT', '0R', S, G, note='VDD_BAT ne doit jamais flotter')
    d.decap('VDD_BAT', ['10uF*', '100nF'], S, G)
    d.R('3V3', 'VDD_USBPHY', '0R', S, G)
    d.decap('VDD_USBPHY', ['10nF', '100nF', '4.7uF'], S, G)
    d.decap('VDD_HP', ['10uF*', '100nF', '100nF', '100nF', '100nF'], S, G)   # VDD_HP_0..3
    d.decap('VDDO_FLASH', ['1uF', '1uF', '100nF'], S, G)  # sortie LDO + VDD_FLASHIO (30)
    d.decap('VDDO_PSRAM', ['1uF', '1uF', '100nF', '1uF', '100nF'], S, G)  # LDO + VDD_PSRAM_0/1
    d.decap('VDDO_3', ['1uF', '10nF', '100nF', '1uF'], S, G)  # LDO + VDD_MIPI_DPHY (41)
    d.decap('VDDO_4', ['1uF', '100nF'], S, G)             # LDO + VDD_IO_5 (85)
    d.R('DSI_REXT', 'GND', '4.02k 1%', S, G)
    d.R('CSI_REXT', 'GND', '4.02k 1%', S, G)

    G = 'DCDC coeur (pilote par le P4)'
    d.part('U2', 'TLV62569DBVR', 'TLV62569DBVR', 'openkvm:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR', S, G,
           {1: 'EN_DCDC', 2: 'GND', 3: 'SW_HP', 4: '3V3', 5: 'FB_DCDC'}, 'C141836', 'TLV62569DBVR',
           note='modele valide par Espressif ; pas de variante a decharge de sortie')
    d.L('SW_HP', 'VDD_HP', S, G)
    d.R('VDD_HP', 'FB_DCDC', '499k 1%', S, G)
    d.R('FB_DCDC', 'GND', '499k 1%', S, G)
    d.C('VDD_HP', '22pF', S, G, b='FB_DCDC')
    d.decap('3V3', ['4.7uF'], S, G)
    d.decap('VDD_HP', ['22uF'], S, G)

    G = 'Quartz 40 MHz'
    d.part('Y1', 'XTAL4', '40MHz 10ppm', 'openkvm:OSC-SMD_4P-L3.2-W2.5-BL_SIT8008BI', S, G,
           {1: 'XTAL_A', 2: 'GND', 3: 'XTAL_B', 4: 'GND'}, 'C9010', 'X322540MPB4SI')
    d.R('XTAL_A', 'XTAL_P', '0R', S, G)
    d.R('XTAL_B', 'XTAL_N', '0R', S, G)
    d.C('XTAL_A', '22pF', S, G, note='CL = 15 pF : valeur a ajuster a la mesure')
    d.C('XTAL_B', '22pF', S, G)

    G = 'Flash SPI 16 Mo'
    d.part('U7', 'GD25Q128ESIGR', 'GD25Q128ESIGR', 'openkvm:SOP-8_L5.3-W5.3-P1.27-LS8.0-BL', S, G,
           {1: 'FLASH_CS', 2: 'FLASH_Q', 3: 'FLASH_WP', 4: 'GND', 5: 'FLASH_D', 6: 'FLASH_CK',
            7: 'FLASH_HOLD', 8: 'VDDO_FLASH'}, 'C2928891', 'GD25Q128ESIGR')
    d.R('VDDO_FLASH', 'FLASH_CS', '10k', S, G)
    d.decap('VDDO_FLASH', ['100nF'], S, G)

    G = 'Reset, boot, boutons, LED'
    d.R('3V3', 'CHIP_PU', '10k', S, G, note='RC de demarrage 10k / 1 uF ; pas de bouton RESET, CHIP_PU est sur J8')
    d.C('CHIP_PU', '1uF', S, G)
    d.R('3V3', 'RMII_TXD1_BOOT', '10k', S, G, note='GPIO35 = strap BOOT, aussi RMII TXD1')
    d.part('SW3', 'SW4', 'BOOT', 'openkvm:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5', S, G,
           {1: 'RMII_TXD1_BOOT', 2: 'RMII_TXD1_BOOT', 3: 'GND', 4: 'GND'}, 'C318884', 'TS-1187A-B-A-B')
    d.part('SW1', 'SWSIDE', 'NAV', 'openkvm:KEY-SMD_TS-1101VS-C-A-A', S, G,
           {1: 'GND', 2: 'GND', 3: 'BTN_NAV', 4: 'GND'}, 'C318936', 'TS-1101VS-C-A-A')
    d.R('VDDO_4', 'BTN_NAV', '10k', S, G, note='GPIO47 est dans le domaine VDD_IO_5 (VDDO_4)')
    d.part('SW2', 'SWSIDE', 'MODE', 'openkvm:KEY-SMD_TS-1101VS-C-A-A', S, G,
           {1: 'GND', 2: 'GND', 3: 'BTN_MODE', 4: 'GND'}, 'C318936', 'TS-1101VS-C-A-A')
    d.R('3V3', 'BTN_MODE', '10k', S, G)
    d.R('LED_DBG', 'LED_DBG_A', '1k', S, G)
    d.part('D3', 'LED', 'LED verte debug', FP_LED, S, G, {1: 'GND', 2: 'LED_DBG_A'},
           'C12624', 'KT-0603G', note='1 = cathode, 2 = anode')
    d.R('3V3', 'I2C_SDA', '4.7k', S, G)
    d.R('3V3', 'I2C_SCL', '4.7k', S, G)
    d.part('J8', 'HDR6', 'DEBUG UART', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',
           S, G, {1: '3V3', 2: 'UART0_TX', 3: 'UART0_RX', 4: 'CHIP_PU', 5: 'RMII_TXD1_BOOT', 6: 'GND'},
           dnp=True, note='non monte : pastilles de test')

    # ------------------------------------------------------------------- hdmi
    S = 'hdmi'
    G = 'Connecteur HDMI'
    d.part('J3', 'HDMI-001', 'HDMI A', 'openkvm:HDMI-SMD_19P-P0.50-H-F', S, G,
           {1: 'HDMI_D2_P', 2: 'GND', 3: 'HDMI_D2_N', 4: 'HDMI_D1_P', 5: 'GND', 6: 'HDMI_D1_N',
            7: 'HDMI_D0_P', 8: 'GND', 9: 'HDMI_D0_N', 10: 'HDMI_CK_P', 11: 'GND', 12: 'HDMI_CK_N',
            13: 'HDMI_CEC', 14: NC, 15: 'HDMI_SCL', 16: 'HDMI_SDA', 17: 'GND', 18: 'HDMI_5V',
            19: 'HDMI_HPD', 20: 'GND', 21: 'GND', 22: 'GND', 23: 'GND'},
           'C138388', 'HDMI-001 19PCBTP')
    esd = 'openkvm:USON-10_L2.5-W1.0-P0.50-BL'
    d.part('U10', 'TPD4E05U06', 'TPD4E05U06DQAR', esd, S, G,
           {1: 'HDMI_D2_P', 2: 'HDMI_D2_N', 3: 'GND', 4: 'HDMI_D1_P', 5: 'HDMI_D1_N',
            6: 'HDMI_D1_N', 7: 'HDMI_D1_P', 8: 'GND', 9: 'HDMI_D2_N', 10: 'HDMI_D2_P'},
           'C138714', 'TPD4E05U06DQAR', note='0,5 pF ; broches 6-7 et 9-10 = traversee des paires')
    d.part('U11', 'TPD4E05U06', 'TPD4E05U06DQAR', esd, S, G,
           {1: 'HDMI_D0_P', 2: 'HDMI_D0_N', 3: 'GND', 4: 'HDMI_CK_P', 5: 'HDMI_CK_N',
            6: 'HDMI_CK_N', 7: 'HDMI_CK_P', 8: 'GND', 9: 'HDMI_D0_N', 10: 'HDMI_D0_P'},
           'C138714', 'TPD4E05U06DQAR')
    d.part('U12', 'TPD4E05U06', 'TPD4E05U06DQAR', esd, S, G,
           {1: 'HDMI_SCL', 2: 'HDMI_SDA', 3: 'GND', 4: 'HDMI_HPD', 5: 'HDMI_CEC',
            6: 'HDMI_CEC', 7: 'HDMI_HPD', 8: 'GND', 9: 'HDMI_SDA', 10: 'HDMI_SCL'},
           'C138714', 'TPD4E05U06DQAR')
    d.C('HDMI_5V', '100nF', S, G)
    d.R('HDMI_5V', 'HDMI_SCL', '47k', S, G, note='rappel SCL cote recepteur (spec HDMI)')
    d.R('HDMI_5V', 'TC_HPDI', '1k', S, G, note='detection du +5 V de la source')
    d.R('TC_HPDO', 'HDMI_HPD', '1k', S, G, note='HPD pilote par le TC358743 (relecture EDID)')
    d.R('HDMI_5V', 'HDMI_HPD', '1k', S, G, dnp=True, note='option : HPD boucle sur le +5 V (schema Antmicro)')

    G = 'TC358743XBG'
    tc = {
        'A1': 'TC_REXT', 'A2': 'GND', 'A3': 'GND', 'A4': 'TC_BIASDA', 'A5': 'TC_DAOUT', 'A6': NC,
        'A7': NC, 'A8': NC, 'B1': 'TC_AVDD33', 'B2': 'TC_AVDD12', 'B3': 'TC_INT', 'B4': 'TC_IR',
        'B5': 'TC_AVDD25', 'B6': 'TC_PCKIN', 'B7': NC, 'B8': NC, 'C1': 'HDMI_CK_P', 'C2': 'HDMI_CK_N',
        'C3': 'TC_VDDC', 'C4': 'GND', 'C5': 'GND', 'C6': 'TC_VDDMIPI', 'C7': 'CSI_CLK_N',
        'C8': 'CSI_CLK_P', 'D1': 'HDMI_D0_P', 'D2': 'HDMI_D0_N', 'D3': 'TC_AVDD12', 'D4': 'GND',
        'D5': 'GND', 'D6': 'GND', 'D7': 'CSI_D1_N', 'D8': 'CSI_D1_P', 'E1': 'HDMI_D1_P',
        'E2': 'HDMI_D1_N', 'E3': 'GND', 'E4': 'GND', 'E5': 'GND', 'E6': 'GND', 'E7': 'CSI_D0_N',
        'E8': 'CSI_D0_P', 'F1': 'HDMI_D2_P', 'F2': 'HDMI_D2_N', 'F3': 'TC_AVDD33', 'F4': '3V3',
        'F5': 'TC_VDDC', 'F6': 'TC_VDDMIPI', 'F7': NC, 'F8': NC, 'G1': 'HDMI_CEC', 'G2': 'TC_VDDC',
        'G3': 'HDMI_SDA', 'G4': 'I2C_SDA', 'G5': 'TC_RESETN', 'G6': NC, 'G7': NC, 'G8': NC,
        'H1': 'TC_HPDO', 'H2': 'TC_HPDI', 'H3': 'HDMI_SCL', 'H4': 'I2C_SCL', 'H5': 'TC_REFCLK',
        'H6': NC, 'H7': '3V3', 'H8': 'GND',
    }
    d.part('U8', 'TC358743XBG', 'TC358743XBG', 'openkvm:BGA-64_8x8_6.0x6.0mm', S, G, tc,
           '', 'TC358743XBG', note='OBSOLETE : achat broker, piece fournie a JLCPCB (consignation)')
    d.R('TC_AVDD33', 'TC_REXT', '2k', S, G, note='valeur du schema Antmicro')
    d.C('TC_BIASDA', '100nF', S, G)
    d.C('TC_DAOUT', '100nF', S, G)
    d.C('TC_PCKIN', '100nF', S, G)
    d.R('TC_IR', 'GND', '10k', S, G, note='entree IR inutilisee')
    d.R('TC_RESETN', 'GND', '10k', S, G, note='pont en reset tant que le P4 ne pilote pas')
    d.R('3V3', 'TC_AVDD33', '0R', S, G)
    d.decap('TC_AVDD33', ['10nF', '100nF', '4.7uF'], S, G)
    d.FB('1V2', 'TC_AVDD12', S, G)
    d.decap('TC_AVDD12', ['10nF', '4.7uF'], S, G)
    d.FB('1V2', 'TC_VDDC', S, G)
    d.decap('TC_VDDC', ['10nF', '100nF', '100nF', '4.7uF'], S, G)
    d.FB('1V2', 'TC_VDDMIPI', S, G)
    d.decap('TC_VDDMIPI', ['10nF', '4.7uF'], S, G)
    d.FB('VDDO_3', 'TC_AVDD25', S, G)
    d.decap('TC_AVDD25', ['10nF', '1uF'], S, G)
    d.decap('3V3', ['100nF', '100nF'], S, G)             # VDDIO1 (F4), VDDIO2 (H7)

    G = 'Oscillateur 27 MHz'
    d.part('Y2', 'OSC4', '27MHz 3V3 HCMOS', 'Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm',
           S, G, {1: 'OSC27_VDD', 2: 'GND', 3: 'OSC27_OUT', 4: 'OSC27_VDD'},
           'C2992365', 'CO32H4-27.000-33JDTSNL', note='1 = EN, 2 = GND, 3 = OUT, 4 = VDD : a verifier sur la fiche')
    d.FB('3V3', 'OSC27_VDD', S, G)
    d.decap('OSC27_VDD', ['100nF'], S, G)
    d.R('OSC27_OUT', 'TC_REFCLK', '22R', S, G)

    # -------------------------------------------------------------------- eth
    S = 'eth'
    G = 'PHY IP101GRI'
    d.part('U9', 'IP101GRI', 'IP101GRI', 'openkvm:QFN-32_L4.0-W4.0-P0.40-BL-EP2.7', S, G,
           {1: NC, 2: 'ETH_X1', 3: 'ETH_X2', 4: 'ETH_RMII_SEL', 5: 'RMII_TX_EN', 6: NC, 7: NC,
            8: 'RMII_TXD1_BOOT', 9: 'RMII_TXD0', 10: NC, 11: 'ETH_LED0', 12: 'ETH_LED3', 13: '3V3',
            14: 'ETH_CLKO', 15: NC, 16: NC, 17: 'RMII_RXD1', 18: 'RMII_RXD0', 19: 'RMII_CRS_DV',
            20: NC, 21: NC, 22: 'RMII_MDC', 23: 'RMII_MDIO', 24: NC, 25: 'ETH_ISET', 26: 'ETH_RX_N',
            27: 'ETH_RX_P', 28: 'ETH_REGOUT', 29: 'ETH_TX_N', 30: 'ETH_TX_P', 31: 'ETH_AVDD33',
            32: 'PHY_RST', 33: 'GND'},
           'C703537', 'IP101GRI', note='adresse PHY = 1, mode RMII, quartz 25 MHz')
    d.R('3V3', 'ETH_RMII_SEL', '4.7k', S, G, note='strap : 1 = RMII')
    d.R('3V3', 'ETH_LED0', '4.7k', S, G, note='strap PHY_AD0 = 1 (adresse 1)')
    d.R('ETH_ISET', 'GND', '6.19k 1%', S, G)
    d.R('ETH_CLKO', 'RMII_REF_CLK', '33R', S, G, note='50 MHz vers GPIO50, au plus pres du PHY')
    d.R('3V3', 'RMII_MDIO', '4.7k', S, G)
    d.R('3V3', 'PHY_RST', '10k', S, G)
    d.decap('3V3', ['100nF'], S, G)                      # VDDIO (13)
    d.FB('3V3', 'ETH_AVDD33', S, G)
    d.decap('ETH_AVDD33', ['10uF*', '100nF'], S, G)
    d.decap('ETH_REGOUT', ['10uF*', '100nF'], S, G)
    d.part('Y3', 'XTAL4', '25MHz 10ppm', 'openkvm:CRYSTAL-SMD_4P-L3.2-W2.5-BL', S, G,
           {1: 'ETH_X1', 2: 'GND', 3: 'ETH_X2', 4: 'GND'}, 'C9006', 'X322525MOB4SI')
    d.C('ETH_X1', '18pF', S, G, note='CL = 12 pF')
    d.C('ETH_X2', '18pF', S, G)

    G = 'RJ45'
    d.part('J4', 'HR911105A', 'HR911105A', 'openkvm:RJ45-TH_HR911105A', S, G,
           {1: 'ETH_TX_P', 2: 'ETH_TX_N', 3: 'ETH_RX_P', 4: 'ETH_CT_TX', 5: 'ETH_CT_RX',
            6: 'ETH_RX_N', 7: NC, 8: 'GND', 9: '3V3', 10: 'ETH_LEDG_K', 11: 'GND',
            12: 'ETH_LEDY_A', 'SH1': 'GND', 'SH2': 'GND'},
           'C12074', 'HR911105A', note='9/10 = LED verte (A/K), 12/11 = LED jaune (A/K)')
    d.C('ETH_CT_TX', '100nF', S, G, note='point milieu : decouplage seul, pas de tension (IP101G)')
    d.C('ETH_CT_RX', '100nF', S, G)
    d.R('ETH_LEDG_K', 'ETH_LED0', '470R', S, G, note='LED verte = lien, active a l etat bas')
    d.R('ETH_LED3', 'ETH_LEDY_A', '470R', S, G, note='LED jaune = 100M / activite, active a l etat haut')

    # ----------------------------------------------------------------- periph
    S = 'periph'
    G = 'microSD (slot SDMMC 0, UHS-I)'
    d.part('J5', 'TF-01A', 'microSD', 'openkvm:TF-SMD_TF-01A', S, G,
           {1: 'SD_C_D2', 2: 'SD_C_D3', 3: 'SD_C_CMD', 4: 'SD_VDD', 5: 'SD_C_CLK', 6: 'GND',
            7: 'SD_C_D0', 8: 'SD_C_D1', 9: 'SD_CD', 10: 'GND', 11: 'GND', 12: 'GND', 13: 'GND'},
           'C91145', 'TF-01A')
    for sig in ('CLK', 'CMD', 'D0', 'D1', 'D2', 'D3'):
        d.R(f'SD_{sig}', f'SD_C_{sig}', '22R', S, G)
    for sig in ('CMD', 'D0', 'D1', 'D2', 'D3'):
        d.R('VDDO_4', f'SD_{sig}', '10k', S, G)
    d.R('3V3', 'SD_CD', '10k', S, G, note='detection de carte, GPIO7 (domaine 3,3 V)')
    d.part('Q1', 'PMOS', 'AO3401A', 'Package_TO_SOT_SMD:SOT-23', S, G,
           {1: 'SD_PWR_EN_N', 2: '3V3', 3: 'SD_VDD'}, 'C15127', 'AO3401A',
           note='1 = G, 2 = S, 3 = D ; coupe la carte pour quitter le mode 1,8 V')
    d.R('3V3', 'SD_PWR_EN_N', '100k', S, G, note='carte eteinte par defaut')
    d.decap('SD_VDD', ['10uF*', '100nF'], S, G)

    G = 'Ecran ST7789 240x240'
    d.part('J7', 'JST8', 'LCD', 'openkvm:CONN-TH_SM08B-SRSS-TB-LF-SN', S, G,
           {1: 'GND', 2: '3V3', 3: 'LCD_SCLK', 4: 'LCD_MOSI', 5: 'LCD_RST', 6: 'LCD_DC',
            7: 'LCD_CS', 8: 'LCD_BL', 9: 'GND', 10: 'GND'},
           'C160407', 'SM08B-SRSS-TB(LF)(SN)', note='meme ordre que le module MSP1541')
    d.decap('3V3', ['100nF'], S, G)

    G = 'ESD USB'
    d.part('U13', 'TPD4E05U06', 'TPD4E05U06DQAR', esd, S, G,
           {1: 'USB_HS_DP', 2: 'USB_HS_DM', 3: 'GND', 4: 'J1_CC1', 5: 'J1_CC2',
            6: 'J1_CC2', 7: 'J1_CC1', 8: 'GND', 9: 'USB_HS_DM', 10: 'USB_HS_DP'},
           'C138714', 'TPD4E05U06DQAR', note='USB HS : capacite <= 1 pF exigee')
    d.part('U14', 'TPD4E05U06', 'TPD4E05U06DQAR', esd, S, G,
           {1: 'USB_FS_CONN_DP', 2: 'USB_FS_CONN_DM', 3: 'GND', 4: 'J2_CC1', 5: 'J2_CC2',
            6: 'J2_CC2', 7: 'J2_CC1', 8: 'GND', 9: 'USB_FS_CONN_DM', 10: 'USB_FS_CONN_DP'},
           'C138714', 'TPD4E05U06DQAR')
    d.R('USB_FS_DP', 'USB_FS_CONN_DP', '22R', S, G, note='USB FS : 22 ohms serie pres du P4')
    d.R('USB_FS_DM', 'USB_FS_CONN_DM', '22R', S, G)
    return d


# Symboles : nom -> liste (numero, nom, cote). Les symboles a 2 broches ont un dessin dedie.
def symbol_pins(lcsc_lib_pins):
    """Complete les brochages des symboles issus de la bibliotheque LCSC."""
    syms = {
        'XTAL4': [('1', 'X1', 'L'), ('2', 'GND', 'L'), ('3', 'X2', 'R'), ('4', 'GND', 'R')],
        'OSC4': [('1', 'EN', 'L'), ('2', 'GND', 'L'), ('4', 'VDD', 'R'), ('3', 'OUT', 'R')],
        'SW4': [('1', 'A', 'L'), ('2', 'A', 'L'), ('3', 'B', 'R'), ('4', 'B', 'R')],
        'SWSIDE': [('3', 'SW', 'L'), ('1', 'MNT', 'L'), ('4', 'SW', 'R'), ('2', 'MNT', 'R')],
        'PMOS': [('1', 'G', 'L'), ('2', 'S', 'R'), ('3', 'D', 'R')],
        'HDR6': [(str(i), str(i), 'L') for i in range(1, 7)],
        'JST8': [(str(i), n, 'L') for i, n in enumerate(
            ['GND', 'VCC', 'SCL', 'SDA', 'RES', 'DC', 'CS', 'BLK', 'MNT', 'MNT'], 1)],
        'TPD4E05U06': [('1', 'D1+', 'L'), ('2', 'D1-', 'L'), ('4', 'D2+', 'L'), ('5', 'D2-', 'L'),
                       ('3', 'GND', 'L'), ('10', 'NC', 'R'), ('9', 'NC', 'R'), ('7', 'NC', 'R'),
                       ('6', 'NC', 'R'), ('8', 'GND', 'R')],
    }
    tc_names = {
        'A1': 'REXT', 'A2': 'VSS', 'A3': 'VPGM', 'A4': 'BIASDA', 'A5': 'DAOUT', 'A6': 'PFIL',
        'A7': 'CSID3N', 'A8': 'CSID3P', 'B1': 'AVDD33', 'B2': 'AVDD12', 'B3': 'INT', 'B4': 'IR',
        'B5': 'AVDD25', 'B6': 'PCKIN', 'B7': 'CSID2N', 'B8': 'CSID2P', 'C1': 'HDMICP',
        'C2': 'HDMICN', 'C3': 'VDDC2', 'C4': 'VSS', 'C5': 'VSS', 'C6': 'VDD_MIPI', 'C7': 'CSICN',
        'C8': 'CSICP', 'D1': 'HDMID0P', 'D2': 'HDMID0N', 'D3': 'AVDD12', 'D4': 'VSS', 'D5': 'VSS',
        'D6': 'VSS', 'D7': 'CSID1N', 'D8': 'CSID1P', 'E1': 'HDMID1P', 'E2': 'HDMID1N', 'E3': 'VSS',
        'E4': 'VSS', 'E5': 'TEST', 'E6': 'VSS', 'E7': 'CSID0N', 'E8': 'CSID0P', 'F1': 'HDMID2P',
        'F2': 'HDMID2N', 'F3': 'AVDD33', 'F4': 'VDDIO1', 'F5': 'VDDC2', 'F6': 'VDD_MIPI',
        'F7': 'A_SCK', 'F8': 'A_SD', 'G1': 'CEC', 'G2': 'VDDC1', 'G3': 'DDC_SDA', 'G4': 'I2C_SDA',
        'G5': 'RESETN', 'G6': 'EDID_SDA', 'G7': 'A_WFS', 'G8': 'A_OSCK', 'H1': 'HPDO', 'H2': 'HPDI',
        'H3': 'DDC_SCL', 'H4': 'I2C_SCL', 'H5': 'REFCLK', 'H6': 'EDID_SCL', 'H7': 'VDDIO2', 'H8': 'VSS',
    }
    left = ['F1', 'F2', 'E1', 'E2', 'D1', 'D2', 'C1', 'C2', 'H3', 'G3', 'G1', 'H1', 'H2', 'A1',
            'A4', 'A5', 'B6', 'A6', 'H5', 'G5', 'B3', 'B4', 'H4', 'G4', 'H6', 'G6', 'F7', 'F8',
            'G7', 'G8', 'E5', 'A3']
    right = [b for b in sorted(tc_names) if b not in left]
    order = ['C8', 'C7', 'E8', 'E7', 'D8', 'D7', 'B8', 'B7', 'A8', 'A7', 'B1', 'F3', 'B5', 'B2',
             'D3', 'G2', 'C3', 'F5', 'C6', 'F6', 'F4', 'H7']
    right = order + [b for b in right if b not in order]
    syms['TC358743XBG'] = [(b, tc_names[b], 'L') for b in left] + [(b, tc_names[b], 'R') for b in right]
    for name, pins in lcsc_lib_pins.items():
        if name in syms:
            continue
        half = (len(pins) + 1) // 2
        syms[name] = [(n, nm, 'L' if i < half else 'R') for i, (n, nm) in enumerate(pins)]
    return syms
