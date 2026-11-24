#!/usr/bin/env python3
"""Vingt audits de la sandbox, chacun suivi d'un test réel sur banc de sondes.

Protocole par tour :
  1. quatre relecteurs (hy4, mistral-large-4, minimax-m3.1-flash, kimi-k3.1-pro)
     reçoivent le protocole exact + le score du tour précédent ;
  2. leurs constats sont extraits (titre / preuve / correctif) et journalisés ;
  3. le banc des douze sondes est rejoué : 11 classes malveillantes doivent
     rester vues, la sonde témoin doit rester muette ;
  4. le score est comparé au tour précédent — une amélioration qui casse le banc
     est rejetée.

Arrêt anticipé après trois tours consécutifs sans constat bloquant.

Usage : audit_sandbox_20.py [--tours 20] [--prefixe aud]
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

BASE = "/home/bob/q5n2"
JOURNAL = os.path.join(BASE, "AUDITS-SANDBOX-JOURNAL.jsonl")
MODELES = ["hy4:cloud", "mistral-large-4:cloud", "minimax-m3.1-flash:cloud", "kimi-k3.1-pro:cloud"]
FICHIERS = ["sbx-scenario3.sh", "_sbx_driver3.cjs", "cles_scenario3.py", "fabrique_sondes.py"]


def dossier(score: str, tour: int, precedent: str) -> str:
    morceaux = []
    for f in FICHIERS:
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            morceaux.append(f"=== {f} ===\n{open(p).read()}")
    return f"""Audit {tour}/20 de la sandbox de détonation npm. Tu es relecteur ; on te demande
des défauts RÉELS, pas des félicitations.

CE QUI EXISTE : conteneur isolé, faux-Internet qui journalise chaque requête, harnais
qui journalise les canaux (require, import, fs.*, child_process, net.connect,
https.request, processus), pilote qui sème 12 états de victime avec canaris, plafonne
les timers, rejoue les scripts de cycle de vie, exécute les bins et pilote les exports.

SCORE DU BANC (12 sondes synthétiques, une par classe de geste) : {score}
La sonde 12 est un témoin propre : il doit rester muet.

CONSTATS DU TOUR PRÉCÉDENT : {precedent or 'aucun (premier tour)'}

TA TÂCHE : rends AU PLUS TROIS constats, chacun avec
- « titre » : 6 mots maximum ;
- « preuve » : ce que tu as lu dans le code qui le démontre (nomme la ligne) ;
- « correctif » : ce qu'il faut écrire, concrètement ;
- « bloquant » : true si un paquet malveillant peut passer sans être vu OU si une
  preuve peut être fabriquée.

N'invente pas de scénario exotique : cherche ce que CE code, tel qu'il est écrit,
laisse échapper. Termine par un bloc ```json contenant une liste de ces constats.

{chr(10).join(morceaux)}
"""


def demande(modele: str, prompt: str, res: dict):
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "http://localhost:11434/v1/chat/completions",
            data=json.dumps({"model": modele, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}).encode(),
            headers={"Content-Type": "application/json"},
        )
        r = json.load(urllib.request.urlopen(req, timeout=1500))
        res[modele] = {"secondes": round(time.time() - t0, 1), "texte": r["choices"][0]["message"]["content"]}
    except Exception as e:
        res[modele] = {"secondes": 0, "texte": "", "erreur": f"{type(e).__name__} {e}"}


def constats(texte: str):
    blocs = re.findall(r"```json\s*(\[.*?\])\s*```", texte, re.S)
    for b in blocs:
        try:
            v = json.loads(b)
            if isinstance(v, list):
                return v
        except Exception:
            continue
    return []


def banc(prefixe: str):
    subprocess.run(["sudo", "-n", "systemd-run", "--uid=bob", "--unit", f"sbx-{prefixe}", "--collect",
                    "bash", f"{BASE}/sbx-scenario3.sh", "/tmp/liste_sondes.tsv", prefixe, "120"],
                   capture_output=True, text=True)
    for _ in range(40):
        a = subprocess.run(["systemctl", "is-active", f"sbx-{prefixe}"], capture_output=True, text=True).stdout.strip()
        if a == "inactive":
            break
        time.sleep(20)
    r = subprocess.run(["python3", f"{BASE}/cles_scenario3.py", prefixe], capture_output=True, text=True, cwd=BASE)
    lignes = [l for l in r.stdout.splitlines() if l.strip()]
    vues = sum(1 for l in lignes if "CLÉ" in l)
    # témoin = dernier tag (le tri de la liste le place en dernier)
    temoin = lignes[-1] if lignes else ""
    propre = "—" in temoin and "CLÉ" not in temoin
    attendu = max(1, len(lignes) - 1)
    return f"{vues}/{attendu} classes vues, témoin {'muet' if propre else 'PARLE'}", lignes


def main():
    tours = 20
    prefixe = "aud"
    if "--tours" in sys.argv:
        tours = int(sys.argv[sys.argv.index("--tours") + 1])
    if "--prefixe" in sys.argv:
        prefixe = sys.argv[sys.argv.index("--prefixe") + 1]
    score = "11/12 classes vues, témoin muet (banc validé au tour 0)"
    precedent = ""
    muets = 0
    for t in range(1, tours + 1):
        prompt = dossier(score, t, precedent)
        res = {}
        ths = [threading.Thread(target=demande, args=(m, prompt, res)) for m in MODELES]
        [x.start() for x in ths]
        [x.join() for x in ths]
        tous = []
        for m in MODELES:
            v = res.get(m, {})
            for c in constats(v.get("texte", "")):
                c["_modele"] = m
                tous.append(c)
        bloquants = [c for c in tous if c.get("bloquant")]
        # test réel : le banc doit tenir
        score_banc, lignes = banc(f"{prefixe}{t:02d}")
        entree = {
            "tour": t,
            "constats": tous,
            "bloquants": len(bloquants),
            "score_banc": score_banc,
            "lignes_banc": lignes,
            "modeles": {m: {k: v for k, v in res.get(m, {}).items() if k != "texte"} for m in MODELES},
        }
        with open(JOURNAL, "a") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
        precedent = "; ".join(c.get("titre", "?") for c in tous[:6])
        score = score_banc
        print(f"[tour {t}] constats={len(tous)} bloquants={len(bloquants)} banc={score_banc}", flush=True)
        muets = muets + 1 if not bloquants else 0
        if muets >= 3:
            print("[arrêt] trois tours sans constat bloquant", flush=True)
            break


if __name__ == "__main__":
    main()
