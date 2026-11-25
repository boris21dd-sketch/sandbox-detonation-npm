#!/usr/bin/env python3
"""Agrège les clés du scénario 3 : pour chaque paquet, ce qui SORT réellement.

Correction importante : un canari trouvé dans `events.jsonl` ne prouve rien — le
pilote du scénario écrit lui-même les douze fichiers d'état de victime, donc
chaque `fs.writeFileSync` contient le canari. La preuve d'exfiltration est un
canari qui apparaît dans un **événement réseau** (requête, URL, en-tête, corps)
ou dans une **commande exécutée**.

Contrat de verdict (attribution d'abord) : le dénominateur est le REGISTRE écrit
par l'hôte (`$SCRATCH/sbx-<prefixe>/registre.tsv`), jamais un listdir. Un dossier
runs-obs n'est une CLÉ que s'il est PROUVÉ appartenir à ce run (nonce).

Usage : cles_scenario3.py <prefixe> [--json]
Code de sortie : 0 banc recevable, 1 non recevable, 2 refus (pas de registre).
"""
import json
import os
import re
import sys
from urllib.parse import urlsplit
from collections import Counter
import base64
import urllib.parse

# Chemins surchargeables (tests) ; les défauts sont ceux du banc. Lus à l'appel.
def chemins():
    return {
        "runs": os.environ.get("SBX_RUNS", "/opt/sandbox/runs-obs"),
        "scratch": os.environ.get("SBX_SCRATCH", "/home/bob/.hermes/cache/scratch"),
        "attendus": os.environ.get("SBX_ATTENDUS", "/home/bob/q5n2/sondes/attendus.json"),
        "json_dir": os.environ.get("SBX_JSON_DIR", "/home/bob/q5n2"),
        "code_attendu": os.environ.get("SBX_CODE_ATTENDU", "/home/bob/q5n2/code-attendu.json"),
    }


SUF_DEFAUT = "7f3ac9"
HOTE_LEURRE = "leurre.exfil-probe.test"
SONDE_LEURRE = "p21-leurre-orphelin"
SONDE_TEMOIN = "p12-propre"
# Classes de sondes (attendus.json). Ancien format : seulement "CLÉ" ou "—".
CLASSE_LEURRE = "CONTRÔLE-LEURRE"
CLASSE_INTENTION = "INTENTION"
CLASSES = ("CLÉ", "—", CLASSE_INTENTION, CLASSE_LEURRE)


def duree_max_ms() -> int:
    """Durée au-delà de laquelle un run est tenu pour interrompu (SBX_DUREE_MAX_MS)."""
    try:
        return int(os.environ.get("SBX_DUREE_MAX_MS", "130000"))
    except ValueError:
        return 130000
CANAUX_RESEAU = {"https.request", "http.request", "net.write", "net.connect", "tls.connect", "dns.lookup", "dns.resolve", "ws.send", "fetch",
                 "websocket", "websocket.send", "http2.connect", "http.corps", "https.corps", "corps"}
# Canaux ou un canari prouve une sortie (valeur + detail serialise). JAMAIS `fs.*` :
# detail.contenu y contient les canaris LUS par le paquet, pas envoyes.
CANAUX_CANARI = {"http.corps", "https.corps", "corps", "fetch", "websocket", "websocket.send",
                 "net.write", "tls.connect", "http2.connect"}


def est_canal_canari(canal: str) -> bool:
    return canal in CANAUX_CANARI or canal.startswith("dns.")


def est_canal_reseau(canal: str) -> bool:
    return canal in CANAUX_RESEAU or canal.startswith("dns.")
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


def lire_jsonl(chemin: str) -> list:
    """Événements d'un .jsonl (dictionnaires seulement). Absent = liste vide."""
    out = []
    if not os.path.isfile(chemin):
        return out
    with open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                j = json.loads(l)
            except Exception:
                continue
            if isinstance(j, dict):
                out.append(j)
    return out


def taille(chemin: str) -> int:
    try:
        return os.path.getsize(chemin)
    except OSError:
        return 0


