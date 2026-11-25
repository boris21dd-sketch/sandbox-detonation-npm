**ARBITRAGE** : forced command = `status` seul depuis SSH ; `preparer|lancer|verifier|montrer` uniquement par argv root local. `detoner-obs.sh`/sudo écartés (règle sans `SETENV` détruirait les variables figées) ; `docker run` direct en root. 5 unités du harnais × 2 supports (`issue`,`seal`) = 10 modules × 25 sondes = 250 probes. Conteneur non `--rm` (CID conservé pour tiers).

---

### A — Repointage

**1. Sauvegarde (hermes, PowerShell administrateur, via CM3588)**

```powershell
$p='C:\Users\bob\.ssh\authorized_keys'
$g='C:\ProgramData\banc\gate.sh'
$bak='C:\ProgramData\banc\sauvegarde\20260815T125847Z'
New-Item -ItemType Directory -Force -Path $bak | Out-Null
Copy-Item -LiteralPath $p -Destination "$bak\authorized_keys" -Force
Copy-Item -LiteralPath $g -Destination "$bak\gate.sh" -Force
icacls $p /save "$bak\authorized_keys.acl" | Out-Null
icacls $g /save "$bak\gate.sh.acl" | Out-Null
Get-FileHash "$bak\authorized_keys","$bak\gate.sh" -Algorithm SHA256 | Format-Table Hash,Path -AutoSize
(Get-Item $g).Length
```
`REUSSITE SI :` 2 hashes affichés, `gate.sh` = 1075, 2 fichiers `.acl` présents.
`ECHEC SI :` copie manquante ou `Length ≠ 1075` → stop, ne pas exécuter 2.

**2. Repointage exact**

```powershell
$gate='wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/gate.sh'
$raw=[System.IO.File]::ReadAllText($p)
if($raw -notmatch 'command="[^"]*root-gate\.sh[^"]*"'){throw 'ECHEC A-2: motif root-gate.sh absent'}
$new=[regex]::Replace($raw,'command="[^"]*root-gate\.sh[^"]*"',('command="'+$gate+'"'),1)
[System.IO.File]::WriteAllText($p,$new,(New-Object System.Text.UTF8Encoding($false)))
Select-String -LiteralPath $p -Pattern ([regex]::Escape($gate)) | ForEach-Object Line
if(([System.IO.File]::ReadAllText($p)) -cnotlike "*$gate*"){throw 'ECHEC A-2: ecriture'}
if(([System.IO.File]::ReadAllText($p)) -match 'q5n2'){throw 'ECHEC A-2: ancienne voie residuelle'}
```
`REUSSITE SI :` une seule ligne affichée contenant exactement `command="wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/gate.sh"`, zéro `q5n2`, pas de BOM.
`ECHEC SI :` `q5n2` encore présent, 2 occurrences, ou BOM → restaurer depuis `$bak`.

**3. Scellement ACL (anti-rollback bob)**

```powershell
$bobSid=(Get-LocalUser -Name bob).SID.Value
icacls $p /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" "*${bobSid}:R" | Out-Null
icacls $p
wsl -d Ubuntu -u bob -- bash -c 'printf "\n# test\n" >> /mnt/c/Users/bob/.ssh/authorized_keys' 2>&1
wsl -d Ubuntu -u bob -- bash -c 'printf "\n# test\n" >> /mnt/c/ProgramData/banc/gate.sh' 2>&1
```
`REUSSITE SI :` `icacls` = `S-1-5-32-544:(F)`, `S-1-5-18:(F)`, bob `(R)` uniquement ; les 2 `wsl -u bob` rendent `Permission denied`.
`ECHEC SI :` un `wsl -u bob` réussit → stop, B invalide.

**4. Non-régression `status` (porte = ancien gate.sh, 1075 o)**

