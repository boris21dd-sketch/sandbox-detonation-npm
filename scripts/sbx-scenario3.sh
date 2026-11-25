#!/usr/bin/env bash
# =============================================================================
#  sbx-scenario3.sh — l'exigence maximale : on cherche une CLÉ sur chaque paquet.
#
#  Ce que le scénario 2 a montré : exécuter les scripts de cycle de vie, fournir
#  un état de victime et écraser les délais ne suffit pas si l'on ne regarde pas
#  ce qui SORT. Le scénario 3 ajoute :
#    - douze canaris (npmrc, ssh, aws, gh, docker, kube, git, env, session WA) ;
#    - les scripts de cycle de vie, les bins, ET les exports ;
#    - 90 s de run (au lieu de 30) ;
#    - une recherche des canaris DANS tout ce qui sort (réseau, exec, fichiers),
#      qui donne la preuve : quel canari, vers quel hôte, à quelle ligne.
#
#  Usage : sbx-scenario3.sh <liste.tsv nom\ttgz> <prefixe> [timeout_s]
# =============================================================================
set -u

# --- tarball NON FIABLE : refus des liens et fichiers speciaux (B5) -------------
# Les etapes python ecrivent dans package/ (package.json, _sbx_*.json) : un lien
# symbolique ou materiel dans le tarball ferait ecrire HORS du dossier de travail
# (fichier de bob). On inspecte donc la LISTE avant extraction (un lien materiel
# n'est plus visible apres), puis l'arbre extrait, et on exige une racine unique
# `package/`. Retourne 0 si sain ; sinon 1 et la raison sur stdout.
liste_saine() {  # $1 = tgz
  local types
  tar tzf "$1" >/dev/null 2>&1 || { echo "LISTE_ILLISIBLE"; return 1; }
  types=$(tar tzvf "$1" 2>/dev/null | cut -c1)
  if printf '%s\n' "$types" | grep -q '[^-d]'; then echo "LIEN_OU_SPECIAL_DANS_TARBALL"; return 1; fi
  return 0
}
arbre_sain() {  # $1 = dossier d'extraction
  if [ -n "$(find "$1" -type l -print -quit 2>/dev/null)" ]; then echo "LIEN_SYMBOLIQUE"; return 1; fi
  if [ -n "$(find "$1" ! -type f ! -type d -print -quit 2>/dev/null)" ]; then echo "FICHIER_SPECIAL"; return 1; fi
  if [ "$(ls -A "$1" | wc -l)" -ne 1 ] || [ ! -d "$1/package" ] || [ -L "$1/package" ]; then echo "RACINE_NON_UNIQUE"; return 1; fi
  return 0
}
# Crochet de test : `SBX_FONCTIONS_SEULEMENT=1 source sbx-scenario3.sh` ne charge que les fonctions.
if [ "${SBX_FONCTIONS_SEULEMENT:-0}" = 1 ]; then return 0 2>/dev/null || exit 0; fi

LIST=${1:?usage: sbx-scenario3.sh <liste> <prefixe> [timeout]}
PREFIXE=${2:-s3}
TMO=${3:-120}
OUT=/home/bob/.hermes/cache/scratch/sbx-${PREFIXE}
WORK=/home/bob/.hermes/cache/scratch/npmwork
mkdir -p "$OUT" "$WORK"
# VERROU EXCLUSIF : sbx-detonation, /work et le journal du faux-Internet sont PARTAGES.
# Deux bancs simultanes (systemd-run sans --wait relance par l'agent) s'effacent
# mutuellement /work/out (ENOENT a detonate.js:194), se tuent par `pkill -f
# detonate.js` (detoner-obs.sh:40) et se volent leurs lignes de faux-internet.jsonl
# (decoupage par numero de ligne, detoner-obs.sh:135). Refus net, jamais d'attente.
VERROU=${SBX_VERROU:-/tmp/sbx-detonation.lock}
exec 9>>"$VERROU" || { echo "BANC REFUSE : verrou $VERROU inaccessible" >&2; exit 75; }
flock -n 9 || { echo "BANC REFUSE : un autre banc tient $VERROU (aucun run concurrent)" >&2; exit 75; }
cd /opt/sandbox || exit 1
# Remise a zero : aucun resultat d'un run precedent ne doit survivre (B4).
# `: > a b c` ne tronque que `a` : une boucle est necessaire.
for f in banc-invalide.txt resultats.txt registre.tsv cles.txt; do : > "$OUT/$f"; done
REDEMARRER=${SBX_REDEMARRER:-1}

