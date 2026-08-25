"""Les familles de ressources Kubernetes generables par le domaine Helm.

L'ordre de ce module est **significatif** : il fixe l'ordre d'affichage de
`forge catalog helm`, celui des slots de composants, et donc celui des fichiers
generes. Ne pas le trier autrement sans regenerer les references.

Les `traps` de chaque famille sont mesures, pas supposes : ils viennent de ce
que `kubeconform -strict` refuse, de ce que l'API Kubernetes rejette a
l'application, et des versions d'API supprimees. Ils sont repris en commentaire
dans les gabarits correspondants.
"""

from __future__ import annotations

from forge.plugins.helm.catalog.definition import ComponentFamily, ValueKey

DEPLOYMENT = ComponentFamily(
    name="deployment",
    kind="Deployment",
    api_version="apps/v1",
    summary="Charge de travail sans etat, remplacable et repliquable",
    selection="kind",
    details=(
        "Le cas courant : des pods interchangeables, remplaces par lots lors "
        "d'une mise a jour. Porte les sondes, le contexte de securite, les "
        "ressources et le placement."
    ),
    values=(
        ValueKey("enabled", "true", "Genere ou non ce composant"),
        ValueKey("replicaCount", "1", "Nombre de pods ; surcharge par environnement"),
        ValueKey("image.tag", '""', "Vide = appVersion du chart"),
        ValueKey(
            "resources.requests.cpu",
            '"100m"',
            "Reservation CPU ; sans elle, l'autoscaling reste aveugle",
        ),
    ),
    traps=(
        "spec.selector est requis ET immuable : employer selectorLabels seul, "
        "jamais labels, qui contient helm.sh/chart et app.kubernetes.io/version "
        "— changeants a chaque release.",
        "Quand l'autoscaling est actif, ne pas rendre `replicas` : Helm et le "
        "HorizontalPodAutoscaler se battraient a chaque mise a jour.",
    ),
)

STATEFULSET = ComponentFamily(
    name="statefulset",
    kind="StatefulSet",
    api_version="apps/v1",
    summary="Charge de travail a etat : identite reseau et volume stables par pod",
    selection="kind",
    details=(
        "Chaque pod garde son nom, son volume et son entree DNS d'un "
        "redemarrage a l'autre. Exige un Service headless, que forge force."
    ),
    values=(
        ValueKey("persistence.enabled", "true", "Volume persistant par pod"),
        ValueKey("persistence.size", '"10Gi"', "Taille du volume, quantite Kubernetes"),
        ValueKey(
            "persistence.storageClass",
            '""',
            "Vide = classe par defaut du cluster",
            'un nom de StorageClass, ou "" pour aucune',
        ),
        ValueKey(
            "updateStrategy.type",
            '"RollingUpdate"',
            "Strategie de mise a jour des pods",
            "RollingUpdate | OnDelete",
        ),
    ),
    requires=("service",),
    traps=(
        "spec.serviceName est requis, et le Service vise doit reellement etre "
        "headless (clusterIP: None).",
        "volumeClaimTemplates est immuable : un `helm upgrade` qui change la "
        "taille du volume echoue.",
        "`storageClassName: \"\"` signifie « aucune classe », omettre la cle "
        "signifie « celle par defaut » : n'emettre la cle que si elle est non vide.",
        "Le nom du volumeClaimTemplate doit etre exactement celui du volumeMount.",
    ),
)

CRONJOB = ComponentFamily(
    name="cronjob",
    kind="CronJob",
    api_version="batch/v1",
    summary="Tache planifiee recurrente, sans Service ni autoscaling",
    selection="kind",
    details=(
        "Cree un Job a chaque echeance. N'a ni replicas, ni selecteur, ni "
        "Service : recopier un Deployment y ferait echouer la validation."
    ),
    values=(
        ValueKey("cron.schedule", '"0 3 * * *"', "Planification, cron a cinq champs"),
        ValueKey(
            "cron.concurrencyPolicy",
            '"Forbid"',
            "Que faire si l'execution precedente dure encore",
            "Allow | Forbid | Replace",
        ),
        ValueKey("cron.timeZone", '""', "Fuseau IANA ; vide = cle omise"),
        ValueKey("cron.suspend", "false", "Suspend les declenchements sans supprimer l'objet"),
    ),
    traps=(
        "batch/v1beta1 est supprimee depuis Kubernetes 1.25 : uniquement batch/v1.",
        "L'imbrication est spec.jobTemplate.spec.template.spec — quatre niveaux. "
        "Chaque `nindent` du bloc conteneur se decale de 8 par rapport a un Deployment.",
        "restartPolicy est obligatoire et ne peut valoir que OnFailure ou Never : "
        "`Always` passe le schema mais est refuse a l'application.",
        "`timeZone: \"\"` est refuse par l'API : la cle doit etre absente si vide.",
    ),
)

