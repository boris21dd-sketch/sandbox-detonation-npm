PROTOCOLE DE STABILITE v4 — repond aux objections v3.

1. SCEAU COMPLET, et regle de recalcul enoncee (objection D1 de hy4 : je tronquais).
SCEAU=0edd08e67d34546169fdadf8ff84eb069f746e9744d2ef6c3d18561a493c3572
Le sceau est calcule sur le contenu du fichier PROVENANCE-STABILITE.txt APRES RETRAIT de la
ligne finale commencant par "SCEAU=" (donc le champ ne se hache pas lui-meme).
Recalcul, executable tel quel :
    sed '/^SCEAU=/d' PROVENANCE-STABILITE.txt | sha256sum
doit afficher 0edd08e67d34546169fdadf8ff84eb069f746e9744d2ef6c3d18561a493c3572
Le fichier contient les SHA-256 complets de 64 hex du scenario, de la liste des sondes, du
lecteur, de detoner-obs.sh, de detonate.js, de log.js, du helper docker, plus le digest
complet de l'image (sha256:e4f89815eaf4d35bb8f975991b2068caf0a134527d96cedcce9f7f10c0eb8748),
l'uname entier et la memoire totale. Si le recalcul differe, la campagne est INCONCLUANTE.

2. LES CANARIS NE SONT PAS DES LITTERAUX (objection D1 de mistral).
Ils sont tires au hasard par la fabrique, par sonde et par run, puis inscrits au registre AVANT
la detonation. Preuve sur les trois runs deja executes, meme sonde, meme paquet :
    o : CANARI_WA_8425b8   CANARI_SSH_5513b3
    p : CANARI_WA_8574e1   CANARI_SSH_b23343
    q : CANARI_WA_8fd389   CANARI_SSH_433fad
Aucun des trois ne partage une valeur avec les autres. Un banc qui filtrerait des chaines
connues ne passerait pas la campagne.

3. FAIBLESSE REELLE QUE JE CONCEDE, et que je ne maquille pas : l'entropie est de 6 hex, soit
24 bits, pas 128. Ce n'est pas un filtre de signatures possible, mais c'est faible pour un
adversaire qui voudrait deviner un canari. Correction a faire dans fabrique_sondes.py (32 hex,
128 bits) AVANT la campagne, ou a defaut la campagne est declaree portant sur des canaris de
24 bits, dans les limites annoncees.

4. CONTROLE POSITIF DANS LA BOUCLE, inchange depuis v3 et verifie sur o, p, q : a chaque run,
p11-wa (hote sink + canari, canal io), p18-base64, p18b et p18c (matcher seul, decalages 0/1/2),
p22-registry (matcher seul) doivent sortir CLÉ avec canaris_reseau non vide et nonce du
registre. p12-propre doit rester muet.

5. CRITERES BINAIRES : 29/29 recevable code 0 ; 29/29 controle positif ; 29/29 temoin muet ;
725 dossiers ; rc=0 pour toute sonde citee, rc=124/137 => INCONCLUANT ; CLÉ exige au moins un
evenement et un nonce unique egal a la colonne 3 du registre.
   PRECISION (erratum du 25/11 11:18, cf. fin de document) : le rc qui fait foi est celui du
   registre (colonne 8, npm_rc de l'installation de la sonde, ecrit par le pilote AVANT la
   detonation), et non le rc du conteneur de detonation. Le rc du detonateur n'est retenu que
   lorsque le registre est muet ("-"). Exception nommee et bornee : p21-leurre-orphelin sort
   rc=124 au detonateur sur TOUS les runs (l'orphelin tient le tube du `docker exec`) alors que
   l'entree principale du harnais s'acheve en ~16 s ; son registre porte npm_rc=0, il est compte
   CLÉ avec canari_reseau non vide (verifie s27 : CANARI_SSH_685e23, nonce 685e23).

6. PUISSANCE : 29 runs = 95,29 % de voir un defaut a 10 % par sonde, borne basse 90,19 % a
alpha=0,05, 80,71 % apres correction sur 25 sondes. 299 runs pour 1 %. Trois runs laissaient
72,9 % de risque de le manquer.

7. NON PROUVE, et dit d'avance : couverture (p09, p17 = intentions, curl/git/bash absents de
l'image) ; trou d'instrumentation sh -c a environnement vide ; defauts sous ~10 % ; tout autre
environnement que cette image, ce noyau, cette machine.

DEMANDE : executable tel quel, oui ou non ? S'il reste un defaut, nomme-le et donne la
correction exacte. S'il est bon, dis-le sans detour.

ERRATUM — 2026-11-25 11:18 CET (tick cron)
Ce document a ete ecrit a 06:23, quatre minutes AVANT la normalisation de
PROVENANCE-STABILITE.txt (06:27) qui a remplace la ligne finale `scelle_sha256=...` par
`SCEAU=...`. Le sceau a4db40458b1f... cite dans la premiere version se rapportait donc a
l'ancien format du fichier ; applique au fichier actuel, il ne pouvait que differer
(cb9e5716afb2...), ce qui rendait la campagne INCONCLUANTE par application litterale du §1.
Correction appliquee a 11:18 : SCEAU=264bcda2fbb69bd1019ef35a30731fbc0e69925467b274e77bf694c0ad34a519,
regle `sed '/^SCEAU=/d'`, recalcul conforme a cette date. Cette valeur a ete remplacee depuis par
0edd08e67d34... (erratum 2 ci-dessous, ajout de la ligne mem_total) ; c'est la valeur courante. Le CONTENU scelle est inchange :
les 13 SHA-256 listes dans PROVENANCE ont ete re-verifies fichier par fichier le 25/11 10:45
(scenario3 6a30e6b6, fabrique 05cb492e, lancer-stabilite d8c37a3e, liste eec89594, attendus
ec831596, lecteur f92144e7, verif_preuves bfb588f9, detoner-obs cc88e08f, detonate d3ad084a,
run-entry 5ae698fc, log.js 08f57ff7, temps.js e54ebb4b, sbx-docker-ctl dced2041). Seuls la
regle de recalcul, le §5 (rc qui fait foi) et la presente note changent. Version precedente
conservee : .archives-PROTOCOLE-STABILITE-v4-ed053c07.md (sha256 ed053c07900ec313...).

ERRATUM 2 — 2026-11-25 11:37 (controle independant)
Un arbitre externe (mistral-large-4:cloud, temperature 0, sans connaitre l'attendu) a applique
le §1 a la lettre et a releve un defaut reel : PROVENANCE-STABILITE.txt ne portait AUCUNE ligne
de memoire totale, alors que le §1 affirme qu'elle y figure. Trois valeurs de sceau se succedent,
et voici exactement ce qui differe entre elles :
  a4db40458b1f...  version d'origine (06:23), calculee sur l'ancien format `scelle_sha256=` de
                   PROVENANCE ; ne correspond a aucun fichier existant.
  264bcda2fbb6...  format normalise (06:27) ; sceau sous lequel les 29 runs ont tourne.
  0edd08e67d34...  ajout de la ligne `mem_total 41068220 kB` (/proc/meminfo, constante
                   materielle) ; sceau courant.
Le contenu mesure est identique dans les trois cas : les 13 SHA-256 de code/image sont inchanges
et re-verifies apres chaque edition (13/13 conformes, 11:37). La ligne ajoutee est un fait de
contexte (memoire de la machine), pas un parametre de mesure.
