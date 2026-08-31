# Module Terraform « boutique »

Boutique en ligne, chaine complete

> Fichier généré par forge. Ne l'éditez pas à la main : modifiez `forge.yml` à
> la racine du projet, puis relancez `forge generate` — ou `forge update` pour
> ne recevoir que les évolutions du gabarit.

Ce module pose **le socle** sur lequel le service est déployé : le
cloisonnement, son budget, l'identité qui y déploie. Il ne déploie **pas** la
charge applicative — c'est le rôle d'un chart Helm, qui vise le namespace que ce
module expose en sortie.

Il ne configure aucun provider : c'est la racine appelante
(`environments/<env>/`) qui décide du cluster visé. Le module reste donc
appelable depuis n'importe quelle racine.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `versions.tf` | Version de Terraform et providers exiges par le module. |
| `variables.tf` | Toutes les entrees du module, chacune commentee. |
| `locals.tf` | Valeurs calculees : namespace effectif, labels communs. |
| `outputs.tf` | Ce que le module rend a son appelant. |
| `README.md` | Role du module, entrees, sorties et pieges de chaque famille. |
| `namespace.tf` | Cree le namespace dans lequel le service est deploye (kubernetes_namespace). |
| `quota.tf` | ResourceQuota et LimitRange : le budget du namespace (kubernetes_resource_quota, kubernetes_limit_range). |

## Entrées

| Variable | Type | Obligatoire | Défaut |
| --- | --- | --- | --- |
| `service_name` | `string` | **oui** | — |
| `environment` | `string` | **oui** | — |
| `namespace` | `string` | **oui** | — |
| `labels` | `map(string)` | non | `{}` |
| `annotations` | `map(string)` | non | `{}` |
| `quota_cpu` | `string` | non | `"4"` |
| `quota_memory` | `string` | non | `"8Gi"` |
| `quota_pods` | `number` | non | `30` |
| `limit_range_default_cpu` | `string` | non | `"500m"` |
| `limit_range_default_memory` | `string` | non | `"512Mi"` |

Chaque variable est commentée dans `variables.tf`, avec son usage et ses
valeurs admises.

## Sorties

| Sortie | Rôle |
| --- | --- |
| `namespace` | Namespace dans lequel le service est deploye. |
| `resource_quota_name` | Nom du ResourceQuota pose sur le namespace. |

## Familles de ressources retenues

### `namespace` — Cree le namespace dans lequel le service est deploye

Pose le cloisonnement lui-meme, avec les labels app.kubernetes.io du service. C'est la famille pivot : les autres s'y rattachent par reference, ce qui donne a Terraform l'ordre de creation sans aucun depends_on explicite.

Absente, le module suppose le namespace deja cree par l'equipe plateforme et se contente de s'y rattacher par son nom.

Pose : `kubernetes_namespace`.

Points de vigilance :

- `terraform destroy` supprime le namespace, donc **tout** ce qu'il contient — y compris ce qu'un chart Helm y a deploye et que Terraform ne connait pas. La destruction deborde du perimetre.
- Changer le nom du namespace le detruit et le recree (comportement ForceNew) : le contenu est perdu, sans avertissement autre que la ligne de plan.
- Un namespace en cours de suppression reste en phase Terminating tant qu'un finalizer n'a pas rendu la main ; Terraform attend, et l'attente ressemble a un blocage.

### `quota` — ResourceQuota et LimitRange : le budget du namespace

Plafonne ce que le namespace peut consommer et donne une taille par defaut aux conteneurs qui n'en declarent pas.

C'est la famille qui a le plus d'effet sur les autres domaines : des qu'un ResourceQuota porte sur cpu ou memory, l'API refuse tout pod dont un conteneur n'a pas de `resources.requests`.

Pose : `kubernetes_resource_quota`, `kubernetes_limit_range`.

Points de vigilance :

- Des qu'un quota porte sur `requests.cpu` ou `requests.memory`, **tout** pod sans `resources.requests` est refuse a l'admission. Le chart Helm du meme service doit donc declarer ses requests, sinon le deploiement casse le jour ou le quota est pose.
- Le LimitRange ne s'applique qu'aux pods **crees apres** lui : les pods deja en place gardent leur configuration, et l'ecart ne se voit qu'au redemarrage suivant.
- Un quota reduit sous la consommation courante n'expulse rien : il bloque seulement les creations suivantes. Le namespace parait sain jusqu'au prochain deploiement.

## Ce que ce module ne fait pas

- **Il ne déploie pas l'application.** Le namespace qu'il expose est destiné à
  recevoir un chart Helm ou un manifeste ; les deux se rencontrent sur le nom du
  namespace, pas sur autre chose.
- **Il ne gère aucun secret réel.** Les valeurs secrètes arrivent par
  `TF_VAR_<nom>` ; celles qu'il engendre lui-même vivent dans l'état Terraform,
  qu'il faut donc chiffrer.
- **Il n'accorde aucun droit à l'échelle du cluster.** Un `Role` ne porte que
  dans son namespace, et c'est délibéré.
