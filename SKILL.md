---
name: sandbox-detonation-npm
description: Use when detonating npm packages to prove exfiltration.
---

# Détonation npm — prouver ou innocenter par l'exécution

Le statique trie, la sandbox juge. Mais une sandbox qui ne fait que `require()`
ne juge rien : elle regarde. Cette skill décrit la seule forme de détonation qui
produit une **preuve** (quel secret sort, vers quel hôte) ou une **absence
étayée**, et les pièges qui transforment un run en faux négatif.

Tant que le banc de sondes ne mesure pas la sandbox, un « rien vu » ne vaut rien :
commencer par le banc, puis durcir.

## Règle d'or : faire relire AVANT de lancer

Tout run de plus d'une heure est relu par **deux modèles différents** (Mistral
et hy4 en second vérificateur) sur le script et le pilote exacts. Un protocole
faux coûte des heures et produit des chiffres faux. Poser des questions fermées
(BLOQUANT / NON BLOQUANT) et exiger la ligne à corriger.

## Les trois couches

1. **disque** : snapshot avant/après sur des racines nommées ;
2. **système** : `strace -f` sans filtre ;
3. **applicatif** : harnais qui journalise les canaux (`require`, `fs.*`,
   `child_process.execSync`, `net.connect`, `https.request`, `processus`).

Un quatrième journal, le **faux-Internet**, enregistre chaque requête (SNI,
chemin, en-têtes, corps) : c'est lui qui porte la preuve.

## Le scénario qui déclenche (scripts/sbx-scenario3.sh)

Un pilote remplace temporairement `main`, sans toucher au code du paquet :

- écrit **12 états de victime** avec des canaris distincts (npmrc, ssh, aws, gh,
  docker, kube, git, env, gcloud, session WhatsApp, cookies, historique) ;
- **plafonne `setTimeout`/`setInterval`** à 1,5 s (un appel à 3 jours part) ;
- exécute les scripts **preinstall/install/postinstall/prepare** — `require()`
  ne les exécute jamais, c'est le vecteur n°1 ;
- exécute les **`bin`** (`--help`, `--version`) ;
- charge le vrai point d'entrée (**ESM par `await import()`**) et pilote ses
  exports avec une session factice + `connection.update`/`messages.upsert`.

La preuve se lit dans `scripts/cles_scenario3.py` : un canari dans un événement
**réseau** vers un hôte ≠ registry, ou dans une commande exécutée.

## Les treize pièges (tous mesurés)

0. **`exports` prime sur `main`** : Node l'ignore. Lister `main`/`index.js` d'abord
   fait charger un leurre bénin et rater la charge utile. Ordre = `exports` d'abord.
   Corollaire : charger **toutes** les entrées (import ET require), pas la première.
1. `npm install --ignore-scripts` : neutralise le vecteur n°1. Installer sans
   scripts sur l'hôte (réseau), puis **rejouer les scripts dans le conteneur** —
   ceux du paquet **et ceux des dépendances** (liste `_sbx_deps_scripts.json`
   construite après installation, 20 scripts max, 3 s chacun).
2. Timeout de 30 s : un `setTimeout` de 3 jours ne se déclenche jamais. Plafonner
   les globales, `require('node:timers')` **et** `timers/promises` — `setTimeout`,
   `setInterval` et `scheduler.wait` : chaque variante oubliée est un timer libre.
   Intercepter `Module._load`, pas seulement les globales.
3. Canari cherché dans `events.jsonl` : le pilote écrit lui-même les fichiers,
   donc **12 faux positifs par paquet**. Ne compter que le réseau.
