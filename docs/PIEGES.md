# Les treize pièges

Chaque entrée vient d'une mesure, pas d'une intuition. Le format est volontaire :
le défaut, la preuve, le correctif.

## 1. `npm install --ignore-scripts`

**Défaut.** Neutralise le vecteur n°1 des compromissions npm : les scripts
`preinstall`/`install`/`postinstall` ne s'exécutent jamais.
**Preuve.** Sur douze paquets suspects, `charges=0` partout — aucune charge
exécutée — alors que plusieurs portaient leur geste dans un script.
**Correctif.** Installer sans scripts sur l'hôte (réseau autorisé), puis
**rejouer** les scripts dans le conteneur, avec un budget.

## 2. Le délai de 30 secondes

**Défaut.** Un `setTimeout(checkRemoteConfig, 259200000)` (trois jours) ne se
déclenche jamais dans une fenêtre de trente secondes.
**Preuve.** `forge-gas-diff` : le geste est planifié à trois jours.
**Correctif.** Plafonner les délais à 1,5 s.

## 3. `node:timers` échappe au plafonnement

**Défaut.** Patcher `global.setTimeout` ne touche pas `require('node:timers')`
ni `timers/promises`.
**Preuve.** Relevé en audit, puis vérifié : un `setInterval` importé du module
natif gardait son délai réel.
**Correctif.** Intercepter `Module._load` et plafonner `setTimeout`,
`setInterval`, `timers/promises.scheduler.wait`.

## 4. Le pilote se `require` lui-même

**Défaut.** Remplacer `main` puis retomber sur `require(P)` exécute le pilote
une seconde fois : `m` vaut `{}`, rien n'est chargé.
**Preuve.** Paquets sans `main` : faux négatif systématique.
**Correctif.** Jamais `require(P)`.

## 5. `exports` prime sur `main`

**Défaut.** Avec `exports`, Node **ignore** `main`. Lister `main`/`index.js`
d'abord fait charger un leurre bénin et rater la charge utile.
**Preuve.** Sonde `p13` : `index.js` bénin + charge utile dans `exports` →
ratée avant correctif.
**Correctif.** `exports` d'abord, et charger **toutes** les entrées.

## 6. Paquet ESM

**Défaut.** Un pilote `.js` dans un paquet `type: module` meurt :
`require is not defined`.
**Preuve.** `yuliawhh` : 201 imports, aucun événement avant correctif.
**Correctif.** Pilote en `.cjs`, cible chargée par `await import()`.

## 7. Budget d'exécution

**Défaut.** `execSync` avec `timeout: 25000` × 4 scripts + × 8 bins = 196 s
bloquants pour un run de 90 s : le run est tué **avant** le chargement du vrai
code.
**Preuve.** Revue bloquante, puis mesure : le main n'était jamais atteint.
**Correctif.** Budget global 75 s, 8 s par script, 4 s par bin, sortie 15 s
après le chargement.

## 8. « Rien vu » sans trace

**Défaut.** « Main non chargé » et « jamais atteint » sont indistinguables.
**Correctif.** Trace de progression **dans le paquet** (`_sbx_etat.jsonl`) :
démarrage, cycle de vie, dépendances, main, pilote.

## 9. Canari compté au mauvais endroit

**Défaut.** Chercher les canaris dans le journal applicatif compte les douze
fichiers que le pilote sème lui-même : douze faux positifs par paquet.
**Correctif.** Ne compter que le réseau et les commandes.

## 10. Registry : sous-chaîne au lieu d'égalité

**Défaut.** `"registry.npmjs.org" in host` valide
`registry.npmjs.org.attaquant.test`.
**Preuve.** Deux relecteurs l'ont relevé indépendamment.
**Correctif.** Égalité stricte sur l'hôte parsé (ou suffixe `.registry.npmjs.org`).

## 11. Le jeton npm est un usage normal

**Défaut.** Un script de cycle de vie qui appelle `npm` envoie `~/.npmrc` au
registry : ce n'est pas une fuite.
**Correctif.** Vers le registry, ignorer **seulement** le canari du jeton npm ;
une session WhatsApp ou une clé SSH envoyée au registry reste une fuite.

## 12. Les paquets scopés sont invisibles

**Défaut.** `node_modules/@scope/nom` : une boucle plate sur `node_modules`
n'inspecte **jamais** les paquets scopés.
**Preuve.** Relevé en audit, tour 2.
**Correctif.** Énumérer `@scope/nom` et remonter leurs scripts de cycle de vie.

## 13. Les scripts des dépendances

**Défaut.** Rejouer seulement les scripts du paquet racine laisse passer un
`postinstall` malveillant logé dans une dépendance.
**Preuve.** Sonde `p14` : charge utile dans le `postinstall` d'une dépendance →
muette avant correctif, `CLÉ` après.
**Correctif.** Construire la liste des scripts des dépendances après
installation (40 max), les rejouer dans le conteneur (3 s chacun).

---

## Ce qu'un « rien » veut dire

Aucun canari sorti, aucun hôte hors registry, aucun `exec` inattendu, sous le
scénario complet : c'est une **absence étayée**. Jamais « le paquet est propre ».
