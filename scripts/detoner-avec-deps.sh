#!/usr/bin/env bash
# Detonation AVEC les vraies dependances.
#   1. extraire le paquet sur l'hote
#   2. npm install --ignore-scripts sur l'hote (le reseau marche la)
#   3. repaqueter, detoner dans le conteneur isole
# Le conteneur ne voit jamais le reseau : il monte un paquet deja complet.
set -u
LIST=${1:?usage: detoner-avec-deps.sh <liste> <prefixe>}
PREFIXE=${2:-d}
OUT=/home/bob/.hermes/cache/scratch/deps-${PREFIXE}
WORK=/home/bob/.hermes/cache/scratch/npmwork
mkdir -p "$OUT" "$WORK"
cd /opt/sandbox || exit 1

i=0
while IFS=$'\t' read -r nom tgz; do
  [ -z "${tgz:-}" ] && continue
  i=$((i+1)); tag=$(printf "%s%02d" "$PREFIXE" "$i")
  echo "$tag|$nom|$tgz" >> "$OUT/index.txt"
  D="$WORK/$tag"
  rm -rf "$D"; mkdir -p "$D"
  if ! tar xzf "$tgz" -C "$D" 2>/dev/null; then
    echo "  $tag EXTRACTION_ECHEC  $nom" | tee -a "$OUT/resultats.txt"; continue
  fi
  if [ ! -f "$D/package/package.json" ]; then
    echo "  $tag PAS_DE_PACKAGE_JSON  $nom" | tee -a "$OUT/resultats.txt"; continue
  fi
  # installer les vraies dependances (scripts d'installation NON executes)
  ( cd "$D/package" && timeout 240 npm install --ignore-scripts --no-audit --no-fund \
      --legacy-peer-deps > "$OUT/$tag.npm.log" 2>&1 )
  NM=$(ls "$D/package/node_modules" 2>/dev/null | wc -l)
  T="$WORK/$tag.tgz"
  tar czf "$T" -C "$D" package 2>/dev/null
  R=$(SBX_OBSERVER_MS=15000 sudo -n bash detoner-obs.sh "$T" "$tag" 30 2>&1 | tail -1)
  echo "  $tag deps=$NM  $R" | tee -a "$OUT/resultats.txt"
  rm -rf "$D" "$T"
done < "$LIST"
echo "[$(date +%H:%M:%S)] FINI — $(wc -l < "$OUT/resultats.txt" 2>/dev/null || echo 0) paquets"
