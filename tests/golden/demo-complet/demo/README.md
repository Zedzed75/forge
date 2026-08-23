# Domaine demo — boutique

== boutique ==

Boutique en ligne de demonstration

Ce repertoire est genere par **forge**, domaine `demo`. Il n'a aucune valeur
operationnelle : il existe pour que la suite de tests du coeur exerce, sur un
domaine reel mais trivial, les mecanismes que les domaines Ansible et Helm
utiliseront (balises `yield` imbriquees, filtres de plugin, filtrage de
fichier, fichier de reponses copier).

- **Service** : `boutique` (`BOUTIQUE`)
- **Responsable** : Equipe Plateforme
- **Salutation** : bonjour

## Environnements

| Environnement | Production |
| --- | --- |
| `dev` | non |
| `prod` | oui |

## Widgets

| Widget | Type | Detail |
| --- | --- | --- |
| `cpu` | gauge ~ | oui |
| `requetes` | counter # | non |

Un fichier est genere par couple (environnement, widget) dans `environments/`,
et un fichier de detail par widget marque `detailed: true` dans `widgets/`.