def analyse_faux_internet(evs: list, suf: str = SUF_DEFAUT) -> dict:
    """Ce que le journal du faux internet prouve : hôtes hors registry, canaris."""
    out = {"reseaux": [], "hotes": set(), "canaris_reseau": set()}
    for j in evs:
        blob = json.dumps(j, ensure_ascii=False)
        out["reseaux"].append(blob[:400])
        # Un canari envoyé au registry est l'usage NORMAL du jeton npm (les scripts
        # de cycle de vie lancent npm, qui lit ~/.npmrc). Seul un envoi vers un
        # AUTRE hôte est une fuite — mesuré sur fn001/fn006.
        vers_registry = est_registry(j.get("sni") or j.get("host") or "")
        for cle in ("qname", "sni", "host", "url", "path"):
            h = hote_de(j.get(cle))
            if h and not est_registry(h):
                out["hotes"].add(h[:120])
        # Vers le registry, seul le jeton npm est un usage normal : une session
        # WhatsApp ou une cle SSH envoyee au registry reste une fuite (tour 2).
        for c in canaris(blob, suf):
            if vers_registry and c.startswith("CANARI_NPM") and c.endswith("_" + suf):
                continue
            out["canaris_reseau"].add(c)
    return out


def analyse_events(evs: list, suf: str = SUF_DEFAUT) -> dict:
    """Preuves tirées de events.jsonl (logique existante conservée)."""
    out = {"hotes": set(), "execs": [], "canaris_reseau": set(), "canaris_exec": set(), "ecritures_hors": []}
    for j in evs:
        canal = j.get("canal", "")
        if not isinstance(canal, str):
            canal = ""
        blob = json.dumps(j, ensure_ascii=False)
        # Le harnais porte l'URL et le corps dans `valeur` : sans ça, une sonde
        # qui atteint son hôte restait « — » (mesuré sur pe012).
        v0 = str(j.get("valeur") or "")
        # Une URL ne prouve un contact reseau que sur un canal reseau ou exec :
        # lire un README qui cite une URL (fs.*, require) n'est pas un contact.
        if est_canal_reseau(canal) or canal in CANAUX_EXEC:
            for u in re.findall(r"https?://[^\s\"'`]+", v0):
                h = hote_de(u)
                if h and not est_registry(h):
                    out["hotes"].add(h[:120])
        if est_canal_canari(canal):
            detail = j.get("detail")
            texte = v0 + " " + (json.dumps(detail, ensure_ascii=False) if detail is not None else "")
            for c in canaris(texte, suf):
                out["canaris_reseau"].add(c)
        if canal in CANAUX_EXEC:
            v = str(j.get("valeur") or "")
            # Seule une URL réellement présente fait une preuve : compter tout
            # valeur contenant un point fabricant des clés (relevé en audit).
            urls = re.findall(r"https?://[^\s\"'`]+", v)
            if any(not est_registry(urlsplit(u).hostname or "") for u in urls):
                out["execs"].append(f"{canal}: {v[:160]}")
            for c in canaris(blob, suf):
                out["canaris_exec"].add(c)
        # Les événements portent le chemin dans `valeur`, pas `chemin` :
        # l'ancien filtre ne voyait donc jamais une écriture hors paquet.
        chemin = j.get("valeur") or j.get("chemin") or j.get("path") or ""
        if canal.startswith("fs.write") and isinstance(chemin, str) and chemin:
            # Normalise AVANT les comparaisons : `/work//maison/.claude/x` est le meme fichier.
            chemin = os.path.normpath(chemin)
            if (chemin == "/work/maison" or chemin.startswith("/work/maison/")) and chemin not in SEMES:
                out["ecritures_hors"].append(chemin[:120])
    return out


def verifie_nonce_etat(run: str, nonce: str):
    """Le dossier vient-il de CE run ? `<run>/_sbx_etat.jsonl` doit contenir une
    ligne `demarrage` au nonce du registre, et AUCUNE ligne à un autre nonce.
    Retourne (statut, raison) : statut = ok | absent | etranger."""
    lignes = lire_jsonl(os.path.join(run, "_sbx_etat.jsonl"))
    if any(l.get("nonce") != nonce for l in lignes):
        return "etranger", "nonce étranger dans _sbx_etat.jsonl"
    if not any(l.get("etape") == "demarrage" and l.get("nonce") == nonce for l in lignes):
        return "absent", "aucune preuve que ce dossier vient de ce run"
    return "ok", ""


def a_trace_fin(run: str, nonce: str) -> bool:
    return any(l.get("etape") == "fin" and l.get("nonce") == nonce
               for l in lire_jsonl(os.path.join(run, "_sbx_etat.jsonl")))


