1. **Trous vus par AUDIT 1, pas par AUDIT 2**
- **Ré-attribution F2×F6** : l'entrée `main` force `dans_paquet=true`, donc `main=../_sbx/pilote.cjs` annule le déplacement et écrase le `main` réel qu'A3 cherche à charger. A2 ne voit que le hash de l'artefact.
- **Sonde `main` orpheline** : A2 fait bien 2→1 mais supprime le producteur de l'entrée `main` ⇒ `charges=0` [F4] par une cause nouvelle ; producteur pilote/detonate.js laissé INCONNU.
- **Causalité F7+F5** : `prepublishOnly` vient du **rejeu**, jamais d'une phase npm ⇒ filtre sur le rejeu **+ exclusion stricte `node_modules/*`**, pas sur « phase installation / par défaut ». A2 laisse « qui l'exécute » en INCONNU.
- **Ordonnancement npm** : après retrait du rejeu, aucune tâche ne rétablit qui ordonnance les dépendances [F7].
- **`$FAUX_NET` 114/218 + 10 runs `dns.lookup`/`net.connect`/`tls.connect`** : données déjà produites, non ingérées — à joindre, pas à recapturer.
- **A6** : 6 valeurs `origine_code` vs 3 `origine_processus` ; `dans_paquet` relatif à l'entrée ⇒ aucun chemin à ré-attribuer (Q4).
- **A3** : repli `--legacy-peer-deps` sur sous-population **non marquée**, à corréler explicitement à `charges=0`.
- **A4** : `set -e`, contrôle du `rc` de `rm -rf`, `chown`/`chmod -R u+w` — A2 ne contrôle pas le rc.

**Trous vus par AUDIT 2, pas par AUDIT 1**
- **Intégrité de l'artefact publié** : `sha256sum package/package.json` avant/après, version Node, comportement d'un `main` avec `../`.
- **`fd=`** : sans fd, `net.write` vers stdout (1/2) et vers un socket sont indiscernables ⇒ `flux_local` non étiquetable sur l'existant.
- **`prepublish` / `prepare`**, version npm, liste exacte des scripts d'installation.
- **Sonde réseau à créer** : `strace -f -e trace=network` / `iptables -j LOG`, `connect(`/`sendto(` = 0.
- **Canaris/nonce avec contre-mesure** : `nonce-$RANDOM` + `grep open/read` dans `.strace` (A1 tient l'absence pour non assertable).
- **`setpriv --reuid=nobody` / `sudo rm -rf` / `find ! -user`** : changer l'UID du code, pas celui du nettoyeur.
- **`origine_code=outil`** pour le pilote + assertion JSON sur les 3 champs.

Partagés, donc non exclusifs : `ppid`/filiation `sh -c`, redémarrage entre sondes, A4 insuffisante, REJOUER.

2. **Contradictions et arbitrage sur les faits rappelés**
- **Double `postinstall`** : A2 « le double persiste si detonate.js lance encore » / A1 « 2→1 acquis, sonde perdue » → **A1**. F5 = detonate(1) + rejeu pilote(1) ; retirer le pilote donne `grep -c ':postinstall'` = 1. A2 contredit son propre Fait 5.
- **Lanceur de `prepublishOnly`** : A2 « INCONNU : detonate.js ? » / A1 « le rejeu [F5] » → **A1**. F7 (npm ne le déclenche **jamais** à l'install) + F5 ne laissent que le pilote ; le filtre « phase » est inopérant.
- **Repli A3** : A2 « repli si échec, run marqué `charges=0` non résolu » / A1 « repli = `charges=0`, à supprimer » → **A1**. F4 : `--legacy-peer-deps` ⇒ 218/218 ; marquer un `main` non chargé ne le charge pas (Q4).
- **`flux_local`** : A1 « substituer un `flux_local` stdout » / A2 « indiscernable sans fd » → **A2 sur les 218 lignes** : F3 (seul `net.write`) + F8 (0 `connect`/`sendto`) ⇒ aucun discriminant. A1 ne vaut que sur traces neuves, ce qu'il concède lui-même en Q5.
- **Réseau** : A1 « journal 114/218 à joindre » / A2 « non tracé, sonde à ajouter » → **A1**. F8 est chiffré ; le `grep→0` d'A2 ne couvre que `traces/*.log`, pas `$FAUX_NET`. Le `strace` d'A2 reste requis pour `ppid`/`fd`, pas pour recapturer le journal.
- **Canaris** : A2 « Fait : aucun canari n'est déposé » / A1 « absence non assertable » → **A1**. Aucun F1–F8 n'en parle ; `find $TMPDIR → rien` sur un banc non fourni n'est pas un constat. La contre-mesure d'A2 est recevable, le « Fait » ne l'est pas.
- **Ordre Q5 + fichier du gate** : A2 (A1 corrigé en 4e, gate `registry` sur `run_001.log`) / A1 (A1 corrigé en 2e, gate sur `$FAUX_NET`) → **A1** : F6 crée `_sbx/` qu'A5 doit exclure, et F2 exige un `main` résolu avant qu'A2 n'en retire le producteur ; l'ordre d'A2 reproduit « rien ne charge le main ». Le **remède** d'A2 (ne pas éditer `package.json`, lancer `node ../_sbx/pilote.cjs` avec cwd=package) est retenu, son placement non.

3. VERDICT : A4 (`set -e` + rc `rm -rf`) → A1 sans éditer `package.json` (pilote `../_sbx/pilote.cjs`, cwd=package, sonde `require('.')`) → A5 (exclusion rejeu + `node_modules/*`) → A2 (detonate seul, 2→1) → A3 (zéro `--legacy-peer-deps`, aucun repli) → A6 sur traces neuves seulement.
Joindre `$FAUX_NET` 114/218 + 10 runs dns/connect et capturer `ppid`/`fd`/strace ; `flux_local` uniquement si fd=1/2, sinon INCONNU — aucune réattribution des 218 lignes.
REJOUER 1 run témoin, gate simultané : `charges>0` sur le vrai `main`, 1 `:postinstall`, 0 `prepublishOnly`, 0 `registry.npmjs.org`, 0 `_sbx/` à `dans_paquet=true`, `ppid` sur `sh -c`, `rm -rf` rc=0.
Gate vert ⇒ 204 runs ; une seule ligne rouge ⇒ arrêt, ni série ni correction d'étiquettes a posteriori.