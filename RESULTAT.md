# RÉSULTAT — banc de détonation npm, 2026-11-24

## Chiffre citable

**23 / 24 sondes détectées, témoin `p12-propre` muet, trois fois de suite.**

| run | CLÉ | — | verdict | code |
|---|---|---|---|---|
| b | 23 | 1 | BANC RECEVABLE | 0 |
| f | 23 | 1 | BANC RECEVABLE | 0 |
| g | 23 | 1 | BANC RECEVABLE | 0 |

Dénominateur = registre (24 sonde inscrites), 0 hors registre.
Configuration : horloge +30 jours (`SBX_OFFSET_JOURS=30`), paquet installé la veille,
redémarrage du conteneur entre chaque sonde.

## Ce qui rend ce chiffre croyable

Trois refus correctement motivés, mesurés sur le vrai banc :

1. **T-H1 — injection de faute.** Les événements de `b001` copiés dans `b012`
   (sonde inscrite) donnent `ATTRIBUTION INVALIDE raisons=nonce étranger`, et le banc
   entier bascule en `BANC NON RECEVABLE`. Un artefact présent n'est pas cru sur parole.
2. **T-H3 — protection retirée.** Avec `SBX_REDEMARRER=0`, l'orphelin du leurre survit et
   frappe dans le témoin : `p12-propre ATTRIBUTION INVALIDE — FORGE DÉMONTRÉE
   (leurre.exfil-probe.test vu dans p12-propre)`. `p21` devient `CLÉ NON RECEVABLE`.
3. **T-H4 — concurrence.** Deux bancs simultanés : le second sort `rc=75` en 7 ms.

Plus **T-H5** : un seul nonce par journal, identique à la colonne 3 du registre
(vérifié sur `b001`, `b023`, `b024`).

## Ce qui n'est PAS prouvé

- **`sh -c` avec environnement vidé** : l'enfant n'est plus instrumenté. Il ne peut pas
  forger un `CLÉ` (pas de nonce), mais ce qu'il fait échappe au journal. Deux
  vérificateurs indépendants ont confirmé que ni un hôte Rust ni un hôte Go ne
  changent cela : seul un filtre `seccomp SECCOMP_RET_USER_NOTIF` (hérité par
  `fork`/`exec`) le fermerait. `LD_PRELOAD` est inopérant ici.
- **P1 ouverts** : plafond des minuteries absent des processus enfants, `SBX_OBSERVER_MS`
  qui coupe le pilote, `sudoers` donnant root à bob.
- **RCE npm** : le correctif est en place (`.npmrc` retiré, configs vides distinctes,
  `--git=/bin/false`), mais la contre-épreuve ne reproduit pas la faille avec
  npm 12.0.2 / node 22.23.2 — le test ne discrimine donc pas ici.

## Chiffres morts

17 / 20, 13 / 20, 12 / 20 et le `CLÉ` du run `v2001` : **non recevables**. Ils venaient
d'un lecteur incapable de distinguer « rien produit » de « rien trouvé », et capables de
lire le dossier d'un run périmé comme une détection.
