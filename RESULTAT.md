# RÉSULTAT — banc de détonation npm, protocole v4 (25 sondes)

## Chiffre citable

**24 / 25 sondes détectées, témoin `p12-propre` muet, trois runs consécutifs (k, l, m).**
`BANC RECEVABLE`, code 0, sur les trois.

| run | CLÉ | — | verdict | pilote | settle | observation (min/méd/max) |
|---|---|---|---|---|---|---|
| k | 24 | 1 | BANC RECEVABLE | 25/25 | 25/25 | 13,1 / 14,2 / 18,6 s |
| l | 24 | 1 | BANC RECEVABLE | 25/25 | 25/25 | 13,4 / 15,6 / 16,9 s |
| m | 24 | 1 | BANC RECEVABLE | 25/25 | 25/25 | 12,7 / 15,7 / 18,2 s |

Registre = 25 sondes, 0 hors registre, 25 journaux distincts par run.

## `verif_preuves.py` — contrôles hors lecteur, passés sur les trois lots

- toutes les lignes de `events.jsonl` portent le nonce du registre ;
- `fin.json`, `entrees.jsonl`, `summary.json` au bon nonce, aucun événement étranger ;
- garde `OK`, redémarrage `OK`, `npm_rc = 0` partout ;
- aucun canari d'un autre suffixe, aucun `leurre.exfil-probe.test` hors `p21` ;
- `p18`, `p18b`, `p18c` : le canari n'apparaît **jamais en clair** dans le faux-Internet —
  ces trois-là ne sont détectées que par le matcher, sur de vraies données ;
- étapes `settle` + `pilote` présentes dans 25/25 `_sbx_etat.jsonl`.

## Ce que la v4 a ajouté, et ce que ça prouve

`p23` est la première sonde dont la charge ne part **que si le pilote appelle une fonction
exportée**. Testée hors banc : frappe avec le nouveau `run-entry.js` (15,1 s, 1 requête),
muette avec l'ancien (1,6 s, 0 requête).

C'est pour elle que le compte passe de 23 à 24. Les runs précédents (`b` à `j`) ne
contenaient aucune sonde dépendant du pilote : le banc ne pouvait donc pas voir que le
pilote était cassé. Ils n'étaient pas faux, ils étaient **muets sur la question**.

## Correction d'un récit erroné (le mien)

- `p11-wa` **ne dépend pas du pilote** : elle frappe au chargement, identiquement en
  `b011` et `h011`. Le `fs.writeFileSync` que j'avais cité est l'**ensemencement des
  canaris par le pilote**, et `p11` n'a pas de postinstall.
- Les runs `b`, `f`, `g` **ne sont pas caducs** : recomptés, ils donnent 23/24 recevable.
  J'avais sur-corrigé.

## Ce que ce chiffre vaut, et ne vaut pas

Sur les 24 détections : 19 sont des secrets réellement exfiltrés, 1 une écriture de
configuration client (`p10`), 1 un simple contact réseau (`p06`), 2 seulement des
intentions parce que `curl` est absent (`p09`, `p17`). La pondération (P7) reste à faire.

**Trois runs ne prouvent pas la stabilité** : réfuter un défaut à 10 % exige 29 runs.
Et le chiffre mesure le banc **sur ses propres sondes**, pas un taux de détection sur du
vrai malware.
