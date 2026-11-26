#!/usr/bin/env python3
"""attribuer2.py — version 2, après l'audit Claude du 26/11.

Corrections appliquées (B2) :
  - hôtes NORMALISÉS : une seule entrée par hôte (http:, https, port, chemin fusionnés) ;
  - registry trié par MÉTHODE ET CHEMIN, jamais par nom : `lecture` (GET/HEAD),
    `ecriture_registry` (PUT/POST/PATCH/DELETE — vecteur ver), `methode_inconnue` ;
    l'endpoint /-/v1/security/audits est signalé séparément (`exfil_audit`) ;
  - `muet` remplacé par `main_charge`, lu dans `_sbx_etat.jsonl` ;
  - ingestion du journal du faux-Internet quand il existe, sinon
    `reseau_non_instrumente: true` ;
  - plus d'attribution `paquet` par défaut quand le chemin manque.
Usage : python3 -I attribuer2.py <dir_runs> [--json sortie.json]
"""
import json, os, sys, collections, urllib.parse

HARNAIS = ('/work/harnais', '_sbx')
OUTIL = ('/usr/local/lib/node_modules', '/opt/yarn', '/usr/lib/node_modules')
CANAUX_RESEAU = {'dns.lookup', 'net.connect', 'tls.connect', 'https.request',
                 'http.request', 'dns.query', 'dgram.send'}
ECRITURE = {'PUT', 'POST', 'PATCH', 'DELETE'}
REGISTRY = 'registry.npmjs.org'


def norme(valeur):
    """ramène toute forme à (hote, chemin, methode)."""
    v = str(valeur or '').strip()
    m = None
    if '://' in v:
        u = urllib.parse.urlsplit(v)
        m, h, p = u.hostname, u.hostname, u.path
        return (h or '', p or '/', (u.scheme or '').lower())
    if v.startswith('//'):
        v = 'http:' + v
        return norme(v)
    # hote:port
    h, _, reste = v.partition('/')
    h = h.split(':')[0]
    return (h or v, '/' + reste if reste else '/', '')


def chemin_appelant(ev):
    a = ev.get('appelant')
    if isinstance(a, dict):
        return str(a.get('fichier') or '')
    return str(a or '')


def classe_code(p):
    if not p:
        return 'inconnu'
    if any(h in p for h in HARNAIS):
        return 'banc'
    if any(o in p for o in OUTIL):
        return 'outil'
    if '/node_modules/' in p:
        return 'dependance'
    if '/work/paquet/package/' in p:
        return 'paquet'
    return 'inconnu'


def classe_proc(entree):
    e = str(entree or '')
    if not e or e.startswith('_sbx'):
        return 'banc' if not e else 'paquet'
    if e.startswith('bin:'):
        return 'paquet'
    if ':' in e:
        return 'dependance'
    return 'paquet'


def lire_main_charge(dossier):
    f = os.path.join(dossier, 'run', '_sbx_etat.jsonl')
    if not os.path.isfile(f):
        return None
    vu = False
    for l in open(f, errors='replace'):
        try:
            d = json.loads(l)
        except Exception:
            continue
        if str(d.get('etape')) == 'main':
            vu = True
            if d.get('charge'):
                return True
    return False if vu else None


def lire_faux_internet(dossier):
    for nom in ('faux-internet.jsonl', 'reseau.jsonl'):
        f = os.path.join(dossier, 'run', nom)
        if os.path.isfile(f):
            h = collections.Counter()
            for l in open(f, errors='replace'):
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                for cle in ('sni', 'host', 'hote', 'hostname'):
                    if d.get(cle):
                        h[str(d[cle]).split(':')[0]] += 1
                        break
            return dict(h)
    return None


def traite(dossier):
    f = os.path.join(dossier, 'run', 'events.jsonl')
    if not os.path.isfile(f):
        return None
    code = collections.Counter()
    proc = collections.Counter()
    flux_local = 0
    hotes = collections.Counter()
    registre = collections.Counter()
    exfil_audit = 0
    methode_inconnue = 0
    for ligne in open(f, errors='replace'):
        try:
            ev = json.loads(ligne)
        except Exception:
            continue
        oc = classe_code(chemin_appelant(ev))
        code[oc] += 1
        proc[classe_proc(ev.get('entree'))] += 1
        canal = str(ev.get('canal'))
        detail = ev.get('detail') if isinstance(ev.get('detail'), dict) else {}
        valeur = ev.get('valeur')
        if canal == 'net.write':
            if str(valeur) == 'socket':
                flux_local += 1          # stdout/stderr, jamais du réseau
            continue
        if canal not in CANAUX_RESEAU:
            continue
        h, p, _ = norme(detail.get('host') or detail.get('hote') or valeur)
        if not h or h in ('socket', 'None'):
            continue
        methode = str(detail.get('method') or detail.get('methode') or '').upper()
        if h.endswith(REGISTRY) or h == REGISTRY:
            if '/-/v1/security/audits' in p:
                exfil_audit += 1
                registre['exfil_audit'] += 1
            elif methode in ECRITURE:
                registre['ecriture_registry'] += 1
            elif methode in ('GET', 'HEAD'):
                registre['lecture'] += 1
            else:
                methode_inconnue += 1
                registre['methode_inconnue'] += 1
            continue
        hotes[h] += 1
    fi = lire_faux_internet(dossier)
    mc = lire_main_charge(dossier)
    return {
        'origine_code': dict(code),
        'origine_processus': dict(proc),
        'flux_local': flux_local,
        'hotes': dict(hotes),
        'registre': dict(registre),
        'exfil_audit': exfil_audit,
        'main_charge': mc,
        'faux_internet': fi,
        'reseau_non_instrumente': fi is None,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    base = sys.argv[1]
    sortie = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    res = {}
    for tag in sorted(os.listdir(base)):
        r = traite(os.path.join(base, tag))
        if r:
            res[tag] = r
    n = len(res)
    mc = sum(1 for v in res.values() if v['main_charge'] is True)
    mc0 = sum(1 for v in res.values() if v['main_charge'] is False)
    mcn = sum(1 for v in res.values() if v['main_charge'] is None)
    reg = collections.Counter()
    for v in res.values():
        for k, c in v['registre'].items():
            reg[k] += c
    hotes = collections.Counter()
    for v in res.values():
        for h, c in v['hotes'].items():
            hotes[h] += 1
    noni = sum(1 for v in res.values() if v['reseau_non_instrumente'])
    print(f'runs: {n}')
    print(f'main_charge : vrai {mc} · faux {mc0} · inconnu {mcn}')
    print(f'registry (methode/chemin) : {dict(reg)}')
    print(f'flux_local (stdout) : {sum(v["flux_local"] for v in res.values())}')
    print(f'hotes hors registry : {hotes.most_common(8)}')
    print(f'reseau_non_instrumente (pas de journal faux-Internet) : {noni}/{n}')
    if sortie:
        json.dump(res, open(sortie, 'w'), indent=1)
        print(f'ecrit: {sortie}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
