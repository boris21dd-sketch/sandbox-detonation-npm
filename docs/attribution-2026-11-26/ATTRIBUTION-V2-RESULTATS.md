# Attribution v2 — résultats immédiats (26/11, 14h)

B2 appliqué. `attribuer2.py` corrige les cinq défauts relevés par Claude :

- hôtes **normalisés** : une entrée par hôte, plus de `http:` / `host:443` / URL comptés trois fois ;
- registry trié par **méthode et chemin**, jamais par nom ;
- `muet` remplacé par `main_charge`, lu dans `run/_sbx_etat.jsonl` ;
- ingestion du faux-Internet tentée, et **absence signalée** au lieu d'être tue ;
- plus d'attribution `paquet` quand le chemin de l'appelant manque (→ `inconnu`).

## Mesure sur 2 917 runs (lecture seule, aucune campagne relancée)

```
main_charge : vrai 1 841 · faux 242 · inconnu 834
registry    : lecture 248 · ECRITURE 628 · methode_inconnue 2 616
flux_local  : 26 176  (stdout, jamais du reseau)
hors registry (nb de runs) :
   sink.exfil-probe.test 1 338 | raw.githubusercontent.com 112 | npm.corp-interne.test 76
   leurre.exfil-probe.test 74 | models.dev 12 | localhost 12 | github.com 7 | web.whatsapp.com 6
reseau_non_instrumente : 2 917 / 2 917
```

## Ce que ça change

**628 écritures vers le registry.** Mon filtre par nom d'hôte les avait rendues invisibles : elles
tombaient dans « registry.npmjs.org » et je les excluais en bloc. C'est le vecteur ver — un paquet
qui publie avec le jeton volé — et il était hors de mon champ. Le chiffre est un **minorant** :
2 616 événements registry n'ont pas de méthode lisible.

**`main_charge` donne le vrai taux d'exécution** : 242 runs où le `main` n'a pas été chargé, 834
indéterminés (pas de `_sbx_etat.jsonl`). Ce n'est donc pas « 0 sur 218 » : la campagne a exécuté du
code plus souvent que l'audit C ne le supposait — mais 242 non-exécutions restent à expliquer.

**Le journal du faux-Internet n'est pas là où je l'ai cherché** : `reseau_non_instrumente` vaut vrai
pour les 2 917 runs. A7 reste ouvert, et je ne peux pas dire si le journal n'existe pas ou s'il est
écrit ailleurs. C'est exactement le `# INCONNU:` que hy4 avait posé.

## Ce qui reste

- B3 : exemption `CANARI_NPM` du lecteur — aujourd'hui un `PUT` vers le registry passe pour un usage
  normal. Non corrigé.
- B1 : déploiement root (pilote hors `package/`, `package.json` intact, entrée `main` garantie).
- B4 : `FICHIERS_ETRANGERS:<chemin>:<uid>` avant tout `rm -rf`.
- A7 : localiser le journal du faux-Internet.

Rien n'est publié : jeton retiré de la machine. Tout est local, empreintes ci-jointes.
