# Module Terraform « boutique »

Boutique en ligne, socle d'infrastructure

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
| `registry_secret.tf` | Secret de tirage d'image pour un registre prive (kubernetes_secret). |
| `service_account.tf` | ServiceAccount, Role et RoleBinding pour les deploiements (kubernetes_service_account, kubernetes_role, kubernetes_role_binding). |
| `network_policy.tf` | Ferme le namespace par defaut, et rouvre le strict necessaire (kubernetes_network_policy). |
| `random_secret.tf` | Mots de passe engendres, deposes en Secret (random_password, kubernetes_secret). |
| `tls_certificate.tf` | Certificat auto-signe des environnements de travail (tls_private_key, tls_self_signed_cert, kubernetes_secret). |

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
| `registry_server` | `string` | non | `"https://index.docker.io/v1/"` |
| `registry_username` | `string` | non | `""` |
| `registry_password` | `string` | **oui** | — *(secrète : `TF_VAR_registry_password`)* |
| `service_account_name` | `string` | non | `""` |
| `ingress_namespace_labels` | `map(string)` | non | `{ "kubernetes.io/metadata.name" = "ingress-nginx" }` |
| `dns_namespace_labels` | `map(string)` | non | `{ "kubernetes.io/metadata.name" = "kube-system" }` |
| `generated_secret_keys` | `list(string)` | non | `["password"]` |
| `generated_secret_length` | `number` | non | `32` |
| `tls_common_name` | `string` | non | `""` |
| `tls_dns_names` | `list(string)` | non | `[]` |
| `tls_validity_hours` | `number` | non | `8760` |
| `tls_early_renewal_hours` | `number` | non | `720` |

Chaque variable est commentée dans `variables.tf`, avec son usage et ses
valeurs admises.

## Sorties

| Sortie | Rôle |
| --- | --- |
| `namespace` | Namespace dans lequel le service est deploye. |
| `resource_quota_name` | Nom du ResourceQuota pose sur le namespace. |
| `image_pull_secret_name` | Nom du Secret a citer dans imagePullSecrets, cote chart Helm. |
| `service_account_name` | Nom du ServiceAccount de deploiement. |
| `generated_secret_name` | Nom du Secret portant les valeurs engendrees. Sa valeur n'est pas exposee en sortie. |
| `tls_secret_name` | Nom du Secret kubernetes.io/tls a citer dans l'Ingress. |

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

### `registry_secret` — Secret de tirage d'image pour un registre prive

Pose un Secret `kubernetes.io/dockerconfigjson` que les pods referencent en `imagePullSecrets`. Les identifiants ne sont **jamais** ecrits dans la specification ni dans les fichiers generes : ils arrivent par TF_VAR_registry_password.

Pose : `kubernetes_secret`.

Points de vigilance :

- La cle du Secret doit etre exactement `.dockerconfigjson`, point initial compris, et la valeur un document complet `{"auths": {...}}`. Une cle `auths` nue est acceptee par Terraform et rejetee par kubelet au premier tirage.
- Le provider encode `data` en base64 lui-meme ; y passer une valeur deja encodee la double-encode en silence. C'est `data`, pas `binary_data`, qui recoit du texte clair.
- Le champ `auth` du document est le couple `utilisateur:motdepasse` en base64 — un encodage, pas un chiffrement. Quiconque lit l'etat Terraform ou le Secret lit le mot de passe.
- Un imagePullSecret ne vaut que dans son namespace : un service deploye dans plusieurs namespaces a besoin d'un Secret par namespace.

### `service_account` — ServiceAccount, Role et RoleBinding pour les deploiements

Donne a la chaine de deploiement une identite propre dans le namespace, avec les droits strictement necessaires a un `helm upgrade` : lire et ecrire les objets applicatifs, rien de plus. Aucun droit cluster-scoped n'est accorde.

Pose : `kubernetes_service_account`, `kubernetes_role`, `kubernetes_role_binding`.

Points de vigilance :

- Depuis Kubernetes 1.24, aucun Secret de jeton n'est cree automatiquement pour un ServiceAccount : `default_secret_name` est vide. Un jeton durable exige un Secret `kubernetes.io/service-account-token` declare explicitement — preferez un jeton court obtenu par `kubectl create token`.
- Dans un `subject` de RoleBinding, un ServiceAccount veut `api_group = ""` ; c'est `rbac.authorization.k8s.io` qui vaut pour un User ou un Group. L'inverse est accepte par Terraform et rejete par l'API au moment d'appliquer.
- Un Role ne porte que dans son namespace. Les objets cluster-scoped — CustomResourceDefinition, StorageClass — resteront inaccessibles, ce qui est voulu.

