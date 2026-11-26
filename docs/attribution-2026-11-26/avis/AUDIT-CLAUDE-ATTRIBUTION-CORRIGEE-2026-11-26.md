# AUDIT CLAUDE — attribution corrigée (26/11 après-midi)
## 1. SCAN
[LIRE-DABORD.md, SPEC-DEPLOIEMENT-CLAUDE.md, EMPREINTES.txt (OK), attribuer.py (version PCfixe), attribution-corrigee.json (2 917 runs), reseau-resume.json, hors-registry.json, trous/{hy4, mistral, hy4-juge, mistral-juge}.md (juges : non lus en entier), AUDIT-CLAUDE-ATTRIBUTION-2026-11-26.md (le mien)]
Statuts : **P** prouvé sur ses fichiers · **D** lu dans le code.

## 2. CE QUI EST FAUX DANS LE DOSSIER
1. **D — `attribuer.py` réécrit au lieu du livré.** Sa version :
   - perd l'origine par hôte, alors que c'est la question posée ;
   - compte `http:`, `github.com:443` et l'URL entière comme 3 hôtes (P : hors-registry.json) ;
   - classe `paquet` tout événement sans chemin si `dans_paquet=true`, alors que ce champ est relatif à l'entrée (prouvé ce matin) ;
   - met les entrées `bin:x` en `dependance`.
2. **P — Exclure registry.npmjs.org PAR NOM cache deux choses :**
   - un ver qui publie avec le jeton volé (`PUT` vers le registry) ;
   - l'exfiltration par le point d'audit. Ses propres sondes le prouvent : 27 runs écrivent vers `registry.npmjs.org/-/v1/security/audits` (base64), et 10 vers `npm.corp-interne.test`.
   Le registry se trie par **méthode et chemin**, jamais par nom.
3. **D — `muet` = « aucun événement paquet ».**
   - Une charge livrée par une dépendance du paquet (cas p14) est déclarée muette.
   - Le vrai indicateur de « code non exécuté », c'est `main` non chargé (`_sbx_etat.jsonl`), pas l'absence d'événement.
4. **P — « Liste produite deux fois indépendamment » : FAUX.**
   - Ma liste des 10 runs venait de `attribution-paquet.json`, c'est-à-dire de ses comptages, sur les mêmes traces. Je ne l'ai pas établie à la main.
   - Même source, même champ `dans_paquet` : la coïncidence ne prouve rien.
5. **P — « Contrôle positif 196/251 » : ce n'est pas un contrôle.**
   - Il compte « au moins un hôte, peu importe lequel ni qui l'a contacté » : 37 runs ne doivent leur hôte qu'au registry.
   - Un contrôle positif = verdict par sonde contre `attendus` (le lecteur `cles_scenario3.py` le fait déjà).
   - Les muets `a016` et `aud*016` (17 runs) sont à nommer via le registre avant toute conclusion.
6. **D — Mon plan C avait 3 trous réels**, relevés par hy4 ou mistral, ou trouvés ici :
   - **package.json modifié (A1)** : l'artefact mesuré n'est plus l'artefact publié.
   - **Pas d'entrée `main` garantie** quand le paquet n'a ni `main` ni index.js.
   - **Faux-Internet non ingéré.** Pas de lecture de trace.raw non plus, pour les enfants non-node.
7. **D — Lecteur des sondes : faille ver.** Un `CANARI_NPM` envoyé au registry est exempté sans regarder méthode ni chemin, donc une publication avec le jeton volé passe pour un usage normal.

## 3. CE QUE hy4/mistral DISENT ET QUI EST FAUX
- mistral :
  - « aucun canari, aucun nonce, pas de redémarrage » : faux, les trois existent depuis le 24/11 ;
  - « le pilote classé outil » : non, c'est `banc` ;
  - `setpriv` en uid `nobody` : non vérifié.
- hy4 :
  - « A5 : exclusion stricte des node_modules non faite » : faux, une dépendance n'est jamais en hors_installation, même avec l'option.
  - « `0 registry.npmjs.org` comme porte » : faux, un paquet légitime a le droit de lire le registry ; la porte doit être « 0 écriture registry non expliquée ».
- Les deux : « A3 repli non marqué » : faux, `INSTALL_PAIRS_DESACTIVEES` + `install.json`.
- Les deux ont raison sur : package.json intact, entrée main garantie, faux-Internet non lu, filiation `sh -c`, rejouer plutôt que réattribuer.

## 4. TÂCHES (Sonnet, SPEC 7)
| ID | FILE | PB | FIX | TEST | COMPAT |
|---|---|---|---|---|---|
| B1 | detonate.js, run-entry.js, sbx-scenario3.sh, pilote | package.json modifié | pilote détecté dans `../_sbx/`, entrée main toujours produite, package.json intact | sha256 package.json avant = après ; main sans index.js | root (harnais) |
| B2 | attribuer.py | origine/hôte, registry, muet | mode `--runs`, hôtes normalisés, registre lecture/écriture, faux-Internet → `reseau_non_instrumente`, `main_charge`, strace → `processus_natifs` | test_attribuer + test_b2 | lecture seule |
| B3 | cles_scenario3.py | exemption ver | exemption registry seulement GET/HEAD hors motifs d'écriture | tests B3 | OK |
| B4 | sbx-scenario3.sh | fichiers root anonymes | `FICHIERS_ETRANGERS:<chemin>:<uid>` avant rm | test faux find | OK |

## 5. PORTE DU RUN TÉMOIN (remplace sa §4)
Une seule ligne rouge = arrêt.
- `main_charge` vrai sur le paquet témoin (node-sass + dépendance pair).
- 1 seul `:postinstall` par paquet.
- 0 `prepublishOnly`.
- sha256 package.json identique.
- `faux-internet.jsonl` joint.
- `registre.ecriture` vide ou expliqué.
- `reseau_non_instrumente` lu.
- Aucune ligne `FICHIERS_ETRANGERS`/`RESIDU`.
- 25 sondes : `BANC RECEVABLE`.
