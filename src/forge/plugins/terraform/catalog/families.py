"""Familles de ressources du domaine Terraform.

Une famille = un fichier `.tf` du module, les ressources qu'il declare, les
variables qu'il ajoute et les pieges qu'il evite. C'est la seule connaissance de
domaine du plugin : le coeur ignore ce qu'est un namespace.

Les **pieges** ne sont pas de la decoration. Chacun explique un choix du code
genere qui paraitrait arbitraire sans lui — pourquoi un quota impose des
`requests` au chart Helm, pourquoi une NetworkPolicy doit ouvrir le DNS,
pourquoi un mot de passe engendre par Terraform impose de chiffrer l'etat. Ils
sont affiches par `forge catalog terraform <famille>` et repris en commentaire
dans les fichiers generes.

Aucune ressource inventee : chaque type cite existe dans le provider annonce.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge.plugins.terraform.enums import ResourceFamily
from forge.plugins.terraform.variables import Variable, optional, required


@dataclass(frozen=True)
class Family:
    """Une famille de ressources retenue ou non par la specification."""

    #: Identifiant employe dans `terraform.resources` de forge.yml.
    name: str

    #: Resume d'une ligne.
    summary: str

    #: Description longue, affichee par `forge catalog terraform <famille>`.
    details: str

    #: Types de ressources Terraform declares par le fichier de la famille.
    resources: tuple[str, ...]

    #: Noms locaux des providers dont elle depend.
    providers: tuple[str, ...]

    #: Variables d'entree qu'elle ajoute au module.
    variables: tuple[Variable, ...] = ()

    #: Sorties du module qu'elle ajoute : nom -> description.
    outputs: dict[str, str] = field(default_factory=dict)

    #: Pieges mesures, affiches et repris en commentaire.
    traps: tuple[str, ...] = ()

    def option_descriptions(self) -> dict[str, str]:
        """Variables de la famille, au format attendu par `CatalogEntry`."""
        return {variable.name: variable.description for variable in self.variables}


#: Pieges communs a toute ressource du provider Kubernetes : ils valent pour
#: chaque famille, les repeter dans chacune serait du bruit.
PROVIDER_TRAPS: tuple[str, ...] = (
    "Dans le provider kubernetes, `metadata` est un bloc **liste** : on ecrit "
    "`metadata[0].name`, jamais `metadata.name`. La seconde forme passe la "
    "validation et echoue au plan.",
    "Sans `config_context`, le provider emploie le contexte *courant* du "
    "kubeconfig de la machine : appliquer en production depuis un poste mal "
    "positionne est l'accident le plus banal de ce provider.",
)


FAMILIES: tuple[Family, ...] = (
    Family(
        name=ResourceFamily.NAMESPACE.value,
        summary="Cree le namespace dans lequel le service est deploye",
        details=(
            "Pose le cloisonnement lui-meme, avec les labels app.kubernetes.io "
            "du service. C'est la famille pivot : les autres s'y rattachent par "
            "reference, ce qui donne a Terraform l'ordre de creation sans "
            "aucun depends_on explicite.\n\n"
            "Absente, le module suppose le namespace deja cree par l'equipe "
            "plateforme et se contente de s'y rattacher par son nom."
        ),
        resources=("kubernetes_namespace",),
        providers=("kubernetes",),
        outputs={"namespace": "Nom du namespace, cree ou repris."},
        traps=(
            "`terraform destroy` supprime le namespace, donc **tout** ce qu'il "
            "contient — y compris ce qu'un chart Helm y a deploye et que "
            "Terraform ne connait pas. La destruction deborde du perimetre.",
            "Changer le nom du namespace le detruit et le recree "
            "(comportement ForceNew) : le contenu est perdu, sans avertissement "
            "autre que la ligne de plan.",
            "Un namespace en cours de suppression reste en phase Terminating "
            "tant qu'un finalizer n'a pas rendu la main ; Terraform attend, et "
            "l'attente ressemble a un blocage.",
        ),
    ),
    Family(
        name=ResourceFamily.QUOTA.value,
        summary="ResourceQuota et LimitRange : le budget du namespace",
        details=(
            "Plafonne ce que le namespace peut consommer et donne une taille "
            "par defaut aux conteneurs qui n'en declarent pas.\n\n"
            "C'est la famille qui a le plus d'effet sur les autres domaines : "
            "des qu'un ResourceQuota porte sur cpu ou memory, l'API refuse "
            "tout pod dont un conteneur n'a pas de `resources.requests`."
        ),
        resources=("kubernetes_resource_quota", "kubernetes_limit_range"),
        providers=("kubernetes",),
        variables=(
            optional(
                "quota_cpu",
                "string",
                "Plafond de CPU demandable dans le namespace, en unites "
                "Kubernetes (ex. '4' pour 4 coeurs, '500m' pour un demi).",
                "4",
                per_environment=True,
            ),
            optional(
                "quota_memory",
                "string",
                "Plafond de memoire demandable, suffixe Kubernetes obligatoire "
                "(Mi, Gi). Un nombre nu serait compris en octets.",
                "8Gi",
                per_environment=True,
            ),
            optional(
                "quota_pods",
                "number",
                "Nombre maximal de pods simultanes dans le namespace.",
                30,
                per_environment=True,
            ),
            optional(
                "limit_range_default_cpu",
                "string",
                "CPU attribue a un conteneur qui n'en demande pas.",
                "500m",
            ),
            optional(
                "limit_range_default_memory",
                "string",
                "Memoire attribuee a un conteneur qui n'en demande pas.",
                "512Mi",
            ),
        ),
        outputs={"resource_quota_name": "Nom du ResourceQuota pose sur le namespace."},
        traps=(
            "Des qu'un quota porte sur `requests.cpu` ou `requests.memory`, "
            "**tout** pod sans `resources.requests` est refuse a l'admission. "
            "Le chart Helm du meme service doit donc declarer ses requests, "
            "sinon le deploiement casse le jour ou le quota est pose.",
            "Le LimitRange ne s'applique qu'aux pods **crees apres** lui : les "
            "pods deja en place gardent leur configuration, et l'ecart ne se "
            "voit qu'au redemarrage suivant.",
            "Un quota reduit sous la consommation courante n'expulse rien : il "
            "bloque seulement les creations suivantes. Le namespace parait "
            "sain jusqu'au prochain deploiement.",
        ),
    ),
    Family(
        name=ResourceFamily.REGISTRY_SECRET.value,
        summary="Secret de tirage d'image pour un registre prive",
        details=(
            "Pose un Secret `kubernetes.io/dockerconfigjson` que les pods "
            "referencent en `imagePullSecrets`. Les identifiants ne sont "
            "**jamais** ecrits dans la specification ni dans les fichiers "
            "generes : ils arrivent par TF_VAR_registry_password."
        ),
        resources=("kubernetes_secret",),
        providers=("kubernetes",),
        variables=(
            optional(
                "registry_server",
                "string",
                "Adresse du registre. Docker Hub exige la forme historique "
                "https://index.docker.io/v1/ ; les autres registres prennent "
                "leur nom d'hote nu.",
                "https://index.docker.io/v1/",
            ),
            optional(
                "registry_username",
                "string",
                "Identifiant de lecture sur le registre. Employez un compte de "
                "service en lecture seule, jamais un compte nominatif.",
                "",
            ),
            required(
                "registry_password",
                "string",
                "Mot de passe ou jeton du registre. Sans valeur par defaut et "
                "absent de terraform.tfvars : fournissez-le par "
                "TF_VAR_registry_password.",
                sensitive=True,
            ),
        ),
        outputs={
            "image_pull_secret_name": (
                "Nom du Secret a citer dans imagePullSecrets, cote chart Helm."
            )
        },
        traps=(
            "La cle du Secret doit etre exactement `.dockerconfigjson`, point "
            "initial compris, et la valeur un document complet `{\"auths\": "
            "{...}}`. Une cle `auths` nue est acceptee par Terraform et rejetee "
            "par kubelet au premier tirage.",
            "Le provider encode `data` en base64 lui-meme ; y passer une valeur "
            "deja encodee la double-encode en silence. C'est `data`, pas "
            "`binary_data`, qui recoit du texte clair.",
            "Le champ `auth` du document est le couple `utilisateur:motdepasse` "
            "en base64 — un encodage, pas un chiffrement. Quiconque lit l'etat "
            "Terraform ou le Secret lit le mot de passe.",
            "Un imagePullSecret ne vaut que dans son namespace : un service "
            "deploye dans plusieurs namespaces a besoin d'un Secret par "
            "namespace.",
        ),
    ),
    Family(
        name=ResourceFamily.SERVICE_ACCOUNT.value,
        summary="ServiceAccount, Role et RoleBinding pour les deploiements",
        details=(
            "Donne a la chaine de deploiement une identite propre dans le "
            "namespace, avec les droits strictement necessaires a un "
            "`helm upgrade` : lire et ecrire les objets applicatifs, rien de "
            "plus. Aucun droit cluster-scoped n'est accorde."
        ),
        resources=(
            "kubernetes_service_account",
            "kubernetes_role",
            "kubernetes_role_binding",
        ),
        providers=("kubernetes",),
        variables=(
            optional(
                "service_account_name",
                "string",
                "Nom du ServiceAccount. Vide, il vaut '<service>-deployer'.",
                "",
            ),
        ),
        outputs={
            "service_account_name": "Nom du ServiceAccount de deploiement.",
        },
        traps=(
            "Depuis Kubernetes 1.24, aucun Secret de jeton n'est cree "
            "automatiquement pour un ServiceAccount : `default_secret_name` est "
            "vide. Un jeton durable exige un Secret "
            "`kubernetes.io/service-account-token` declare explicitement — "
            "preferez un jeton court obtenu par `kubectl create token`.",
            "Dans un `subject` de RoleBinding, un ServiceAccount veut "
            "`api_group = \"\"` ; c'est `rbac.authorization.k8s.io` qui vaut "
            "pour un User ou un Group. L'inverse est accepte par Terraform et "
            "rejete par l'API au moment d'appliquer.",
            "Un Role ne porte que dans son namespace. Les objets "
            "cluster-scoped — CustomResourceDefinition, StorageClass — "
            "resteront inaccessibles, ce qui est voulu.",
        ),
    ),
    Family(
        name=ResourceFamily.NETWORK_POLICY.value,
        summary="Ferme le namespace par defaut, et rouvre le strict necessaire",
        details=(
            "Pose une politique deny-by-default sur tout le namespace, puis "
            "rouvre ce sans quoi rien ne fonctionne : la resolution DNS, et le "
            "trafic entrant venant du namespace de l'ingress controller.\n\n"
            "Sans plugin reseau qui les applique (Calico, Cilium, Antrea), une "
            "NetworkPolicy est acceptee par l'API et **sans aucun effet** : le "
            "namespace parait protege et ne l'est pas."
        ),
        resources=("kubernetes_network_policy",),
        providers=("kubernetes",),
        variables=(
            optional(
                "ingress_namespace_labels",
                "map(string)",
                "Labels du namespace autorise a joindre le service (celui de "
                "l'ingress controller). Vide, seul le trafic interne au "
                "namespace est autorise.",
                {"kubernetes.io/metadata.name": "ingress-nginx"},
            ),
            optional(
                "dns_namespace_labels",
                "map(string)",
                "Labels du namespace hebergeant le service DNS du cluster. "
                "Sans cette ouverture, plus aucun nom ne se resout.",
                {"kubernetes.io/metadata.name": "kube-system"},
            ),
        ),
        outputs={},
        traps=(
            "Une politique deny-by-default sans regle d'egress vers le DNS "
            "(port 53, UDP **et** TCP) casse toute resolution de nom dans le "
            "namespace. La panne se presente comme une lenteur applicative, pas "
            "comme un probleme reseau.",
            "`pod_selector {}` vide selectionne **tous** les pods du namespace. "
            "C'est exactement ce qu'on veut pour un deny-by-default, et "
            "exactement ce qu'on ne veut pas dans une regle d'ouverture.",
            "Dans une regle `from`, `namespace_selector` et `pod_selector` dans "
            "un **meme** bloc forment un ET ; dans deux blocs separes, un OU. "
            "L'ecart entre les deux est une ouverture bien plus large que "
            "prevu, et rien ne le signale.",
            "Les sondes du kubelet viennent du noeud, pas d'un pod : une regle "
            "d'ingress trop stricte fait echouer les probes et redemarre le "
            "service en boucle.",
        ),
    ),
    Family(
        name=ResourceFamily.RANDOM_SECRET.value,
        summary="Mots de passe engendres, deposes en Secret",
        details=(
            "Engendre un mot de passe par cle demandee et les depose dans un "
            "Secret unique. Aucune valeur secrete n'entre dans forge.yml ni "
            "dans un fichier genere : c'est le point de la famille."
        ),
        resources=("random_password", "kubernetes_secret"),
        providers=("random", "kubernetes"),
        variables=(
            optional(
                "generated_secret_keys",
                "list(string)",
                "Cles a engendrer dans le Secret (ex. ['database-password', "
                "'api-token']). Une valeur aleatoire est produite par cle.",
                ["password"],
            ),
            optional(
                "generated_secret_length",
                "number",
                "Longueur de chaque valeur engendree, en caracteres.",
                32,
            ),
        ),
        outputs={
            "generated_secret_name": (
                "Nom du Secret portant les valeurs engendrees. Sa valeur n'est "
                "pas exposee en sortie."
            )
        },
        traps=(
            "`random_password` conserve la valeur **en clair dans l'etat "
            "Terraform**. Le backend d'etat doit donc etre chiffre et son acces "
            "restreint : le mot de passe n'est pas plus secret que l'etat.",
            "Sans `keepers`, la valeur ne change jamais — ce qui est le "
            "comportement voulu, mais interdit toute rotation. Faire tourner un "
            "mot de passe demande de modifier un keeper, pas de detruire la "
            "ressource.",
            "`random_password` produit par defaut des caracteres speciaux qui "
            "cassent les URL de connexion (`@`, `/`, `:`). D'ou "
            "`override_special` restreint dans le code genere.",
            "Le service qui lit ce Secret ne le relit pas tout seul : un Secret "
            "monte en volume est rafraichi avec du retard, un Secret injecte en "
            "variable d'environnement ne l'est **jamais** avant un "
            "redemarrage.",
        ),
    ),
    Family(
        name=ResourceFamily.TLS_CERTIFICATE.value,
        summary="Certificat auto-signe des environnements de travail",
        details=(
            "Fabrique une cle privee et un certificat auto-signe, deposes en "
            "Secret `kubernetes.io/tls` pret a etre reference par un Ingress.\n\n"
            "**Pour les environnements de travail uniquement.** En production, "
            "un certificat auto-signe est refuse par tout client serieux : "
            "employez cert-manager ou un certificat emis par une autorite "
            "reconnue. Le code genere le rappelle en commentaire."
        ),
        resources=("tls_private_key", "tls_self_signed_cert", "kubernetes_secret"),
        providers=("tls", "kubernetes"),
        variables=(
            optional(
                "tls_common_name",
                "string",
                "Nom porte par le certificat (CN). Vide, il vaut le premier "
                "nom de tls_dns_names.",
                "",
                per_environment=True,
            ),
            optional(
                "tls_dns_names",
                "list(string)",
                "Noms DNS couverts par le certificat (SAN). Les navigateurs "
                "ignorent le CN depuis longtemps : c'est cette liste qui "
                "compte.",
                [],
                per_environment=True,
            ),
            optional(
                "tls_validity_hours",
                "number",
                "Duree de validite du certificat, en heures (8760 = un an).",
                8760,
            ),
            optional(
                "tls_early_renewal_hours",
                "number",
                "Delai avant expiration a partir duquel un apply reengendre le "
                "certificat, en heures (720 = trente jours).",
                720,
            ),
        ),
        outputs={"tls_secret_name": "Nom du Secret kubernetes.io/tls a citer dans l'Ingress."},
        traps=(
            "Le certificat expire sans rien signaler : Terraform ne le "
            "reengendre qu'au prochain apply, et seulement si "
            "`early_renewal_hours` est atteint. Un projet applique deux fois "
            "par an avec un certificat d'un an tombe en panne.",
            "La cle privee est stockee **en clair dans l'etat**, comme toute "
            "ressource du provider tls.",
            "Les navigateurs ignorent le Common Name depuis 2017 : un "
            "certificat sans `dns_names` correspondant a l'hote est refuse, "
            "quel que soit son CN.",
            "Un Secret `kubernetes.io/tls` exige exactement les deux cles "
            "`tls.crt` et `tls.key`. Toute autre nomenclature est acceptee par "
            "l'API et ignoree par l'ingress controller.",
        ),
    ),
)

#: Familles indexees par nom.
BY_NAME: dict[str, Family] = {famille.name: famille for famille in FAMILIES}
