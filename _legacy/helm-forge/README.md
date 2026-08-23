# helm-forge

Générateur déterministe de projets Kubernetes/Helm complets et entièrement
commentés, à partir d'une spécification (`forge.yml`).

Aucun appel à un modèle de langage ni à une API externe : tout est produit par
rendu de gabarits Jinja2. Deux spécifications identiques produisent deux projets
identiques, octet pour octet.

> Projet en cours de construction. Ce README sera complété à l'étape 6 avec les
> exemples d'utilisation complets.

## Installation (développement)

```bash
python3 -m venv ~/.venvs/helm-forge
~/.venvs/helm-forge/bin/pip install -e ".[dev]"
```

## Outils externes attendus

| Outil | Version de référence | Usage |
|---|---|---|
| `helm` | 4.2.4 | `helm lint`, `helm template` |
| `kubeconform` | 0.8.0 | validation stricte des manifestes rendus |

## Tests

```bash
~/.venvs/helm-forge/bin/pytest
```

## Documentation

- [Document de conception](docs/DESIGN.md) — questions du CLI, arborescence
  générée, architecture de l'outil et décisions retenues.
- [CLAUDE.md](CLAUDE.md) — conventions du projet.
