# DISCLAIMER — Conditions d'utilisation et limitation de responsabilité

**Version 1.0 — 24 novembre 2026.** En clonant, installant, exécutant ou
distribuant ce logiciel, vous acceptez l'intégralité des conditions ci-dessous.
Si vous ne les acceptez pas, n'utilisez pas ce logiciel.

## 1. Objet

Ce dépôt fournit un protocole et des scripts d'analyse **défensive** permettant
d'exécuter des paquets logiciels non fiables dans un environnement isolé afin
d'observer leur comportement. Il est destiné aux chercheurs en sécurité, aux
auditeurs et aux mainteneurs de chaînes d'approvisionnement.

## 2. Aucune garantie — « AS IS »

LE LOGICIEL EST FOURNI « EN L'ÉTAT », SANS GARANTIE D'AUCUNE SORTE, EXPRESSE OU
IMPLICITE, Y COMPRIS, SANS LIMITATION, LES GARANTIES DE QUALITÉ MARCHANDE,
D'ADÉQUATION À UN USAGE PARTICULIER, D'ABSENCE DE CONTREFAÇON, ET TOUTE GARANTIE
QUANT À L'EXACTITUDE, L'EXHAUSTIVITÉ OU LA FIABILITÉ DES RÉSULTATS PRODUITS.

Aucun résultat négatif ne constitue une preuve d'innocence d'un paquet. Un
résultat produit par ce logiciel ne remplace ni un audit humain, ni un avis
juridique, ni une décision de sécurité engageant un tiers.

## 3. Exécution de code non fiable

Ce logiciel exécute volontairement du code potentiellement malveillant. Vous
reconnaissez que l'isolation (conteneur, réseau filtré, utilisateur non
privilégié) est une **obligation de votre fait** et qu'une mauvaise
configuration peut entraîner une compromission de votre système, une perte de
données ou une divulgation d'informations. Vous assumez seul ce risque.

## 4. Usage autorisé

Vous vous engagez à n'utiliser ce logiciel que :
- sur des paquets que vous êtes en droit d'analyser ;
- dans un environnement dont vous êtes propriétaire ou pour lequel vous disposez
  d'une autorisation écrite ;
- conformément aux lois applicables, notamment en matière d'accès aux systèmes
  informatiques, d'interception de communications et de protection des données.

Toute utilisation contre un système tiers sans autorisation est expressément
prohibée.

## 5. Absence d'incitation

Rien dans ce dépôt ne constitue une incitation, une instruction ou une aide à
commettre une infraction. Les sondes fournies sont des paquets de test inertes,
destinés à mesurer la capacité d'observation d'un environnement isolé, et
n'exfiltrent aucune donnée réelle.

## 6. Limitation de responsabilité

DANS TOUTE LA MESURE PERMISE PAR LA LOI APPLICABLE, LES AUTEURS, CONTRIBUTEURS ET
DISTRIBUTEURS NE POURRONT ÊTRE TENUS RESPONSABLES D'AUCUN DOMMAGE DIRECT,
INDIRECT, ACCESSOIRE, SPÉCIAL, EXEMPLAIRE OU IMMATÉRIEL, NI D'AUCUNE PERTE
D'EXPLOITATION, DE DONNÉES, DE CLIENTÈLE OU DE PROFITS, RÉSULTANT DE L'USAGE OU
DE L'IMPOSSIBILITÉ D'UTILISER CE LOGICIEL, MÊME S'ILS ONT ÉTÉ INFORMÉS DE LA
POSSIBILITÉ DE TELS DOMMAGES.

## 7. Indemnisation

Vous vous engagez à indemniser, défendre et dégager de toute responsabilité les
auteurs, contributeurs et distributeurs contre toute réclamation, action,
dommage, perte, responsabilité, coût ou frais (y compris honoraires d'avocat
raisonnables) résultant de votre usage du logiciel, de votre violation des
présentes conditions ou de votre violation de droits de tiers.

## 8. Loi applicable et juridictions

Les présentes conditions sont régies par le droit français, sans préjudice des
dispositions impératives protégeant les consommateurs dans votre pays de
résidence habituelle.

| Situation | Juridiction compétente |
|---|---|
| Utilisateur professionnel établi en France | Tribunaux compétents de Paris, France |
| Utilisateur professionnel établi dans l'Union européenne | Juridiction du siège du défendeur, droit français applicable |
| Utilisateur établi hors Union européenne | Juridiction du siège du défendeur, droit français applicable |
| Litige de consommation | Juridiction du domicile du consommateur (règles impératives) |

## 9. Arbitrage et renonciation aux recours collectifs

Dans les limites permises par le droit applicable, tout litige né de l'usage de
ce logiciel sera soumis à un arbitrage individuel. **Vous renoncez à toute
action collective ou recours collectif** (« class action », « action de groupe »)
à l'encontre des auteurs, contributeurs ou distributeurs.

Cette renonciation ne s'applique pas là où la loi l'interdit, notamment aux
consommateurs de l'Union européenne bénéficiant de dispositions impératives.

## 10. Réglementation des États-Unis — annexe

Pour les utilisateurs soumis au droit des États-Unis : ce logiciel est fourni
« commercial computer software » au sens du FAR 12.212 et du DFARS 227.7202. Son
usage, sa modification et sa distribution sont soumis aux présentes conditions.
Les dispositions de la section 6 (limitation de responsabilité) et de la
section 9 (arbitrage et renonciation aux recours collectifs) s'appliquent dans
toute la mesure permise par le droit fédéral et étatique applicable ; certaines
juridictions interdisent la limitation de responsabilité pour dol ou dommage
corporel, et ces limitations ne s'y appliquent pas.

## 11. Divisibilité et intégralité

Si une clause est jugée nulle ou inapplicable, elle sera réputée divisible et
n'affectera pas les autres clauses. Les présentes conditions constituent
l'intégralité de l'accord entre les parties quant à ce logiciel.

## 12. Acceptation au moment de l'exécution

L'exécution des scripts de ce dépôt vaut acceptation. Pour un usage industrialisé,
il est recommandé d'enregistrer une acceptation versionnée (horodatage, empreinte
du dépôt, version des présentes conditions) au démarrage de chaque exécution.