def verifie_nonce_evenements(evs: list, nonce: str):
    """Nonce par événement. Retourne (statut, raison) : statut = present | absent |
    invalide. `absent` = aucun événement ne porte de nonce (harnais pas patché)."""
    def nonce_de(j):
        for k in ("nonce", "run_nonce"):
            if k in j:
                return True, j[k]
        return False, None
    infos = [nonce_de(j) for j in evs]
    if not any(p for p, _ in infos):
        return "absent", ""
    if any(not p for p, _ in infos):
        return "invalide", "événement sans nonce parmi des événements à nonce"
    if any(v != nonce for _, v in infos):
        return "invalide", "nonce étranger dans un événement"
    return "present", ""


def lit_registre(chemin: str) -> list:
    """Lignes du registre. Une ligne malformée ou en double reste dans le
    dénominateur mais INVALIDE (elle ne disparaît jamais)."""
    entrees, vus = [], set()
    with open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.rstrip("\n")
            if not l.strip():
                continue
            c = l.split("\t")
            e = {"tag": c[0].strip(), "nom": "", "nonce": "", "debut_ms": "", "garde": "REGISTRE_MALFORME",
                 "redemarrage": "", "suffixe": SUF_DEFAUT, "npm_rc": "-"}
            # 8 colonnes (suffixe, npm_rc) ; l'ancien format a 6 colonnes reste lisible
            # (suffixe=7f3ac9, npm_rc=-).
            if len(c) >= 6:
                e.update(nom=c[1], nonce=c[2], debut_ms=c[3], garde=c[4], redemarrage=c[5])
            if len(c) >= 8:
                e.update(suffixe=c[6].strip(), npm_rc=c[7].strip())
                if not re.fullmatch(r"[0-9a-f]{6}", e["suffixe"]):
                    e["garde"] = "REGISTRE_MALFORME"
            elif len(c) == 7:
                e["garde"] = "REGISTRE_MALFORME"
            if e["tag"] in vus:
                e["garde"] = "REGISTRE_DOUBLON"
            vus.add(e["tag"])
            entrees.append(e)
    return entrees


