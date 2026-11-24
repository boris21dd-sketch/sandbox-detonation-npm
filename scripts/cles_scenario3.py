#!/usr/bin/env python3
"""Agrège les clés du scénario 3 : pour chaque paquet, ce qui SORT réellement.

Correction importante : un canari trouvé dans `events.jsonl` ne prouve rien — le
pilote du scénario écrit lui-même les douze fichiers d'état de victime, donc
chaque `fs.writeFileSync` contient le canari. La preuve d'exfiltration est un
canari qui apparaît dans un **événement réseau** (requête, URL, en-tête, corps)
ou dans une **commande exécutée**.

Usage : cles_scenario3.py <prefixe> [--json]
"""
import json
import os
import re
import sys
from urllib.parse import urlsplit
from collections import Counter

RUNS = "/opt/sandbox/runs-obs"
CANAUX_RESEAU = {"https.request", "http.request", "net.write", "net.connect", "tls.connect", "dns.lookup", "dns.resolve", "ws.send", "fetch"}
CANAUX_EXEC = {"child_process.execSync", "child_process.spawn", "exec", "spawn", "processus"}

# Les douze fichiers que le pilote sème lui-même : les compter comme écriture
# « hors paquet » noierait la vraie observation (mesuré : 5 lignes identiques
# sur les douze paquets, et `/work/maison/.claude/settings.json` coupé par le [:5]).
SEMES = {
    "/work/maison/.npmrc",
    "/work/maison/.ssh/id_ed25519",
    "/work/maison/.aws/credentials",
    "/work/maison/.config/gh/hosts.yml",
    "/work/maison/.docker/config.json",
    "/work/maison/.kube/config",
    "/work/maison/.gitconfig",
    "/work/maison/.env",
    "/work/maison/.config/gcloud/application_default_credentials.json",
    "/work/maison/wa-session/creds.json",
    "/work/maison/Cookies",
    "/work/maison/.bash_history",
}


def charge(tag: str) -> dict:
    d = os.path.join(RUNS, tag)
    out = {"tag": tag, "reseaux": [], "hotes": set(), "execs": [], "canaris_reseau": set(), "canaris_exec": set(), "ecritures_hors": []}
    fi = os.path.join(d, "faux-internet.jsonl")
    if os.path.exists(fi):
        for l in open(fi, errors="replace"):
            try:
                j = json.loads(l)
            except Exception:
                continue
            blob = json.dumps(j, ensure_ascii=False)
            out["reseaux"].append(blob[:400])
            # Un canari envoyé au registry est l'usage NORMAL du jeton npm (les scripts
            # de cycle de vie lancent npm, qui lit ~/.npmrc). Seul un envoi vers un
            # AUTRE hôte est une fuite — mesuré sur fn001/fn006.
            vers_registry = est_registry(j.get("sni") or j.get("host") or "")
            for cle in ("qname", "sni", "host", "url", "path"):
                v = j.get(cle)
                h = hote_de(v)
                if h and not est_registry(h):
                    out["hotes"].add(h[:120])
            # Vers le registry, seul le jeton npm est un usage normal : une session
            # WhatsApp ou une cle SSH envoyee au registry reste une fuite (tour 2).
            for c in canaris(blob):
                if vers_registry and c.startswith("CANARI_NPM"):
                    continue
                out["canaris_reseau"].add(c)
    ev = os.path.join(d, "run", "events.jsonl")
    if os.path.exists(ev):
        for l in open(ev, errors="replace"):
            try:
                j = json.loads(l)
            except Exception:
                continue
            canal = j.get("canal", "")
            blob = json.dumps(j, ensure_ascii=False)
            # Le harnais porte l'URL et le corps dans `valeur` : sans ça, une sonde
            # qui atteint son hôte restait « — » (mesuré sur pe012).
            v0 = str(j.get("valeur") or "")
            for u in re.findall(r"https?://[^\s\"'`]+", v0):
                h = hote_de(u)
                if h and not est_registry(h):
                    out["hotes"].add(h[:120])
            if canal in ("http.corps", "https.corps", "net.write", "corps"):
                for c in canaris(v0):
                    out["canaris_reseau"].add(c)
            if canal in CANAUX_EXEC:
                v = str(j.get("valeur") or "")
                # Seule une URL réellement présente fait une preuve : compter tout
                # valeur contenant un point fabricant des clés (relevé en audit).
                urls = re.findall(r"https?://[^\s\"'`]+", v)
                if any(not est_registry(urlsplit(u).hostname or "") for u in urls):
                    out["execs"].append(f"{canal}: {v[:160]}")
                for c in canaris(blob):
                    out["canaris_exec"].add(c)
            # Les événements portent le chemin dans `valeur`, pas `chemin` :
            # l'ancien filtre ne voyait donc jamais une écriture hors paquet.
            chemin = j.get("valeur") or j.get("chemin") or j.get("path") or ""
            if canal.startswith("fs.write") and isinstance(chemin, str) and chemin.startswith("/work/maison") and chemin not in SEMES:
                out["ecritures_hors"].append(chemin[:120])
    return out


