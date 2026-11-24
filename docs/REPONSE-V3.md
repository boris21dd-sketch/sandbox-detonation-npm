# SANDBOX DE DÉTONATION npm — RÉPONSE À LA v3 ET VÉRIFICATION

**2026-11-24 — document de clôture de l'échange v3.**
Ce document répond point par point au correctif v3, enregistre les décisions prises, et
consigne ce qui a été vérifié sur le vrai banc après application.

---

## 1. Le défaut qu'il a trouvé, et qui invalide mes runs précédents

**`piloter()` n'était jamais appelé.** Le plafond de `setTimeout` posé par le pilote
raccourcissait aussi la fenêtre d'observation de `run-entry.js` : 1,6 s au lieu de 8 s.
Toute charge déclenchée par les exports — session WhatsApp, exports piégés — passait
inaperçue.

Vérifié par moi-même sur mes propres runs, comme il le demandait :

```
b011 étapes : demarrage, horloge_decalee, cycle_vie_deps, cycle_vie_fini,
              main, entree_module, fin          <- AUCUNE étape « pilote »
b011 observation : 1,6 s
```

Conséquence assumée : **les runs `b`, `f`, `g` sont caducs.** Ils affichaient 23/24 sur un
banc amputé de l'étape qui déclenche la charge. Le chiffre était juste, la mesure ne
l'était pas.

Détail que j'avais mal lu : `p11-wa` était `CLÉ` dans `b011`, mais par
`fs.writeFileSync` pendant le postinstall, pas par les exports. Le `CLÉ` est réel, il ne
prouvait simplement pas ce que je croyais.

## 2. Ce que la v3 corrige, vérifié après application

```
run h : pilote=24/24 | observation=13,4 s | CLÉ=23, —=1 | BANC RECEVABLE
run i : pilote=24/24 | observation=16,0 s | CLÉ=23, —=1 | BANC RECEVABLE
run j : pilote=24/24 | observation=13,4 s | CLÉ=23, —=1 | BANC RECEVABLE
```

`h011` va jusqu'à l'étape `pilote`, observe 13,4 s, et `p11-wa` frappe désormais par
`net.write` et `tls.connect` — le canal qu'elle annonce.

Délais mesurés par lui, que je n'ai pas reproduits : `setTimeout` 3 jours → 1,56 s,
délai en texte → 1,54 s, ESM `node:timers` → 1,54 s, `node:timers/promises` → 1,54 s,
petit-enfant node → 1,57 s. Horloge décalée de +30 jours (et non +60 : le pilote ne
l'applique plus deux fois). `Date()` sans `new` ne plante plus. Horodatages des journaux
en heure réelle.

## 3. Les six suites de tests, chez moi

```
test_lecteur.py        : 57 tests, OK
test_fabrique.sh       : OK
test_scripts.sh        : OK
test_nonce_harnais.sh  : OK
test_temps.sh          : OK
test_rce_npm_reel.sh   : 1 ÉCHEC -> INCONCLUANT (voulu)
```

Le test RCE passe de 2 échecs à 1 : il affiche désormais `INCONCLUANT` au lieu de
prétendre tester quelque chose sur npm 12.0.2.

## 4. Ses décisions, acceptées

1. **Pas de seccomp maintenant.** `strace -f` suit déjà les enfants à environnement vidé ;
   lire `trace.raw` repère les processus non surveillés. Le paquet pouvant modifier ce
   fichier, c'est une **confirmation, pas une preuve**. C'est juste, et moins coûteux que
   ce que je proposais.
2. **sudoers**, dans cet ordre : chemin absolu exact dans la règle ; `npm install` dans un
   conteneur jetable ; puis **retirer bob du groupe `docker`** — tant qu'il y est, il a de
   fait les droits root. Cette dernière étape est la vraie, et je ne l'avais pas mise dans
   cet ordre.
3. **Test RCE** : on garde la protection, le test affiche `INCONCLUANT`, **aucune version
   de npm n'est figée** — figer une vieille version rouvrirait la faille pour faire passer
   un test.
4. **Minuteries et horloge dans les enfants** : fait en v3.
5. **Témoin** : `CONSIGNES-VERIFICATEURS.md` corrige le critère. Mes deux vérificateurs
   exigeaient `p12-propre` = `CLÉ` ; ce critère valide un banc contaminé. Le témoin doit
   sortir `—`.
6. **Ordre P5 → P6 → P7**, P5 en même temps que le correctif temps pour ne réétalonner
   qu'une fois.

## 5. Les refus qui rendent le 23/24 croyable

Mesurés sur le vrai banc, pas déduits :

- **Injection de faute** : événements de `b001` copiés dans `b012` (sonde **inscrite au
  registre**) → `ATTRIBUTION INVALIDE raisons=nonce étranger`, banc `NON RECEVABLE`.
  Un tag non inscrit ne prouve rien : il sort `HORS REGISTRE (ignoré)` — mon premier
  essai avait échoué pour cette raison.
- **Protection retirée** : `SBX_REDEMARRER=0` → l'orphelin du leurre frappe dans le témoin,
  `p12-propre ATTRIBUTION INVALIDE — FORGE DÉMONTRÉE`, `p21` en `CLÉ NON RECEVABLE`.
- **Concurrence** : deux bancs simultanés, le second `rc=75` en 7 ms, aucune détonation.
- **Nonce** : une seule valeur par journal, identique à la colonne 3 du registre.

## 6. Pièces fournies pour son recomptage

`PREUVE-v3-23-24.tar.gz` :

- `runs-hij.tar.gz` : les 72 dossiers `h001`…`j024`, avec `events.jsonl`, `entrees.jsonl`,
  `summary.json` et **`_sbx_etat.jsonl`** — la preuve du pilote, sonde par sonde ;
- `registre-{h,i,j}.tsv` : registres bruts, 24 lignes chacun ;
- `lecteur-{h,i,j}.txt` : sortie complète du lecteur, non retouchée ;
- `sha-deploye.txt` : `sha256sum` du harnais **actuellement déployé** dans
  `/opt/sandbox/harnais`, plus `detoner-obs.sh`.

Correction d'une faute précédente : l'annexe de mon dossier d'hier montrait un harnais
sans nonce, parce que je l'avais pris dans le miroir `K:\` et non dans `/opt/sandbox`.
**Code relu ≠ code déployé.** Cette fois les empreintes viennent du répertoire d'exécution.

## 7. Ce qui n'est pas prouvé

- **Enfant `sh -c` à environnement vidé** : non instrumenté. Pas de nonce ⇒ pas de `CLÉ`
  forgeable, mais son activité échappe au journal. Ni Rust ni Go n'y changent rien —
  établi par deux vérificateurs indépendants : un hôte `deno_core` garde `node:fs` en JS
  dans le même isolate, `op_spawn(clearEnv:true)` obéit au paquet, et `LD_PRELOAD` est
  inopérant sur `env -i`, les binaires statiques et les syscalls directs.
- **RCE npm** : correctif en place, contre-épreuve non reproduite → `INCONCLUANT`.
- **P5/P6/P7** : binaires absents de l'image (faux négatifs par construction sur les
  droppers `curl | sh`), identité du tarball, score pondéré sans plancher 51.
- **sudoers / groupe docker** : bob a de fait les droits root.

## 8. Ce que je ne ferai pas sans accord

- Citer un chiffre issu d'un run non recevable.
- Figer une version de npm pour faire passer un test.
- Réécrire le superviseur dans un autre langage : le banc sort trois fois recevable, et le
  langage ne change aucun de ces chiffres.
- Toucher `main` du dépôt du moteur : tout reste sur `integration-nuit-23nov`.
