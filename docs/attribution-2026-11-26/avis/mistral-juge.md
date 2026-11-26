**1. Trous vus par un seul audit**

*Vus par AUDIT 1 seul :*
- Le mécanisme F2/F6 : l'entrée `main` artificielle force `dans_paquet=true` et ré-attribue le banc au paquet **malgré** le déplacement — AUDIT 2 ne voit que l'altération du hash, pas la ré-attribution.
- Le producteur de l'entrée `main` (pilote vs `detonate.js`) non identifié : si A2 supprime le rejeu sans sonde, `charges=0` persiste par cause nouvelle.
- La portée du filtre A5 : « par défaut » n'est pas l'exclusion stricte de `node_modules/*` (F7).
- L'incohérence de cardinalité A6 : 6 valeurs `origine_code` contre 3 `origine_processus`.
- L'ordonnancement des dépendances après suppression du rejeu (qui ordonne, F7) — non couvert.
- La sous-population du repli A3 non marquée.

*Vus par AUDIT 2 seul :*
- L'intégrité de l'artefact : A1 édite le `package.json` du paquet sous test (sha256) → la mesure ne porte plus sur l'artefact publié.
- `prepublish`/`prepare` non traités par A5.
- L'indiscernabilité `net.write` fd 1/2 vs vrai socket si le fd n'est pas tracé.
- La **collecte** réseau réelle absente du plan (`strace -f -e trace=network`, `iptables -j LOG`) — AUDIT 1 ne parle que d'ingérer l'existant.
- La contre-mesure A4 concrète : `setpriv --reuid=nobody` / `sudo rm -rf` + détection `find ! -user`.
- La méthode de correction de A1 **sans toucher** `package.json` (`cwd=package`, `node ../_sbx/pilote.cjs`) — AUDIT 1 signale le défaut sans la résoudre.

**2. Contradictions, arbitrées par les faits**

- **Tâche A2** : AUDIT 1 prédit `charges=0` par cause nouvelle (rien ne charge le `main`) ; AUDIT 2 prédit le double `postinstall` persistant (`detonate.js` lancerait encore). **F5 tranche** : « detonate.js lance les cycles de vie puis le pilote les rejoue » — les deux lancent aujourd'hui. Ce n'est pas l'un contre l'autre : le plan ne désigne **aucun lanceur unique**, et les deux risques sont réels. Correction : en choisir un (detonate.js, sonde `main` conservée).
- **Tâche A1** : AUDIT 1 invoque `dans_paquet=true` (F2), AUDIT 2 l'artefact altéré. Même défaut, deux facettes. **F2/F6 tranchent** que l'entrée `main` artificielle est le mécanisme d'attribution fausse → la correction de AUDIT 2 (ne pas modifier `package.json`) résout les deux ; celle de AUDIT 1 (« sans écraser main ») reste muette sur la méthode. **AUDIT 2 gagne.**
- **A5** : les deux s'accordent, **F7 tranche contre le plan** (npm n'exécute jamais `prepublishOnly` à l'installation ; le script vient du rejeu F5), pas entre les audits. AUDIT 1 ajoute `node_modules/*`, AUDIT 2 ajoute `prepublish`/`prepare` : complémentaires, à prendre tous.
- **Réseau** : AUDIT 1 « ingérer le faux-Internet existant (114/218) » vs AUDIT 2 « collecter le réseau réel manquant ». **F8 tranche** : dns/connect absents des traces → collecte obligatoire au rejoue ; le faux-Internet doit aussi être ingéré. Complémentaires.
- **Ordre A1/A2/A5** : séquences différentes, mais A4 premier et A6 dernier dans les deux. Pas de contradiction factuelle, non bloquant.

**3. VERDICT — correction minimale**

1. Rejouer (F4 : `charges=0` 218/218 = code jamais exécuté ; F8 : réseau jamais tracé) — A6 ne réattribue que ce qui existe.
2. A1 sans toucher l'artefact : `cd package && node ../_sbx/pilote.cjs` (package.json intact, `main` résolu dans `package/`, `dans_paquet` correct) ; A2+A5 : `detonate.js` seul lanceur (1 `postinstall`), exclusion stricte de `prepublishOnly`/`prepublish`/`prepare` et de `node_modules/*`.
3. A3 sans `--legacy-peer-deps` (repli marqué `charges=0`) ; A4 : rc de `rm -rf` contrôlé + détection fichiers root (`find ! -user`, `setpriv --reuid=nobody`).
4. Sondes obligatoires au rejoue : `strace -f -e trace=network` + capture `ppid`/fd, ingestion du faux-Internet, canari/nonce par run ; gate sur 1 run témoin (`charges=0`=0, `postinstall`=1, `registry.npmjs.org`=0, `ppid` présent) avant les 204 runs.