### `network_policy` — Ferme le namespace par defaut, et rouvre le strict necessaire

Pose une politique deny-by-default sur tout le namespace, puis rouvre ce sans quoi rien ne fonctionne : la resolution DNS, et le trafic entrant venant du namespace de l'ingress controller.

Sans plugin reseau qui les applique (Calico, Cilium, Antrea), une NetworkPolicy est acceptee par l'API et **sans aucun effet** : le namespace parait protege et ne l'est pas.

Pose : `kubernetes_network_policy`.

Points de vigilance :

- Une politique deny-by-default sans regle d'egress vers le DNS (port 53, UDP **et** TCP) casse toute resolution de nom dans le namespace. La panne se presente comme une lenteur applicative, pas comme un probleme reseau.
- `pod_selector {}` vide selectionne **tous** les pods du namespace. C'est exactement ce qu'on veut pour un deny-by-default, et exactement ce qu'on ne veut pas dans une regle d'ouverture.
- Dans une regle `from`, `namespace_selector` et `pod_selector` dans un **meme** bloc forment un ET ; dans deux blocs separes, un OU. L'ecart entre les deux est une ouverture bien plus large que prevu, et rien ne le signale.
- Les sondes du kubelet viennent du noeud, pas d'un pod : une regle d'ingress trop stricte fait echouer les probes et redemarre le service en boucle.

### `random_secret` — Mots de passe engendres, deposes en Secret

Engendre un mot de passe par cle demandee et les depose dans un Secret unique. Aucune valeur secrete n'entre dans forge.yml ni dans un fichier genere : c'est le point de la famille.

Pose : `random_password`, `kubernetes_secret`.

Points de vigilance :

- `random_password` conserve la valeur **en clair dans l'etat Terraform**. Le backend d'etat doit donc etre chiffre et son acces restreint : le mot de passe n'est pas plus secret que l'etat.
- Sans `keepers`, la valeur ne change jamais — ce qui est le comportement voulu, mais interdit toute rotation. Faire tourner un mot de passe demande de modifier un keeper, pas de detruire la ressource.
- `random_password` produit par defaut des caracteres speciaux qui cassent les URL de connexion (`@`, `/`, `:`). D'ou `override_special` restreint dans le code genere.
- Le service qui lit ce Secret ne le relit pas tout seul : un Secret monte en volume est rafraichi avec du retard, un Secret injecte en variable d'environnement ne l'est **jamais** avant un redemarrage.

### `tls_certificate` — Certificat auto-signe des environnements de travail

Fabrique une cle privee et un certificat auto-signe, deposes en Secret `kubernetes.io/tls` pret a etre reference par un Ingress.

**Pour les environnements de travail uniquement.** En production, un certificat auto-signe est refuse par tout client serieux : employez cert-manager ou un certificat emis par une autorite reconnue. Le code genere le rappelle en commentaire.

Pose : `tls_private_key`, `tls_self_signed_cert`, `kubernetes_secret`.

Points de vigilance :

- Le certificat expire sans rien signaler : Terraform ne le reengendre qu'au prochain apply, et seulement si `early_renewal_hours` est atteint. Un projet applique deux fois par an avec un certificat d'un an tombe en panne.
- La cle privee est stockee **en clair dans l'etat**, comme toute ressource du provider tls.
- Les navigateurs ignorent le Common Name depuis 2017 : un certificat sans `dns_names` correspondant a l'hote est refuse, quel que soit son CN.
- Un Secret `kubernetes.io/tls` exige exactement les deux cles `tls.crt` et `tls.key`. Toute autre nomenclature est acceptee par l'API et ignoree par l'ingress controller.

## Ce que ce module ne fait pas

- **Il ne déploie pas l'application.** Le namespace qu'il expose est destiné à
  recevoir un chart Helm ou un manifeste ; les deux se rencontrent sur le nom du
  namespace, pas sur autre chose.
- **Il ne gère aucun secret réel.** Les valeurs secrètes arrivent par
  `TF_VAR_<nom>` ; celles qu'il engendre lui-même vivent dans l'état Terraform,
  qu'il faut donc chiffrer.
- **Il n'accorde aucun droit à l'échelle du cluster.** Un `Role` ne porte que
  dans son namespace, et c'est délibéré.
