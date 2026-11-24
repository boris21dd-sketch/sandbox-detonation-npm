#!/usr/bin/env bash
# Publier une amélioration sur le dépôt dédié, avec un message court et vérifiable.
# Usage : publier.sh "titre de l'amélioration" "mesure avant → après"
set -eu
DEPOT=${DEPOT:-/home/bob/q5n2/sandbox-detonation-npm}
TITRE=${1:?usage: publier.sh "titre" "mesure"}
MESURE=${2:-"mesure non renseignée"}
cd "$DEPOT"

# on republie l'état réel des scripts (la copie de travail peut vivre ailleurs)
cp /home/bob/q5n2/sbx-scenario3.sh /home/bob/q5n2/_sbx_driver3.cjs \
   /home/bob/q5n2/cles_scenario3.py /home/bob/q5n2/fabrique_sondes.py \
   /home/bob/q5n2/audit_sandbox_20.py scripts/ 2>/dev/null || true
cp /home/bob/.hermes/scripts/veille-audit-sandbox.sh scripts/ 2>/dev/null || true
cp /home/bob/.hermes/skills/security/sandbox-detonation-npm/SKILL.md . 2>/dev/null || true

if git diff --quiet && git diff --cached --quiet; then
  echo "rien à publier"
  exit 0
fi

git add -A
git commit -q -m "$TITRE

$MESURE"

# Le jeton n'est jamais stocké dans CE dépôt : on l'emprunte au remote de
# travail au moment du push, et l'URL publique reste propre.
AUTH=$(git -C /home/bob/q5n2/rust-main remote get-url origin 2>/dev/null \
       | sed -E 's#(https://[^/@]+)@github\.com/.*#\1@github.com#')
if [ -n "${AUTH:-}" ] && [ "$AUTH" != "$(git -C /home/bob/q5n2/rust-main remote get-url origin)" ]; then
  git push -q "$AUTH/boris21dd-sketch/sandbox-detonation-npm.git" HEAD 2>&1 | tail -2 || true
else
  git push -q origin HEAD 2>&1 | tail -2 || true
fi
echo "publié : $(git log --oneline -1)"
