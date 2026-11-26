# AUDIT CLAUDE — attribution des gestes (26/11)
## 1. SCAN
[LIRE-DABORD.md, EMPREINTES.txt (25/25 OK), attribution-paquet.json, comportements-paquet.json, detonation.tsv, journal-lot-{1,10..19}.log, events-manq16010.jsonl, regles/tour-7/{retenues, hy4-prop, mistral-prop, kimi-prop, hy4-juge, mistral-juge, kimi-juge-hy4, kimi-juge-mistral}.md (grep, non lus en entier)]
Non lus : demander.py (outil de tours LLM, hors sujet). Absent : `lib/sbx/provenance.js` (calcul réel de `dans_paquet`) → déduit des traces.
Statuts : **P** prouvé ici sur traces brutes · **D** lu dans le code · **H** à vérifier.

## 2. DIAG — ce que le dossier ne dit pas
1. **P — `dans_paquet` est relatif à l'ENTRÉE, pas au paquet.** Dans l'entrée `node-sass:postinstall`, npmlog (autre dépendance) = `false` (426), node-sass = `true` (81) ; dans `main`, toute dépendance = `true` (1265). Le booléen change de sens d'une entrée à l'autre → inutilisable tel quel, même pilote exclu.
2. **P — `net.write` « socket » = écritures stdout/stderr, pas du réseau.** Fixture : 426/449 depuis `npmlog/log.js:271` (journal npm), 7 depuis le `console.error('[trace]…')` du pilote, le reste depuis les scripts de node-sass. DOUTE 1 tranché : bruit de journalisation. Les 4 règles LLM reposent sur `net.write` → elles mesurent la verbosité, pas l'exfiltration. **À jeter telles quelles**, pas « non mesurables ».
3. **P — « deux contacts nominatifs » est faux.** 10 runs ont `dns.lookup/net.connect/tls.connect/https.request` attribués : manq6004, 8004, 17010, 5010, 6003, 16010, 11004, 17003, 7002, 7007. Et le faux-Internet a vu du trafic sur 114/218 lignes de journal (`evenements_reseau>0`). L'analyse n'a regardé que `net.write`.
4. **P — github.com (manq16010, manq17003) = node-sass 4.14 / 3.13** qui télécharge son module binaire depuis les « releases » GitHub pendant son installation : comportement documenté d'une DÉPENDANCE. Lancé ici par le pilote dans l'entrée `main` (doublon, voir 6).
5. **P — le code au chargement n'est presque jamais observé.** manq16010 : `Cannot find module 'webpack'` (dépendance pair) → main jamais chargé. Cause **D** : `npm install … --legacy-peer-deps` n'installe pas les dépendances pair. Journal : `charges=0` sur 218/218 lignes → **H** : si `charges` = champ `charge` du pilote, AUCUN main n'a été chargé de toute la campagne. Vérifier : `grep -h '"etape": *"main"' runs-obs/manq*/run/_sbx_etat.jsonl | grep -vc '"charge": *""'`.
6. **D/P — tout est exécuté deux fois.** detonate.js lance les cycles de vie (paquet + dépendances) et le bin en entrées séparées ; le pilote (entrée `main`) les rejoue par execSync (étapes 1, 1 bis, 2). Fixture : `node scripts/install.js` de node-sass lancé par le pilote, seq 30, étiqueté `main`. Défaut hérité de MA conception (pilote antérieur au support des dépendances dans detonate.js).
7. **P — prepublishOnly des dépendances exécuté** : `cosmiconfig:prepublishOnly` lance le VRAI npm (`/usr/local/lib/node_modules/npm`) vers registry.npmjs.org. npm ne lance jamais ce script à l'installation. Et **npm EST dans l'image** (contredit « ni npm » du 25/11).
8. **P — 2 sondes perdues (EXTRACTION_ECHEC)** : `rm -rf` échoue en silence sur des fichiers root dans le dossier de travail réutilisé (`Permission denied`), puis l'extraction échoue.

