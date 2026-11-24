# RÉSULTAT — banc de détonation npm (protocole v3)

## Chiffre citable

**23 / 24 sondes détectées, témoin `p12-propre` muet, trois runs consécutifs avec le
harnais v3.**

| run | CLÉ | — | verdict | pilote | observation |
|---|---|---|---|---|---|
| h | 23 | 1 | BANC RECEVABLE | 24/24 | 13,4 s |
| i | 23 | 1 | BANC RECEVABLE | 24/24 | 16,0 s |
| j | 23 | 1 | BANC RECEVABLE | 24/24 | 13,4 s |

Dénominateur = registre (24 sondes), 0 hors registre. Horloge +30 jours, paquet installé
la veille, redémarrage du conteneur entre chaque sonde.

## Pourquoi ces runs remplacent ceux de la veille

Les runs `b`, `f`, `g` (même compte) sont **caducs** : `_sbx_etat.jsonl` y montre les étapes
`demarrage, horloge_decalee, cycle_vie_deps, cycle_vie_fini, main, entree_module, fin` —
**aucune étape `pilote`**. Le plafond de `setTimeout` posé par le pilote raccourcissait
aussi la fenêtre d'observation de `run-entry.js` (1,6 s au lieu de 8 s), donc `piloter()`
n'était jamais appelé et toute charge déclenchée à l'usage — session WhatsApp, exports —
passait inaperçue.

Avec v3 : `pilote` présent dans **24 sondes sur 24**, fenêtre mesurée **13 à 16 s**, et le
compte ne bouge pas. Le banc observe désormais ce qu'il annonce observer.

## Les refus qui rendent le chiffre croyable (mesurés sur le vrai banc)

- **Injection de faute** : événements de `b001` copiés dans `b012` (sonde inscrite) →
  `ATTRIBUTION INVALIDE raisons=nonce étranger`, banc `NON RECEVABLE`.
  Un tag **non inscrit** ne prouve rien : il sort `HORS REGISTRE (ignoré)`.
- **Protection retirée** : `SBX_REDEMARRER=0` → l'orphelin du leurre frappe dans le témoin,
  `p12-propre ATTRIBUTION INVALIDE — FORGE DÉMONTRÉE`, `p21` en `CLÉ NON RECEVABLE`.
- **Concurrence** : deux bancs simultanés, le second `rc=75` en 7 ms.
- **Nonce** : une seule valeur par journal, identique à la colonne 3 du registre.

## Ce qui n'est pas prouvé

- **Enfant `sh -c` à environnement vidé** : non instrumenté. Pas de nonce ⇒ pas de `CLÉ`
  forgeable, mais son activité échappe au journal. `strace -f` le suit déjà ; lire
  `trace.raw` donne une confirmation, pas une preuve (le paquet peut modifier ce fichier).
  Ni Rust ni Go ne changent cela ; seul `seccomp` + `SECCOMP_RET_USER_NOTIF` le fermerait.
- **RCE npm** : correctif en place, contre-épreuve non reproduite sur npm 12.0.2 →
  test **INCONCLUANT**, aucune version de npm n'est figée pour le faire passer.
- **P5/P6/P7** : binaires absents de l'image, identité du tarball, score pondéré.
- **sudoers** : bob a de fait les droits root tant qu'il est dans le groupe `docker`.