```powershell
$env:SSH_ORIGINAL_COMMAND='status'; $env:WSLENV='SSH_ORIGINAL_COMMAND'
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/gate.sh
Remove-Item Env:SSH_ORIGINAL_COMMAND,Env:WSLENV -ErrorAction SilentlyContinue
ssh -i C:\Users\bob\.ssh\id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=no bob@127.0.0.1 status
```
`REUSSITE SI :` les deux sorties contiennent `status`, codes 0. (Seule valeur adaptable : le nom de la clé `-i`.)
`ECHEC SI :` `Permission denied`, `command not found`, ou silence → restaurer `$bak\authorized_keys` + `$bak\authorized_keys.acl`.

---

### B — Lanceur scellé

**5. Contenu EXACT — `C:\ProgramData\banc\gate.sh`** (remplace les 1075 o)

```bash
#!/usr/bin/bash
# Entree forced-command. root. bob -> status uniquement. Aucun argument libre.
set -Eeuo pipefail
umask 077
[ "$(id -u)" -eq 0 ] || { printf 'ECHEC: gate hors root\n' >&2; exit 90; }
raw="${SSH_ORIGINAL_COMMAND:-status}"
unset SSH_ORIGINAL_COMMAND WSLENV BASH_ENV ENV CDPATH NODE_OPTIONS NODE_COMPILE_CACHE
[ "$raw" = "status" ] || { printf 'ECHEC: verbe SSH refuse\n' >&2; exit 91; }
exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LC_ALL=C TZ=UTC \
  /usr/bin/bash /mnt/c/ProgramData/banc/banc-ctl.sh status
```

**6. Contenu EXACT — `C:\ProgramData\banc\banc-ctl.sh`** (lanceur scellé, root)

