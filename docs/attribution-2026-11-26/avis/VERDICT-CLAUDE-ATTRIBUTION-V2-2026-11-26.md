# VERDICT CLAUDE — attribution v2 (26/11 soir)
## 1. SCAN
[LIRE-DABORD.md, EMPREINTES.txt, attribuer2.py, attribuer-v1-pour-comparaison.py (= v1 déjà auditée), attribution-v2.json (2 917 runs), claude/AUDIT-D.md (= mon audit, identique octet pour octet)]
Statuts : **P** prouvé sur attribution-v2.json · **D** lu dans attribuer2.py.

## 2. VERDICT SUR LES 4 CHIFFRES
| Affirmation | Verdict | Preuve |
|---|---|---|
| « 628 écritures vers le registry, vecteur ver hors de mon champ » | **FAUX dans le sens donné** | P : les 310 runs concernés sont TOUS des campagnes de sondes (r 124, s 117, aud 10…), **0 sur les 204 manq**. D : ce sont les sondes d'exfiltration par le point d'audit (POST `/-/v1/security/audits`), mal classées : `norme(detail.host or valeur)` prend l'hôte seul quand `detail.host` existe → chemin = `/` → `exfil_audit` = 0 partout (P), ce qui contredit les 27 runs « audits b64 » de son propre `reseau-resume.json` du matin. |
| « main_charge : vrai 1 841 · faux 242 · inconnu 834 » | **Juste mais mal présenté** | Chiffre global mêlant sondes et vrais paquets. Sur les 204 manq (P) : **vrai 114 · faux 85 · inconnu 5**. Mon hypothèse « charges=0 sur 218 = aucun main chargé » est **réfutée** : `charges` du journal ne mesurait pas ça. Je la retire. Restent 85 vrais paquets jamais exécutés (pairs absents probables). |
| « reseau_non_instrumente 2 917/2 917 » | **Artefact de son outil** | D : il cherche `<tag>/run/faux-internet.jsonl` ; detoner-obs l'écrit en `<tag>/faux-internet.jsonl` (`$OUT/faux-internet.jsonl`) et le lecteur des sondes le lit là (`os.path.join(d, "faux-internet.jsonl")`). Et `reseau_non_instrumente = journal absent` confond « pas de journal » avec « trafic non instrumenté ». A7 n'est pas ouvert : le chemin est faux. |
| « B3, B1, B4 restent » | **Déjà livrés** | Tous dans la livraison D (16 suites vertes) ; non déployée. |

## 3. LE VRAI PROBLÈME
Troisième réécriture locale d'un outil livré et testé ; chacune réintroduit des défauts déjà corrigés (chemin du journal, chemin du registry perdu, absence = vrai). Cause probable : mon outil ne donnait que du détail par run, pas le résumé de campagne dont PCfixe a besoin → ajouté (`--resume`, E1). **Règle** : PCfixe n'écrit plus d'outil d'analyse ; il lance celui livré et renvoie sa sortie brute.

## 4. MA FAILLE RESTANTE (corrigée en E)
`attribuer.py` (D) : journal absent → `reseau_non_instrumente = []`, indiscernable de « rien d'anormal ». Désormais `null` + liste des chemins essayés.

## 5. À LANCER (aucune campagne, lecture seule)
```
python3 -I attribuer.py --runs /opt/sandbox/runs-obs --resume
python3 -I attribuer.py --runs /opt/sandbox/runs-obs --familles manq --resume --json > resume-manq.json
```
RÉUSSITE SI : manq `faux-Internet : présent` > 0 ; écritures registry listées avec origine (attendu : sondes audit seulement) ; manq `main_charge` = 114/85/5 (sinon une des deux mesures est fausse).
Puis déploiement D (même commande root) et run témoin.