def hote_de(v) -> str:
    """Hôte réel d'une valeur : une URL se parse, un nom d'hôte se garde.
    L'ancien test « contient un point » acceptait `foo.` et refusait un chemin."""
    if not isinstance(v, str):
        return ""
    v = v.strip()
    if not v:
        return ""
    if "://" in v:
        try:
            return (urlsplit(v).hostname or "").lower()
        except Exception:
            return ""
    return v.lower() if re.fullmatch(r"[a-z0-9._-]+", v) and "." in v else ""


def est_registry(host) -> str:
    """Égalité stricte : `registry.npmjs.org.attaquant.test` n'est PAS le registry.
    Défaut relevé par deux relecteurs (sous-chaîne contournable)."""
    h = hote_de(host)
    return bool(h) and (h == "registry.npmjs.org" or h.endswith(".registry.npmjs.org"))


SUF = "7f3ac9"
CANARIS_CONNUS = [f"CANARI_{n}_{SUF}" for n in
                  ("NPM", "SSH", "AWS", "GH", "DOCKER", "KUBE", "GIT", "HIST",
                   "WA", "GCLOUD", "COOKIE")]


def variantes(c: str):
    """Formes sous lesquelles un canari peut sortir encode.

    Un attaquant qui serialise l'environnement complet en JSON puis en base64
    n'envoie JAMAIS la chaine nue : la recherche en sous-chaine directe le
    manque. On cherche donc aussi base64 (std et urlsafe, avec et sans padding),
    hex et percent. (Idee reprise de Malwhunter wiretap/canary.py:27-51.)
    """
    import base64, urllib.parse
    b = c.encode()
    formes = {c}
    for enc in (base64.b64encode(b).decode(),
                base64.b64encode(b).decode().rstrip("="),
                base64.urlsafe_b64encode(b).decode(),
                base64.urlsafe_b64encode(b).decode().rstrip("="),
                b.hex(), urllib.parse.quote(c, safe="")):
        formes.add(enc)
    return formes


def canaris(blob: str):
    import re
    # `CANARI_FACTICE_…` est le jeton que le harnais pose lui-même dans ~/.npmrc :
    # le compter comme fuite rendrait chaque paquet « coupable ».
    trouves = {c for c in re.findall(r"CANARI_[A-Z]+_[0-9a-f]{6}", blob) if "FACTICE" not in c}
    # Passe complementaire : si le blob ne contient aucun canari en clair, on
    # tente les formes encodees des canaris connus (le semeur les a poses).
    if not trouves:
        for connu in CANARIS_CONNUS:
            for f in variantes(connu):
                if f and f in blob:
                    trouves.add(connu)
                    break
    return trouves


def main():
    prefixe = sys.argv[1] if len(sys.argv) > 1 else "fn"
    index = os.path.join("/home/bob/.hermes/cache/scratch", f"sbx-{prefixe}", "index.txt")
    noms = {}
    if os.path.exists(index):
        for l in open(index):
            p = l.strip().split("|")
            if len(p) >= 2:
                noms[p[0]] = p[1]
    import re
    motif = re.compile(rf"^{prefixe}\d{{3}}$")  # nos tags ont trois chiffres : fn001…
    tags = sorted(t for t in os.listdir(RUNS) if motif.match(t))
    lignes = []
    for t in tags:
        c = charge(t)
        lignes.append({
            "tag": t,
            "nom": noms.get(t, ""),
            "hotes": sorted(c["hotes"]),
            "execs": len(c["execs"]),
            "canaris_reseau": sorted(c["canaris_reseau"]),
            "canaris_exec": sorted(c["canaris_exec"]),
            "ecritures_hors": sorted(set(c["ecritures_hors"]))[:8],
        })
    for r in lignes:
        config_client = [c for c in r["ecritures_hors"] if any(k in c for k in (".claude", ".codex", ".cursor", ".gemini", ".mcp"))]
        cle = bool(r["canaris_reseau"] or r["canaris_exec"] or r["hotes"] or r["execs"] or config_client)
        marque = "CLÉ" if cle else "—"
        print(f"{r['tag']:8s} {r['nom'][:30]:30s} {marque:4s} hotes={r['hotes']} exec={r['execs']} "
              f"canaris_reseau={r['canaris_reseau']} canaris_exec={r['canaris_exec']} ecrit_hors={r['ecritures_hors']}")
    if "--json" in sys.argv:
        json.dump(lignes, open(f"/home/bob/q5n2/cles-{prefixe}.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
