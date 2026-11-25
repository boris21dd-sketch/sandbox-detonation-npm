# CAMPAGNE DE STABILITE — 29 runs, résultat

Vérification mécanique par `outils/verif-campagne.py`, qui relit les 29 registres et les
29 sorties du lecteur. Aucun chiffre n'est repris d'un run précédent.

```
runs                          29 / 29
BANC RECEVABLE (code 0)       29 / 29
sondes dénombrées            725 / 725   (29 × 25)
CLÉ                          696          (24 × 29), aucune exception
témoin p12-propre muet        29 / 29
contrôle positif (5 sondes)   29 / 29     p11-wa, p18-base64, p18b, p18c, p22-registry-ssh
   → verdict CLÉ + canaris_reseau non vide + nonce du registre, à chaque run
nonce absent ou étranger       0
rc de détonation ≠ 0           0
dossier de sonde manquant      0
canaris réutilisés entre runs  0          (4 126 canaris distincts sur la campagne)
```

## Ce que la campagne établit

Sur cette image, ce noyau, cette machine, le banc produit 24 détections et un témoin muet de
façon reproductible sur 29 exécutions consécutives, sans dérive du compte, sans perte de
rapatriement, sans canari rejoué. La puissance : 95,29 % de chance d'observer un défaut à 10 %
par sonde (0,9²⁹ = 4,71 %), borne basse unilatérale 90,19 % à α = 0,05, 80,71 % après correction
sur 25 sondes. Un défaut à 1 % demanderait 299 runs.

**Le contrôle positif est le point qui compte** : les cinq sondes désignées sortent `CLÉ` avec
un canari non vide à chacun des 29 runs. Un détecteur mort au dixième tour se serait vu ; il ne
s'est pas vu.

## Ce que la campagne n'établit pas — écrit avant, pas après

- **couverture** : `p09` et `p17` ne mesurent que des intentions, `curl`, `git` et `bash` sont
  absents de l'image `sbx-detonation:obs`. 29 répétitions d'une sonde qui ne teste rien donnent
  29 résultats vides ;
- **trou d'instrumentation** : un enfant lancé par `sh -c` avec un environnement vidé échappe au
  journal. Aucune répétition ne le révèle ;
- **entropie des canaris** : 24 bits, pas 128. Non filtrable en pratique (ils changent à chaque
  run), mais faible face à qui voudrait deviner ;
- **racine de confiance** : la machine de l'opérateur. Le sceau protège de la dérive, pas d'un
  opérateur qui réécrirait tout ;
- **défauts sous ~9,8 % par sonde** ;
- **généralisation** : un autre noyau, une autre image, une autre charge machine ne sont pas
  couverts.

## Provenance

`PROVENANCE-STABILITE.txt`, sceau en première ligne :

```
SCEAU=0edd08e67d34546169fdadf8ff84eb069f746e9744d2ef6c3d18561a493c3572
recalcul : sed '/^SCEAU=/d' PROVENANCE-STABILITE.txt | sha256sum   → identique

(sceau antérieur `264bcda2…` remplacé le 25/11 11:36 par l'ajout de `mem_total` exigé au §1 ;
version antérieure conservée en `.archives-PROVENANCE-264bcda2.txt`. Corrigé ici au tick 11:59.)
```

Treize fichiers scellés, dont `fabrique_sondes.py` (qui tire les canaris), `lancer-stabilite.sh`
(la boucle) et le comparateur. `registres-sceau.txt` contient l'empreinte du registre de chacun
des 29 runs.

## Deux corrections faites en cours de route, à ne pas oublier

- `outils/verif-campagne.py` cherchait les lignes de verdict avec `^s\d{3}\s` alors que les tags
  font six caractères (`s01011`). Les 29 « contrôles positifs manquants » du premier passage
  étaient un défaut de mon script, pas du banc. Corrigé, puis 0 manquant.
- le nom exact de la sonde est `p22-registry-ssh`, pas `p22-registry`.
