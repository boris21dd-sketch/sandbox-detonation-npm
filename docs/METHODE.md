# Méthode : mesurer la sandbox, pas l'imaginer

## Le principe

Un protocole de détonation n'a de valeur que s'il est **noté**. Sans banc, chaque
« amélioration » est une opinion. Ici, la note est mécanique : douze classes
d'attaque, une sonde par classe, un témoin qui doit rester muet.

## Le banc de sondes

`scripts/fabrique_sondes.py` fabrique treize paquets npm réels :

| # | Sonde | Gestes couverts |
|---|---|---|
| 1 | `p01-postinstall` | script de cycle de vie classique |
| 2 | `p02-esm` | paquet ESM pur |
| 3 | `p03-timer` | déclenchement différé (3 jours) |
| 4 | `p04-bin` | geste uniquement dans le `bin` |
| 5 | `p05-npmrc` | vol du jeton npm |
| 6 | `p06-c2` | config distante mutable puis exécution |
| 7 | `p07-exports` | `exports` sans `main` |
| 8 | `p08-eval` | charge utile encodée et évaluée |
| 9 | `p09-shell` | shell + réseau |
| 10 | `p10-hook` | configuration de client auto-installée |
| 11 | `p11-wa` | vol de session WhatsApp |
| 12 | `p13-exports-piege` | charge utile dans `exports` derrière un `index.js` bénin |
| 13 | `p14-dep-postinstall` | charge utile dans le `postinstall` d'une dépendance |
| — | `p12-propre` | **témoin** : doit rester muet |

Chaque sonde exfiltre vers `sink.exfil-probe.test`, que le faux-Internet
journalise. Aucune donnée réelle n'est utilisée : les canaris sont synthétiques.

## La note

```
13/13 classes vues, témoin muet
```

Une amélioration qui fait baisser ce chiffre, ou qui fait parler le témoin, est
**rejetée** — même si elle paraît élégante.

## La boucle d'audit

`scripts/audit_sandbox_20.py` déroule vingt tours :

1. quatre relecteurs différents (hy4, mistral-large-4, minimax-m3.1-flash,
   kimi-k3.1-pro) reçoivent le protocole exact et le score du tour précédent ;
2. leurs constats sont extraits (titre, preuve, correctif, bloquant) et
   journalisés dans `AUDITS-SANDBOX-JOURNAL.jsonl` ;
3. le banc est **rejoué** ;
4. le score est comparé au tour précédent.

Arrêt anticipé après trois tours consécutifs sans constat bloquant.

## La règle des deux relecteurs

Tout run de plus d'une heure est relu **avant** d'être lancé, par deux modèles
différents, sur le script et le pilote exacts. Poser des questions fermées
(`BLOQUANT` / `NON BLOQUANT`) et exiger la ligne à corriger.

Cette règle vient d'un échec concret : un run de quatre heures lancé sans revue
rendait des hôtes vides pour ses 87 paquets, parce que l'agrégateur lisait un
fichier jamais écrit.

## La veille

`scripts/veille-audit-sandbox.sh` : relance l'audit s'il est arrêté ou figé
(journal inchangé plus de 25 minutes), sans jamais relancer si un banc tourne
encore. Silencieuse quand tout va bien.

<!-- etat : 13/13, temoin muet -->
