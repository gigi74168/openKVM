# 01 — Recherche : les KVM-over-IP existants

Date de vérification : **2026-11-12**. Chaque chiffre renvoie à une source listée en fin de document
(numéro entre crochets). Si une info n'a pas pu être confirmée, c'est écrit noir sur blanc.

## 1. Résumé en 5 points

1. Le **JetKVM Mini** est la seule référence sans DRAM ni eMMC : tout tient dans un ESP32-P4X avec
   32 Mo de PSRAM intégrée. C'est ce qui lui permet d'être à 39 $ [1][3].
2. Tous les KVM Linux **à bas prix** (JetKVM, PicoKVM, NanoKVM) sont en **100 Mbit/s**. Le Gigabit
   n'apparaît qu'à partir d'environ 90-100 $ (NanoKVM Pro, GL.iNet Comet) [5][7][8][9].
3. La **pénurie de mémoire** fait monter les prix : JetKVM passe de **89 $ à 103 $** à cause du coût
   de l'eMMC (×3) et de la DDR [4]. C'est un argument de plus pour l'architecture sans DRAM retenue.
4. Le pont **TC358743** (Toshiba) est la puce de capture HDMI de référence : JetKVM Mini [2],
   PiKVM V4 [11], LeafKVM [14], et probablement le PicoKVM [13]. D'autres RV1106 utilisent des ponts
   Rockchip RK628/RK682 [15].
5. Il faut **impérativement un ESP32-P4X** (révision de puce ≥ 3.x). Sur la révision 1.3, la
   conversion de couleurs passe par le PPA et le H.264 1080p plafonne à 5-7 i/s [3].

## 2. Tableau comparatif

| Produit | SoC | Mémoire / stockage | Capture HDMI | Vidéo max | Ethernet | USB cible | Écran | Taille (mm) | Prix public (date) | Logiciel | Matériel publié ? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **JetKVM Mini** | ESP32-P4X (RISC-V) | 32 Mo PSRAM, 16 Mo flash, TF | TC358743, CSI 2 voies | 1080p30 / 720p60 | 100M (IP101) | USB 2.0 HS + port EXT FS | 240×240 ST7789 | 42×42×23 (alu) | 39 $ ; 33 $/u par 3 (2026-10) | **MIT** | Non (le brochage est déductible du firmware, cf. §3) |
| JetKVM | Rockchip RV1106G3 (A7 1 GHz) | 256 Mo DDR3L intégrée ; eMMC 16 Go → microSD 32 Go | Non confirmé | 1080p | 100M (PoE en option) | USB 2.0 HS | 1,69" 280×240 tactile | 60×43×31 | **103 $** (119 $ PoE) | GPL-2.0 (Go + TS) | Non |
| Luckfox PicoKVM | RV1106G3 (A7 1,2 GHz) | 256 Mo DDR3L, eMMC 8 Go, microSD | TC358743 probable (forum, non confirmé) | 1080p60 | 10/100 | USB-C HID + stockage | 1,54" 240×240 tactile (version complète) | 48,5×48,5×29 ; base 44×42×23,6 | 34,59 $ / 59,59 $ AliExpress (2025-09) | Buildroot, en majorité open source (blobs Rockchip) | Schémas et CAO annoncés (GitHub / Google Drive) |
| Sipeed NanoKVM (Cube/Lite) | SG2002 (C906 1 GHz) | 256 Mo DDR3, microSD 32 Go | Carte HDMI→CSI, puce non confirmée | 1080p60 | 100M | USB 2.0 | OLED | 40×36×36 | ~20 $+ (2024) | **GPL-3.0** | **Oui** : schémas NanoKVM-A/B/PCIe publiés |
| Sipeed NanoKVM Pro | Axera AX630C (2×A53 1,2 GHz) | 1 Go LPDDR4X, eMMC 32 Go | Intégrée, loop-out 4K | 4K30 / 2K60 | **1000M**, PoE/Wi-Fi 6 en option | USB-C HID | 1,47" 320×172 ou OLED | 65×65×28 | 89-109 $ AliExpress (2025-08) | GPL-3.0 (dépôt `sipeed/NanoKVM`) | Non trouvé |
| GL.iNet Comet GL-RM1 | Quad-core non déclaré (RV1126 selon un commentateur) | 1 Go DDR3, eMMC 8 Go | Non publiée | 2K60 / 4K30 | **1000M** | USB 2.0 Type-C | Aucun | 80×60×17,5 | 99,99 $ (boutique US) | Propriétaire | Non |
| PiKVM V4 Mini | Raspberry Pi CM4 | Selon le CM4 | **TC358743** (service `kvmd-tc358743`) | 1080p50 (1920×1200@60 selon revendeur) | 1000M (CM4) | USB OTG | Non vérifié | — | 394,95 AUD TTC (Core Electronics) | Open source (licence kvmd non revérifiée) | Non trouvé |
| ESP-KVM (projet DIY) | ESP32-P4X sur carte EV / Waveshare | Carte de dev | Selon la carte | ~22-24 i/s en 1080p, 28 i/s en 720p (rev 3.x) | Selon la carte | USB HS | — | — | Carte de dev | Open source | Pas de PCB dédié |