```bash
#!/usr/bin/bash
# banc-ctl.sh — root uniquement. Aucun argument libre de bob. Aucun eval.
set -Eeuo pipefail
umask 077
export LC_ALL=C TZ=UTC
[ "$(id -u)" -eq 0 ] || { echo 'ECHEC: root requis' >&2; exit 90; }
[ "$#" -eq 1 ] || { echo 'ECHEC: arite' >&2; exit 92; }
case "$1" in
  status|preparer|lancer|verifier|montrer) V="$1" ;;
  *) echo 'ECHEC: verbe inconnu' >&2; exit 91 ;;
esac
unset SSH_ORIGINAL_COMMAND WSLENV BASH_ENV ENV CDPATH NODE_OPTIONS NODE_COMPILE_CACHE DOCKER_HOST
export PATH=/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root

BANC=/mnt/c/ProgramData/banc
HAR=/opt/sandbox/harnais
TRACE=/mnt/nvme/sbx-trace
ISSUE="$BANC/issue-1.json"
SEAL="$HAR/issue-sha256.seal"
MAN="$HAR/manifest.bin"
ENTRY="$HAR/seal-entry.cjs"
IMG=sbx-detonation:obs
UNITES='detonate.js harness.js run-entry.js lib/sbx/log.js emettre.js'
SUPPORTS='issue seal'
issue_sha(){ grep -oE 'sha256\(probe\)=[0-9a-f]{64}' "$ISSUE" | cut -d= -f2 | sed -n '1p'; }

case "$V" in
status)
  H=$([ -r "$SEAL" ] && cat "$SEAL" || printf 'absent')
  printf 'status ok uid=%s gate=scelle sha256(manifest)=%s\n' "$(id -u)" "$H"
  ;;
preparer)
  [ -r "$ISSUE" ] || { echo 'ECHEC: issue-1.json absent' >&2; exit 70; }
  H=$(issue_sha); [ -n "$H" ] || { echo 'ECHEC: issue sans sha256(probe)' >&2; exit 70; }
  grep -q 'T12:58:47Z' "$ISSUE" || { echo 'ECHEC: horodatage issue' >&2; exit 72; }
  D=$(docker image inspect "$IMG" --format '{{.Id}}') || { echo 'ECHEC: image' >&2; exit 73; }
  for U in $UNITES; do [ -f "$HAR/$U" ] || { echo "ECHEC: unite $U" >&2; exit 74; }; done
  : > "$MAN.tmp"
  for P in $SUPPORTS; do for U in $UNITES; do for S in $(seq -w 1 25); do
    L=$({ printf '%s\t%s\t%s\t%s\t' "$P" "$U" "$S" "$D"; cat "$HAR/$U"; } | sha256sum | cut -d' ' -f1)
    printf '%s\t%s\t%s\t%s\n' "$P" "$U" "$S" "$L" >> "$MAN.tmp"
  done; done; done
  G=$(sha256sum "$MAN.tmp" | cut -d' ' -f1)
  [ "$G" = "$H" ] || { echo "ECHEC: pont texte->octets non franchi attendu=$H obtenu=$G" >&2; rm -f "$MAN.tmp"; exit 71; }
  mv -f "$MAN.tmp" "$MAN"; chown root:root "$MAN"; chmod 0444 "$MAN"
  printf '%s\n' "$H" > "$SEAL"; chown root:root "$SEAL"; chmod 0400 "$SEAL"
  cat > "$ENTRY" <<'SEAL_EOF'
'use strict';
const g = process.getBuiltinModule;
if (typeof g !== 'function') { process.stderr.write('ECHEC: getBuiltinModule absent\n'); process.exit(79); }
const fs = g('node:fs'), cr = g('node:crypto');
if (!fs || !cr) { process.stderr.write('ECHEC: builtins\n'); process.exit(79); }
const b = fs.readFileSync('/harnais/manifest.bin');
const got = cr.createHash('sha256').update(b).digest('hex');
const want = process.env.SBX_EXPECTED_SHA256 || '';
if (!/^[0-9a-f]{64}$/.test(want) || got !== want ||
    process.env.NODE_COMPILE_CACHE !== '' || !process.env.NODE_OPTIONS) {
  process.stderr.write('FAIL-CLOSED sha=' + got + ' attendu=' + want + '\n'); process.exit(78);
}
process.stdout.write(JSON.stringify({seal:'ok',sha256:got,modules:10,sondes:25}) + '\n');
for (const l of b.toString('utf8').trimEnd().split('\n')) {
  const [p,u,s,h] = l.split('\t');
  process.stdout.write(JSON.stringify({sonde:s,module:p+'/'+u,sha256:h}) + '\n');
}
require('/harnais/run-entry.js');
SEAL_EOF
  chown root:root "$ENTRY"; chmod 0444 "$ENTRY"
  printf 'PREPARE sha256(manifest)=%s image=%s lignes=%s\n' "$H" "$D" "$(wc -l < "$MAN")"
  ;;
lancer)
  [ -r "$MAN" ] && [ -r "$SEAL" ] && [ -r "$ENTRY" ] || { echo 'ECHEC: preparer absent' >&2; exit 75; }
  H=$(cat "$SEAL"); G=$(sha256sum "$MAN" | cut -d' ' -f1)
  [ "$G" = "$H" ] || { echo 'ECHEC: manifest altere' >&2; exit 71; }
  [ "$(issue_sha)" = "$H" ] || { echo 'ECHEC: issue ne porte plus H' >&2; exit 71; }
  RUN="obs-250-${H:0:12}"; OUT="$TRACE/$RUN"; mkdir -p "$OUT"; chmod 0700 "$OUT"
  CID=$(docker run -d --read-only --network none --user 0:0 \
    -e NODE_OPTIONS='--no-warnings --no-deprecation --max-old-space-size=256' \
    -e NODE_COMPILE_CACHE= \
    -e SBX_EXPECTED_SHA256="$H" \
    -v "$HAR:/harnais:ro" -v "$TRACE:/trace:ro" \
    --entrypoint node "$IMG" /harnais/seal-entry.cjs) || { echo 'ECHEC: docker run' >&2; exit 76; }
  printf '%s\n' "$CID" > "$OUT/run.cid"
  docker logs -f "$CID" > "$OUT/trace.jsonl" 2> "$OUT/stderr.log"
  RC=$(docker inspect "$CID" --format '{{.State.ExitCode}}')
  [ "$RC" = 0 ] || { echo "ECHEC: conteneur rc=$RC" >&2; exit 77; }
  printf 'LANCE run=%s cid=%s sondes=%s\n' "$RUN" "$CID" "$(grep -c '"sonde":' "$OUT/trace.jsonl")"
  ;;
verifier|montrer)
  H=$(cat "$SEAL"); G=$(sha256sum "$MAN" | cut -d' ' -f1)
  [ "$G" = "$H" ] && [ "$(issue_sha)" = "$H" ] || { echo 'ECHEC: seal/issue' >&2; exit 71; }
  [ "$(wc -l < "$MAN")" -eq 250 ] || { echo 'ECHEC: 250' >&2; exit 71; }
  [ "$(cut -f1,2 "$MAN" | sort -u | wc -l)" -eq 10 ] || { echo 'ECHEC: 10 modules' >&2; exit 71; }
  [ "$(cut -f3 "$MAN" | sort -u | wc -l)" -eq 25 ] || { echo 'ECHEC: 25 sondes' >&2; exit 71; }
  RUN="obs-250-${H:0:12}"; OUT="$TRACE/$RUN"; CID=$(cat "$OUT/run.cid")
  [ "$(docker inspect "$CID" --format '{{.HostConfig.ReadonlyRootfs}}')" = true ] || { echo 'ECHEC: read-only' >&2; exit 71; }
  [ "$(docker inspect "$CID" --format '{{range .Mounts}}{{.RW}} {{end}}')" = 'false false ' ] || { echo 'ECHEC: montures RW' >&2; exit 71; }
  [ "$(docker inspect "$CID" --format '{{.State.ExitCode}}')" = 0 ] || { echo 'ECHEC: rc' >&2; exit 71; }
  [ "$(docker inspect "$CID" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -c '^NODE_COMPILE_CACHE=$')" = 1 ] || { echo 'ECHEC: cache' >&2; exit 71; }
  [ "$(grep -c '"sonde":' "$OUT/trace.jsonl")" -eq 250 ] || { echo 'ECHEC: trace' >&2; exit 71; }
  head -n1 "$OUT/trace.jsonl" | grep -q '"seal":"ok"' || { echo 'ECHEC: seal' >&2; exit 71; }
  ! grep -q 'FAIL-CLOSED' "$OUT/trace.jsonl" "$OUT/stderr.log" || { echo 'ECHEC: fail-closed' >&2; exit 71; }
  if [ "$V" = montrer ]; then
    printf 'issue_created_at=%s\nsha256(manifest)=%s\nimage=%s\nrun=%s\ncid=%s\ntrace=%s/trace.jsonl\nstderr=%s/stderr.log\n' \
      "$(grep -oE '"created_at"[^,]*' "$ISSUE" | head -n1)" "$H" \
      "$(docker image inspect "$IMG" --format '{{.Id}}')" "$RUN" "$CID" "$OUT" "$OUT"
  else printf 'VERIFIE sha=%s run=%s cid=%s\n' "$H" "$RUN" "$CID"; fi
  ;;
esac
```

