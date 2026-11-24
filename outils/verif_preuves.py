#!/usr/bin/env python3
"""Contrôles d'intégrité indépendants du lecteur sur des runs bruts : nonce sur 100 % des
lignes, fin.json/entrees/summary au bon nonce, garde/redémarrage/npm_rc, suffixes étrangers,
leurre hors p21, étapes settle/pilote, durée d'observation, p18 sans canari en clair."""
import json,os,sys,glob,re,base64,hashlib,collections
def jl(p):
    out=[]
    if not os.path.isfile(p): return out
    for l in open(p,encoding='utf-8',errors='replace'):
        l=l.strip()
        if l:
            try: out.append(json.loads(l))
            except Exception: out.append({'__illisible__':l[:80]})
    return out
# Usage : python3 -I verif_preuves.py <dossier_preuve> <prefixes>   (ex. . hij)
# <dossier_preuve> contient registre-<p>.tsv et runs/<tag>/ (runs-obs extraits).
if len(sys.argv) < 3: sys.exit('usage: verif_preuves.py <dossier_preuve> <prefixes>')
R=sys.argv[1]
if True:
    for p in sys.argv[2]:
        reg=[l.rstrip('\n').split('\t') for l in open(f'{R}/registre-{p}.tsv') if l.strip()]
        pb=collections.Counter(); hashes=set(); notes=[]
        for c in reg:
            tag,nom,nonce,deb,garde,redem,suf,npmrc=c
            d=f'{R}/runs/{tag}'; run=d+'/run'
            ev=jl(run+'/events.jsonl')
            ns=collections.Counter(e.get('nonce','<ABSENT>') for e in ev)
            if set(ns)!={nonce}: pb['nonce_evt_KO']+=1; notes.append(f'{tag} nonces={dict(ns)}')
            et=jl(run+'/_sbx_etat.jsonl'); etapes=[e.get('etape') for e in et]
            if any(e.get('nonce')!=nonce for e in et): pb['nonce_etat_KO']+=1
            if 'pilote' in etapes: pb['pilote']+=1
            if 'settle' in etapes: pb['settle']+=1
            fin=jl(d+'/fin.json')
            if not fin or fin[0].get('nonce')!=nonce: pb['fin_json_KO']+=1
            en=jl(run+'/entrees.jsonl')
            if any(e.get('nonce')!=nonce for e in en): pb['nonce_entrees_KO']+=1
            mains=[e for e in en if e.get('nom')=='main']
            if mains: pb['obs_main_ms']+= 0; pb.setdefault('obs',[]) if False else None
            if mains: pb[f'_obs_{tag}']=mains[0].get('duree_ms',0)
            try:
                sm=json.load(open(run+'/summary.json'))
                if sm.get('evenements_etrangers',0): pb['etrangers>0']+=1
                if sm.get('nonce')!=nonce: pb['summary_nonce_KO']+=1
            except Exception: pb['summary_absent']+=1
            if garde!='OK' or redem!='OK': pb['garde_redem_KO']+=1
            if npmrc!='0': pb['npm_rc!=0']+=1
            # canaris dans le reseau a un autre suffixe
            fi=open(d+'/faux-internet.jsonl',encoding='utf-8',errors='replace').read() if os.path.isfile(d+'/faux-internet.jsonl') else ''
            evtxt=open(run+'/events.jsonl',encoding='utf-8',errors='replace').read() if os.path.isfile(run+'/events.jsonl') else ''
            autres={s for s in re.findall(r'CANARI_[A-Z]+_([0-9a-f]{6})',fi) if s!=suf}
            if autres: pb['suffixe_etranger_fi']+=1; notes.append(f'{tag} suffixes etrangers fi={autres}')
            autres2={s for s in re.findall(r'CANARI_[A-Z]+_([0-9a-f]{6})',evtxt) if s!=suf and s!='0123456789'[:6]}
            autres2-= {'012345'}
            if autres2: pb['suffixe_etranger_evt']+=1; notes.append(f'{tag} suffixes etrangers evt={autres2}')
            if 'leurre.exfil-probe.test' in (fi+evtxt).lower() and nom!='p21-leurre-orphelin': pb['leurre_hors_p21']+=1
            if nom.startswith('p18'):
                plain=f'CANARI_SSH_{suf}' in fi
                pb[f'_p18_{nom}_clair_dans_fi']=int(plain)
            hashes.add(hashlib.sha256(evtxt.encode()).hexdigest())
        obs=[v for k,v in pb.items() if k.startswith('_obs_')]
        p18={k[5:]:v for k,v in pb.items() if k.startswith('_p18_')}
        keep={k:v for k,v in pb.items() if not k.startswith('_')}
        print(f"{p}: sondes={len(reg)} events.jsonl distincts={len(hashes)} {keep} obs_main_ms min/med/max={min(obs)}/{sorted(obs)[len(obs)//2]}/{max(obs)} p18_canari_en_clair_dans_fi={p18}")
        for n in notes[:4]: print('   ',n)
