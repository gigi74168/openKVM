# Livrable 5 — BOM chiffrée et coût par carte

**État : rév. 0.2 (version sans écran), à valider.** Prix lus le **2026-11-12** sur l'API publique de JLCPCB (stock et paliers de prix) et sur
la page d'aide « PCB Assembly Cost » de JLCPCB (mise à jour le 22 octobre 2026). Les prix bougent : relancez
`python3 hardware/scripts/bom_cost.py --refresh` avant toute commande.

Fichiers produits :

| Fichier | Contenu |
|---|---|
| [`hardware/fabrication/openkvm-bom-jlcpcb.csv`](../hardware/fabrication/openkvm-bom-jlcpcb.csv) | BOM à téléverser chez JLCPCB (46 lignes, **une seule** sans code LCSC : le TC358743) |
| [`hardware/fabrication/openkvm-bom-chiffree.csv`](../hardware/fabrication/openkvm-bom-chiffree.csv) | Même BOM avec stock, quantité commandée, prix unitaire et coût par ligne |
| [`hardware/fabrication/prix-composants.json`](../hardware/fabrication/prix-composants.json) | Instantané daté des paliers de prix et des stocks |
| [`hardware/scripts/bom_cost.py`](../hardware/scripts/bom_cost.py) | Le calcul, rejouable |

## 1. Résumé

- **À 5 cartes, on ne bat pas le JetKVM Mini à 39 $.** Pour 8 cartes assemblées (2 panneaux de 4, voir §3), les composants
  et l'assemblage coûtent déjà **34,2 à 35,7 $ par carte**, *avant* le PCB nu, le TC358743 et le transport.
- **À 20 cartes**, le sous-total tombe à **22,0 à 24,5 $** : l'objectif devient jouable, mais seulement si le TC358743 acheté
  chez un broker reste raisonnable (il reste **non chiffré**, voir §5).
- La cause : des frais **fixes** d'assemblage d'environ 135 $ par commande (installation, pochoir, une charge par référence
  distincte, gabarits). Répartis sur 8 cartes, ça fait 16,8 $ chacune ; sur 20 cartes, 7,5 $.
- Les composants eux-mêmes coûtent 15,0 $/carte (8 cartes) ou 13,0 $/carte (20 cartes), dont **6,15 $ pour l'ESP32-P4**.
- **Sans écran**, il n'y a plus de module à acheter à part (les annonces allaient de 1,70 à 21 $) ni de montage manuel.
  Les composants de la carte, eux, ne baissent que de 0,4 $ : on retire un connecteur et un bouton, on ajoute une LED.

## 2. Les trois composants de précision (ligne « à choisir » résolue)