**7. Dépôt + ACL (PowerShell administrateur)**

```powershell
$gateTxt = @'
<COLLER ICI LE BLOC 5>
'@ -replace "`r`n","`n"
$ctlTxt = @'
<COLLER ICI LE BLOC 6>
'@ -replace "`r`n","`n"
$enc = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText('C:\ProgramData\banc\gate.sh',    $gateTxt + "`n", $enc)
[IO.File]::WriteAllText('C:\ProgramData\banc\banc-ctl.sh',$ctlTxt + "`n", $enc)
wsl -d Ubuntu -u root -- bash -c 'chown root:root /mnt/c/ProgramData/banc/gate.sh /mnt/c/ProgramData/banc/banc-ctl.sh; chmod 0500 /mnt/c/ProgramData/banc/gate.sh /mnt/c/ProgramData/banc/banc-ctl.sh; bash -n /mnt/c/ProgramData/banc/gate.sh && bash -n /mnt/c/ProgramData/banc/banc-ctl.sh && echo SYNTAXE-OK'
foreach($f in @('C:\ProgramData\banc\gate.sh','C:\ProgramData\banc\banc-ctl.sh','C:\ProgramData\banc\issue-1.json')){
  icacls $f /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" | Out-Null }
wsl -d Ubuntu -u bob -- bash -c 'printf x >> /mnt/c/ProgramData/banc/banc-ctl.sh' 2>&1
```
`REUSSITE SI :` `SYNTAXE-OK`, `bash -n` silencieux, `Permission denied` pour bob, `icacls` sans bob.
`ECHEC SI :` `bash: ... CRLF` ou `syntax error` → LF non appliqué, re-écrire.

**8. Support n°1 : export immuable de l'issue #1** (1 seule valeur externe : `$REPO`)

```bash
wsl -d Ubuntu -u root -- bash -lc '
set -e
REPO="OWNER/REPO"
curl -fsS -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${REPO}/issues/1" > /mnt/c/ProgramData/banc/issue-1.json
grep -q "T12:58:47Z" /mnt/c/ProgramData/banc/issue-1.json
grep -oE "sha256\(probe\)=[0-9a-f]{64}" /mnt/c/ProgramData/banc/issue-1.json | sed -n 1p
chown root:root /mnt/c/ProgramData/banc/issue-1.json
chmod 0444 /mnt/c/ProgramData/banc/issue-1.json'
```
`REUSSITE SI :` une ligne `sha256(probe)=` 64 hex, `T12:58:47Z` présent, fichier `0444`.
`ECHEC SI :` aucune ligne → `preparer` sortira `exit 70`, aucun conteneur lancé (fail-closed voulu).

**9. Re-test `status` après scellement**

```powershell
$env:SSH_ORIGINAL_COMMAND='status'; $env:WSLENV='SSH_ORIGINAL_COMMAND'
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/gate.sh
Remove-Item Env:SSH_ORIGINAL_COMMAND,Env:WSLENV -ErrorAction SilentlyContinue
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/banc-ctl.sh lancer 2>&1 | Select-Object -First 1
```
`REUSSITE SI :` `status ok uid=0 gate=scelle sha256(manifest)=absent` ; la 2e commande rend `ECHEC: preparer absent` (code 75) — preuve que `lancer` refuse sans `preparer`.
`ECHEC SI :` `status` muet, ou `lancer` démarre quoi que ce soit.

---

### C — Run unique probant

**10. Ordre des opérations (root local, jamais via SSH bob)**

```bash
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/banc-ctl.sh preparer
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/banc-ctl.sh lancer
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/banc-ctl.sh verifier
wsl -d Ubuntu -u root -- bash /mnt/c/ProgramData/banc/banc-ctl.sh montrer
```
`REUSSITE SI :` `PREPARE sha256(manifest)=<H> ... lignes=250` → `LANCE run=obs-250-<12hex> ... sondes=250` → `VERIFIE` → `montrer` avec `issue_created_at=...T12:58:47Z`. Un seul `docker run`, un seul CID.
`ECHEC SI :` `exit 71 attendu=... obtenu=...` = pont texte→octets toujours non franchi : **aucun conteneur lancé**, ne pas corriger le manifeste, ne pas éditer l'issue, livrer cet écart au vérificateur. `exit 78`/`FAIL-CLOSED` = garde conteneur active. `exit 77` = harnais a tenté d'écrire sous `--read-only`.

**11. Vérification mécanique tierce, sans moi, sans `banc-ctl.sh`**

```bash
#!/usr/bin/bash
set -Eeuo pipefail
B=/mnt/c/ProgramData/banc; H=/opt/sandbox/harnais; T=/mnt/nvme/sbx-trace
ISS=$B/issue-1.json; MAN=$H/manifest.bin
HI=$(grep -oE 'sha256\(probe\)=[0-9a-f]{64}' "$ISS" | cut -d= -f2 | sed -n '1p')
grep -q 'T12:58:47Z' "$ISS"
D=$(docker image inspect sbx-detonation:obs --format '{{.Id}}')
: > /tmp/tiers.manifest
for P in issue seal; do for U in detonate.js harness.js run-entry.js lib/sbx/log.js emettre.js; do for S in $(seq -w 1 25); do
  L=$({ printf '%s\t%s\t%s\t%s\t' "$P" "$U" "$S" "$D"; cat "$H/$U"; } | sha256sum | cut -d' ' -f1)
  printf '%s\t%s\t%s\t%s\n' "$P" "$U" "$S" "$L" >> /tmp/tiers.manifest
done; done; done
cmp /tmp/tiers.manifest "$MAN"
G=$(sha256sum /tmp/tiers.manifest | cut -d' ' -f1); [ "$G" = "$HI" ]
[ "$(wc -l < "$MAN")" -eq 250 ]
[ "$(cut -f1,2 "$MAN" | sort -u | wc -l)" -eq 10 ]
[ "$(cut -f3 "$MAN" | sort -u | wc -l)" -eq 25 ]
RUN="obs-250-${G:0:12}"; OUT="$T/$RUN"; CID=$(cat "$OUT/run.cid")
[ "$(docker inspect "$CID" --format '{{.HostConfig.ReadonlyRootfs}}')" = true ]
[ "$(docker inspect "$CID" --format '{{range .Mounts}}{{.RW}} {{end}}')" = 'false false ' ]
[ "$(docker inspect "$CID" --format '{{.State.ExitCode}}')" = 0 ]
[ "$(docker inspect "$CID" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -c '^NODE_COMPILE_CACHE=$')" = 1 ]
[ "$(docker inspect "$CID" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -c '^SBX_EXPECTED_SHA256='"$G"'$')" = 1 ]
[ "$(grep -c '"sonde":' "$OUT/trace.jsonl")" -eq 250 ]
head -n1 "$OUT/trace.jsonl" | grep -q '"seal":"ok"'
! grep -q 'FAIL-CLOSED' "$OUT/trace.jsonl" "$OUT/stderr.log"
printf 'VERIFIE-TIERS sha=%s run=%s cid=%s\n' "$G" "$RUN" "$CID"
```
`REUSSITE SI :` `cmp` silencieux, `VERIFIE-TIERS sha=<H>` identique au `PREPARE` et au `sha256(probe)=` de l'API ; 250/10/25 ; `true` ; `false false` ; `NODE_COMPILE_CACHE=` vide.
`ECHEC SI :` `cmp` diffère, `HI ≠ G`, `ReadonlyRootfs=false`, un `RW=true`, ou `FAIL-CLOSED` → run non recevable, aucun rattrapage.

---

### D — Non prouvé même si tout passe

1. Les 29 runs, r1 et les octets de l'ancien `/home/bob/q5n2/root-gate.sh` restent non liés à l'issue : leur abandon n'efface pas l'absence de preuve qu'ils n'ont pas été pré-positionnés par bob avant 12:58:47Z.
2. L'issue #1 n'est pas signée : on prouve seulement que `issue-1.json` et l'API courante portent le même `H`, pas que ce `H` n'a pas été remplacé côté API/administrateur après `created_at`.
3. On prouve l'auto-cohérence des 250 probes, pas leur sémantique : root WSL, `Administrateurs`, `SYSTEM` et tout titulaire du socket Docker restent dans la racine de confiance non auditée.