# Registre (hote, hors d'atteinte du conteneur), 8 colonnes :
#   tag nom nonce debut_ms garde redemarrage suffixe npm_rc
# `suffixe` = 6 hex propres a la sonde (canaris), `npm_rc` = code retour de l'install
# (`-` si pas d'install). Une ligne par sonde, ecrite AVANT la detonation : c'est
# lui le denominateur.
registre() {  # $1 = garde (OK|raisons)  $2 = redemarrage (OK|ECHEC|DESACTIVE)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$tag" "$nom" "$NONCE" "$(date +%s%3N)" "$1" "$2" "${SUFFIXE:--}" "${NPM_RC:--}" >> "$OUT/registre.tsv"
}
# Sonde invalide : elle reste dans le denominateur (banc-invalide + resultats + registre).
invalide() {  # $1 = raisons  $2 = redemarrage
  echo "$tag|INVALIDE|$1" >> "$OUT/banc-invalide.txt"
  echo "$tag|INVALIDE|$1" >> "$OUT/resultats.txt"
  echo "  BANC INVALIDE ($tag: $1) — sonde non executee"
  registre "$1" "$2"
  rm -rf "$D" "${T:-}"
}

# Configs npm VIDES et DISTINCTES : `--userconfig=/dev/null --globalconfig=/dev/null`
# fait refuser npm (« double-loading config /dev/null ») -> toutes les installs
# echouaient. Mesure par Claude, npm 10.9.
NPM_VIDE_U=$(mktemp); NPM_VIDE_G=$(mktemp)
trap 'rm -f "$NPM_VIDE_U" "$NPM_VIDE_G"' EXIT

# Le pilote vit dans _sbx_driver3.cjs (CommonJS force, ESM gere par import()) :
cp /home/bob/q5n2/_sbx_driver3.cjs /tmp/_sbx_driver3.cjs

i=0
while IFS=$'\t' read -r nom tgz; do
  [ -z "${tgz:-}" ] && continue
  i=$((i+1)); tag=$(printf "%s%03d" "$PREFIXE" "$i")
  D="$WORK/$tag"; rm -rf "$D"; mkdir -p "$D"; T=""
  # Nonce d'attribution de CETTE sonde, genere avant tout (B4).
  NONCE=$(python3 -I -c 'import secrets;print(secrets.token_hex(16))')
  # Suffixe des canaris propre a CETTE sonde : un canari d'une autre sonde est une forge.
  SUFFIXE=$(python3 -I -c 'import secrets;print(secrets.token_hex(3))')
  NPM_RC='-'
  # Aucune sonde ne disparait du denominateur : tout refus passe par invalide().
  RAISON=$(liste_saine "$tgz") || { invalide "REFUS_LIEN:$RAISON" DESACTIVE; continue; }
  tar xzf "$tgz" -C "$D" 2>/dev/null || { echo "$tag|$nom|EXTRACTION_ECHEC" >> "$OUT/resultats.txt"; invalide "EXTRACTION_ECHEC" DESACTIVE; continue; }
  RAISON=$(arbre_sain "$D") || { invalide "REFUS_LIEN:$RAISON" DESACTIVE; continue; }
  [ -f "$D/package/package.json" ] || { echo "$tag|$nom|PAS_DE_PKG" >> "$OUT/resultats.txt"; invalide "PAS_DE_PKG" DESACTIVE; continue; }
  # RCE hote prouvee : un .npmrc du tarball (`git=./evil.sh` + dependance git) s'executait
  # pendant `npm install --ignore-scripts`. On supprime les configs du paquet et on
  # neutralise les configs utilisateur/globale et le binaire git.
  rm -f "$D/package/.npmrc" "$D/package/.yarnrc" "$D/package/.yarnrc.yml" "$D/package/.pnpmfile.cjs"
  ( cd "$D/package" && timeout 300 npm install --ignore-scripts --no-audit --no-fund --legacy-peer-deps \
      --userconfig="$NPM_VIDE_U" --globalconfig="$NPM_VIDE_G" --git=/bin/false > "$OUT/$tag.npm.log" 2>&1 )
  NPM_RC=$?
  NM=$(ls "$D/package/node_modules" 2>/dev/null | wc -l)
  # scripts de cycle de vie des dependances : on note la commande, le pilote la
  # rejouera DANS le conteneur (l'installation, elle, est faite sans scripts).
  python3 -I - "$D/package" <<'PY'
import json,os,sys
p=sys.argv[1]; nm=os.path.join(p,'node_modules'); out=[]
MAXP=4   # profondeur maximale des node_modules imbriques
MAXN=40  # plafond de scripts collectes