| Valeur | Rôle | Référence retenue | Code LCSC | Stock JLCPCB (12/11/2026) | Prix 1 pièce |
|---|---|---|---|---|---|
| 4,02 kΩ 1 % | REXT du ESP32-P4 (R13, R14) | 0402WGF4021TCE (UNI-ROYAL) | [C43251](https://www.lcsc.com/product-detail/C43251.html) | 735 399 | 0,0013 $ |
| 499 kΩ 1 % | Pont de retour du DC-DC cœur (R15, R16) | 0402WGF4993TCE | [C25793](https://www.lcsc.com/product-detail/C25793.html) | 97 563 | 0,0032 $ |
| 6,19 kΩ 1 % | ISET de l'IP101GRI (R38) | 0402WGF6191TCE | [C25914](https://www.lcsc.com/product-detail/C25914.html) | 112 984 | 0,0012 $ |

J'ai aussi remplacé la 10 kΩ (14 pièces) par la version **basse bibliothèque** `0402WGF1002TCE`
([C25744](https://www.lcsc.com/product-detail/C25744.html), 20,2 millions en stock, 1 %) : l'ancienne (C25531) n'avait que
231 k pièces et n'est pas dans la bibliothèque de base.

## 3. Ce que JLCPCB impose à *cette* carte

Constats tirés de la [page des capacités d'assemblage](https://jlcpcb.com/capabilities/pcb-assembly-capabilities) :

| Contrainte | Économique | Standard | Notre carte |
|---|---|---|---|
| Pas minimal des circuits intégrés | 0,4 mm | 0,35 mm | **ESP32-P4 en QFN-104 à 0,35 mm → Standard obligatoire** |
| Taille d'une carte seule | 10 × 10 mm min. | **70 × 70 mm min.** | 45 × 45 mm → **il faut un panneau** |
| Faces assemblées | une | une ou deux | une seule, tout est dessus |
| Rails et repères | inutiles | **obligatoires** | à prévoir dans le panneau |
| Quantité | 2 à 50 | 2 à 80 000 | |

Conséquences pour le routage (livrable 6) :

1. **Panneau de 2 × 2 cartes** (environ 90 × 90 mm, plus les rails), assemblé en Standard. Pour 5 cartes il faut donc
   **2 panneaux = 8 cartes** (3 de rechange). Le calcul ci-dessous suppose ce cas.
2. **Tout sur la face supérieure** (c'est déjà le cas du pré-placement) : la double face double l'installation (51,12 $ au lieu
   de 25,56 $), le pochoir (16,42 $ au lieu de 8,21 $), etc.
3. Prévoir deux repères optiques par panneau et des ponts de découpe (« mouse bites ») compatibles avec le contour arrondi.

## 4. Coût par carte

Hypothèses : Standard une face, **692 soudures CMS** et **16 soudures manuelles** (le RJ45 est le seul composant traversant),
44 références LCSC distinctes + le TC358743 fourni = 45 références chargées, pertes d'assemblage de JLCPCB incluses dans les quantités.

| Poste | 8 cartes (2 panneaux) | 20 cartes (5 panneaux) |
|---|---|---|
| Composants (hors TC358743) | 119,57 $ | 259,92 $ |
| Installation (setup) | 25,56 $ | 25,56 $ |
| Pochoir | 8,21 $ | 8,21 $ |
| Chargement des bobines : 45 réf. × 1,53 $ | 68,85 $ | 68,85 $ |
| Soudures CMS (0,0016 $ / soudure) | 8,86 $ | 22,14 $ |
| Soudures manuelles RJ45 | 2,10 $ | 5,25 $ |
| Gabarits (2) + main-d'œuvre + confirmation + emballage | 20,95 $ | 20,95 $ |
| **Sous-total sans rayons X** | **254,10 $** | **410,88 $** |
| Rayons X : BGA + 2 QFN seulement | 19,68 $ | 29,40 $ |
| Rayons X : + 5 boîtiers USON (TPD4E05U06) | 31,36 $ | 78,40 $ |
| **Total par carte, fourchette** | **34,22 à 35,68 $** | **22,01 à 24,46 $** |

**Non compris** dans ces totaux : voir §5.

La fourchette « rayons X » existe parce que la page de JLCPCB parle de BGA, QFN « et autres boîtiers sans broches visibles »
sans dire si les USON 10 broches en font partie ni comment le nombre de pièces est compté. Le devis en ligne tranchera.

### Les dix lignes qui pèsent le plus (8 cartes)

| Composant | Code LCSC | Prix unit. | Ligne | Stock |
|---|---|---|---|---|
| ESP32-P4NRW32X | [C54540373](https://www.lcsc.com/product-detail/C54540373.html) | 6,1467 $ | 49,17 $ | **203** |
| HR911105A (RJ45) | [C12074](https://www.lcsc.com/product-detail/C12074.html) | 1,724 $ | 13,79 $ | 52 499 |
| GD25Q128ESIGR (flash) | [C2928891](https://www.lcsc.com/product-detail/C2928891.html) | 1,4214 $ | 11,37 $ | **1 085** |
| IP101GRI (PHY) | [C703537](https://www.lcsc.com/product-detail/C703537.html) | 1,0256 $ | 8,20 $ | 17 717 |
| 22 µF 0805 | [C45783](https://www.lcsc.com/product-detail/C45783.html) | 0,1055 $ | 4,64 $ | 4,4 M |
| TPD4E05U06DQAR | [C138714](https://www.lcsc.com/product-detail/C138714.html) | 0,0835 $ | 3,67 $ | 4 535 |
| Oscillateur 27 MHz | [C2992365](https://www.lcsc.com/product-detail/C2992365.html) | 0,4041 $ | 3,23 $ | **27** |
| LM66100DCKR | [C2869734](https://www.lcsc.com/product-detail/C2869734.html) | 0,1949 $ | 3,12 $ | 44 098 |
| 10 µF 0603 | [C19702](https://www.lcsc.com/product-detail/C19702.html) | 0,0233 $ | 1,91 $ | 9,8 M |
| TLV62569DBVR | [C141836](https://www.lcsc.com/product-detail/C141836.html) | 0,0674 $ | 1,89 $ | 645 436 |

## 5. Ce qui n'est pas chiffré, et pourquoi

| Poste | État | Détail |
|---|---|---|
| **TC358743XBG** | **Non chiffré** | Obsolète. Octopart le donne « Obsolete » sans prix ; Avnet : 0 en stock, délai 182 semaines. Aucun prix vérifiable : il faut un **devis de broker**. [`docs/02`](02-choix-soc-capture.md) relève environ 3,84 $ sur un agrégateur, **non confirmé**. |
| ~~Module d'écran~~ | **Supprimé** | La version sans écran n'en a plus. C'était un poste non vérifiable (annonces de 1,70 à 20,95 $). |
| PCB nu 4 couches | **Non vérifié** | La page de devis de JLCPCB est dynamique. Indications publiques : « à partir de 2 $ » pour 5 cartes 100 × 100 mm (page promotionnelle, prix d'appel) ; un forum cite environ 7 $ (sans date) ; des blogs tiers 12–25 $ pour 10 pièces. JLCPCB a **ajusté ses prix 4 couches en août 2026**. À chiffrer avec les Gerbers finaux. |
| Consigne du TC358743 | **Inconnu** | Faire livrer à JLCPCB une pièce achetée ailleurs : frais et délais non publiés, à demander au support. |
| Transport, douane, TVA | Non chiffré | Dépend de la destination et du transporteur. |
| Boîtier imprimé | Non chiffré | Imprimé par vous. |
| Pré-soudure (« pre-reflow soldering », 0,016 $/soudure) | Ignoré | Je ne sais pas à quelles soudures s'applique cette ligne de la grille. Si elle s'appliquait à toutes les soudures CMS : environ **+11 $ par carte** (692 × 0,016 $). |

### Marge restante sous 39 $ (arithmétique, pas une promesse)

| Cas | Sous-total | Reste pour PCB nu + TC358743 + transport |
|---|---|---|
| 8 cartes | 34,2 à 35,7 $ | **3,3 à 4,8 $** : très serré, probablement insuffisant une fois le TC358743 et le port payés |
| 20 cartes | 22,0 à 24,5 $ | **14,5 à 17,0 $** : jouable si le TC358743 reste sous la dizaine de dollars |

## 6. Leviers pour descendre

1. **Plus de cartes par commande.** Les ~135 $ de frais fixes sont le premier poste : passer de 8 à 20 cartes fait baisser
   l'assemblage de 16,8 à 7,5 $ par carte.
2. **Moins de références distinctes.** Chaque référence coûte 1,53 $ par commande. On peut en supprimer une dizaine en
   regroupant les valeurs (par exemple 18 pF et 22 pF, 4,7 µF et 10 µF, 1 kΩ et 2 kΩ si le circuit le tolère) : environ 15 $
   par commande, soit 1,9 $/carte à 8 cartes. À arbitrer avec la relecture du schéma, pas sans elle.
3. **Cinq boîtiers USON (TPD4E05U06) à revoir** : ils pèsent 3,67 $ en composants (8 cartes) et peuvent ajouter environ 1,5 $
   de rayons X par carte. Une seule protection multi-lignes pour l'HDMI et l'USB ferait mieux.
4. **Oscillateur 27 MHz** : 27 pièces en stock chez JLCPCB. Suffisant pour 8 cartes, juste pour 20. Un quartz 27 MHz
   avec les condensateurs de charge est une alternative, mais le brochage du TC358743 attend un oscillateur ou un quartz :
   à trancher à la relecture (voir les points à relire de [`docs/04`](04-schema-electronique.md)).
5. **ESP32-P4NRW32X** : 213 pièces en stock. Commander tôt, la disponibilité d'un SoC récent peut changer vite.

## 7. Points à valider

1. Le Standard obligatoire et le panneau 2 × 2 vous conviennent-ils ? Ils imposent des rails et des repères sur votre PCB.
2. Je fais le devis complet du panier JLCPCB dès que vous avez routé (c'est la seule façon d'avoir le prix du PCB et des
   rayons X).
3. Qui contacte le broker pour le TC358743 ? Je peux rédiger la demande de devis (quantité 8 à 20, boîtier BGA-64 6 × 6 mm,
   date code récent, test de conformité demandé).

## Sources

- [JLCPCB — PCB Assembly Cost: What Does the Price Include?](https://jlcpcb.com/help/article/pcb-assembly-price) (mise à jour du 22/10/2026, lue le 12/11/2026)
- [JLCPCB — PCB Assembly Capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)
- [JLCPCB — Pricing notice (juin 2026)](https://jlcpcb.com/news/jlcpcb-pcb-pricing-notice) et [ajustement des prix FR4, août 2026](https://jlcpcb.com/news/jlcpcb-fr4-pcb-price-adjustment-august2026)
- API publique JLCPCB, `getComponentDetail`, interrogée le 12/11/2026 pour chaque code LCSC (instantané dans `prix-composants.json`)
- [LCSC — ESP32-P4NRW32X, C54540373](https://www.lcsc.com/product-detail/C54540373.html)
- [Octopart — TC358743XBG](https://octopart.com/part/toshiba/TC358743XBG) et [Avnet — TC358743XBG](https://www.avnet.com/americas/product/toshiba/tc358743xbg/evolve-49502165)
- [JLCPCB — Discount on quality 4-layer PCBs](https://jlcpcb.com/news/discount-on-quality-4-layer-pcbs) (prix d'appel) ; [DIYAudio — via sizes](https://www.diyaudio.com/community/threads/jlcpcb-just-changed-the-cost-of-via-sizes.404166/) (anecdote)