SERVICE = ComponentFamily(
    name="service",
    kind="Service",
    api_version="v1",
    summary="Expose le composant a l'interieur du cluster, sous un nom stable",
    selection="addon",
    details=(
        "Point d'entree reseau du composant. La variante headless "
        "(clusterIP: None) sert l'identite par pod d'un StatefulSet."
    ),
    values=(
        ValueKey(
            "service.type",
            '"ClusterIP"',
            "Portee de l'exposition",
            "ClusterIP | NodePort | LoadBalancer",
        ),
        ValueKey("service.port", "80", "Port du Service ; le conteneur ecoute ailleurs"),
        ValueKey("service.headless", "false", "Sans adresse de service, une entree DNS par pod"),
    ),
    traps=(
        "targetPort par NOM de port lie le Service au conteneur sans repeter le "
        "numero ; le nom est limite a 15 caracteres.",
    ),
)

INGRESS = ComponentFamily(
    name="ingress",
    kind="Ingress",
    api_version="networking.k8s.io/v1",
    summary="Expose le Service en HTTP(S) sur un hote, par environnement",
    selection="addon",
    details=(
        "L'hote est derive par environnement : le domaine de l'environnement "
        "l'emporte quand il est renseigne, sinon le domaine de base du "
        "composant, avec ou sans infixe d'environnement selon le profil."
    ),
    values=(
        ValueKey("ingress.enabled", "true", "Genere ou non l'Ingress"),
        ValueKey("ingress.className", '"nginx"', "Controleur vise", "nginx | traefik"),
        ValueKey("ingress.host", '""', "Hote ; pose par chaque values-<env>.yaml"),
        ValueKey(
            "ingress.pathType",
            '"Prefix"',
            "Mode de comparaison du chemin",
            "Exact | Prefix | ImplementationSpecific",
        ),
        ValueKey("ingress.tls.enabled", "true", "Termine TLS pour cet hote"),
    ),
    requires=("service",),
    traps=(
        "pathType est obligatoire sur chaque chemin : son absence est l'echec "
        "kubeconform -strict le plus frequent.",
        "backend.service.port veut exactement `number` OU `name`, jamais les deux.",
        "Un `host:` vide rend null la ou le schema attend une chaine : garder le "
        "champ sous condition.",
        "tls[].hosts doit reprendre litteralement l'hote de la regle, sinon le "
        "certificat ne couvre pas l'hote — invisible pour kubeconform, casse a "
        "l'execution.",
        "Ne jamais emettre a la fois ingressClassName et l'annotation "
        "kubernetes.io/ingress.class.",
        "Le bloc tls doit etre entierement absent — pas `tls: []` — quand TLS "
        "est desactive.",
    ),
)

CONFIGMAP = ComponentFamily(
    name="configmap",
    kind="ConfigMap",
    api_version="v1",
    summary="Configuration non sensible, injectee en variables ou montee en fichier",
    selection="addon",
    details=(
        "Porte les cles declarees par le composant. Une modification declenche "
        "un redemarrage des pods grace a une empreinte posee sur le modele de pod."
    ),
    values=(
        ValueKey("config.enabled", "true", "Genere ou non le ConfigMap"),
        ValueKey(
            "config.mountAs",
            '"env"',
            "Mode d'injection dans le conteneur",
            "env | file",
        ),
        ValueKey("config.mountPath", '"/etc/<composant>"', "Employe seulement en mode file"),
        ValueKey("config.data", "{}", "Cles de configuration ; valeurs toujours textuelles"),
    ),
    traps=(
        "Toutes les valeurs de `data` doivent etre des chaines : un entier "
        "echoue en -strict. Passer systematiquement par `quote`.",
        "`data:` sans contenu rend null et echoue : ecrire `{}` ou omettre la cle.",
        "Sans empreinte `checksum/config` sur le modele de pod, une modification "
        "de configuration ne declenche aucun redemarrage.",
        "Le chemin cite dans l'empreinte doit correspondre exactement au nom de "
        "fichier produit, sinon `helm template` echoue sur un modele introuvable.",
    ),
)

