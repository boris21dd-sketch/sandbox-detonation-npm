# ⚠️ AVERTISSEMENT — CE BANC N'EST PAS EN ÉTAT DE PRODUIRE UN VERDICT

Verdict des vérificateurs (3 passes croisées hy4 / Mistral, 24/11) : **BLOQUANT**.
Aucun nouveau run, aucun verdict, aucune ligne « sécurité OK » tant que ce qui suit
n'est pas fermé. Le miroir sur `K:` est une **archive**, pas une déclaration de solidité.

## Le mensonge par attribution (le bloquant réel)

Le garde-fou fail-closed ferme un cas et en laisse un autre ouvert :

| Cas | Effet |
|---|---|
| artefact **absent** | `BANC INVALIDE` ✅ fermé |
| artefact **présent mais écrit par la sonde précédente** | le sink l'accepte, le verdict lit **CLÉ** ❌ **forgé** |

Un `detonate.js` orphelin qui écrit encore après l'effacement de `/work/out` produit
exactement cela : les canaris d'une sonde antérieure atterrissent dans le dossier de la
sonde courante. Le contrôle « `/work/out/run` inscriptible » ne l'empêche pas — il vérifie
la condition dont **l'orphelin a besoin aussi**.

**Correctif exigé** : un **nonce par sonde**, exigé dans chaque événement du sink. Un
événement sans le nonce courant est rejeté, pas compté. Sans cela, un `CLÉ` peut être
un artefact et personne ne peut le distinguer d'une vraie détection.

Conséquence sur les chiffres : 17/20, 13/20 et 12/20 ne mesurent pas seulement des runs
vides — ils viennent d'un banc **capable de forger un positif**. Aucun de ces trois
chiffres n'est recevable.

---
# sandbox-detonation-npm — état, problèmes ouverts, protocole de correction

Dépôt public : https://github.com/boris21dd-sketch/sandbox-detonation-npm
Dernier commit connu : `3486218` (puis commits locaux non poussés).
Skill Hermes : `/home/bob/.hermes/skills/security/sandbox-detonation-npm/`
Scripts de travail : `/home/bob/q5n2/` (`sbx-scenario3.sh`, `_sbx_driver3.cjs`,
`cles_scenario3.py`, `fabrique_sondes.py`)
Harnais : `/opt/sandbox/harnais/` (root) · `detonate.js`, `lib/sbx/sinks-io.js`,
`lib/sbx/sinks-code.js` · `detoner-obs.sh` (root)

## Ce qui est mesuré et tient

- Banc de 20 sondes, une classe de geste par sonde, témoin `p12-propre` en dernier.
- `p16-main-module` : le harnais ne lançait pas le paquet comme module d'entrée, donc
  tout loader gardé par `require.main === module` était invisible. Muette avant, CLÉ après.
- Horloge accélérée : `_sbx_offset.json` + `SBX_OFFSET_JOURS` décale `Date.now()` du paquet.
  Contrôle obligatoire : installé il y a 1 jour + offset 0 → muet ; +30 jours → frappe.
  Piège : le budget du harnais doit lire la VRAIE horloge, sinon il saute tout.
- `p19-split` et `p20-endpoint-npmrc` : découpage lecture/envoi, et hôte dérivé de `~/.npmrc`
  sans URL littérale. Les deux vues.