def sous(nm):
    # Les paquets scopes vivent dans node_modules/@scope/nom. Liens symboliques ignores.
    try: noms=sorted(os.listdir(nm))
    except OSError: return
    for n in noms:
        if n.startswith('.'): continue
        c=os.path.join(nm,n)
        # npm cree des liens pour les dependances `file:` (p14 : node_modules/sonde-dep -> ../dep) :
        # on les suit SEULEMENT s'ils restent dans le paquet (jamais hors de package/).
        if os.path.islink(c) and not os.path.realpath(c).startswith(os.path.realpath(p)+os.sep): continue
        if not os.path.isdir(c): continue
        if n.startswith('@'):
            try: ms=sorted(os.listdir(c))
            except OSError: continue
            for m in ms:
                if m.startswith('.') or os.path.islink(os.path.join(c,m)): continue
                yield n+'/'+m
        else:
            yield n

def parcourt(base,prefixe,prof):
    # `prefixe` = chemin relatif a package/node_modules du dossier node_modules courant.
    if prof>MAXP or len(out)>=MAXN: return
    for n in sous(base):
        if len(out)>=MAXN: return
        rel=prefixe+n
        d_pkg=os.path.join(base,n)
        f=os.path.join(d_pkg,'package.json')
        if os.path.isfile(f) and os.path.realpath(f).startswith(os.path.realpath(p)+os.sep):
            try: d=json.load(open(f,encoding='utf-8-sig'))
            except Exception: d=None
            sc=(d.get('scripts') if isinstance(d,dict) else None) or {}
            if isinstance(sc,dict):
                for k in ('preinstall','install','postinstall'):
                    if isinstance(sc.get(k),str) and sc.get(k) and len(out)<MAXN:
                        out.append({'nom':rel,'etape':k,'script':sc[k]})
        parcourt(os.path.join(d_pkg,'node_modules'),rel+'/node_modules/',prof+1)

if os.path.isdir(nm) and not os.path.islink(nm):
    parcourt(nm,'',1)
json.dump(out,open(os.path.join(p,'_sbx_deps_scripts.json'),'w'),ensure_ascii=False)
PY
  # BOM : un package.json en UTF-8 avec BOM faisait echouer json.load (sonde jamais
  # pilotee). Lecture en utf-8-sig ; ecriture sans BOM (le pilote fait JSON.parse sur
  # package.json, que le BOM ferait echouer). Echec = sonde INVALIDE, jamais detonee sans pilote.
  python3 -I - "$D/package" "$NONCE" "$SUFFIXE" <<'PY' || { invalide "INJECTION_PILOTE_ECHEC" DESACTIVE; continue; }