SECRET = ComponentFamily(
    name="secret",
    kind="Secret",
    api_version="v1",
    summary="Emplacement de secret a valeurs vides : declare les cles attendues",
    selection="addon",
    details=(
        "forge n'ecrit jamais de valeur secrete reelle — ni dans la "
        "specification, ni dans les values, ni dans le manifeste. Le chart "
        "declare les cles et sait referencer un Secret gere hors du chart."
    ),
    values=(
        ValueKey("secret.enabled", "false", "Genere ou non le Secret"),
        ValueKey("secret.create", "true", "Faux = referencer un Secret existant"),
        ValueKey("secret.existingSecret", '""', "Nom d'un Secret gere hors du chart"),
        ValueKey("secret.type", '"Opaque"', "Type de Secret", "Opaque, ou un type specialise"),
        ValueKey("secret.mountAs", '"env"', "Mode d'injection", "env | file"),
    ),
    traps=(
        "`data` attend du base64, `stringData` du texte clair : melanger les "
        "deux pour une meme cle fait silencieusement gagner `data`.",
        "Un bloc `stringData:` vide rend null et echoue : emettre `{}` ou omettre.",
        "Un type specialise impose ses cles (kubernetes.io/tls exige tls.crt et "
        "tls.key) : ne pas les melanger.",
        "`required` ferait echouer `helm template`, donc la validation et les "
        "tests golden : la contrainte se documente en commentaire.",
    ),
)

HPA = ComponentFamily(
    name="hpa",
    kind="HorizontalPodAutoscaler",
    api_version="autoscaling/v2",
    summary="Ajuste le nombre de repliques sur l'utilisation CPU et memoire",
    selection="addon",
    details=(
        "Active par le profil d'environnement : desactive en developpement, "
        "actif en production. Exige des `requests` sur le conteneur."
    ),
    values=(
        ValueKey("hpa.enabled", "false", "Active l'autoscaling ; pose par environnement"),
        ValueKey("hpa.minReplicas", "2", "Plancher de repliques"),
        ValueKey("hpa.maxReplicas", "5", "Plafond de repliques"),
        ValueKey("hpa.targetCPUUtilizationPercentage", "80", "Cible d'utilisation CPU, en pourcent"),
    ),
    requires=("deployment",),
    traps=(
        "autoscaling/v2beta1 et v2beta2 sont supprimees depuis 1.26 : uniquement "
        "autoscaling/v2.",
        "La forme des metriques n'est pas celle de v1 : un "
        "`targetCPUUtilizationPercentage` au niveau de spec est un champ inconnu.",
        "averageUtilization doit etre un entier : la chaine \"80\" echoue.",
        "Sans `resources.requests` sur le conteneur, la metrique reste inconnue "
        "et l'autoscaling ne fait rien — invisible pour les validateurs.",
    ),
)

PDB = ComponentFamily(
    name="pdb",
    kind="PodDisruptionBudget",
    api_version="policy/v1",
    summary="Garantit un minimum de pods disponibles pendant les interruptions",
    selection="addon",
    details=(
        "Protege le composant des drains de noeud et des mises a jour de "
        "cluster. Active par le profil d'environnement."
    ),
    values=(
        ValueKey("pdb.enabled", "false", "Active la garantie ; pose par environnement"),
        ValueKey(
            "pdb.minAvailable",
            "1",
            "Pods disponibles au minimum",
            "un entier, ou un pourcentage entre guillemets",
        ),
    ),
    requires=("deployment",),
    traps=(
        "policy/v1beta1 est supprimee depuis 1.25 : uniquement policy/v1.",
        "minAvailable et maxUnavailable sont mutuellement exclusifs. "
        "kubeconform ne modele pas cette exclusion : la garde est dans le gabarit.",
        "Le selecteur doit viser le composant seul : trop large, il bloquerait "
        "les evictions des autres composants du chart.",
        "minAvailable: 1 avec une seule replique rend tout drain impossible : "
        "d'ou la desactivation en developpement.",
    ),
)

