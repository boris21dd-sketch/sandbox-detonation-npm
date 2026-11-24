# sandbox-detonation-npm

Détoner des paquets npm dans un conteneur pour obtenir une **preuve** — quel secret
sort, vers quel hôte — ou une **absence étayée**, au lieu d'un « rien vu » qui ne
veut rien dire.

Ce dépôt contient le protocole complet, les scripts qui tournent réellement, un
banc de sondes qui note la sandbox, et le journal des audits successifs.

## Le problème

Une sandbox qui fait `require(main)` et attend 30 secondes ne juge rien : elle
regarde. Mesuré sur douze paquets suspects, ce protocole rendait `charges=0`
partout — aucune charge exécutée — pour cinq raisons cumulées :

- l'installation est faite avec `--ignore-scripts`, donc les scripts de cycle de
  vie (`preinstall`/`install`/`postinstall`) ne tournent **jamais**, alors que
  c'est le vecteur n°1 des compromissions npm ;
- un `setTimeout` de trois jours ne se déclenche pas en trente secondes ;
- sans état de victime (`~/.ssh`, `~/.npmrc`, session WhatsApp), il n'y a rien à
  voler, donc rien à observer ;
- sans pilotage, un client WhatsApp ne fait qu'enregistrer des callbacks ;
- et le journal réseau ne dit pas **ce qui** sort, seulement **où** ça allait.

## Ce que fait ce protocole

Un pilote remplace temporairement le `main` du paquet — le code du paquet n'est
pas modifié — et, dans le conteneur :

1. **sème douze états de victime** avec des canaris distincts (npmrc, clé SSH,
   AWS, GitHub, Docker, kube, gitconfig, `.env`, gcloud, session WhatsApp,
   cookies, historique shell) ;
2. **plafonne les délais** (`setTimeout`/`setInterval` globaux, `node:timers`,
   `timers/promises`) : un appel à trois jours part en 1,5 s ;
3. **rejoue les scripts de cycle de vie** du paquet **et de ses dépendances** —
   y compris les paquets scopés `@scope/nom` ;
4. **exécute les `bin`** (`--help`, `--version`) ;
5. **charge tous les points d'entrée** (`exports` d'abord — Node ignore `main`
   quand `exports` existe — ESM par `await import()`, CJS par `require`) et
   pilote les exports avec une session factice.

La preuve est ensuite lue par un agrégateur qui ne compte comme fuite que ce qui
sort réellement : un canari dans un événement réseau vers un hôte autre que le
registry, ou une commande portant une URL, ou l'écriture d'une configuration de
client (`~/.claude`, `~/.codex`, `~/.cursor`, `~/.gemini`, `.mcp.json`).

## État mesuré

- Banc de sondes : **13/13 classes malveillantes vues, témoin muet**.
- Audits : journal dans `journal/` ; chaque tour est suivi d'un rejeu réel du
  banc, et une amélioration qui casse le banc est rejetée.

## Usage

```bash
# 1. fabriquer le banc de sondes (12 classes + témoin)
python3 scripts/fabrique_sondes.py

# 2. détoner une liste (nom<TAB>chemin.tgz)
sudo systemd-run --uid=$USER --unit=sbx --collect \
  bash scripts/sbx-scenario3.sh /tmp/liste_sondes.tsv pf 120

# 3. lire les clés
python3 scripts/cles_scenario3.py pf

# 4. audits successifs (4 relecteurs + rejeu du banc)
python3 scripts/audit_sandbox_20.py --tours 20
```

## Ce que ce n'est pas

Pas un antivirus, pas un verdict d'innocence. Aucun canari sorti, aucun hôte
hors registry, aucun `exec` inattendu sous le scénario le plus dur : c'est une
**absence étayée**, jamais « le paquet est propre ».

## Licence

Usage défensif, recherche et audit. Voir [DISCLAIMER.md](DISCLAIMER.md) — le
logiciel est fourni en l'état, sans garantie, et l'utilisateur assume l'exécution
de code non fiable dans son propre environnement isolé.