- `exec_indisponible` : un binaire absent (`curl`, `git`, `bash` ABSENTS de l'image) n'est
  plus lu comme un paquet propre.

## Problèmes ouverts (à corriger, avec le test qui tranche)

### P1 — Le banc n'est pas reproductible (le plus grave)
Trois runs identiques ont donné 17/20, 13/20, 12/20. Cause identifiée : les sondes
muettes n'avaient **pas de `run/entrees.jsonl`** — le harnais n'avait rien produit.
`detonate.js:194` meurt sur `ENOENT /work/out/run/events.jsonl`.
Hypothèse principale : un `detonate.js` orphelin de la sonde précédente écrit encore
après que le scénario a effacé `/work/out`, et/ou une paire de conteneurs réutilisée
pendant des heures dérive.
**Test qui tranche** : redémarrer `sbx-detonation` et `sbx-fauxinternet` ENTRE CHAQUE
sonde, relancer les 20, et vérifier que `banc-invalide.txt` est vide.
Un `pkill -f detonate.js` avant effacement a été ajouté mais n'a pas suffi.

### P2 — Un garde-fou qui peut masquer une détection
Distinguer deux échecs (remarque de Mistral, à implémenter complètement) :
échec **avant** la charge utile → `BANC INVALIDE`, on rejoue ;
échec **après** (le stderr montre un canari) → `DETECTION NON LOGGUEE`, à rejouer,
**jamais** comptée muette.
État : le contrôle existe et pointe le bon chemin, la seconde branche n'a jamais été
exercée en vrai.

### P3 — Le matcher de canari multi-encodage n'est pas prouvé
`variantes()` couvre base64/urlsafe/hex/percent, mais **pas les décalages d'alignement**.
Un fichier encodé en base64 ne contient pas la base64 du canari isolé : la base64 n'est
pas composable. Il faut, comme Malwhunter (`wiretap/canary.py:27-51`), encoder
`b"\0"*shift + canari` pour shift 0,1,2 et chercher le cœur stable (`encoded[4:-4]`).
Sonde de test : `p18-base64` (muette aujourd'hui).
**Attention** : une lecture de fichier (`fs.readFileSync`) ne doit JAMAIS compter comme
preuve réseau. Vérifier l'attribution avant de conclure.

### P4 — Un hook enrichi casse la mesure
Ajouter une émission dans `sinks-code.js` sans `try/catch` fait lever l'appel chez le
paquet : deux sondes sont devenues muettes. Tout ajout s'enveloppe.

### P5 — `curl`, `git`, `bash` absents de l'image de détonation
Un `postinstall: curl … | sh` échoue en *command not found*. On voit l'intention
(`exec_indisponible`) mais pas ce qui aurait été envoyé. Ajouter ces binaires à l'image.

### P6 — Pas de vérification d'identité du tarball
Le `name`+`version` du manifeste doit égaler ce qui est démandé, sinon substitution.
Repris de SkillSpector `dependency_worker.py:207-220`.

### P7 — Verdict binaire, sans pondération
`CLÉ` / `—` ne distingue pas un canari exfiltré d'une simple résolution DNS. Reprendre
le score de SkillSpector (`report.py:622-790`) : points par sévérité, rendements
décroissants par règle, plancher 51 si un composant exécutable n'a pas pu être analysé.

## Ce qui a été écarté, et pourquoi (ne pas le réintroduire)

- **LLM comme juge** (SkillSpector) : actif par défaut, sans seed, et peut **supprimer**
  un constat statique. Incompatible avec un banc rejoué ×3.
- **Réputation** : allowlists d'hôtes, typosquat, compteurs de téléchargements, âge du
  paquet. Refusé par doctrine.
- **LavaMoat/SES** : confinement, pas observation ; masque le comportement.
- **`npm install` dans la sandbox en remplacement du rejeu** : détruit l'attribution
  script par script.

## Liens

- Dépôt : https://github.com/boris21dd-sketch/sandbox-detonation-npm
- `ossf/package-analysis` (dynamique de référence) : https://github.com/ossf/package-analysis
- `DataDog/guarddog` (statique, concurrent direct) : https://github.com/DataDog/guarddog
- `NVIDIA/SkillSpector` (statique skills, 27,5k★) : https://github.com/NVIDIA/SkillSpector
- `huawei-csl/KillSkillSpector` (jeu d'évasions) : https://github.com/huawei-csl/KillSkillSpector
- `ImGauravbhosale/Malwhunter` (canaris multi-encodage) : https://github.com/ImGauravbhosale/Malwhunter
- `boredchilada/pkgward-oss` (module d'entrée, settle, honeytokens) : https://github.com/boredchilada/pkgward-oss

## Comment reproduire

```bash
cd /home/bob/q5n2
python3 fabrique_sondes.py                       # 20 sondes dans sondes/
sudo -n systemd-run --uid=bob --unit=sbx-x --collect \
  --setenv=SBX_OFFSET_JOURS=30 --setenv=SBX_INSTALLE_MS=<now-1j en ms> \
  bash sbx-scenario3.sh /tmp/liste_sondes.tsv x 120
python3 cles_scenario3.py x                      # verdict par sonde
cat ~/.hermes/cache/scratch/sbx-x/banc-invalide.txt   # sondes non exécutées
```

## Série 2 — cinq passes croisées sur l'état réel (échecs inclus)

Passes 6 à 10, alternance Mistral → hy4 → Mistral → hy4 → Mistral. Verbatim dans
`verificateurs/passe6..10-*.txt`. Ce qu'elles ont établi, et qui corrige ce document :

- **Le `CLÉ` obtenu après le revert de la sonde `v2001` n'est PAS une preuve.** Il peut
  être l'artefact d'un `detonate.js` orphelin. Je l'ai cité comme « retour à un état sain » :
  les deux vérificateurs l'ont repris comme un blanc-seing, puis hy4 a retiré ce crédit.
  **Un run fonctionnel n'est pas un run authentifié.** Aucun chiffre, y compris celui-là,
  n'est recevable.
- Le point « P1 reste ouvert » et le point « le banc peut forger un positif » **se
  contredisent** tant que le nonce n'existe pas : le seul énoncé recevable est le second.
- Les trois fermetures (fail-closed, stderr hors preuve, garde-fou pré-sonde) ferment sur
  l'**absence**. Aucune ne ferme sur l'**attribution**. C'est là, et seulement là, que se
  situe le bloquant.

### Ce que doit faire un tiers, dans cet ordre

1. **Nonce par sonde** : chaque événement du sink porte le nonce courant ; un événement
   sans ce nonce est rejeté, jamais compté. Tant que ce n'est pas fait, ne rien mesurer.
2. **Prouver que le nonce marche** par une injection de faute déterministe : lancer une
   sonde leurre qui écrit un canari d'une sonde précédente. Le banc doit répondre
   `ATTRIBUTION INVALIDE`. Un nonce non testé est une croyance.
3. Seulement ensuite : P1 (runs vides), P3 (shifts d'alignement), P5 (curl/git/bash
   absents de l'image), P6 (identité du tarball), P7 (score pondéré, sans plancher 51 —
   ce plancher blanchit un banc invalide).
4. Ne jamais conclure « stable » sur moins de 29 runs, ou sur une injection de faute.

### Tentatives qui ont échoué (ne pas les refaire sans mesure)

- `pkill -f detonate.js` avant effacement : insuffisant, un `sleep 1` n'est pas une garantie.
- Dossier de sortie unique par sonde (`/work/out-<tag>`) : **a cassé le pipeline**, les
  4 sondes de contrôle sont devenues `BANC INVALIDE` (aucune entrée). Reverté.
  Piste toujours valable en principe, mais elle exige de reprendre `detonate.js:194` et
  le `tar` de récupération ensemble, pas une substitution de chaîne.

## Reproductions faites après les passes (Claude avait raison)

**R1 — la branche fail-closed ne s'exécutait pas.** Relevé par Claude, reproduit ici :
un dossier de run sans `run/entrees.jsonl` sortait `—`. Cause trouvée : `main()`
reconstruit chaque ligne dans un dict neuf et **la clé `verdict` y était perdue**.
Corrigé (`"verdict": c.get("verdict","")`), retesté : `zz001` → `BANC INVALIDE`.
Leçon : un verdict calculé puis recopié champ par champ se perd silencieusement.

**R2 — un dossier de run périmé est lu comme une détection.** `cp -r runs-obs/v2001
runs-obs/zz002` puis agrégation → **CLÉ forgée** avec le canari SSH d'une sonde
antérieure. Non corrigé : c'est exactement le mensonge par attribution, il exige le
nonce + un reset prouvé (tâches P0-01 et P0-03 du plan Claude).

**R3 — `p18` ne teste pas les décalages.** Le matcher actuel l'attrape déjà au décalage 0 :
la sonde ne prouve donc rien sur l'alignement. Il faut une sonde dont le canari est
**entouré** de contenu, pour que la base64 du fichier ne contienne jamais celle du canari.

**R4 — `.env` et `MSG` encodés ne sont jamais détectés.** Constat de Claude, non revérifié ici.
