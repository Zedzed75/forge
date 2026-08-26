# forge

Generateur deterministe de projets d'infrastructure complets et commentes
(Ansible, Helm, Terraform, et d'autres domaines ensuite) a partir d'une
seule specification `forge.yml`.

> **Etat** : en construction. Le coeur et les domaines **Ansible**, **Helm** et
> **Terraform** sont livres et valides par leurs outils reels. Les domaines
> **pipeline** et **monitoring** prevus par l'architecture restent a ecrire.
> La documentation complete — architecture, guide d'ecriture de plugin,
> exemples — arrive en derniere phase. Voir `PLAN.md` pour l'avancement et
> `DESIGN.md` pour l'architecture.

## Un projet n'a pas besoin de tout

Un projet peut n'avoir besoin que d'un chart Helm. Un autre, que de roles et de
playbooks Ansible. Un troisieme, que d'un socle Terraform. **C'est vous qui
choisissez**, et forge ne produit rien d'autre.

```bash
forge generate -s examples/helm-seul.yml       -o /tmp/boutique    # helm/ seul
forge generate -s examples/ansible-seul.yml    -o /tmp/passerelle  # ansible/ seul
forge generate -s examples/terraform-seul.yml  -o /tmp/socle       # terraform/ seul
```

Ces quatre exemples sont commites et testes : voir [`examples/`](examples/).

| Domaine | Section `forge.yml` | Produit | Valide par |
| --- | --- | --- | --- |
| Ansible | `ansible:` | `ansible/` — inventaires, playbooks, roles | `ansible-playbook --syntax-check`, `ansible-lint` |
| Helm | `helm:` | `helm/` — chart complet et values par environnement | `helm lint`, `helm template`, `kubeconform -strict` |
| Terraform | `terraform:` | `terraform/` — module et racine par environnement | `terraform fmt`, `validate`, `tflint` |

Trois facons de choisir :

| Vous voulez | Vous faites |
| --- | --- |
| un seul domaine | n'ecrivez que sa section dans `forge.yml` — une section absente ne genere rien |
| une execution restreinte | `forge generate --only helm` |
| decider a la creation | `forge new` demande quels domaines produire |

`--only` **restreint** toujours, il n'ajoute jamais : demander un domaine que la
specification ne declare pas est une erreur nommee, pas une generation vide.

`forge plugins -s forge.yml` dit quels domaines sont demandes et lesquels ne le
sont pas ; `forge generate --dry-run` annonce ce qu'il produirait sans rien
ecrire. Une specification qui ne declare aucun domaine ne produit pas un projet
vide en silence : forge dit lesquels sont disponibles et comment en demander un.

Demander plusieurs domaines a la fois est **un** usage possible — forge verifie
alors qu'ils restent coherents entre eux — pas l'usage normal. Terraform cree le
namespace, Helm y deploie : si les deux ne s'accordent pas sur son nom,
`forge validate` le dit.

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
| `forge new` | entretien interactif — **demande quels domaines generer** — ecrit `forge.yml` puis genere |
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
