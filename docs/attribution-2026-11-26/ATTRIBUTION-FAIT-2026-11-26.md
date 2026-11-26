# Attribution corrigée — ce qui est fait, ce qui reste

**26/11/2026, 13h10.** Suite à l'audit de Claude (LIVRAISON-SANDBOX-C) et aux deux audits
croisés de hy4 et mistral. Ce document dit ce qui a été **exécuté**, pas ce qui est prévu.

---

## 1. Ce qui est corrigé et mesuré

`attribuer.py` (livré, exécuté sur les 2 917 runs présents) recalcule l'attribution **sans
relancer la campagne**, et sépare trois choses que le harnais confondait :

```
origine_code        paquet | dependance | banc | outil | node | inconnu   (chemin de l'appelant)
origine_processus   paquet | dependance | banc                            (entrée lancée)
flux_local          net.write valeur 'socket' = stdout/stderr — JAMAIS du réseau
reseau              hôtes réels : dns.lookup, net.connect, tls.connect, https.request
muet                True si aucun événement attribuable au paquet
```

**Contrôle positif du banc de sondes, sur les mêmes règles :**

```
251 runs de sondes → 196 avec un hôte réel (sink.exfil-probe.test, raw.githubusercontent.com)
                     13 muets
```

L'outil discrimine : il voit les sondes frapper leur sink. Il n'est pas aveugle.

## 2. Les 204 « manquants », recalculés

```
204 runs · 77 muets (aucun événement du paquet) · 4 081 flux_locaux (stdout)
100 runs avec un hôte réel, dont 90 vers registry.npmjs.org  ← npm de l'image, cf. F7 de Claude
 10 runs avec un hôte HORS registry — exactement ceux que Claude avait nommés
```

Les dix, avec leur paquet :

| run | hôte | paquet |
|---|---|---|
| manq11004 | github.com | — |
| manq16010 | github.com | @zeit/next-sass@1.0.1 (node-sass télécharge son binaire) |
| manq17003 | github.com | zen-grids@2.0.3 |
| manq17010 | bitbucket.org | — |
| manq5010 | github.com | — |
| manq6003 | github.com | — |
| manq6004 | github.com | — |
| manq7002 | storage.googleapis.com | — |
| manq7007 | 0.0.0.0 | webappengine@1.2.0 |
| manq8004 | http: / saucelabs.com | — |

**Cette liste a été produite deux fois indépendamment** — par Claude en lisant les traces à la main,
par `attribuer.py` en classant 95 811 événements. Elles coïncident. C'est le seul chiffre de la
journée qui ait passé deux chemins différents.

## 3. Ce qui reste à faire, et qui exige root

Les corrections A1–A5 touchent le harnais déployé (`/opt/sandbox`, root) et le détoneur. Elles ne
sont **pas appliquées** : la porte root est fermée depuis hier soir et je ne la rouvre pas sans le
run témoin qui la valide.

```
A1  pilote déplacé : `cd package && node ../_sbx/pilote.cjs`
    → package.json INTACT (correction de hy4 et mistral, contre ma version qui l'éditait)
A2  cycles de vie en double supprimés, et une entrée `main` toujours produite
A3  dépendances pair installées (retirer --legacy-peer-deps, repli marqué charges=0)
A4  mktemp -d + code retour de rm -rf contrôlé (2 sondes perdues sur fichiers root)
A5  prepublishOnly filtré en phase installation, pour le paquet ET les dépendances
A7  ingestion du journal du faux-Internet — trou que NI Claude NI moi n'avions mis au lot,
    relevé par hy4 : 114/218 lignes de trafic vu, jamais lues
A8  strace -f -e trace=network + capture ppid/fd pour attribuer les enfants `sh -c`
```

## 4. La porte, qu'ils exigent tous les deux

Avant toute série, **un** run témoin, avec quatre conditions simultanées :

```
charges > 0 sur le vrai `main`        (aujourd'hui : 0 sur 218/218)
exactement 1 entrée `:postinstall`
0 `prepublishOnly` exécuté
journal du faux-Internet lu et joint
```

Porte verte → 204 runs. Une seule ligne rouge → arrêt, ni série, ni correction d'étiquettes après
coup.

## 5. Ce que je ne signe pas

- **Les 204 runs ne sont pas à réattribuer, ils sont à refaire.** `charges=0` sur 218 lignes : le
  code du paquet n'a presque jamais tourné. Corriger l'étiquette d'une mesure vide ne la remplit pas.
  Les chiffres du §2 décrivent ce que le **banc** a fait, pas ce que les paquets font.
- Les quatre règles du tour 7 sont **mortes** : elles comptaient `net.write`, c'est-à-dire stdout.
  Pas « non mesurables » — fausses.
- Aucun verdict de propreté sur les 203 paquets. Aucun chiffre de rappel.
- Rien n'est poussé sur GitHub.

## 6. Pièces

```
attribuer.py               l'outil, réexécutable : python3 -I attribuer.py /opt/sandbox/runs-obs
attribution-corrigee.json  2 917 runs, un enregistrement par run
reseau-resume.json         manquants vs sondes (contrôle positif)
hors-registry.json         les 10 runs et leurs hôtes
AUDIT-CLAUDE-*.md          l'audit qui a démoli mes trois lectures
trous/hy4.md, mistral.md   les deux audits du plan A1–A6
trous/*-juge.md            les jugements croisés, verbatim
EMPREINTES.txt             sha256 de chaque pièce
```
