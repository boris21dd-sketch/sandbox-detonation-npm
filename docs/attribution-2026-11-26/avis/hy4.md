**1. Erreurs restantes, par tâche**

**Fait.** Le plan reste faux en **A1** (`main=../_sbx/pilote.cjs` écrase le `main` réel que A3 cherche à charger et, l'entrée `main` forçant `dans_paquet=true` [F2], ré-attribue le banc au paquet malgré le déplacement [F6]), **A2** (ramène bien 2→1 [F5] mais supprime le rejeu du pilote sans préserver de sonde pour l'entrée `main` [F2], donc A3 installe les pairs sans que rien ne charge le `main` et `charges=0` [F4] persiste par une cause nouvelle ; `# INCONNU:` c'est le pilote ou `detonate.js` qui produisait l'entrée `main`), **A3** (le « repli si echec » réintroduit `--legacy-peer-deps`, donc `charges=0` [F4], sur une sous-population non marquée), **A4** (ne traite pas l'UID, cf. Q3), **A5** (filtre la « phase installation » alors que le F7 dit que npm n'y déclenche **jamais** `prepublishOnly` — le script vient du rejeu [F5] — et « par defaut » n'est pas l'exclusion stricte des `node_modules/*` [F7]) et **A6** (n'ingère ni le faux-Internet 114/218 ni les 10 runs dns/connect [F8], annonce une filiation `sh -c` sans `ppid`/`strace` dans les traces existantes, et donne 6 valeurs à `origine_code` contre 3 à `origine_processus`).

**Test.**
```sh
# A1 — le main résolu doit rester DANS package/, et aucun _sbx/ ne doit être à true
node -e "console.log(require.resolve('./package'))"
grep 'dans_paquet=true' "$JOURNAL" | grep '_sbx/'          # attendu: vide
# INCONNU: chemin/format de $JOURNAL non fourni (218 lignes citées, non localisées)

# A2 — une seule exécution, ET une entrée main toujours produite
test "$(grep -c ':postinstall' "$JOURNAL")" -eq 1
grep -c '^main' "$JOURNAL"                                  # doit rester > 0
# INCONNU: producteur de l'entrée main (pilote ou detonate.js)

# A3 — tout repli doit être explicitement corrélé à charges=0
grep -Rn 'legacy-peer-deps' "$RUNS" | wc -l
grep -c 'charges=0' "$JOURNAL"
# INCONNU: arborescence $RUNS des 204 runs non fournie

# A5 — le filtre doit porter sur le rejeu ET sur les dépendances
grep -Rn 'prepublishOnly' "$PLAN" node_modules/*/package.json | grep -v EXCLU
grep -c 'registry.npmjs.org' "$FAUX_NET"                     # attendu 0
# INCONNU: $PLAN (plan fourni en texte libre) et $FAUX_NET non fournis

# A6 — champs réellement disponibles
head -1 "$JOURNAL" | grep -oE 'ppid|strace|dns|connect|abs_path' || echo "# INCONNU: champs du journal non fournis"
grep -n 'origine_processus' attribuer.py
```

---

**2. Trou couvert par AUCUNE tâche**

**Fait.** Aucune tâche ne lit le journal du faux-Internet (114/218 lignes, F8) ni les 10 runs `dns.lookup`/`net.connect`/`tls.connect` — A6 ne substitue au `net.write` (F3) qu'un `flux_local` stdout — et aucune ne rétablit l'ordre d'ordonnancement réel de `npm` après suppression du rejeu (A2/A5 retirent des exécutions sans dire qui ordonnance les dépendances, F7) ; l'attribution des enfants `sh -c` est nommée en A6 mais non couverte faute de capture strace ; `# INCONNU:` canaris, nonce, redémarrage entre sondes, dont le contexte ne dit rien, et `# INCONNU:` si `detonate.js` appelle `npm install` ou énumère lui-même les scripts.

**Test.**
```sh
grep -nE 'faux.internet|dns\.lookup|net\.connect|tls\.connect|strace|ppid|ordre|npm install' "$PLAN" || echo "AUCUNE TACHE"
# INCONNU: $PLAN fourni en texte, pas en fichier
wc -l "$FAUX_NET"          # 114/218 lignes à joindre aux traces, pas à ignorer
# INCONNU: chemin de $FAUX_NET non fourni
grep -Rn 'canary\|nonce\|restart\|reboot' "$BANC" || echo "# INCONNU: chemin du banc non fourni, absence non assertable"
```

---

**3. A4 contre les fichiers root**

**Fait.** Non : `mktemp -d` crée un dossier neuf appartenant à l'UID courant mais ne change ni l'UID du créateur des fichiers root (A6 atteste qu'un `sh -c` écrit, F7 qu'un vrai npm tourne) ni celui du nettoyeur, et A4 n'ajoute ni `chown`/`chmod -R u+w`, ni `set -e`, ni contrôle du code de retour de `rm -rf`, donc l'échec reste silencieux dans un dossier simplement renommé ; `# INCONNU:` UID du processus de nettoyage et du créateur des fichiers root, et `# INCONNU:` droits disponibles pour reproduire le cas ici.

**Test.**
```sh
d=$(mktemp -d)
sudo install -o root -g root /dev/null "$d/f" 2>/dev/null || echo "# INCONNU: root non reproductible sur ce poste"
stat -c '%U:%G %a' "$d" "$d/f"
rm -rf "$d"; echo "rc=$?"
test -e "$d" && echo "ECHEC SILENCIEUX — A4 insuffisante"
# INCONNU: ps -o uid= -p <pid_nettoyeur>   (pid non fourni)
```

---

**4. Rejouer ou réattribuer**

**Fait.** Il faut **REJOUER** : A1 déplace le code (F6), A2 retire une exécution sur deux (F5) et A3 fait enfin exister le graphe de pairs (F4, `charges=0` sur 218/218), donc les données manquantes sont des **événements jamais produits** (un `main` non chargé, `Cannot find module 'webpack'`, un `postinstall` en trop) et non des étiquettes mal posées — `attribuer.py` ne peut pas re-attribuer une écriture qui n'a pas eu lieu, et `dans_paquet` (F2) étant relatif à l'entrée, il ne contient pas le chemin qu'A1 corrige ; `# INCONNU:` présence éventuelle d'un `ppid` ou d'un chemin absolu déjà persisté dans les 218 lignes.

**Test.**
```sh
grep -c 'charges=0' "$JOURNAL"                 # 218/218 : aucun main à réattribuer
grep -c "Cannot find module 'webpack'" "$JOURNAL"  # dépendance absente, non reconstructible
grep -c 'node-sass:postinstall' "$JOURNAL"     # 2 (F5) : à ne pas rejouer, pas à « corriger »
head -1 "$JOURNAL" | grep -oE 'ppid|abs_path' || echo "# INCONNU: champs/format du journal non fournis"
```

---

**5. Ordre d'exécution et gate sur UN run**

**Fait.** L'ordre est **A4** (isolation + contrôle du `rc` de `rm -rf`) → **A1 corrigé** (déplacer vers `_sbx/` **sans** écraser `main`) → **A5 corrigé** (exclusion stricte du rejeu, racine **et** `node_modules/*`) → **A2** (2→1, `detonate.js` seul exécutant, sonde `main` conservée) → **A3** (pairs installés, repli marqué) → **A6 corrigé** (+ capture `ppid`/strace, + ingestion `$FAUX_NET`, appliqué aux **nouvelles** traces seulement) → **1 run témoin** → série des 204 runs, le run unique devant valider simultanément `charges>0` sur le vrai `main`, une seule occurrence de `:postinstall`, zéro `registry.npmjs.org`, zéro `_sbx/` à `dans_paquet=true`, `net.write` étiqueté `flux_local`, un `ppid` sur un `sh -c`, et `rm -rf` rc=0 même avec fichier root ; `# INCONNU:` noms exacts des fichiers de run et variable désignant le run témoin.

**Test.** *(gate : toute ligne qui échoue interdit `for i in $(seq 204)`)*
```sh
r="$RUN_TEMOIN"        # INCONNU: variable/chemin d'un run non fourni
test "$(grep -c 'charges=0' "$r/journal")" -eq 0
test "$(grep -c ':postinstall' "$r/journal")" -eq 1
test "$(grep -c 'registry.npmjs.org' "$FAUX_NET")" -eq 0
! grep 'dans_paquet=true' "$r/journal" | grep -q '_sbx/'
grep -q 'flux_local' "$r/attribue"
grep -q 'ppid' "$r/attribue"
node -e "process.exit(require.resolve('./package').startsWith('./package/')?0:1)"
d=$(mktemp -d); sudo install -o root -g root /dev/null "$d/f"; rm -rf "$d"; test ! -e "$d"
# INCONNU: $r/journal, $r/attribue, $FAUX_NET non fournis ; le faux-Internet doit être JOINT, pas remis à 0 sans lecture
```