4. Canari envoyé au **registry** : seul le **jeton npm** y est un usage normal
   (un script qui appelle npm relit `~/.npmrc`). Une session WhatsApp, une clé SSH
   ou des cookies envoyés au registry restent une fuite : ne jamais exempter
   l'hôte entier, exempter le seul canari du jeton. Comparer l'hôte par
   **égalité** (`registry.npmjs.org.attaquant.test` n'est pas le registry).
5. Jeton que le harnais pose lui-même (`CANARI_FACTICE`) : l'exclure.
6. `main` remplacé puis `require(P)` : le pilote **se require lui-même** et rend
   `{}`. Jamais `require(P)`.
7. Paquet `type: module` : un pilote `.js` meurt (`require is not defined`).
   Pilote en `.cjs`, cible chargée par `await import()`.
8. `execSync` à `timeout: 25000` × 4 scripts + × 8 bins : 196 s bloquants pour
   un run de 90 s. Budget global, 8 s par script, 4 s par bin.
9. « Rien vu » sans trace de progression : indistinguable de « jamais exécuté ».
   Écrire la trace **dans le paquet** (le `/tmp` du conteneur n'est pas ramené).
10. Le harnais porte l'URL et le corps dans `valeur`, pas dans `url`/`chemin`.
    Chercher les preuves là aussi, sinon une sonde qui atteint son hôte reste « — ».
11. Compter « toute valeur contenant un point » comme une URL **fabrique des clés**.
    Extraire les URL, parser l'hôte.
12. Un banc sans témoin propre ne mesure rien : la sonde témoin doit rester muette,
    sinon chaque « amélioration » peut être une machine à faux positifs. La placer
    **en dernier** dans la liste pour que sa vérification soit positionnelle.
13. Énumérer `node_modules` à plat rate **tous les paquets scopés**
    (`node_modules/@scope/nom`) : la moitié de l'écosystème n'est alors jamais
    inspectée. Descendre d'un niveau dans les dossiers `@*`.

## Le banc de sondes (scripts/fabrique_sondes.py)

Douze classes malveillantes + un témoin : postinstall, ESM, timer 3 jours, bin
seul, jeton npm, config C2, `exports` sans `main`, payload `eval`, shell+curl,
hook auto-installé, session WhatsApp, **charge utile dans `exports` derrière un
`index.js` bénin**, **postinstall d'une dépendance**. Note de départ : 13/13 vues,
témoin muet.

## Audit en boucle (scripts/audit_sandbox_20.py)

Le protocole se durcit par **tours** : un panel de modèles relit le code exact et
rend des constats, puis le **banc est rejoué**. Le banc est le juge, le panel est
l'inspirateur : un constat n'est retenu que si le score tient et que le témoin
reste muet. Détail du panel, du format de constat et de la veille :
`references/audit-loop.md`.

## Ce qu'un « rien » veut dire

Aucun canari sorti, aucun hôte hors registry, aucun `exec` inattendu, sous
scripts de cycle de vie + bins + exports pilotés + délais écrasés : c'est une
**absence étayée**, pas une innocence. La formuler ainsi, jamais « le paquet
est propre ».

## Dépôt dédié

Le protocole complet, les scripts réels et le journal d'audit vivent sur
`github.com/boris21dd-sketch/sandbox-detonation-npm`. Toute amélioration y est
publiée avec sa mesure (`scripts/publier.sh "titre" "avant → après"`), pour que
l'historique dise ce qui a été corrigé **et ce que ça a changé**.

## Enchaînement

0. Construire ou rejouer le banc **avant** de promettre quoi que ce soit :
   `python3 scripts/fabrique_sondes.py` puis
   `bash scripts/sbx-scenario3.sh /tmp/liste_sondes.tsv <prefixe> 120`.
1. `bash scripts/sbx-scenario3.sh <liste.tsv nom\ttgz> <prefixe> 120`
2. `python3 scripts/cles_scenario3.py <prefixe>` → une ligne par paquet, `CLÉ`
   ou `—`, avec les hôtes et les canaris sortis.
3. Verser les clés dans le rapport ; ne jamais promouvoir une règle statique sur
   la base d'un run partiel.
