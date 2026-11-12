# 00 — Décision d'architecture : ESP32-P4 en 10/100 Mbit/s

Date : 2026-11-12 — statut : **validée**

## Le conflit
- Exigence initiale : RJ45 **Gigabit** + fork du firmware JetKVM Mini (ESP32-P4, MIT).
- L'ESP32-P4 n'a qu'un MAC 10/100 (MII/RMII ; ESP-IDF ne gère que le RMII). Son unique port USB HS
  est réservé à la machine cible, donc pas d'adaptateur USB→GbE.
- Le RV1106 (JetKVM original, GPL-2.0) est **lui aussi** limité à 10/100 (MAC + PHY intégré, RMII).
- Le Gigabit impose un autre SoC (ex. RV1126B : GMAC RGMII 1G) avec DDR + eMMC + BGA, PCB 6 couches
  probable et coût incompatible avec l'objectif < 39 $.

## Décision
- **v1 : ESP32-P4 + PHY 10/100**, fork de `jetkvm/mini` (MIT, copyright d'origine conservé).
- Exigence « RJ45 Gigabit » remplacée par « RJ45 10/100 ».
- Piste **v2 « Pro » Gigabit** (RV1126B + RTL8211F, portage de `jetkvm/kvm` GPL-2.0) : documentée, hors périmètre.

## Pourquoi le Gigabit était voulu : envoi rapide d'ISO
- 100 Mbit/s ≈ 11 Mo/s théoriques → ISO de 5 Go ≈ 8 min (estimation, à mesurer au bring-up).
- Mitigations à étudier (livrables 2, 7 et 8) :
  - slot microSD accessible de l'extérieur pour copier l'ISO directement depuis un PC ;
  - bibliothèque d'ISO persistante sur la carte (on n'envoie une image qu'une fois) ;
  - upload reprenable, en arrière-plan ;
  - mesure du débit SDIO réel du P4 et du débit USB Mass Storage vers la cible.

## Sources
- JetKVM Mini — https://jetkvm.com/blog/introducing-jetkvm-mini
- jetkvm/mini (MIT, ESP-IDF 6.0.2, IP101, TC358743) — https://github.com/jetkvm/mini
- jetkvm/kvm (GPL-2.0) — https://github.com/jetkvm/kvm
- ESP32-P4 Features (Zephyr) — https://docs.zephyrproject.org/latest/boards/espressif/common/soc-esp32p4-features.html
- ESP-IDF esp_eth ESP32-P4 — https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32p4/api-reference/network/esp_eth.html
- Rockchip RV1106 Datasheet V1.7 — https://rockchips.net/wp-content/uploads/2025/03/Rockchip-RV1106-Datasheet-V1.7-20231218.pdf
- Forlinx OK1126B-S Hardware Manual — https://docs.forlinx.net/rockchip/ok1126bx-s/OK1126B-S_OK1126BJ-S_User_Hardware_Manual.html
