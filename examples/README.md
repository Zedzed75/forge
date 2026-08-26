# Exemples

**Un projet n'a pas besoin de tout.** Il peut n'avoir besoin que d'un chart
Helm, ou que de rôles et de playbooks Ansible, ou que d'un socle Terraform. Ce
répertoire montre les quatre cas, et c'est le choix de l'utilisateur qui les
distingue — rien d'autre.

| Exemple | Produit | Pour qui |
| --- | --- | --- |
| [`ansible-seul.yml`](ansible-seul.yml) | `ansible/` | des machines à configurer, aucun conteneur |
| [`helm-seul.yml`](helm-seul.yml) | `helm/` | un cluster qui existe déjà, un service à empaqueter |
| [`terraform-seul.yml`](terraform-seul.yml) | `terraform/` | une équipe plateforme qui prépare le terrain |
| [`socle-et-chart.yml`](socle-et-chart.yml) | `terraform/` **et** `helm/` | le socle et ce qui s'y pose, ensemble |

```bash
forge generate -s examples/helm-seul.yml -o /tmp/boutique
```

## Comment se fait le choix

Trois façons, et elles se combinent :

**1. Une section absente ne génère rien.** C'est le mécanisme de base, sans
exception. `ansible-seul.yml` ne contient pas de section `helm:` : aucun chart
n'est produit. Il n'y a pas d'option à passer, pas de drapeau à désactiver.

**2. `--only` restreint une exécution.** Sur un projet qui déclare deux
domaines, pour n'en régénérer qu'un :

```bash
forge generate -s examples/socle-et-chart.yml -o /tmp/inventaire --only helm
```

`--only` restreint toujours, il n'ajoute jamais : demander un domaine que la
spécification ne déclare pas ne le fait pas apparaître.

**3. L'entretien demande lesquels produire.** `forge new` pose la question avant
d'écrire quoi que ce soit, et n'interroge ensuite que sur les domaines retenus.

```bash
forge new -o /tmp/mon-service
```

## Savoir ce qui va sortir, avant que ça sorte

```bash
forge plugins -s examples/helm-seul.yml
```

dit, pour cette spécification, quels domaines sont demandés et lesquels ne le
sont pas. Et `forge generate --dry-run` annonce ce qu'il produirait sans rien
écrire.

Si une spécification ne déclare aucun domaine, forge ne produit pas un projet
vide en silence : il dit lesquels sont disponibles et comment en demander un.

## Ajouter un domaine à un projet existant

Ajoutez sa section à `forge.yml`, puis :

```bash
forge generate --only terraform
```

Les domaines déjà générés ne sont pas touchés. À l'inverse, retirer une section
n'efface rien : forge n'a jamais supprimé de fichier que vous avez pu modifier —
`forge diff` vous montre l'écart, la suppression reste la vôtre.

## Ces exemples sont testés

`tests/test_choix_des_domaines.py` génère chacun de ces fichiers et vérifie
qu'il produit exactement les domaines qu'il déclare, ni plus ni moins. Il
vérifie aussi qu'**un exemple mono-domaine existe pour chaque domaine livré** :
un domaine ajouté sans le sien fait échouer la suite. Un exemple périmé n'est
pas possible ici.