import json,sys,os
p=sys.argv[1]; f=os.path.join(p,'package.json')
d=json.load(open(f,encoding='utf-8-sig')); d['_sbx_main']=d.get('main') or (None if d.get('exports') else 'index.js'); d['main']='_sbx_scenario3.cjs'
json.dump(d,open(f,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
json.dump({"jours": os.environ.get('SBX_OFFSET_JOURS','0'),
           "installe_ms": os.environ.get('SBX_INSTALLE_MS','0')},
          open(os.path.join(p,'_sbx_offset.json'),'w'))
open(os.path.join(p,'_sbx_scenario3.cjs'),'w').write(open('/home/bob/q5n2/_sbx_driver3.cjs').read())
# Nonce + suffixe de canaris : meme canal que _sbx_offset.json (piege 15) ; le pilote
# lit puis supprime ce fichier.
json.dump({"nonce": sys.argv[2], "suffixe": sys.argv[3]}, open(os.path.join(p,'_sbx_nonce.json'),'w'))
PY
  T="$WORK/$tag.tgz"; tar czf "$T" -C "$D" package 2>/dev/null
  # `sudo` ne propage pas l'environnement : les variables de scenario doivent
  # passer par `env` sinon elles sont silencieusement perdues (mesure : la sonde
  # d'horloge restait muette meme avec un decalage de 30 jours).
  # CONTROLE POSITIF D ETAT (a) : le temoin muet prouve qu on ne crie pas au loup,
  # pas que le banc a fonctionne. Sans ceci, une panne d infrastructure se lit
  # « paquet propre » (mesure : pp003/pp010/pp016 sans entrees.jsonl).
  ETAT="$OUT/etat-banc.txt"
  : > "$ETAT"
  # ISOLATION PROCESSUS (cause racine de l'orphelin) : les processus detaches de la
  # sonde N (fenetre SETTLE, petits-enfants d'execSync tues par timeout) survivent
  # et ecrivent dans la sonde N+1. On redemarre le conteneur de detonation avant
  # chaque sonde (jamais sbx-fauxinternet ; le chemin /work/out n'est pas touche,
  # piege 21), puis on verifie qu'aucun `node` ne tourne.
  REDEM=DESACTIVE
  if [ "$REDEMARRER" = 1 ]; then
    if docker restart -t 2 sbx-detonation >/dev/null 2>&1; then REDEM=OK; else REDEM=ECHEC; fi
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
      docker exec sbx-detonation true >/dev/null 2>&1 && break; sleep 1
    done
  fi
  docker inspect -f '{{.State.Running}}' sbx-detonation 2>/dev/null | grep -q true \
    || echo "detonation=ARRETE" >> "$ETAT"
  docker inspect -f '{{.State.Running}}' sbx-fauxinternet 2>/dev/null | grep -q true \
    || echo "fauxinternet=ARRETE" >> "$ETAT"
  docker exec sbx-fauxinternet sh -c 'test -w /data/logs' 2>/dev/null \
    || echo "journal_reseau=NON_INSCRIPTIBLE" >> "$ETAT"
  docker exec "$(docker ps -qf name=sbx-detonation)" sh -c 'mkdir -p /work/out/run && test -w /work/out/run' 2>/dev/null \
    || echo "sortie=NON_INSCRIPTIBLE" >> "$ETAT"
  # Processus `node` vivants juste apres le redemarrage. Le PID 1 du conteneur peut
  # lui-meme etre un `node` (inconnu d'ici) : on compare donc a la LIGNE DE BASE prise
  # au premier redemarrage du run, au lieu d'exiger zero (sinon 100 % INVALIDE).
  if [ "$REDEMARRER" = 1 ] && [ "$REDEM" = OK ]; then
    NB_NODE=$(docker top sbx-detonation -eo pid,args 2>/dev/null \
       | awk 'NR>1 { c=$2; sub(".*/","",c); if (c=="node") n++ } END { print n+0 }')
    if [ -z "${BASE_NODE:-}" ]; then BASE_NODE=$NB_NODE; fi
    if [ "$NB_NODE" -gt "$BASE_NODE" ]; then
      echo "PROCESSUS_RESIDUEL(node=$NB_NODE>base=$BASE_NODE)" >> "$ETAT"
    fi
  fi
  if [ -s "$ETAT" ]; then
    # Garde en echec : la sonde RESTE dans le denominateur (avant : `continue` muet).
    invalide "$(tr '\n' ',' < "$ETAT" | sed 's/,$//')" "$REDEM"
    continue
  fi
  registre OK "$REDEM"

  # La regle sudoers n autorise QUE cette commande exacte, en SETENV sur ces
  # variables precises. `sudo env` n est plus permis : il equivaut a un root total.
  R=$(SBX_NONCE="$NONCE" SBX_OBSERVER_MS=15000 SBX_PAR_ENTREE=$TMO \
       SBX_OFFSET_JOURS="${SBX_OFFSET_JOURS:-0}" SBX_INSTALLE_MS="${SBX_INSTALLE_MS:-0}" \
       sudo -n --preserve-env=SBX_NONCE,SBX_OBSERVER_MS,SBX_PAR_ENTREE,SBX_OFFSET_JOURS,SBX_INSTALLE_MS \
        /bin/bash /opt/sandbox/detoner-obs.sh "$T" "$tag" "$TMO" 2>&1 | tail -1)

  # CONTROLE APRES (Mistral) : deux echecs tres differents.
  #  - rien n a ete ecrit -> banc invalide, on rejoue.
  #  - une detection mais l ecriture a echoue -> DETECTION NON LOGGUEE : l effacer
  #    serait criminel.
  # FAIL-CLOSED (verificateurs, passe 1) : un artefact absent = on n a rien mesure.
  # Le stderr ne sert JAMAIS de preuve — il est sous le controle du paquet, qui peut
  # le laisser vide tout en exfiltrant. La preuve ne vient que du sink.
  ENT="/opt/sandbox/runs-obs/$tag/run/entrees.jsonl"
  if [ ! -s "$ENT" ]; then
    echo "  BANC INVALIDE ($tag) — aucune entree produite, a rejouer" | tee -a "$OUT/resultats.txt"
    echo "$tag|INVALIDE" >> "$OUT/banc-invalide.txt"
  fi

  # ---- la CLÉ : les canaris retrouvés dans ce qui sort
  RUNDIR="/opt/sandbox/runs-obs/$tag"
  # Ni CLE ni HOTE ici : le shell comptait les 12 écritures du pilote comme des fuites
  # (12 faux positifs par paquet) et lisait $OUT/faux-internet.jsonl, qui n'existe pas.
  # La preuve est calculée par cles_scenario3.py, sur les seuls événements réseau.
  echo "  $tag deps=$NM $R" | tee -a "$OUT/resultats.txt"
  echo "$tag|$nom|$R" >> "$OUT/cles.txt"
  rm -rf "$D" "$T"
done < "$LIST"
echo "[$(date +%H:%M:%S)] FINI — clés dans $OUT/cles.txt"
