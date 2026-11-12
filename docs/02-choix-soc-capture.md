# 02 — Choix du SoC et de la puce de capture HDMI

Date de vérification : **2026-11-12**. Les prix LCSC viennent de l'API produit LCSC, lue le jour même.
Un prix « 5 pcs » correspond au palier 1-9 pièces. Les numéros entre crochets renvoient aux sources.

## 1. Décisions proposées

| Bloc | Choix | Statut |
|---|---|---|
| SoC | **ESP32-P4NRW32X** (révision de puce ≥ 3.x, 32 Mo de PSRAM intégrée, QFN-104 10×10) | ✅ Recommandé, en stock |
| Flash | 16 Mo SPI externe (le P4 n'a pas de flash intégrée), même taille que le Mini | Référence exacte au livrable 5 (la W25Q128JVSIQ est **à 0 en stock** chez LCSC aujourd'hui) |
| Capture HDMI | **TC358743XBG** comme le Mini, **mais la puce est obsolète** (voir §3) | ⚠️ **À valider par toi** |
| Plan B capture | **RK628D** (Rockchip, en stock LCSC) | Gros travail firmware, réservé à une v1.1 / v2 |

## 2. Le SoC : ESP32-P4X

| Critère | ESP32-P4NRW32X | ESP32-P4NRW32 (sans X) |
|---|---|---|
| LCSC | C54540373 | C22387510 |
| Révision de puce | ≥ 3.x (« P4X ») | 1.x |
| H.264 1080p | Natif : la capture alimente directement l'encodeur. ~22-24 i/s mesurés par ESP-KVM, 30 i/s sur le Mini [3] | 5-7 i/s (conversion de couleurs par le PPA) [3] |
| PSRAM | 32 Mo intégrée | 32 Mo intégrée |
| Boîtier | QFN-104 10×10 | QFN-104 10×10 |
| Stock LCSC (2026-11-12) | **217** | 0 |
| Prix 1-9 pcs | **6,21 $** | 6,02 $ (rupture) |
| Prix 10+ | 5,41 $ | 5,41 $ |
| Verdict | ✅ | ❌ inutilisable pour du H.264 temps réel |

