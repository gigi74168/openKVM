// openKVM v1 SANS ECRAN - boitier CONCEPT (apercu, pas un fichier d'impression final)
// CERN-OHL-S-2.0. Toutes les cotes sont en mm et seront figees au livrable 7,
// une fois le PCB route. Repere : origine = coin arriere gauche du PCB,
// X vers la droite, Y vers l'avant, Z vers le haut.

/* [Carte] */
pcb = [45, 45, 1.6];      // contour du pre-placement KiCad
jeu = 0.3;                // jeu PCB / paroi
/* [Boitier] */
paroi = 2.0;
fond = 1.6;
entretoise = 2.5;         // sous le PCB (soudures des broches du RJ45)
capot = 1.6;
h_interne = 14.2;         // du dessus du PCB au dessous du capot : RJ45 (13,4 mm) + 0,8 mm de jeu
/* [Vue] */
vue = "assemble";         // [assemble, eclate, coque]
montrer_carte = true;

z_pcb = fond + entretoise + pcb[2];              // dessus du PCB
ext = [pcb[0] + 2*(jeu + paroi), pcb[1] + 2*(jeu + paroi), z_pcb + h_interne + capot];
o = jeu + paroi;                                  // decalage PCB -> exterieur

// Decoupes : [centre le long de la face, largeur, bas au-dessus du PCB, hauteur]
rj45   = [ 9.0, 16.6, -0.2, 13.9];   // face arriere
hdmi   = [26.0, 15.8, -0.2,  6.6];   // face arriere
usb_c  = [39.5,  9.8,  0.0,  3.9];   // face arriere (CIBLE)
usb_e  = [31.0,  9.8,  0.0,  3.9];   // face gauche (EXT)
sd     = [19.4, 13.0,  0.0,  2.4];   // face droite
btn    = [[38.0, 4.4, 0.4, 2.6]];   // face droite : bouton FN unique
leds   = [29.6, 33.6];               // face avant : X des LED alim (D4) et etat (D3)
d_led  = 2.0;                        // diametre des trous de LED
trous  = [[2.5, 23.9], [2.5, 42.5], [40.6, 43.5]];          // vis M2

module arrondi(d, r = 3) {
  hull() for (x = [r, d[0]-r], y = [r, d[1]-r]) translate([x, y, 0]) cylinder(r = r, h = d[2], $fn = 48);
}

module decoupe_y(c, y) {   // dans une paroi perpendiculaire a Y
  translate([o + c[0] - c[1]/2, y - 0.1, z_pcb + c[2]]) cube([c[1], paroi + 0.2, c[3]]);
}
module decoupe_x(c, x) {   // dans une paroi perpendiculaire a X
  translate([x - 0.1, o + c[0] - c[1]/2, z_pcb + c[2]]) cube([paroi + 0.2, c[1], c[3]]);
}

module coque() {
  difference() {
    arrondi([ext[0], ext[1], ext[2] - capot]);
    translate([paroi, paroi, fond]) cube([ext[0] - 2*paroi, ext[1] - 2*paroi, ext[2]]);
    decoupe_y(rj45, 0); decoupe_y(hdmi, 0); decoupe_y(usb_c, 0);
    decoupe_x(usb_e, 0);
    decoupe_x(sd, ext[0] - paroi);
    for (b = btn) decoupe_x(b, ext[0] - paroi);
    // trous des 2 LED, face avant, juste au-dessus du PCB (conduit de lumiere a definir au livrable 7)
    for (x = leds) translate([o + x, ext[1] - paroi - 0.1, z_pcb + 1.0]) rotate([-90, 0, 0]) cylinder(d = d_led, h = paroi + 0.2, $fn = 24);
    // aerations sous les puces chaudes (P4 et TC358743)
    for (i = [0:5]) translate([o + 18 + i*3.2, o + 14, -0.1]) cube([1.6, 22, fond + 0.2]);
  }
  // plots de fixation
  for (t = trous) translate([o + t[0], o + t[1], fond]) difference() {
    cylinder(d = 5, h = entretoise, $fn = 32);
    translate([0, 0, -0.1]) cylinder(d = 1.8, h = entretoise + 0.2, $fn = 24);
  }
}

module couvercle() {
  translate([0, 0, ext[2] - capot]) difference() {
    union() {
      arrondi([ext[0], ext[1], capot]);
      translate([paroi + 0.15, paroi + 0.15, -2]) difference() {   // levre d'emboitement
        cube([ext[0] - 2*paroi - 0.3, ext[1] - 2*paroi - 0.3, 2]);
        translate([1.2, 1.2, -0.1]) cube([ext[0] - 2*paroi - 2.7, ext[1] - 2*paroi - 2.7, 2.2]);
        // pas de levre a l'arriere : elle toucherait le dessus du RJ45
        translate([-0.1, -0.1, -0.1]) cube([ext[0], 1.5, 2.2]);
      }
    }
    // capot plein (pas d'ecran) : seulement des ouies au-dessus du TC358743 et de l'ESP32-P4
    for (i = [0:6]) translate([o + 19, o + 15 + i*3.2, -0.1]) cube([15, 1.6, capot + 0.2]);
  }
}

module carte() {   // volumes simplifies, pour situer les decoupes
  translate([o, o, z_pcb - pcb[2]]) {
    color("#1f5c3a") cube(pcb);
    translate([0, 0, pcb[2]]) {
      color("#b8b8b8") translate([1, -0.2, 0]) cube([16, 21.3, 13.4]);          // RJ45
      color("#cfcabd") translate([18.5, -1.3, 0]) cube([15, 12.2, 6.1]);        // HDMI
      color("#e8e8e8") translate([35, -0.2, 0.1]) cube([9, 7.5, 3.2]);          // USB-C CIBLE
      color("#e8e8e8") translate([-0.2, 26.5, 0.1]) cube([7.5, 9, 3.2]);        // USB-C EXT
      color("#d0d0d0") translate([30.5, 12.4, 0]) cube([14.7, 14, 1.9]);          // microSD
      color("#303030") translate([21.5, 26, 0]) cube([10, 10, 0.9]);            // ESP32-P4
      color("#303030") translate([23, 15.5, 0]) cube([6, 6, 1.2]);              // TC358743
      color("#f0f0f0") translate([41.2, 38.0 - 3.5, 0.2]) cube([4.6, 7, 2.5]);     // bouton FN
      color("#30c040") translate([29.6 - 0.8, 43.3, 0]) cube([1.6, 0.8, 0.6]);     // LED alim
      color("#e0c020") translate([33.6 - 0.8, 43.3, 0]) cube([1.6, 0.8, 0.6]);     // LED etat
    }
  }
}

if (vue == "coque") { color("#e9e4d8") coque(); if (montrer_carte) carte(); }
else if (vue == "eclate") {
  color("#e9e4d8") coque();
  if (montrer_carte) translate([0, 0, 12]) carte();
  color("#e9e4d8") translate([0, 0, 30]) couvercle();
} else {
  color("#e9e4d8") coque();
  if (montrer_carte) carte();
  color("#e9e4d8") couvercle();
}
echo(dimensions_exterieures = ext);
