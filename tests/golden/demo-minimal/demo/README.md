# Domaine demo — api

== api ==

Service minimal

Ce repertoire est genere par **forge**, domaine `demo`. Il n'a aucune valeur
operationnelle : il existe pour que la suite de tests du coeur exerce, sur un
domaine reel mais trivial, les mecanismes que les domaines Ansible et Helm
utiliseront (balises `yield` imbriquees, filtres de plugin, filtrage de
fichier, fichier de reponses copier).

- **Service** : `api` (`API`)
- **Responsable** : Equipe Plateforme
- **Salutation** : bonjour

## Environnements

| Environnement | Production |
| --- | --- |
| `prod` | oui |

## Widgets

| Widget | Type | Detail |
| --- | --- | --- |
| `sante` | log > | non |

Un fichier est genere par couple (environnement, widget) dans `environments/`,
et un fichier de detail par widget marque `detailed: true` dans `widgets/`.
