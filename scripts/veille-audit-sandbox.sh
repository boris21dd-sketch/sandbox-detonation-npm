#!/usr/bin/env bash
# Veille de l'audit sandbox : relance les tours s'ils sont bloqués ou arrêtés.
# Silencieuse quand tout va bien (stdout vide = rien n'est envoyé).
set -u
JOURNAL=/home/bob/q5n2/AUDITS-SANDBOX-JOURNAL.jsonl
UNIT=audit-sandbox20
SCRIPT=/home/bob/q5n2/audit_sandbox_20.py
TOTAL=20

etat=$(systemctl is-active "$UNIT" 2>/dev/null)
tours=$(python3 - "$JOURNAL" <<'PY'
import json,os,sys
p=sys.argv[1]
if not os.path.exists(p):
    print(0); raise SystemExit
m=0
for l in open(p, errors="replace"):
    try: m=max(m, json.loads(l).get("tour",0))
    except Exception: pass
print(m)
PY
)

# 1. audit terminé : plus rien à faire, on se tait
if [ "$tours" -ge "$TOTAL" ]; then exit 0; fi

relance() {
  # un banc en cours empêcherait la relance (conteneur unique) : on attend le tour suivant
  if pgrep -f 'detoner-obs' >/dev/null 2>&1; then
    echo "audit-sandbox : $1 ; banc encore en cours, relance reportée"
    exit 0
  fi
  # unités de banc orphelines d'un run précédent
  for u in $(systemctl list-units --all --plain --no-legend 'sbx-aud*' 2>/dev/null | awk '{print $1}' | sed 's/\.service//'); do
    sudo -n systemctl stop "$u" >/dev/null 2>&1
  done
  if sudo -n systemd-run --uid=bob --unit="$UNIT" --collect python3 "$SCRIPT" --tours "$TOTAL" >/dev/null 2>&1; then
    echo "audit-sandbox : $1 (tour $tours/$TOTAL) → relancé $(date +%H:%M)"
  else
    echo "audit-sandbox : $1 → ÉCHEC de relance (systemd-run a refusé)"
  fi
  exit 0
}

# 2. unité arrêtée alors que l'audit n'est pas fini
if [ "$etat" != "active" ]; then
  relance "unité inactive"
fi

# 3. unité active mais figée : journal inchangé depuis plus de 25 min
age=$(( $(date +%s) - $(stat -c %Y "$JOURNAL" 2>/dev/null || echo 0) ))
if [ "$age" -gt 1500 ]; then
  sudo -n systemctl stop "$UNIT" >/dev/null 2>&1
  relance "figé depuis $((age/60)) min"
fi

exit 0
