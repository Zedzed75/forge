# forge

Generateur deterministe de projets d'infrastructure complets et commentes
(Ansible, Helm, et d'autres domaines ensuite) a partir d'une seule
specification `forge.yml`.

> **Etat** : en construction. Le coeur (phase 2) est en place ; les plugins
> Ansible et Helm arrivent aux phases 3 et 4. La documentation complete —
> architecture, guide d'ecriture de plugin, exemples — est ecrite en phase 6.
> Voir `PLAN.md` pour l'avancement et `DESIGN.md` pour l'architecture.

## Principes

- **Le coeur ne connait aucun domaine.** Il sait charger une specification,
  appeler copier et executer des validateurs ; SSH, namespaces et charts
  n'existent que dans les plugins.
- **Un plugin par domaine**, branche par des hooks pluggy. Ajouter un domaine
  ne demande de modifier aucun fichier du coeur.
- **copier fait le rendu**, toujours : aucune ecriture de fichier genere en
  dur, et donc `forge update` fonctionne sur un projet deja livre.
- **Meme specification, meme sortie**, octet pour octet. Des tests golden
  l'imposent.
- **Tout fichier genere s'explique** : en-tete de fichier, noms explicites,
  commentaire sur chaque variable exposee a l'utilisateur.

## Installation (developpement)

```bash
uv venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
```

Sous Linux et macOS, remplacez `.venv/Scripts/python.exe` par
`.venv/bin/python`. Si `uv` n'est pas sur le PATH, il s'installe avec
`python -m pip install uv` puis s'invoque par `python -m uv`.

## Commandes

| Commande | Role |
| --- | --- |
| `forge new` | entretien interactif, ecrit `forge.yml` puis genere |
| `forge generate` | rejoue une specification existante |
| `forge validate` | validateurs de chaque domaine + coherence inter-domaines |
| `forge update` | applique les evolutions de gabarit (`copier update`) |
| `forge diff` | resume l'ecart entre la cible et un rendu neuf |
| `forge plugins` | domaines enregistres et etat des outils externes |
| `forge catalog <domaine>` | catalogue publie par un plugin |

## Tests

```bash
.venv/Scripts/python.exe -m pytest
```

Les references golden se regenerent avec `-m pytest --regen-golden`, a ne faire
qu'apres avoir constate que l'ecart est voulu : la commande **enterine** la
sortie courante, elle ne la verifie pas.

Un test est ignore tant que le depot porte des modifications non committees :
`copier update` compare deux references git, et un rendu fait depuis un arbre de
travail sale reference un commit temporaire introuvable ensuite. Les autres
tests de mise a jour, eux, tournent toujours : ils fabriquent leur propre depot
de gabarit temporaire.
