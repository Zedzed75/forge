# Socle Terraform — boutique

Boutique en ligne, socle d'infrastructure

Responsable : Equipe Plateforme (plateforme@example.net)
> Projet généré par forge. Ne l'éditez pas à la main : modifiez `forge.yml` à la
> racine, puis `forge generate`. Pour ne recevoir que les évolutions du gabarit
> sans perdre vos modifications, `forge update --only terraform`.

## Ce que ce projet pose, et ce qu'il ne pose pas

Ce projet pose **le socle** : le cloisonnement dans lequel le service vit, son
budget, l'identité qui y déploie, ce qui y entre et en sort. Il ne déploie pas
l'application — c'est le rôle d'un chart Helm ou d'un manifeste, qui vise le
namespace exposé ici en sortie.

Familles retenues :

- **`namespace`** — Cree le namespace dans lequel le service est deploye.
- **`quota`** — ResourceQuota et LimitRange : le budget du namespace.
- **`registry_secret`** — Secret de tirage d'image pour un registre prive.
- **`service_account`** — ServiceAccount, Role et RoleBinding pour les deploiements.
- **`network_policy`** — Ferme le namespace par defaut, et rouvre le strict necessaire.
- **`random_secret`** — Mots de passe engendres, deposes en Secret.
- **`tls_certificate`** — Certificat auto-signe des environnements de travail.

Le catalogue complet, avec les pièges de chaque famille, se consulte par
`forge catalog terraform` et `forge catalog terraform <famille>`.

## Disposition

Un module écrit **une fois**, appelé **une fois par environnement**. C'est ce
qui garantit que `dev` et `prod`
posent les mêmes objets, aux valeurs près.

```
.copier-answers.yml
.gitignore
.tflint.hcl
Makefile
README.md
modules/boutique/
  versions.tf
  variables.tf
  locals.tf
  outputs.tf
  README.md
  namespace.tf
  quota.tf
  registry_secret.tf
  service_account.tf
  network_policy.tf
  random_secret.tf
  tls_certificate.tf
environments/
  dev/
    versions.tf
    backend.tf
    providers.tf
    variables.tf
    main.tf
    outputs.tf
    terraform.tfvars
  staging/
    versions.tf
    backend.tf
    providers.tf
    variables.tf
    main.tf
    outputs.tf
    terraform.tfvars
  prod/
    versions.tf
    backend.tf
    providers.tf
    variables.tf
    main.tf
    outputs.tf
    terraform.tfvars
```

| Fichier de la racine | Rôle |
| --- | --- |
| `.copier-answers.yml` | Reponses du gabarit, relues par `forge update`. Ne pas editer. |
| `.gitignore` | Exclut l'etat, les plans et le cache de providers. L'etat porte des valeurs en clair : il ne doit jamais etre committe. |
| `.tflint.hcl` | Jeu de regles tflint applique au projet. |
| `Makefile` | Raccourcis : `make init ENV=prod`, `make plan ENV=prod`. |
| `README.md` | Ce fichier : comment employer le projet. |

| Fichier d'un environnement | Rôle |
| --- | --- |
| `versions.tf` | Version de Terraform et providers exiges par cette racine. |
| `backend.tf` | Ou l'etat de cet environnement est conserve. |
| `providers.tf` | Configuration des providers : cluster vise, contexte. |
| `variables.tf` | Entrees de la racine, reprises de celles du module. |
| `main.tf` | Appel du module, avec les valeurs de cet environnement. |
| `outputs.tf` | Sorties remontees depuis le module. |
| `terraform.tfvars` | Valeurs de cet environnement. Aucune valeur secrete. |

## Environnements

| Environnement | Namespace | Contexte kubeconfig | État |
| --- | --- | --- | --- |
| `dev` | `boutique-dev` | `dev` | `s3` |
| `staging` | `boutique-staging` | `staging` | `s3` |
| `prod` **(production)** | `boutique-prod` | `plateforme-prod-eu-west-3` | `s3` |

Les namespaces sont dérivés selon la stratégie `per_env`.
Terraform **crée** ces namespaces.

## Employer le projet

Avec `make` :

```bash
make init  ENV=dev
make plan  ENV=dev
make apply ENV=dev
```

Sans `make`, ou pour une commande que le Makefile ne couvre pas :

```bash
terraform -chdir=environments/dev init -input=false
terraform -chdir=environments/dev plan -input=false
terraform -chdir=environments/dev apply -input=false
```

Validation, sans toucher à aucune infrastructure :

```bash
terraform fmt -check -recursive
terraform -chdir=environments/dev init -backend=false
terraform -chdir=environments/dev validate
tflint --recursive
```

`forge validate` enchaîne exactement ces commandes sur chaque environnement.

## Valeurs secrètes

**Aucun fichier de ce projet ne porte de valeur secrète**, et cela ne changera
pas : `terraform.tfvars` est versionné.

Les variables suivantes n'ont pas de valeur par défaut et se fournissent par
variable d'environnement :

- `TF_VAR_registry_password` — Mot de passe ou jeton du registre. Sans valeur par defaut et absent de terraform.tfvars : fournissez-le par TF_VAR_registry_password.

Les identifiants d'accès au stockage d'état, eux, se passent à l'initialisation
(`terraform init -backend-config="..."`) ou par les variables d'environnement du
fournisseur.

## Ce qu'il faut savoir avant d'appliquer

- **`terraform destroy` déborde du périmètre.** Supprimer le namespace supprime
  tout ce qu'il contient, y compris ce qu'un chart Helm y a déployé et que
  Terraform ne connaît pas.
- **L'état porte des valeurs en clair.** Mots de passe engendrés, clés privées :
  l'état les contient. Le `.gitignore` l'exclut du dépôt ; en équipe, un backend
  chiffré et verrouillé est une condition, pas une amélioration.
- **Vérifiez le contexte avant d'appliquer.** Sans `config_context`, Terraform
  part vers le cluster que le kubeconfig de la machine désigne au moment de la
  commande. La variable `kube_context` de chaque `terraform.tfvars` existe pour
  l'éviter.
