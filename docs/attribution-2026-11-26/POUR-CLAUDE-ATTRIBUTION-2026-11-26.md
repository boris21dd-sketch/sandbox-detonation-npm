# Attribuer un geste à son auteur — et pourquoi quatre règles viennent de tomber

**Pour Claude.** Rédigé le 26/11/2026, 08h20, après une campagne de détonation de 203 paquets
et huit tours de propositions de règles par hy4, mistral et kimi-k3.1-pro.

Ce document ne demande pas d'avis général. Il expose deux erreurs de mesure (une de ma part, une
dans le harnais), les chiffres recalculés, et **trois questions fermées**. Les points de doute sont
marqués `DOUTE n`. Si une information te manque, écris `# INCONNU:` à l'endroit exact plutôt que de
la combler : c'est la règle de la maison, une valeur inventée produit un patch plausible et faux.

---

## 1. Ce qui a été mesuré

Campagne de nuit, 203 paquets npm que **GuardDog 3.12 et notre moteur Python considèrent tous deux
comme propres** (les « manquants » : des paquets qu'aucun des deux ne signale). Détonation réelle
dans la sandbox (conteneurs, faux-Internet, scripts de cycle de vie rejoués après installation
`--ignore-scripts`).

```
204 runs lus          (203 paquets + 1 reliquat)
95 811 événements
75 319 marqués dans_paquet = true
```

Chaque événement porte déjà : `appelant` (fichier:ligne:colonne lu sur la pile V8), `dans_paquet`
(booléen), `pile`, `canal`, `valeur`, `nonce`.

## 2. Erreur n°1 — la mienne

J'ai agrégé les traces sur le seul champ `canal`, **sans regarder `dans_paquet`**. Donc les gestes du
harnais lui-même (son `require`, ses écritures de canaris, sa journalisation de fin) entraient dans
les compteurs du paquet. J'en ai conclu, à tort, que « les compteurs mesurent le banc » et j'ai
demandé d'ajouter un champ `provenance` qui **existait déjà**. C'est écrit ici parce que c'est la
faute la plus coûteuse de la nuit : elle a produit un diagnostic faux sur mon propre outil.

## 3. Erreur n°2 — réelle, et dans le harnais

Le pilote `_sbx_scenario3.cjs` est **copié à la racine du paquet** (`/work/paquet/package/`) pour
être exécuté par Node. Ses propres écritures de fichiers et ses lectures de canaris ont donc, aux
yeux de `dans_paquet`, le même statut que du code du paquet : même racine, même processus.

Mesure, à canaux identiques :

| agrégation | R1 (write + append + net) |
|---|---|
| sans filtre, `dans_paquet` seul | **200 / 204** (98 %) — absurde |
| en excluant `_sbx_*` et `/work/harnais` | **0 / 204** |
| `net.write` après exclusion | 20 / 204 |
| aucun événement attribuable au paquet | 50 / 204 |

R1 = `CO_OCCURRENCE_WRITE_APPEND_NET`, une des quatre règles proposées par les LLM.

**Conclusion de mesure : les quatre règles candidates ne sont pas réfutées, elles sont
non mesurables sur ce corpus.** Elles n'ont aucun support dans les traces une fois le pilote
exclu. On ne les active pas, et on ne les jette pas non plus : il manque l'attribution.

## 4. Les seules pistes réelles

19 paquets émettent un `net.write` depuis leur code. Presque tous vers `socket` sans hôte
exploitable (`DOUTE 1` : est-ce une vraie émission, ou l'ouverture d'un socket local par une
bibliothèque ?). Deux sortent du lot, et ce sont les seuls contacts nominatifs :

```
manq16010 → manq16010 = @zeit/next-sass@1.0.1   → github.com:443
manq17003 → manq17003 = zen-grids@2.0.3         → github.com:443
manq7007  → webappengine@1.2.0                  → 0.0.0.0
```

`github.com:443` peut être parfaitement légitime (résolution de dépendances, téléchargement
d'outil) — c'est précisément le geste qu'aucune règle ne doit condamner sans sa chaîne.

## 5. Les quatre règles proposées, et leur état

Tour 7, cascade : hy4 (9 563 car.) et mistral (5 034) proposent, se jugent (hy4 juge 11 529 car.,
mistral 8 342), aucun des deux ne conclut, **kimi-k3.1-pro** reprend (2 993 car.) et sa proposition
est jugée par les deux (6 515 / 2 745). Accord des juges sur quatre noms :

```
SPAWN_NODE_E_POSTINSTALL_MASQUAGE_PARENTHESE   les deux : blocage fort
ENUM_ENV_AVEC_SONDAGE_CLI_ET_NET               les deux : alerte haute
BUFFER_FROM_AVEC_WRITE_ET_NET                  les deux : corrélation
CO_OCCURRENCE_WRITE_APPEND_NET                 hy4 blocage / mistral alerte  (désaccord)
```

Rejetées : `FS_QUATRE_OPERATIONS_CYCLE` (canaux inexistants, relevé par les deux),
`NET_WRITE_SPAWN_FICHIER_HORS_POSTINSTALL_MASQUE` (réintroduit `== 0` sur clé absente),
`FS_READDIRSYNC_RECONNAISSANCE` (geste isolé érigé en règle).

État : **0 activée**. Mesure sur traces attribuées : `CO_OCCURRENCE…` = 0/204.
`DOUTE 2` : une règle à 0 occurrence sur 204 paquets propres est-elle morte, ou seulement non
testée faute de charge dans l'échantillon ?

## 6. Les trois questions fermées

**Q1 — Le pilote doit-il sortir du répertoire du paquet ?**
Options : (a) le poser dans `/work/harnais` et le lancer avec `--pkg /work/paquet/package`
(`require` absolu, aucun `..` hors racine) ; (b) garder l'emplacement et exclure `_sbx_*` dans le
calcul de `dans_paquet` ; (c) les deux.
Ma préférence : (c) — (a) ferme la cause, (b) protège contre une réapparition. Réponds
`Q1 : a|b|c` et, si (a), dis ce qui casse : `DOUTE 3` — le pilote utilise-t-il des chemins relatifs
au paquet (`./`, `package.json` relatif) qui cesseraient de résoudre depuis `/work/harnais` ?

**Q2 — Un `dans_paquet` fondé sur la racine suffit-il, ou faut-il le processus ?**
Aujourd'hui c'est une comparaison de chemin. Un `spawn` dont l'enfant `require` un fichier du paquet
reste « dans le paquet » — est-ce voulu, ou faut-il distinguer `paquet`, `dependance`, `banc` sur
trois valeurs au lieu d'un booléen ? `DOUTE 4` : quelle valeur donnerais-tu à un fichier écrit par
un enfant `sh -c` lancé par le paquet ? C'est le trou que la skill appelle « sh -c ».

**Q3 — Que faire des 19 paquets à `net.write` ?**
(a) les inspecter à la main, un par un, avant toute règle ; (b) formuler d'abord la règle sur les
seuls deux contacts nominatifs, puis remonter ; (c) considérer `socket` sans hôte comme du bruit du
harnais et ne garder que `github.com`.
Ma préférence : (a) puis (b). Réponds `Q3 : a|b|c`.

## 7. Ce que je ne signe pas

- Aucun chiffre de rappel : le corpus est majoritairement **propre**, détecter dessus ne mesure rien.
- Les tours 1 à 6 des règles sont à jeter : ils ont tourné sur 4 paquets (bug de ma part : `npm pack`
  nomme lui-même ses fichiers, la liste de détonation est restée vide).
- `dans_paquet` répond « oui » à 98 % des événements en l'état : **il ne vaut rien** tant que le
  pilote n'est pas exclu. C'est le seul chiffre à retenir de ce document.
- Rien n'est poussé sur GitHub (jeton retiré de la machine) : tout est local, empreintes ci-dessous.

## 8. Pièces jointes

```
attribution-paquet.json      canaux par run, filtrés pilote exclu, + les 19 paquets réseau
comportements-paquet.json    agrégat brut dans_paquet (pour comparer les deux lectures)
regles/tour-7/               7 fichiers : propositions, jugements croisés, kimi, retenues
demander.py                  le pilote des tours (corrigé : gabarit JUGEMENT)
liste/detonation.tsv         203 lignes paquet <TAB> tarball (l'ordre des lots)
journal-lot-*.log            une ligne par paquet : deps, rc, durée, événements
events-manq16010.jsonl       la trace complète du seul paquet qui contacte github.com
```

Empreintes : voir `EMPREINTES.txt`, produit par `sha256sum` sur les pièces ci-dessus.
