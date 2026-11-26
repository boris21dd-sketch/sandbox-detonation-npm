## 1. Erreurs restantes dans le plan, par tâche

**A1** — Fait : A1 édite le `package.json` du paquet sous test (`main=../_sbx/pilote.cjs`), donc la mesure ne portera plus sur l'artefact publié et le `main` pointe hors de la racine du paquet.
Test : `sha256sum package/package.json` avant/après A1 → hashs différents ; `cd package && node -e "console.log(require.resolve('.'))"` → résout vers `../_sbx/pilote.cjs`.
`# INCONNU:` version de Node et comportement exact d'un `main` contenant `../`.

**A2** — Fait : le fait 5 dit que detonate.js lance les cycles de vie puis le pilote les rejoue ; A2 ne corrige que le pilote, donc si detonate.js les lance encore, le double persiste.
Test : `grep -n "postinstall\|preinstall\|lifecycle" detonate.js _sbx_scenario3.cjs` → compter les appels ; après correction, `grep -c "postinstall" traces/run_001.log` doit valoir 1, pas 2.
`# INCONNU:` detonate.js lance-t-il aussi `prepublishOnly` (fait 7) ?

**A3** — Fait : le repli sur `--legacy-peer-deps` en cas d'échec restaure exactement la cause de `charges=0` (fait 4), et A3 ne garantit pas que le pilote fasse un `require` du paquet après installation.
Test : après A3 sans repli, `cd $TMPDIR/package && node -e "require('.')"` → doit charger sans `Cannot find module` ; `grep -c "charges=0" traces/run_001.log` → 0 pour ce paquet.
`# INCONNU:` le pilote fait-il un `require` explicite du paquet ?

**A4** — Fait : `mktemp -d` isole le dossier de départ mais ne change pas l'UID du processus exécutant le code du paquet ; voir réponse 3.
Test : voir réponse 3.

**A5** — Fait : npm n'exécute jamais `prepublishOnly` à l'installation (seulement sur `npm publish`), donc « hors phase par défaut » laisse une porte ouverte ; de plus A5 ne dit pas qui l'exécute et ne traite pas `prepublish`/`prepare`.
Test : `grep -rn "prepublishOnly" detonate.js _sbx_scenario3.cjs` → identifier le lanceur ; après correction, `grep -c "prepublishOnly" traces/run_001.log` → 0 ; `npm install --loglevel silly` sur un paquet avec `prepublishOnly` → aucune exécution.
`# INCONNU:` version de npm et liste exacte des scripts exécutés à l'installation.

**A6** — Fait : recalculer sur les traces existantes ne peut pas créer les données manquantes (réseau non lu, fait 8 ; filiation `sh -c` si absente), et si les traces n'ont pas le fd, `net.write` vers stdout (fd 1/2) et vers un vrai socket sont indiscernables.
Test : `grep -cE "connect\(|sendto\(" traces/run_001.log` → 0 (réseau absent) ; `grep -c "ppid" traces/run_001.log` → `# INCONNU:` les traces contiennent-elles les ppid ? ; `grep -c "fd=" traces/run_001.log` → `# INCONNU:` les traces contiennent-elles le fd ?

## 2. Trou couvert par AUCUNE tâche

Trou principal : **la collecte du réseau réel**. Fait : le fait 8 dit que seul `net.write` a été lu et que dns.lookup/net.connect/tls.connect n'ont pas été tracés ; aucune tâche A1–A6 n'ajoute de sonde réseau, et A6 ne recalcule que l'attribution sur ce qui existe.
Test : `grep -E "dns.lookup|net.connect|tls.connect" traces/*.log | grep -v "net.write" | wc -l` → 0 sur les traces existantes ; il faudrait `strace -f -e trace=network -o trace.net ...` ou un `iptables -j LOG`, absent du plan.