## 3. RÉPONSES
**Q1 : c**, mais (b) se fait dans l'ANALYSE, pas dans `dans_paquet` du harnais (code root non fourni, et le booléen est déjà faux par construction, voir 2.1).
- (a) : pilote et `_sbx_*` dans `/work/paquet/_sbx/`, hors racine ; `main` du package.json = `../_sbx/pilote.cjs`. Pas besoin de toucher /opt.
- DOUTE 3 : OUI, le pilote est relatif au paquet : `P = __dirname` pour package.json, `_sbx_offset.json`, `_sbx_nonce.json`, `_sbx_deps_scripts.json`, node_modules, bins, candidats, cwd des enfants, trace de repli. Tout passe par `P = ../package` ; les fichiers du banc lus dans `_sbx/`.
- H : detoner-obs.sh doit extraire `_sbx/` à côté de `package/` (`tar -C /work/paquet`). Si le run de contrôle montre « main introuvable », c'est que non → m'envoyer la ligne d'extraction de detoner-obs.sh.
- Reste visible pour le paquet : `main` modifié dans son package.json, `../_sbx/` lisible pendant ses scripts d'installation (le nonce n'est supprimé qu'au démarrage du pilote). Acceptable : modèle de menace = erreur, pas adversaire.

**Q2 : ni booléen racine, ni trois valeurs : deux champs.**
- `origine_code` (fichier appelant) : paquet / dependance / banc / outil (npm, yarn de l'image) / node / inconnu.
- `origine_processus` (entrée lancée) : paquet / dependance / banc.
- Un `spawn` dont l'enfant `require` un fichier du paquet : `origine_code=paquet` dans l'enfant, `origine_processus` = l'entrée qui l'a lancé. Voulu.
- **DOUTE 4** : un fichier écrit par un `sh -c` est INVISIBLE au JS (sh n'est pas node). Seul strace le voit, et on l'attribue par filiation à l'entrée qui a lancé sh : `origine_processus=paquet` si c'est un cycle de vie du paquet. `origine_code` = inconnu. Le lecteur ne lit pas encore trace.raw.
- Outil : `attribuer.py` (A6), recalculé sur les traces existantes, sans relancer la campagne.

**Q3 : ni a, ni b, ni c tels quels.**
- « socket sans hôte » = journalisation (preuve ci-dessus) → `flux_local`, sorti du réseau. C'est (c), mais pour une raison différente : le bruit vient du paquet et de ses dépendances qui écrivent sur stderr, pas du harnais.
- Les vraies pistes sont les **10 runs à hôte** + le journal du faux-Internet. On les passe à `attribuer.py` (tri mécanique : Sonnet ou script), PAS à la main un par un.
- github.com = node-sass : à classer « téléchargement de binaire par une dépendance au cycle de vie » ; pas une graine de règle.

**DOUTE 2.** 0/204 sur des paquets propres ne mesure que les faux positifs, pas l'efficacité. Une règle se juge sur des positifs : les 25 sondes + des détonations de malwares connus. Et une règle qui compte `net.write` est morte d'avance (2.2).

## 4. CE QUE JE NE SIGNE PAS
- Aucun verdict de propreté sur les 203 : main presque jamais chargé (2.5), cycles de vie doublés (2.6), réseau non lu (2.3).
- Les règles du tour 7 : toutes à réécrire sur des canaux réseau à hôte + `origine_code`, puis à mesurer sur positifs.

## 5. TÂCHES (Sonnet) — voir SPEC 6
| ID | FILE | PB | FIX | TEST | COMPAT |
|---|---|---|---|---|---|
| A1 | sbx-scenario3.sh, _sbx_driver3.cjs | pilote dans le paquet | `_sbx/` frère de `package/`, `main=../_sbx/pilote.cjs` | `bash tests/test_scenario_a.sh`, `bash tests/test_scripts.sh` | H : extraction detoner-obs |
| A2 | _sbx_driver3.cjs | cycles de vie en double | supprimer étapes 1, 1 bis, 2 | test_scripts.sh | OK : detonate.js les fait |
| A3 | sbx-scenario3.sh | pairs non installées | sans `--legacy-peer-deps`, repli si échec, tracé | test_scenario_a.sh | OK : plus de mains chargés |
| A4 | sbx-scenario3.sh | dossier réutilisé | `mktemp -d`, `RESIDU:` si nettoyage impossible | test_scenario_a.sh | OK |
| A5 | detonate.js (root, avec B) | prepublishOnly exécuté | phase installation seule par défaut | `bash tests/test_a5.sh` | OK |
| A6 | attribuer.py (nouveau) | dans_paquet ambigu | origine_code + origine_processus + flux_local | `python3 -I tests/test_attribuer.py` | OK : lecture seule |