def lit_identite(run: str):
    """(code_sha256, code) lus dans <run>/summary.json ; (None, None) si absent/illisible."""
    try:
        with open(os.path.join(run, "summary.json"), encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return None, None
    if not isinstance(j, dict):
        return None, None
    sha = j.get("code_sha256")
    code = j.get("code")
    return (sha if isinstance(sha, str) and sha else None), (code if isinstance(code, dict) else None)


def fichiers_differents(exec_code, attendu_code) -> list:
    if not isinstance(exec_code, dict) or not isinstance(attendu_code, dict):
        return []
    return sorted(k for k in set(exec_code) | set(attendu_code) if exec_code.get(k) != attendu_code.get(k))


def classe(e: dict, runs: str, classe_att=None, code_attendu=None) -> dict:
    """Verdict d'UNE sonde du registre, dans l'ordre de décision du contrat.
    classe_att : classe de la sonde dans attendus.json (None = inconnue).
    code_attendu : contenu de code-attendu.json (None = manifeste absent)."""
    tag, nom, nonce = e["tag"], e["nom"], e["nonce"]
    leurre = classe_att == CLASSE_LEURRE
    suf = e.get("suffixe") or SUF_DEFAUT
    npm_rc = str(e.get("npm_rc", "-"))
    d = os.path.join(runs, tag)
    run = os.path.join(d, "run")
    r = {"tag": tag, "nom": nom, "etat": "", "raisons": [], "nonce_evenement": "",
         "redemarrage": e["redemarrage"], "garde": e["garde"],
         "hotes": set(), "execs": [], "canaris_reseau": set(), "canaris_exec": set(), "ecritures_hors": [],
         "config_client": [], "code_sha256": None, "classe": classe_att}

    # 1. garde du registre
    if e["garde"] != "OK":
        r["etat"] = "BANC INVALIDE"
        r["raisons"].append(f"garde={e['garde']}")
        return r

    # Un nonce vide au registre prouverait tout (le pilote écrit '' sans fichier de nonce).
    if len(nonce) < 8:
        r["etat"] = "BANC INVALIDE"
        r["raisons"].append("nonce absent ou trop court dans le registre")
        return r

    r["code_sha256"], code_exec = lit_identite(run)
    fi_evs = lire_jsonl(os.path.join(d, "faux-internet.jsonl"))
    ev_evs = lire_jsonl(os.path.join(run, "events.jsonl"))
    fi = analyse_faux_internet(fi_evs, suf)
    ev = analyse_events(ev_evs, suf)
    statut_etat, raison_etat = verifie_nonce_etat(run, nonce)

    # 1 bis. l'hôte leurre (AVANT la branche DETECTION NON LOGGUEE : sinon un orphelin
    # fabriquerait une DNL hors de p21 — trou relevé par Sonnet, fermé ici)
    # l'hôte leurre hors de sa sonde = orphelin d'une sonde précédente
    if nom != SONDE_LEURRE and not leurre:
        brut = ""
        for fichier in (os.path.join(d, "faux-internet.jsonl"), os.path.join(run, "events.jsonl")):
            try:
                with open(fichier, encoding="utf-8", errors="replace") as f:
                    brut += f.read().lower()
            except OSError:
                pass
        if HOTE_LEURRE in brut:
            r["etat"] = "ATTRIBUTION INVALIDE"
            r["raisons"].append(f"FORGE DÉMONTRÉE : orphelin d'une sonde précédente ({HOTE_LEURRE} vu dans {nom or tag})")
            return r

    # 1 ter. canari d'une AUTRE sonde (suffixe different) dans ce qui sort : forge ou
    # orphelin d'une autre sonde, jamais une preuve pour celle-ci.
    autres = sorted(c for c in (fi["canaris_reseau"] | ev["canaris_reseau"] | ev["canaris_exec"])
                    if not c.endswith("_" + suf))
    if autres:
        r["etat"] = "ATTRIBUTION INVALIDE"
        r["raisons"].append(f"canari d'une autre sonde (suffixe attendu {suf}) : {', '.join(autres[:4])}")
        return r

    # 2. entrees.jsonl absent OU VIDE (taille > 0, pas seulement « existe »).
    # DETECTION NON LOGGUEE : le paquet peut effacer ses propres fichiers (/work/out est
    # dans son realm) ; fin.json, lui, est ecrit par root. Une trace d'etat au bon nonce
    # OU un fin.json au bon nonce suffit donc a attribuer la preuve du faux-Internet.
    fin_root = lire_jsonl(os.path.join(d, "fin.json"))
    fin_ok = bool(fin_root) and str(fin_root[0].get("nonce", "")) == nonce
    if taille(os.path.join(run, "entrees.jsonl")) <= 0:
        if (fi["canaris_reseau"] or fi["hotes"]) and ((statut_etat == "ok") or (fin_ok and statut_etat != "etranger")):
            r["etat"] = "DETECTION NON LOGGUEE"
            r["hotes"], r["canaris_reseau"] = fi["hotes"], fi["canaris_reseau"]
            r["raisons"].append("preuve dans faux-internet.jsonl, entrees.jsonl absent ou vide")
        else:
            r["etat"] = "BANC INVALIDE"
            r["raisons"].append("entrees.jsonl absent ou vide")
        return r

    # 3. run-nonce (nonce du registre dans l'état du pilote) + fin.json root si présent
    if fin_root and not fin_ok:
        r["etat"] = "ATTRIBUTION INVALIDE"
        r["raisons"].append("fin.json (detoner-obs) porte un autre nonce : dossier d'un autre run")
        return r
    if statut_etat != "ok":
        r["etat"] = "ATTRIBUTION INVALIDE"
        r["raisons"].append(raison_etat)
        return r

    # 4. nonce par événement
    # Le faux-Internet ne peut PAS porter notre nonce (c'est le trafic du paquet) :
    # l'exiger sur ses lignes rendrait tout run ATTRIBUTION INVALIDE des que le
    # harnais estampille ses evenements. Son attribution repose sur redemarrage=OK
    # + verrou exclusif (aucun processus d'une autre sonde vivant pendant la fenetre).
    statut_ev, raison_ev = verifie_nonce_evenements(ev_evs, nonce)
    r["nonce_evenement"] = "absent" if statut_ev == "absent" else "present"
    if statut_ev == "invalide":
        r["etat"] = "ATTRIBUTION INVALIDE"
        r["raisons"].append(raison_ev)
        return r

    # 6. preuves (logique existante conservée)
    r["hotes"] = fi["hotes"] | ev["hotes"]
    r["execs"] = ev["execs"]
    r["canaris_reseau"] = fi["canaris_reseau"] | ev["canaris_reseau"]
    r["canaris_exec"] = ev["canaris_exec"]
    # config_client sur la liste COMPLETE : la troncature a 8 (affichage) ne doit pas
    # masquer un hook ecrit apres huit ecritures leurres.
    toutes_hors = sorted(set(ev["ecritures_hors"]))
    r["ecritures_hors"] = toutes_hors[:8]
    config_client = [c for c in toutes_hors if any(k in c for k in (".claude", ".codex", ".cursor", ".gemini", ".mcp"))]
    r["config_client"] = config_client
    cle = bool(r["canaris_reseau"] or r["canaris_exec"] or r["hotes"] or r["execs"] or config_client)
    # Run interrompu : lu dans fin.json ECRIT PAR ROOT (fin_root[0]), pas dans le registre.
    # `rc` = code de detonation (124/137 = timeout), `duree_ms` = duree mesuree par root.
    # npm_rc (code de `npm install`) ne sert qu'a D7 (ci-dessous). fin.json absent : inchange.
    # Exception nommee : la sonde CONTRÔLE-LEURRE (l'orphelin tient strace/docker exec).
    interrompu, detail_int = False, ""
    if fin_root and not leurre:
        rc = fin_root[0].get("rc")
        duree = fin_root[0].get("duree_ms")
        rc_ko = rc is not None and str(rc).strip() != "0"
        duree_ok = isinstance(duree, (int, float)) and not isinstance(duree, bool) or (
            isinstance(duree, str) and duree.strip().isdigit())
        duree_ko = duree_ok and int(float(duree)) > duree_max_ms()
        interrompu = rc_ko or duree_ko
        detail_int = f"run interrompu (rc={rc}, duree_ms={duree})"
    if leurre:
        # Contrôle, jamais une détection : recevable si SON run montre l'hôte leurre.
        if HOTE_LEURRE in r["hotes"]:
            r["etat"] = "CONTRÔLE OK"
        else:
            r["etat"] = "CONTRÔLE KO"
            r["raisons"].append(f"hôte leurre {HOTE_LEURRE} absent du run de la sonde leurre")
    elif cle and interrompu:
        r["etat"] = "CLÉ NON RECEVABLE"
        r["raisons"].append(detail_int)
    elif cle:
        if r["nonce_evenement"] == "present" and e["redemarrage"] == "OK":
            r["etat"] = "CLÉ"
        else:
            r["etat"] = "CLÉ NON RECEVABLE"
            if r["nonce_evenement"] != "present":
                r["raisons"].append("nonce_evenement=absent")
            if e["redemarrage"] != "OK":
                r["raisons"].append(f"redemarrage={e['redemarrage'] or 'inconnu'}")
    else:
        if interrompu:
            # Silence d'un run interrompu : le paquet n'a pas tourné jusqu'au bout, rien n'est prouvé.
            r["etat"] = "— NON RECEVABLE (run interrompu)"
            r["raisons"].append(detail_int)
        elif npm_rc not in ("0", "-"):
            # Rien n'est sorti, mais les dependances n'ont pas ete installees : le
            # silence ne prouve rien (npm a echoue, le paquet n'a pas tourne en entier).
            r["etat"] = f"— NON RECEVABLE (dépendances non installées, npm_rc={npm_rc})"
            r["raisons"].append(f"npm_rc={npm_rc}")
        elif a_trace_fin(run, nonce):
            r["etat"] = "—"
        else:
            r["etat"] = "— NON RECEVABLE (pas de trace fin)"
            r["raisons"].append("pas de trace fin au bon nonce")

    # T3 : identité du code exécuté, comparée au manifeste attendu (s'il existe).
    if code_attendu is not None:
        sha_att = code_attendu.get("code_sha256")
        if r["code_sha256"] is None:
            r["raisons"].append("identité du code absente")
            if r["etat"] == "CLÉ":
                r["etat"] = "CLÉ NON RECEVABLE"
            elif r["etat"] == "—":
                r["etat"] = "— NON RECEVABLE"
            elif r["etat"] == "CONTRÔLE OK":
                r["etat"] = "CONTRÔLE KO"
        elif r["code_sha256"] != sha_att:
            diff = fichiers_differents(code_exec, code_attendu.get("code"))
            r["etat"] = "BANC INVALIDE"
            r["raisons"].append("code exécuté ≠ code-attendu.json (" + (", ".join(diff) if diff else "fichiers non identifiés") + ")")
    return r


def hote_de(v) -> str:
    """Hôte réel d'une valeur : une URL se parse, un nom d'hôte se garde.
    Minuscules AVANT le test, `:port` et point final retirés, IPv4 acceptées."""
    if not isinstance(v, str):
        return ""
    v = v.strip()
    if not v:
        return ""
    if "://" in v:
        try:
            h = (urlsplit(v).hostname or "").lower()
        except Exception:
            return ""
    else:
        h = re.sub(r":\d{1,5}$", "", v.lower())
    h = h.rstrip(".")
    return h if re.fullmatch(r"[a-z0-9_-]+(?:\.[a-z0-9_-]+)+", h) else ""


def est_registry(host) -> str:
    """Égalité stricte : `registry.npmjs.org.attaquant.test` n'est PAS le registry.
    Défaut relevé par deux relecteurs (sous-chaîne contournable)."""
    h = hote_de(host)
    return bool(h) and (h == "registry.npmjs.org" or h.endswith(".registry.npmjs.org"))


SUF = SUF_DEFAUT
CANARIS_NOMS = ("NPM", "SSH", "AWS", "GH", "DOCKER", "KUBE", "GIT", "ENV",
                "GCLOUD", "WA", "COOKIE", "HIST", "MSG")
CANARIS_CONNUS = [f"CANARI_{n}_{SUF}" for n in CANARIS_NOMS]


def variantes(c: str):
    """Formes sous lesquelles un canari peut sortir encode.

    Un attaquant qui serialise l'environnement complet en JSON puis en base64
    n'envoie JAMAIS la chaine nue : la recherche en sous-chaine directe le
    manque. On cherche donc aussi base64 (std et urlsafe, avec et sans padding),
    hex et percent. (Idee reprise de Malwhunter wiretap/canary.py:27-51.)

    ALIGNEMENTS : le base64 d'un flux ou le canari est precede de n octets ne
    ressemble a celui du canari nu que si n est multiple de 3. On calcule donc le
    base64 de (shift octets nuls + canari) pour shift = 0, 1, 2 et on ne garde que
    le COEUR : on retire les caracteres de tete influences par le prefixe (4 si
    shift > 0) et ceux de queue influences par l'octet suivant inconnu (4). Le
    padding disparait avec la queue, donc avec/sans « = » sont couverts.
    """
    b = c.encode()
    formes = {c, b.hex(), b.hex().upper(), urllib.parse.quote(c, safe="")}
    for shift in (0, 1, 2):
        brut = b"\0" * shift + b
        for enc in (base64.b64encode(brut), base64.urlsafe_b64encode(brut)):
            s = enc.decode().rstrip("=")
            tete = 4 if shift > 0 else 0
            coeur = s[tete:len(s) - 4]
            if len(coeur) < 12:
                continue
            formes.add(coeur)
            # un base64 std passe dans une URL ou un formulaire est percent-encode (+ et /)
            q = urllib.parse.quote(coeur, safe="")
            if q != coeur:
                formes.add(q)
    return formes


def connus(suf: str = SUF_DEFAUT) -> list:
    return [f"CANARI_{n}_{suf}" for n in CANARIS_NOMS]


def canaris(blob: str, suf: str = SUF_DEFAUT):
    """Canaris trouves dans `blob` : clairs (tout suffixe hex6, pour reperer ceux d'une
    autre sonde) + formes encodees DU SUFFIXE DE LA SONDE."""
    # `CANARI_FACTICE_…` est le jeton que le harnais pose lui-même dans ~/.npmrc :
    # le compter comme fuite rendrait chaque paquet « coupable ».
    trouves = {c for c in re.findall(r"CANARI_[A-Z]+_[0-9a-f]{6}", blob) if "FACTICE" not in c}
    # Les formes encodees sont TOUJOURS tentees : un canari en clair trouve ne
    # prouve pas qu'il n'y en a pas d'autres, encodes (B3).
    for connu in connus(suf):
        if connu in trouves:
            continue
        for f in variantes(connu):
            if f and f in blob:
                trouves.add(connu)
                break
    return trouves


def classe_attendue(att):
    """Classe d'une valeur d'attendus.json ; None si absente ou inconnue."""
    return att if att in CLASSES else None


def nature(r: dict) -> str:
    """Même classification que le contrat : canari > config client > contact > intention."""
    if r["canaris_reseau"] or r["canaris_exec"]:
        return "canari"
    if r["config_client"]:
        return "config"
    if r["hotes"] and not r["execs"]:
        return "contact"
    return "intention"


def resume(lignes: list) -> dict:
    """Compteurs du résumé final (T2) à partir des verdicts par sonde."""
    det = [r for r in lignes if r["classe"] == "CLÉ"]
    inte = [r for r in lignes if r["classe"] == CLASSE_INTENTION]
    leur = [r for r in lignes if r["classe"] == CLASSE_LEURRE]
    tem = [r for r in lignes if r["nom"] == SONDE_TEMOIN]
    nat = Counter(nature(r) for r in lignes if r["etat"] == "CLÉ" and r["classe"] != CLASSE_LEURRE)
    return {
        "detections": sum(1 for r in det if r["etat"] == "CLÉ"), "detections_sur": len(det),
        "intentions": sum(1 for r in inte if r["etat"] == "CLÉ"), "intentions_sur": len(inte),
        "temoin": "—" if tem and all(r["etat"] == "—" for r in tem) else "KO",
        "leurre": ("n/a" if not leur else ("OK" if all(r["etat"] == "CONTRÔLE OK" for r in leur) else "KO")),
        "nature": {k: nat.get(k, 0) for k in ("canari", "config", "contact", "intention")},
    }


def charge_classes_fabrique():
    """CLASSES_ATTENDUES de fabrique_sondes.py (source unique), lu à côté du lecteur
    (surchargeable SBX_FABRIQUE). Charge le module SANS exécuter fabrique() (appelée
    seulement sous __main__). Retourne (dict|None, chemin)."""
    chemin = os.environ.get("SBX_FABRIQUE") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fabrique_sondes.py")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("sbx_fabrique_sondes", chemin)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        cl = m.CLASSES_ATTENDUES
        if not isinstance(cl, dict):
            return None, chemin
        return dict(cl), chemin
    except Exception:
        return None, chemin


def charge_code_attendu(chemin: str):
    """Manifeste attendu (dict) ; None s'il n'existe pas ou est illisible."""
    if not os.path.isfile(chemin):
        return None
    try:
        with open(chemin, encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return None
    return j if isinstance(j, dict) and isinstance(j.get("code_sha256"), str) else None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    prefixe = args[0] if args else "fn"
    ch = chemins()
    reg_chemin = os.path.join(ch["scratch"], f"sbx-{prefixe}", "registre.tsv")
    # Pas de registre = pas de dénominateur : refus explicite, JAMAIS de repli sur listdir.
    if not os.path.isfile(reg_chemin):
        print(f"REFUS : registre absent ({reg_chemin}) — dénominateur inconnu, aucun verdict", file=sys.stderr)
        return 2
    registre = lit_registre(reg_chemin)
    if not registre:
        print(f"REFUS : registre vide ({reg_chemin}) — dénominateur nul, aucun verdict", file=sys.stderr)
        return 2

    attendus = {}
    try:
        with open(ch["attendus"], encoding="utf-8") as f:
            attendus = json.load(f)
        if not isinstance(attendus, dict):
            attendus = {}
    except Exception:
        attendus = {}
    code_attendu = charge_code_attendu(ch["code_attendu"])

    # Dossiers au bon motif mais absents du registre : ignorés, jamais comptés.
    motif = re.compile(rf"^{re.escape(prefixe)}\d{{3}}$")  # nos tags ont trois chiffres : fn001…
    tags_reg = {e["tag"] for e in registre}
    try:
        hors = sorted(t for t in os.listdir(ch["runs"]) if motif.match(t) and t not in tags_reg)
    except OSError:
        hors = []

    canon, chemin_fab = charge_classes_fabrique()
    ecarts = []
    if canon is None:
        print("fabrique_sondes.py introuvable : classes non vérifiées")

    def attendu_canonique(nom):
        """Classe canonique (fabrique) si elle est connue, sinon attendus.json tel quel."""
        if canon is None:
            return attendus.get(nom)
        return canon.get(nom, "CLÉ")

    if canon is not None:
        vus = set()
        for e in registre:
            nom = e["nom"]
            if nom in vus:
                continue
            vus.add(nom)
            c = canon.get(nom, "CLÉ")
            v = attendus.get(nom)
            if v != c:
                ligne = (f"ATTENDUS PÉRIMÉS : {nom} attendu.json={v if v is not None else 'absent'} "
                         f"fabrique={c} → relancer : python3 -I {chemin_fab}")
                print(ligne)
                ecarts.append(ligne)

    lignes = [classe(e, ch["runs"], classe_attendue(attendu_canonique(e["nom"])), code_attendu) for e in registre]

    valeurs = sorted({r["code_sha256"] for r in lignes if r["code_sha256"]})
    if len(valeurs) == 1:
        print(f"code_sha256 exécuté : {valeurs[0]}")
    elif not valeurs:
        print("code_sha256 exécuté : aucun (summary.json sans identité)")
    else:
        print("code_sha256 exécuté : PLUSIEURS VALEURS : " + ", ".join(valeurs))
        ecarts.append("code_sha256 exécuté : PLUSIEURS VALEURS dans un run (" + ", ".join(valeurs) + ")")

    for r in lignes:
        etat = r["etat"]
        extra = ""
        if etat.startswith(("CLÉ", "—", "DETECTION NON LOGGUEE", "CONTRÔLE")):
            extra = (f" hotes={sorted(r['hotes'])} exec={len(r['execs'])} "
                     f"canaris_reseau={sorted(r['canaris_reseau'])} canaris_exec={sorted(r['canaris_exec'])} "
                     f"ecrit_hors={r['ecritures_hors']} nonce_evenement={r['nonce_evenement'] or '-'}")
        if r["raisons"]:
            extra += " raisons=" + "; ".join(r["raisons"])
        affiche = etat + (" (intention)" if r["classe"] == CLASSE_INTENTION and etat == "CLÉ" else "")
        print(f"{r['tag']:8s} {r['nom'][:30]:30s} {affiche}{extra}")
        att = attendu_canonique(r["nom"])
        r["attendu"] = att
        recevable = etat in ("CLÉ", "—", "CONTRÔLE OK")
        # classe INTENTION : recevable si CLÉ ; CONTRÔLE-LEURRE : CONTRÔLE OK ; sinon l'attendu tel quel.
        attendu_etat = {CLASSE_INTENTION: "CLÉ", CLASSE_LEURRE: "CONTRÔLE OK"}.get(att, att)
        if not recevable:
            ecarts.append(f"{r['tag']} {r['nom']}: {etat}" + (f" ({'; '.join(r['raisons'])})" if r["raisons"] else ""))
        elif att is None:
            ecarts.append(f"{r['tag']} {r['nom']}: sans attendu (non recevable)")
        elif attendu_etat != etat:
            ecarts.append(f"{r['tag']} {r['nom']}: obtenu {etat}, attendu {att}")
    for t in hors:
        print(f"{t:8s} {'':30s} HORS REGISTRE (ignoré)")

    temoin = [r for r in lignes if r["nom"] == SONDE_TEMOIN]
    if not temoin:
        ecarts.append(f"{SONDE_TEMOIN}: absent du registre")
    elif any(r["etat"] != "—" for r in temoin):
        ecarts.append(f"{SONDE_TEMOIN}: doit valoir « — »")

    res = resume(lignes)
    # BANC RECEVABLE exige le leurre CONTRÔLE OK si p21 est au registre (classe CONTRÔLE-LEURRE).
    if any(r["classe"] == CLASSE_LEURRE and r["etat"] != "CONTRÔLE OK" for r in lignes):
        ecarts.append(f"{SONDE_LEURRE}: le contrôle leurre doit valoir CONTRÔLE OK")

    recevable = not ecarts
    verdict = "BANC RECEVABLE" if recevable else "BANC NON RECEVABLE"
    compte = Counter(r["etat"] for r in lignes)

    if "--json" in sys.argv:
        sortie = [{"tag": r["tag"], "nom": r["nom"], "etat": r["etat"], "attendu": r.get("attendu"),
                   "raisons": r["raisons"], "nonce_evenement": r["nonce_evenement"],
                   "redemarrage": r["redemarrage"], "hotes": sorted(r["hotes"]), "execs": len(r["execs"]),
                   "canaris_reseau": sorted(r["canaris_reseau"]), "canaris_exec": sorted(r["canaris_exec"]),
                   "ecritures_hors": r["ecritures_hors"], "code_sha256": r["code_sha256"]} for r in lignes]
        with open(os.path.join(ch["json_dir"], f"cles-{prefixe}.json"), "w", encoding="utf-8") as f:
            json.dump(sortie, f, ensure_ascii=False, indent=1)

    print(f"Dénominateur (registre) : {len(registre)} ; hors registre ignorés : {len(hors)}")
    print("Par état : " + ", ".join(f"{k}={v}" for k, v in sorted(compte.items())))
    if ecarts:
        print("Écarts :")
        for x in ecarts:
            print(f"  - {x}")
    n = res["nature"]
    print(f"Détections : {res['detections']}/{res['detections_sur']} (sondes de détection) | "
          f"intentions : {res['intentions']}/{res['intentions_sur']} | "
          f"contrôles : témoin {res['temoin']}, leurre {res['leurre']}")
    print(f"Nature : canari exfiltré {n['canari']}, config client {n['config']}, "
          f"contact réseau seul {n['contact']}, intention {n['intention']}")
    if code_attendu is None:
        print("code-attendu.json absent : identité du code non vérifiée")
    print(verdict)
    return 0 if recevable else 1


if __name__ == "__main__":
    sys.exit(main())