Interfaces utiles du P4 [4][5] :
- **MIPI CSI-2 2 voies × 1,5 Gbit/s** (Espressif conseille ≤ 1 Gbit/s par voie côté capteur [5]).
- **DVP 16 bits** (via l'ISP ou LCD_CAM). Pixel-clock max non documentée publiquement.
- **USB 2.0 HS OTG** pour la cible, **USB FS** pour le port EXT.
- **EMAC RMII 10/100**, **SDMMC** sur 2 slots, encodeur H.264 matériel.

⚠️ **À la commande** : exige bien le suffixe **X**. Le stock est faible (217 pièces). Pour 5 cartes il en faut
5 + 2 de rechange, ça passe, mais réserve-les tôt.

## 3. La capture HDMI → CSI-2 / DVP

### 3.1 Le problème : le TC358743 est en fin de vie

- **Octopart** le classe **« Obsolete »** et **Partstack** **« Discontinued »** [6][7]. **Avnet** : 0 en stock, délai usine **182 semaines** [8].
- **Absent de LCSC et JLCPCB** : seuls les cousins TC358748/TC358775 y sont référencés [9].
- Il reste du stock chez des **brokers** (Win Source, Utsource, Rutronik…). Un agrégateur indique ~3,84 $ chez Utsource [10].
  Je n'ai **pas pu vérifier ce prix moi-même** : les pages broker bloquent les accès automatiques.
- Le JetKVM Mini l'utilise quand même en 2026 [2]. Ils ont probablement constitué un stock, mais ce n'est **pas confirmé**.

### 3.2 Tableau comparatif

| Puce | Entrée | Sortie vers P4 | Boîtier | Stock LCSC | Prix 1-9 pcs | Statut de vie | Pilote réutilisable | Remarques |
|---|---|---|---|---|---|---|---|---|
| **TC358743XBG** (Toshiba) | HDMI 1.4, 1080p60 max | CSI-2 jusqu'à 4 voies (2 sur le Mini) | TFBGA-64 6×6, pas 0,65 mm [11] | **Non référencé** | ~3,84 $ (broker, non vérifié) | **Obsolète** | ✅ **Oui** : `components/jetkvm_hdmi_bridge` du Mini (MIT) | EDID en RAM interne, rien à programmer. Contrefaçons possibles chez les brokers. |
| **RK628D** (Rockchip) | HDMI 2.0 RX | MIPI CSI / DSI, LVDS, RGB | WBBGA-144 8×8 | **351** | **4,39 $** | Actif | ❌ Pilote Linux en **GPL-2.0** : réécriture « propre » nécessaire pour rester MIT | Datasheet publique partielle. Travail firmware : plusieurs semaines. |
| RK628F (Rockchip) | HDMI 2.0 RX | idem | BGA-144 8×8 | 251 | 6,87 $ | Actif (récent) | ❌ | Même remarque, plus cher |
| LT6911C (Lontium) | HDMI 1.4 | MIPI CSI/DSI 1-4 voies, ×2 ports | QFN-64 | **0** | 5,29 $ | MP | ❌ | MCU interne avec firmware en flash ; docs « advance information ». Accès au firmware à clarifier avec Lontium [12]. |
| LT6911UXC (Lontium) | HDMI 2.0 (4K60) | MIPI CSI/DSI ×2 | QFN-64 7,5×7,5 | **0** | 8,82 $ | MP | ❌ | Surdimensionné ; firmware MCU, mise à jour par I²C [13] |
| ADV7611 (ADI) | HDMI 1.4a | **Parallèle** 24 bits → DVP du P4 | LQFP-64 10×10 (soudure facile) | 46 (BSWZ) / 0 (BSWZ-P) | 8,36 $ | « Recommended for new designs » [14] | ❌ Nouveau chemin DVP à écrire | Pixel-clock DVP du P4 non documentée : **risque bloquant** pour du 1080p30 |

**Bande passante** : du 1080p30 en YUV422 représente environ 1 Gbit/s utiles, soit ~0,5 Gbit/s par voie
sur 2 voies. Ça tient dans les limites du P4. Le 1080p60 dépasserait la recommandation de 1 Gbit/s par
voie, et de toute façon **l'encodeur H.264 du P4 plafonne à 1080p30**. Viser plus haut en capture ne
servirait à rien.

### 3.3 Recommandation

**v1 (série de 5) : TC358743XBG, acheté chez un broker et fourni à l'assembleur (consignation).**
- C'est la seule option avec un pilote **déjà écrit, testé en production et sous MIT**. Le fork reste quasi inchangé.
- Pour 5 cartes : en acheter **8 à 10** (rechanges, puces défectueuses), chez un broker qui fournit une traçabilité
  et un **contrôle anti-contrefaçon** (inspection, rayons X). Prévoir une **radiographie** des BGA après assemblage.
- JLCPCB et PCBWay acceptent les pièces fournies par le client : délais et frais à confirmer au livrable 5.

**Plan B documenté : RK628D** si le stock de TC358743 devient introuvable ou trop cher, ou pour une v2 reproductible par tous.
- Coût puce comparable (4,39 $), en stock chez LCSC, toujours produit.
- En contrepartie : **portage complet du pilote** et risque de licence. Il faudrait réécrire depuis la datasheet,
  sans copier le code Linux GPL, pour rester compatible MIT.

**Écartés** :
- **LT6911C / LT6911UXC** : 0 en stock, firmware propriétaire à obtenir.
- **ADV7611** : chemin DVP non éprouvé à 1080p30 sur le P4.

## 4. Blocs annexes (cadrage, détails au livrable 4)

| Bloc | Pièce envisagée | Source de la décision |
|---|---|---|
| PHY Ethernet | **IP101GRI** (10/100 RMII), comme le Mini, pilote ESP-IDF intégré | Firmware Mini [2] |
| Horloge TC358743 | Oscillateur 27 MHz alimenté par le LDO VDD_O3 du P4 | Firmware Mini [2] |
| Écran | IPS 1,54" 240×240, contrôleur **ST7789**, SPI sans MISO | Firmware Mini [2] |
| Port EXT | USB-C : alimentation + USB FS, **power-mux** avec l'alimentation venant de la cible | Ta réponse + [1] |
| microSD | Slot SDMMC 0 (IOMUX) à étudier pour accélérer les ISO | Livrable 1, §5 |
| PoE | **Non** | Ta réponse |

## 5. Sous-total provisoire (puces principales, 1 carte, palier 1-9 pcs)

| Pièce | Prix | Vérifié ? |
|---|---|---|
| ESP32-P4NRW32X | 6,21 $ | ✅ LCSC 2026-11-12 |
| TC358743XBG | ~3,84 $ + frais broker et port | ❌ agrégateur, à confirmer |
| Flash 16 Mo | ~2,28 $ (W25Q128JVSIQ, en rupture) | ⚠️ alternative à trouver |
| **Sous-total** | **≈ 12-13 $** | Hors PHY, écran, connecteurs, passifs, PCB, assemblage |

Il reste environ 26 $ sous les 39 $ du Mini pour le reste de la carte, le PCB et l'assemblage. C'est jouable, mais
**l'assemblage de 5 cartes chez JLCPCB (frais fixes, BGA, consignation) va peser lourd**. Chiffrage complet au livrable 5.

## 6. Risques ouverts

1. **Obsolescence du TC358743** : stock broker, contrefaçons, prix volatils. *Revue humaine indispensable avant de commander.*
2. **Stock limité du P4X** (217 chez LCSC) : à réserver.
3. **Pénurie de flash** : W25Q128 à 0 en stock, il faut une alternative (GigaDevice, XMC, Puya…).
4. **BGA 0,65 mm** (TC358743 ou RK628D) : demande un PCB 4 couches avec des vias fins. Contraintes au livrable 6.
5. **HDCP** : aucune de ces puces ne déchiffre de contenu protégé par HDCP dans notre usage. Les sources HDCP
   (lecteurs vidéo, certains OS en plein écran DRM) afficheront un écran noir. C'est le comportement normal d'un KVM.

## Sources

1. JetKVM — *Introducing JetKVM Mini* — https://jetkvm.com/blog/introducing-jetkvm-mini
2. GitHub `jetkvm/mini` (MIT) : `components/jetkvm_hdmi_bridge/tc358743_regs.h`, `jetkvm_hdmi_bridge.c`, `jetkvm_board_network.c`, `docs/hardware-variants.md` — https://github.com/jetkvm/mini
3. CNX Software — *JetKVM Mini…* (P4X = rev ≥ 3.x ; débits mesurés par l'auteur d'ESP-KVM) — https://www.cnx-software.com/2026/09/14/jetkvm-mini-a-low-cost-esp32-p4x-based-kvm-with-ethernet-or-wifi-connectivity/
4. Espressif — *ESP32-P4 Datasheet* (MIPI CSI-2 2 voies × 1,5 Gbit/s, CAM 16 bits) — https://documentation.espressif.com/esp32-p4_datasheet_en.html ; révision v1.3 — https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_datasheet_en.html
5. Espressif — *Camera Controller Driver, ESP-IDF v6.0.2* — https://docs.espressif.com/projects/esp-idf/en/v6.0.2/esp32p4/api-reference/peripherals/camera_driver.html ; *Camera Sensor Tuning* (≤ 1 Gbit/s par voie) — https://docs.espressif.com/projects/esp-video-components/en/latest/esp32p4/ESP_Camera_Sensor/cam_sensor_test.html
6. Octopart — *TC358743XBG* (Obsolete) — https://octopart.com/part/toshiba/TC358743XBG
7. Partstack — *TC358743XBG* (Discontinued) — https://partstack.com/p/toshiba/tc358743xbg/1765021976
8. Avnet — *TC358743XBG* (0 en stock, 182 semaines) — https://www.avnet.com/americas/product/toshiba/tc358743xbg/evolve-49502165
9. LCSC — API produit : ESP32-P4NRW32X C54540373, ESP32-P4NRW32 C22387510, RK628D C2843533, RK628F C29779897, LT6911C C2149630, LT6911UXC C5261040, ADV7611BSWZ C146553, ADV7611BSWZ-P C169370, TC358748XBG C5447096, W25Q128JVSIQ C97521 — https://www.lcsc.com/product-detail/C54540373.html (même schéma d'URL pour les autres codes)
10. Electronicsdatasheets — *TC358743XBG* (distributeurs, Utsource ~3,84 $) — https://www.electronicsdatasheets.com/manufacturers/toshiba-electronics-europe/parts/tc358743xbg
11. Toshiba — *TC358743XBG* (P-TFBGA64-0606-0.65) — https://toshiba.semicon-storage.com/us/semiconductor/product/interface-bridge-ics-for-mobile-peripheral-devices/hdmir-interface-bridge-ics/detail.TC358743XBG.html
12. Newhaven Display — *LT6911C* (datasheet) — https://support.newhavendisplay.com/hc/en-us/articles/29830212424215-LT6911C
13. LCSC — *LT6911UXC product brief* — https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2211151030_LONTIUM-SEMICONDUCTOR-LT6911UXC_C5261040.pdf
14. Analog Devices — *ADV7611* — https://www.analog.com/en/products/adv7611.html
15. CNX Software — *RK628D adds HDMI input…* — https://www.cnx-software.com/2020/12/21/rk628d-adds-hdmi-input-extra-video-outputs-to-rockchip-processors/ ; *RK628D based HDMI-to-MIPI-CSI board* — https://www.cnx-software.com/2025/12/29/rockchip-rk628d-based-hdmi-to-mipi-csi-board-converts-hdmi-video-into-camera-feed-for-embedded-systems/
