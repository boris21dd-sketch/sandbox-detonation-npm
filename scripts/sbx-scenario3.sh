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
LIST=${1:?usage: sbx-scenario3.sh <liste> <prefixe> [timeout]}
PREFIXE=${2:-s3}
TMO=${3:-120}
OUT=/home/bob/.hermes/cache/scratch/sbx-${PREFIXE}
WORK=/home/bob/.hermes/cache/scratch/npmwork
mkdir -p "$OUT" "$WORK"
cd /opt/sandbox || exit 1
: > "$OUT/cles.txt"

# Le pilote vit dans _sbx_driver3.cjs (CommonJS force, ESM gere par import()) :
cp /home/bob/q5n2/_sbx_driver3.cjs /tmp/_sbx_driver3.cjs

i=0
while IFS=$'\t' read -r nom tgz; do
  [ -z "${tgz:-}" ] && continue
  i=$((i+1)); tag=$(printf "%s%03d" "$PREFIXE" "$i")
  D="$WORK/$tag"; rm -rf "$D"; mkdir -p "$D"
  tar xzf "$tgz" -C "$D" 2>/dev/null || { echo "$tag|$nom|EXTRACTION_ECHEC" >> "$OUT/resultats.txt"; continue; }
  [ -f "$D/package/package.json" ] || { echo "$tag|$nom|PAS_DE_PKG" >> "$OUT/resultats.txt"; continue; }
  ( cd "$D/package" && timeout 300 npm install --ignore-scripts --no-audit --no-fund --legacy-peer-deps > "$OUT/$tag.npm.log" 2>&1 )
  NM=$(ls "$D/package/node_modules" 2>/dev/null | wc -l)
  # scripts de cycle de vie des dependances : on note la commande, le pilote la
  # rejouera DANS le conteneur (l'installation, elle, est faite sans scripts).
  python3 - "$D/package" <<'PY'
import json,os,sys
p=sys.argv[1]; nm=os.path.join(p,'node_modules'); out=[]
def paquets(nm):
    # Les paquets scopes vivent dans node_modules/@scope/nom : la boucle plate
    # les ignorait tous (audit, tour 2).
    for n in sorted(os.listdir(nm)):
        if n.startswith('.'): continue
        if n.startswith('@'):
            for m in sorted(os.listdir(os.path.join(nm,n))):
                yield n + '/' + m
        else:
            yield n

if os.path.isdir(nm):
    for n in paquets(nm):
        f=os.path.join(nm,n,'package.json')
        if not os.path.exists(f): continue
        try: d=json.load(open(f))
        except Exception: continue
        sc=d.get('scripts') or {}
        for k in ('preinstall','install','postinstall'):
            if sc.get(k):
                out.append({'nom':n,'etape':k,'script':sc[k]})
                break
        if len(out)>=40: break
json.dump(out,open(os.path.join(p,'_sbx_deps_scripts.json'),'w'),ensure_ascii=False)
PY
  python3 - "$D/package" <<'PY'
import json,sys,os
p=sys.argv[1]; f=os.path.join(p,'package.json')
d=json.load(open(f)); d['_sbx_main']=d.get('main') or (None if d.get('exports') else 'index.js'); d['main']='_sbx_scenario3.cjs'
json.dump(d,open(f,'w'),ensure_ascii=False,indent=2)
open(os.path.join(p,'_sbx_scenario3.cjs'),'w').write(open('/home/bob/q5n2/_sbx_driver3.cjs').read())
PY
  T="$WORK/$tag.tgz"; tar czf "$T" -C "$D" package 2>/dev/null
  R=$(SBX_OBSERVER_MS=15000 SBX_PAR_ENTREE=$TMO sudo -n bash detoner-obs.sh "$T" "$tag" "$TMO" 2>&1 | tail -1)
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