SERVICEACCOUNT = ComponentFamily(
    name="serviceaccount",
    kind="ServiceAccount",
    api_version="v1",
    summary="Identite dediee du composant, au lieu du compte par defaut",
    selection="addon",
    details=(
        "Sans compte dedie, les pods tournent sous `default`, dont les droits "
        "sont partages par tout le namespace. Les annotations portent les "
        "identites federees des fournisseurs cloud."
    ),
    values=(
        ValueKey("serviceAccount.create", "true", "Cree le compte, ou reference un existant"),
        ValueKey("serviceAccount.name", '""', "Vide = nom derive du composant"),
        ValueKey("serviceAccount.annotations", "{}", "Identite federee du fournisseur cloud"),
        ValueKey(
            "serviceAccount.automountServiceAccountToken",
            "false",
            "Monte le jeton d'API dans les pods",
        ),
    ),
    traps=(
        "Le workload doit poser serviceAccountName avec le helper dedie, sans "
        "quoi les pods tournent sous `default`.",
        "Si create vaut faux alors que le workload reference encore le nom, les "
        "pods ne demarrent pas.",
    ),
)

RBAC = ComponentFamily(
    name="rbac",
    kind="Role, RoleBinding",
    api_version="rbac.authorization.k8s.io/v1",
    summary="Droits minimaux dans le namespace, lies au compte du composant",
    selection="addon",
    details=(
        "Genere avec l'addon `serviceaccount` : un Role n'a de sens qu'avec un "
        "sujet. Aucune ressource de portee cluster n'est produite."
    ),
    values=(
        ValueKey("rbac.create", "false", "Cree le Role et son RoleBinding"),
        ValueKey("rbac.rules", "[]", "Regles ; vide = ni Role ni RoleBinding"),
    ),
    requires=("serviceaccount",),
    traps=(
        "roleRef est immuable : changer le Role vise fait echouer tout "
        "`helm upgrade`.",
        "Un sujet de type ServiceAccount exige un `namespace` explicite.",
        "apiGroups doit contenir la chaine vide pour les ressources du groupe "
        "core (pods, configmaps, secrets).",
        "Ne pas generer un Role a regles vides : valide au schema, mais inutile "
        "et trompeur.",
    ),
)

NETWORKPOLICY = ComponentFamily(
    name="networkpolicy",
    kind="NetworkPolicy",
    api_version="networking.k8s.io/v1",
    summary="Restreint le trafic entrant et sortant des pods du composant",
    selection="addon",
    details=(
        "Ferme par defaut, ouvert explicitement. La resolution DNS est "
        "preservee : sans elle, le composant ne joint plus rien."
    ),
    values=(
        ValueKey("networkPolicy.enabled", "false", "Applique la restriction"),
        ValueKey("networkPolicy.allowFromSameNamespace", "true", "Trafic du meme namespace"),
        ValueKey("networkPolicy.allowFromNamespaces", "[]", "Namespaces autorises, par nom"),
        ValueKey("networkPolicy.allowDNS", "true", "Autorise la resolution DNS sortante"),
    ),
    requires=("deployment",),
    traps=(
        "podSelector est requis meme vide, et doit viser le composant seul.",
        "policyTypes doit lister explicitement Ingress et/ou Egress ; declarer "
        "Egress sans aucune regle coupe tout le sortant, DNS compris.",
        "Une regle vide `- {}` autorise TOUT, alors que l'absence de regle "
        "interdit tout : les deux se ressemblent, aucun validateur ne les separe.",
        "namespaceSelector et podSelector dans le meme element de `from` sont un "
        "ET ; dans deux elements, un OU. La difference tient a un tiret.",
        "La regle entrante vise le port du conteneur, pas celui du Service.",
    ),
)

TEST_CONNECTION = ComponentFamily(
    name="test_connection",
    kind="Pod",
    api_version="v1",
    summary="Test `helm test` : verifie que le premier composant expose repond",
    selection="derive",
    details=(
        "Un unique pod de test, vise le premier composant portant un Service "
        "non headless. Genere seulement si les tests Helm sont demandes."
    ),
    traps=(
        "Le pod porte l'annotation helm.sh/hook: test ; sans elle, il serait "
        "installe avec le chart au lieu d'etre lance par `helm test`.",
    ),
)

#: Familles, dans l'ordre d'affichage et de generation. **Ordre significatif.**
FAMILIES: tuple[ComponentFamily, ...] = (
    DEPLOYMENT,
    STATEFULSET,
    CRONJOB,
    SERVICE,
    INGRESS,
    CONFIGMAP,
    SECRET,
    HPA,
    PDB,
    SERVICEACCOUNT,
    RBAC,
    NETWORKPOLICY,
    TEST_CONNECTION,
)