Notes :
- Les prix datés de 2025 n'ont pas été revérifiés en magasin : vu la hausse de la mémoire [4], considère-les comme
  **des planchers probablement dépassés**.
- Pour PiKVM V4 Mini, la résolution diffère selon la source : PiKVM annonce 1080p50, Pimoroni 1920×1200@60 [10].

## 3. Le JetKVM Mini sous le capot (déduit de son firmware MIT)

JetKVM ne publie pas le matériel, mais le firmware [2] contient le brochage exact. C'est notre schéma de départ.

### 3.1 Brochage ESP32-P4 (variante Ethernet)

| Fonction | GPIO P4 | Remarque (source : fichiers du dépôt) |
|---|---|---|
| Écran SPI MOSI / SCLK / rétroéclairage | 3 / 13 / 4 | ST7789, **pas de MISO** (`docs/hardware-variants.md`) |
| Écran DC / RST / CS | 20 / 21 / 22 | Ethernet ; 14/15/16 sur la variante Wi-Fi |
| Bouton SW2 (actif bas) | 47 | Pull-up externe 10 kΩ (`jetkvm_board_config`) |
| Bouton SW3 « mode » (actif bas) | 23 | Pull-up externe 10 kΩ |
| TC358743 I²C SDA / SCL | 2 / 5 | I2C0, adresse **0x0F**, 100 kHz (`tc358743_regs.h`) |
| TC358743 RESETN / INT | 32 / 33 | |
| TC358743 MIPI CSI-2 | Port CSI dédié | **2 voies** (`TC358743_LANES 2`), YUV422 |
| TC358743 REFCLK | — | **Oscillateur externe 27 MHz alimenté par la sortie LDO VDD_O3 du P4** (`jetkvm_hdmi_bridge.c`) |
| PHY Ethernet IP101 | RMII (broches par défaut d'ESP-IDF) | Adresse PHY **1**, reset PHY sur **GPIO51** (`jetkvm_board_network.c`) |
| Carte TF (microSD) | Contrôleur SDMMC **slot 1** (matrice GPIO) | La variante Wi-Fi la met sur le slot 0 (GPIO39..44) |
| USB vers la cible | Contrôleur **USB 2.0 HS OTG** | `sdkconfig.defaults` |
| Port USB-C « EXT » | USB FS | Extensions, alimentation de secours, mode hôte possible |

### 3.2 Autres faits utiles tirés du firmware

- **Mémoire** : flash 16 Mo, PSRAM en mode HEX à 250 MHz (`sdkconfig.defaults`).
- **Partitions** : 2 slots OTA de 6 Mo, plus NVS 256 Ko et LittleFS 3,6 Mo (`partitions.csv`). OTA signé GPG avec retour arrière.
- **Audio** : **pas d'audio HDMI**. Le Mini expose une **carte son USB (UAC2)** à la machine cible, encodée en Opus à 64 kbit/s (`components/jetkvm_audio/README.md`). On n'a donc pas besoin de câbler l'I²S du TC358743.
- **Répartition CPU** : le cœur 1 est réservé à l'encodeur H.264, le cœur 0 gère TCP/IP, l'audio et HTTP.
- **Alimentation** : les deux USB-C peuvent alimenter, avec bascule automatique entre la cible et EXT [1]. Il faut donc un **OU de diodes ou un power-mux** au schéma.
- **Sécurité** : le hash de la clé de signature JetKVM est gravé en eFuse sur leurs appareils [1]. Sans conséquence pour nous : nos P4 seront vierges.
- **Boîtier** : aluminium, 42×42×23 mm, écran sur le dessus, boutons sur le côté, slot TF sur le côté [1].
- **Modules firmware réutilisables** (dossier `components/`) : `jetkvm_hdmi_bridge`, `p4_csi_capture`, `jetkvm_video`,
  `jetkvm_usb_hid`, `jetkvm_virtual_media(_http)`, `jetkvm_screen` (LVGL), `jetkvm_ota`, `webrtc_transport`,
  `web_app`, `jetkvm_board_config`, `jetkvm_board_network`…

## 4. Schémas de référence disponibles

| Source | Contenu | Utilité pour openKVM |
|---|---|---|
| NanoKVM-A / B / PCIe (Sipeed) [6] | Schémas PDF (1 page chacun pour A/B : carte de base OLED, boutons, ATX, ESD). Le texte n'est pas extractible (polices manquantes), lecture visuelle seulement. | Protections ESD USB/HDMI, boutons, petit écran SPI |
| LicheeRV Nano (Sipeed) [6] | Schémas et plans cotés de la carte cœur | Faible (SoC différent) |
| Luckfox PicoKVM [12] | Schémas et modèles CAO annoncés sur GitHub / Google Drive. Page de téléchargement dynamique, fichier non récupéré automatiquement. | **Élevée** : format 44×42 mm, écran 240×240, HDMI + RJ45 + USB-C. À récupérer à la main. |
| JetKVM Mini (firmware) [2] | Brochage complet (§3) | **Très élevée** |
| Fiche technique TC358743 / design guide Toshiba | À collecter au livrable 2 | Schéma du pont HDMI |
| Guide de conception matérielle ESP32-P4 (Espressif) [16] | Alimentations, LDO, découplage, USB, RMII | **Très élevée** |

**Ce qui manque** : aucun schéma de pont HDMI→CSI TC358743 publié par un KVM. On partira de la datasheet
Toshiba et de cartes HAT TC358743 open source, à identifier au livrable 2.

## 5. Ce qu'on en retient pour openKVM

| # | Enseignement | Conséquence pour la conception |
|---|---|---|
| 1 | Il faut un P4 révision ≥ 3.x | Ne commander que des références **ESP32-P4…X** (ex. `ESP32P4NRW32X`, JLCPCB C54540373 [17]). À confirmer au livrable 2. |
| 2 | Le TC358743 en 2 voies CSI suffit pour du 1080p30 | Même pont que le Mini, donc driver réutilisé tel quel. Comparatif LT6911UXC au livrable 2. |
| 3 | L'oscillateur 27 MHz est alimenté par le LDO du P4 | Le reprendre à l'identique : séquencement déjà géré par le firmware. |
| 4 | Le débit microSD limite les ISO | Étudier le **slot SDMMC 0 (IOMUX, UHS-I possible)** plutôt que le slot 1 du Mini. Débit réel à mesurer. |
| 5 | Double alimentation | Power-mux idéal (ex. famille TPS2121) ou diodes Schottky : choix au livrable 4. |
| 6 | Audio par USB, pas par HDMI | On n'a pas à câbler l'I²S du TC358743. Option : prévoir des points de test I²S « au cas où ». |
| 7 | Garder la compatibilité de brochage avec le Mini | Vrai pour le pont HDMI, le PHY et le bouton. **Mise à jour du 2026-11-12 : openKVM n'a pas d'écran** ([00](00-decision-architecture.md)) : en plus de `jetkvm_board_config.h`, il faudra retirer le pilote d'écran du fork et ajouter une LED d'état. |
| 8 | Le marché bas prix est en 100M, le Gigabit coûte plus de 90 $ | Le choix v1 en 100M est cohérent. Différenciation : prix, matériel ouvert (CERN-OHL), boîtier imprimable. |
| 9 | « JetKVM » est une marque de BuildJet, Inc. [1] | Ne pas utiliser ce nom ni le logo sur notre produit, notre UI ni nos boîtiers : retirer le branding du fork. |

## 6. Points non confirmés (à lever plus tard)

- Puce de capture du JetKVM original et du NanoKVM : non trouvée.
- PicoKVM : TC358743 supposé d'après un fil de forum, schéma à télécharger à la main.
- Broches RMII exactes du Mini : il utilise la config ESP-IDF par défaut, à relever dans `ETH_ESP32_EMAC_DEFAULT_CONFIG` de l'ESP-IDF 6.0.2.
- Prix NanoKVM / PicoKVM / Comet : datés de 2025, sans doute en hausse depuis.

## Sources

1. JetKVM — *Introducing JetKVM Mini* (prix 39/42 $, 99/108 $ par 3, boîtier alu 42×42×23, USB HS/FS) — https://jetkvm.com/blog/introducing-jetkvm-mini ; *JetKVM Mini docs* — https://jetkvm.com/docs/devices/jetkvm-mini
2. GitHub — `jetkvm/mini` (MIT, © 2026 JetKVM ; `docs/hardware-variants.md`, `components/jetkvm_board_config`, `components/jetkvm_hdmi_bridge/tc358743_regs.h`, `components/jetkvm_board_network`, `components/jetkvm_audio/README.md`, `sdkconfig.defaults`, `partitions.csv`) — https://github.com/jetkvm/mini
3. CNX Software — *JetKVM Mini – A low-cost, ESP32-P4X-based KVM* (P4X = rev ≥ 3.x ; commentaire de l'auteur d'ESP-KVM sur les débits) — https://www.cnx-software.com/2026/09/14/jetkvm-mini-a-low-cost-esp32-p4x-based-kvm-with-ethernet-or-wifi-connectivity/
4. JetKVM — *New Internals, New Ports & a Price Update* (89 → 103 $, PoE 119 $, eMMC → microSD) — https://jetkvm.com/blog/new-internals-new-ports-price-update
5. CNX Software — *JetKVM – A $69 KVM over IP solution* (RV1106G3, 256 Mo DDR3L, 100M, 60×43×31) — https://www.cnx-software.com/2025/03/21/jetkvm-a-69-kvm-over-ip-solution-with-open-source-software/ ; JetKVM docs — https://jetkvm.com/docs/devices/jetkvm
6. GitHub — `sipeed/NanoKVM` README (tableau comparatif, GPL-3.0, liens vers les schémas) — https://github.com/sipeed/NanoKVM ; schéma NanoKVM-A — https://cn.dl.sipeed.com/fileList/KVM/nanoKVM/HDK/02_Schematic/SCH_RV_Nano_KVM_A_30111.pdf ; NanoKVM-B — https://cn.dl.sipeed.com/fileList/KVM/nanoKVM/HDK/02_Schematic/SCH_RV_Nano_KVM_B_30131.pdf ; Wiki NanoKVM — https://wiki.sipeed.com/hardware/en/kvm/NanoKVM/introduction.html
7. CNX Software — *Sipeed NanoKVM Pro* (AX630C, 1000M, 65×65×28, 89-109 $) — https://www.cnx-software.com/2025/08/29/sipeed-nanokvm-pro-a-4k-ip-kvm-with-atx-and-desk-versions-pikvm-nanokvm-firmware-support/ ; Wiki — https://wiki.sipeed.com/hardware/en/kvm/NanoKVM_Pro/introduction.html
8. CNX Software — *GL.iNet Comet GL-RM1* — https://www.cnx-software.com/2025/03/18/gl-inet-comet-gl-rm1-low-cost-kvm-over-ip-solution-supports-up-to-2k-resolution/
9. GL.iNet Store US — *Comet GL-RM1* (99,99 $) — https://store-us.gl-inet.com/products/comet-gl-rm1-remote-keyboard-video-mouse
10. Core Electronics — *PiKVM V4 Mini* (394,95 AUD) — https://core-electronics.com.au/pikvm-v4-mini.html ; Pimoroni — https://shop.pimoroni.com/products/pikvm-v4-mini
11. PiKVM docs — *V4 Mini & Plus* (`kvmd-tc358743`) — https://docs.pikvm.org/v4/
12. CNX Software — *Luckfox PicoKVM* (specs, prix, schémas/CAO annoncés) — https://www.cnx-software.com/2025/09/23/luckfox-picokvm-low-cost-ip-kvm-with-1080p-hdmi-capture-wake-on-lan-virtual-storage-emulation/ ; Wiki Luckfox — https://wiki.luckfox.com/Luckfox-PicoKVM/
13. Forum Luckfox — fil sur l'audio HDMI du PicoKVM (pilote tc358743 → I²S) — https://forums.luckfox.com/viewtopic.php?p=7762
14. LeafKVM — *How it works* (TC358743 + RV1106) — https://leafkvm-website.pages.dev/reference
15. CNX Software — *Radxa Linkr* (pont RK682F) — https://www.cnx-software.com/2026/08/30/radxa-linkr-a-usb-drive-sized-ip-kvm-with-usb-c-ethernet-and-wifi-support/ ; *AweSun Cloud KVM Q1 Review* (RK628H) — https://www.cnx-software.com/2026/06/07/awesun-cloud-kvm-q1-review-an-ultra-compact-low-cost-kvm-over-ip-solution/
16. Espressif — *ESP32-P4 Hardware Design Guidelines* — https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32p4/esp-hardware-design-guidelines-en-master-esp32p4.pdf
17. JLCPCB — *ESP32P4NRW32X* (C54540373) — https://jlcpcb.com/partdetail/EspressifSystems-ESP32P4NRW32X/C54540373