Autres trous non couverts : **canaris et nonce** (aucun fichier piège ni identifiant unique par run), **redémarrage entre sondes**, **filiation des enfants `sh -c`** (A6 la mentionne mais ne prévoit pas de la collecter si absente). Fait : aucun canari n'est déposé dans le dossier de travail, donc une lecture/exfiltration de fichier n'est pas détectable.
Test : `find $TMPDIR -name "*canari*" -o -name "*nonce*"` → rien ; contre-mesure : `echo "nonce-$RANDOM-$(date +%s)" > $TMPDIR/canari.txt` puis `grep "canari" traces/*.strace` → 0 open/read.
`# INCONNU:` le banc redémarre-t-il la sandbox entre les sondes d'un même run ?

## 3. A4 est-elle suffisante contre les fichiers root ?

Non. Fait : `mktemp -d` crée un répertoire 0700 possédé par l'utilisateur, mais si le code testé tourne en root (ou fait `chown root`) et crée des fichiers root, `rm -rf` en non-root échoue silencieusement.
Test : `d=$(mktemp -d); sudo touch $d/f; sudo chown root:root $d/f; rm -rf $d 2>/dev/null; test -d $d && echo "ECHEC rm -rf silencieux"` → affiche ECHEC ; détection : `find $d ! -user $(id -u) -ls` avant nettoyage ; contre-mesure : `sudo rm -rf $d` ou exécution en non-root (`setpriv --reuid=nobody --regid=nogroup --clear-groups node ...`).
`# INCONNU:` UID sous lequel le banc exécute le code du paquet.

## 4. Faut-il rejouer la campagne après A1+A2+A3 ?

Il faut **REJOUER**. Fait : `charges=0` sur 218/218 lignes (fait 4) signifie que le code du paquet n'a jamais été exécuté dans les traces existantes, et le réseau n'a pas été lu (fait 8) ; on ne peut pas attribuer a posteriori un code qui n'a pas tourné ni des événements qui n'ont pas été collectés — A6 ne peut que réattribuer les événements présents.
Test : `grep -c "charges=0" traces/*.log | awk -F: '{s+=$2} END{print s}'` → 218 ; après rejoue avec A3, ce compte doit diminuer (0 pour les paquets dont les peer deps sont satisfaites) ; `python3 attribuer.py traces/run_001.log -o out.json` → champs `origine_processus` vides ou `# INCONNU` si les ppid manquent, prouvant que la réattribution est partielle.

## 5. Ordre d'exécution correct et validation sur UN run

Ordre :
1. **A4** (mktemp -d + nettoyage robuste + détection des fichiers root) — base de l'isolation.
2. **A5** (bloquer totalement `prepublishOnly` et scripts hors installation, côté detonate.js ET pilote) — évite les appels réseau réels.
3. **A2** (un seul jeu de cycles de vie, côté detonate.js uniquement) — définit ce qui est exécuté.
4. **A1 corrigé** : déplacer le pilote dans `_sbx/` frère de `package/` **sans modifier le `package.json` du paquet** (lancer `node ../_sbx/pilote.cjs` avec cwd=package) — fixe l'attribution sans altérer l'artefact.
5. **A3** (retirer `--legacy-peer-deps`, repli si échec mais marquer le run `charges=0` non résolu) — permet de charger le `main`.
6. **A6** (`attribuer.py`) — en dernier, sur les nouvelles traces.

Validation sur UN run avant la série (paquet avec postinstall + peer dep, ex. node-sass) :
- `d=$(mktemp -d); <run>; test ! -d $d && echo OK` ou `find $d ! -user $(id -u) | wc -l` → 0.
- `grep -c "postinstall" traces/run_001.log` → 1.
- `grep -c "prepublishOnly" traces/run_001.log` → 0.
- `grep -c "registry.npmjs.org" traces/run_001.log` → 0 (hors faux-Internet).
- `grep -c "charges=0" traces/run_001.log` → 0.
- `python3 attribuer.py traces/run_001.log` → `origine_code=outil` pour le pilote (pas `paquet`), et `origine_code`/`origine_processus`/`flux_local` tous renseignés : `python3 attribuer.py traces/run_001.log | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['origine_code'] and d['origine_processus'] and 'flux_local' in d"`.
Puis lancer la série des 204 runs.