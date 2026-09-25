"""The Kubernetes resource families the Helm domain can generate.

The order of this module is **significant**: it fixes the display order of
`forge catalog helm`, that of the component slots, and therefore that of the
generated files. Do not sort it differently without regenerating the references.

Each family's `traps` are measured, not assumed: they come from what
`kubeconform -strict` refuses, from what the Kubernetes API rejects on apply,
and from removed API versions. They are echoed as comments in the corresponding
templates.
"""

from __future__ import annotations

from forge.plugins.helm.catalog.definition import ComponentFamily, ValueKey

DEPLOYMENT = ComponentFamily(
    name="deployment",
    kind="Deployment",
    api_version="apps/v1",
    summary="Stateless workload, replaceable and replicable",
    selection="kind",
    details=(
        "The common case: interchangeable pods, replaced in batches during an "
        "update. Carries the probes, the security context, the resources and "
        "the placement."
    ),
    values=(
        ValueKey("enabled", "true", "Whether this component is generated"),
        ValueKey("replicaCount", "1", "Number of pods; overridden per environment"),
        ValueKey("image.tag", '""', "Empty = appVersion of the chart"),
        ValueKey(
            "resources.requests.cpu",
            '"100m"',
            "CPU reservation; without it autoscaling stays blind",
        ),
    ),
    traps=(
        "spec.selector is required AND immutable: use selectorLabels alone, "
        "never labels, which contains helm.sh/chart and "
        "app.kubernetes.io/version — both change on every release.",
        "When autoscaling is on, do not render `replicas`: Helm and the "
        "HorizontalPodAutoscaler would fight on every update.",
    ),
)

STATEFULSET = ComponentFamily(
    name="statefulset",
    kind="StatefulSet",
    api_version="apps/v1",
    summary="Stateful workload: stable network identity and volume per pod",
    selection="kind",
    details=(
        "Each pod keeps its name, its volume and its DNS entry from one restart "
        "to the next. Requires a headless Service, which forge forces."
    ),
    values=(
        ValueKey("persistence.enabled", "true", "Persistent volume per pod"),
        ValueKey("persistence.size", '"10Gi"', "Volume size, a Kubernetes quantity"),
        ValueKey(
            "persistence.storageClass",
            '""',
            "Empty = the cluster default class",
            'a StorageClass name, or "" for none',
        ),
        ValueKey(
            "updateStrategy.type",
            '"RollingUpdate"',
            "Pod update strategy",
            "RollingUpdate | OnDelete",
        ),
    ),
    requires=("service",),
    traps=(
        "spec.serviceName is required, and the Service it points at must really "
        "be headless (clusterIP: None).",
        "volumeClaimTemplates is immutable: a `helm upgrade` that changes the "
        "volume size fails.",
        "`storageClassName: \"\"` means \"no class\", omitting the key means "
        "\"the default one\": only emit the key when it is non-empty.",
        "The volumeClaimTemplate name must be exactly that of the volumeMount.",
    ),
)

CRONJOB = ComponentFamily(
    name="cronjob",
    kind="CronJob",
    api_version="batch/v1",
    summary="Recurring scheduled task, with no Service and no autoscaling",
    selection="kind",
    details=(
        "Creates a Job at every occurrence. It has no replicas, no selector and "
        "no Service: copying a Deployment here would fail validation."
    ),
    values=(
        ValueKey("cron.schedule", '"0 3 * * *"', "Schedule, five-field cron"),
        ValueKey(
            "cron.concurrencyPolicy",
            '"Forbid"',
            "What to do when the previous run is still going",
            "Allow | Forbid | Replace",
        ),
        ValueKey("cron.timeZone", '""', "IANA time zone; empty = key omitted"),
        ValueKey("cron.suspend", "false", "Suspends the triggers without deleting the object"),
    ),
    traps=(
        "batch/v1beta1 has been removed since Kubernetes 1.25: batch/v1 only.",
        "The nesting is spec.jobTemplate.spec.template.spec — four levels. "
        "Every `nindent` of the container block shifts by 8 compared with a Deployment.",
        "restartPolicy is mandatory and can only be OnFailure or Never: "
        "`Always` passes the schema but is refused on apply.",
        "`timeZone: \"\"` is refused by the API: the key must be absent when empty.",
    ),
)

SERVICE = ComponentFamily(
    name="service",
    kind="Service",
    api_version="v1",
    summary="Exposes the component inside the cluster, under a stable name",
    selection="addon",
    details=(
        "Network entry point of the component. The headless variant "
        "(clusterIP: None) serves the per-pod identity of a StatefulSet."
    ),
    values=(
        ValueKey(
            "service.type",
            '"ClusterIP"',
            "Scope of the exposure",
            "ClusterIP | NodePort | LoadBalancer",
        ),
        ValueKey("service.port", "80", "Service port; the container listens elsewhere"),
        ValueKey("service.headless", "false", "No service address, one DNS entry per pod"),
    ),
    traps=(
        "targetPort by port NAME ties the Service to the container without "
        "repeating the number; the name is limited to 15 characters.",
    ),
)

INGRESS = ComponentFamily(
    name="ingress",
    kind="Ingress",
    api_version="networking.k8s.io/v1",
    summary="Exposes the Service over HTTP(S) on a host, per environment",
    selection="addon",
    details=(
        "The host is derived per environment: the environment domain wins when "
        "it is set, otherwise the component base domain, with or without an "
        "environment infix depending on the profile."
    ),
    values=(
        ValueKey("ingress.enabled", "true", "Whether the Ingress is generated"),
        ValueKey("ingress.className", '"nginx"', "Target controller", "nginx | traefik"),
        ValueKey("ingress.host", '""', "Host; set by each values-<env>.yaml"),
        ValueKey(
            "ingress.pathType",
            '"Prefix"',
            "How the path is matched",
            "Exact | Prefix | ImplementationSpecific",
        ),
        ValueKey("ingress.tls.enabled", "true", "Terminates TLS for this host"),
    ),
    requires=("service",),
    traps=(
        "pathType is mandatory on every path: its absence is the most frequent "
        "kubeconform -strict failure.",
        "backend.service.port wants exactly `number` OR `name`, never both.",
        "An empty `host:` renders null where the schema expects a string: keep "
        "the field behind a condition.",
        "tls[].hosts must repeat the rule host literally, otherwise the "
        "certificate does not cover the host — invisible to kubeconform, broken "
        "at runtime.",
        "Never emit both ingressClassName and the kubernetes.io/ingress.class "
        "annotation.",
        "The tls block must be entirely absent — not `tls: []` — when TLS is "
        "disabled.",
    ),
)

CONFIGMAP = ComponentFamily(
    name="configmap",
    kind="ConfigMap",
    api_version="v1",
    summary="Non-sensitive configuration, injected as variables or mounted as a file",
    selection="addon",
    details=(
        "Carries the keys declared by the component. A change triggers a pod "
        "restart thanks to a checksum placed on the pod template."
    ),
    values=(
        ValueKey("config.enabled", "true", "Whether the ConfigMap is generated"),
        ValueKey(
            "config.mountAs",
            '"env"',
            "How it is injected into the container",
            "env | file",
        ),
        ValueKey("config.mountPath", '"/etc/<component>"', "Used in file mode only"),
        ValueKey("config.data", "{}", "Configuration keys; values are always textual"),
    ),
    traps=(
        "Every value of `data` must be a string: an integer fails in -strict. "
        "Always go through `quote`.",
        "`data:` with no content renders null and fails: write `{}` or omit the key.",
        "Without a `checksum/config` fingerprint on the pod template, a "
        "configuration change triggers no restart at all.",
        "The path quoted in the checksum must match the produced file name "
        "exactly, otherwise `helm template` fails on a template it cannot find.",
    ),
)

SECRET = ComponentFamily(
    name="secret",
    kind="Secret",
    api_version="v1",
    summary="Secret placeholder with empty values: declares the expected keys",
    selection="addon",
    details=(
        "forge never writes a real secret value — not in the specification, not "
        "in the values, not in the manifest. The chart declares the keys and "
        "knows how to reference a Secret managed outside the chart."
    ),
    values=(
        ValueKey("secret.enabled", "false", "Whether the Secret is generated"),
        ValueKey("secret.create", "true", "False = reference an existing Secret"),
        ValueKey("secret.existingSecret", '""', "Name of a Secret managed outside the chart"),
        ValueKey("secret.type", '"Opaque"', "Secret type", "Opaque, or a specialised type"),
        ValueKey("secret.mountAs", '"env"', "How it is injected", "env | file"),
    ),
    traps=(
        "`data` expects base64, `stringData` plain text: mixing the two for the "
        "same key silently lets `data` win.",
        "An empty `stringData:` block renders null and fails: emit `{}` or omit it.",
        "A specialised type imposes its keys (kubernetes.io/tls requires tls.crt "
        "and tls.key): do not mix them.",
        "`required` would fail `helm template`, hence validation and the golden "
        "tests: the constraint is documented as a comment instead.",
    ),
)

HPA = ComponentFamily(
    name="hpa",
    kind="HorizontalPodAutoscaler",
    api_version="autoscaling/v2",
    summary="Adjusts the replica count on CPU and memory usage",
    selection="addon",
    details=(
        "Enabled by the environment profile: off in development, on in "
        "production. Requires `requests` on the container."
    ),
    values=(
        ValueKey("hpa.enabled", "false", "Enables autoscaling; set per environment"),
        ValueKey("hpa.minReplicas", "2", "Replica floor"),
        ValueKey("hpa.maxReplicas", "5", "Replica ceiling"),
        ValueKey("hpa.targetCPUUtilizationPercentage", "80", "Target CPU usage, as a percentage"),
    ),
    requires=("deployment",),
    traps=(
        "autoscaling/v2beta1 and v2beta2 have been removed since 1.26: "
        "autoscaling/v2 only.",
        "The shape of the metrics is not the v1 one: a "
        "`targetCPUUtilizationPercentage` at spec level is an unknown field.",
        "averageUtilization must be an integer: the string \"80\" fails.",
        "Without `resources.requests` on the container the metric stays unknown "
        "and autoscaling does nothing — invisible to the validators.",
    ),
)

PDB = ComponentFamily(
    name="pdb",
    kind="PodDisruptionBudget",
    api_version="policy/v1",
    summary="Guarantees a minimum of available pods during disruptions",
    selection="addon",
    details=(
        "Protects the component from node drains and cluster upgrades. Enabled "
        "by the environment profile."
    ),
    values=(
        ValueKey("pdb.enabled", "false", "Enables the guarantee; set per environment"),
        ValueKey(
            "pdb.minAvailable",
            "1",
            "Minimum available pods",
            "an integer, or a quoted percentage",
        ),
    ),
    requires=("deployment",),
    traps=(
        "policy/v1beta1 has been removed since 1.25: policy/v1 only.",
        "minAvailable and maxUnavailable are mutually exclusive. kubeconform "
        "does not model that exclusion: the guard is in the template.",
        "The selector must target the component alone: too broad, it would block "
        "the evictions of the other components of the chart.",
        "minAvailable: 1 with a single replica makes any drain impossible: hence "
        "it being disabled in development.",
    ),
)

SERVICEACCOUNT = ComponentFamily(
    name="serviceaccount",
    kind="ServiceAccount",
    api_version="v1",
    summary="Dedicated identity for the component, instead of the default account",
    selection="addon",
    details=(
        "Without a dedicated account the pods run as `default`, whose rights are "
        "shared by the whole namespace. The annotations carry the federated "
        "identities of the cloud providers."
    ),
    values=(
        ValueKey("serviceAccount.create", "true", "Creates the account, or references an existing one"),
        ValueKey("serviceAccount.name", '""', "Empty = name derived from the component"),
        ValueKey("serviceAccount.annotations", "{}", "Federated identity of the cloud provider"),
        ValueKey(
            "serviceAccount.automountServiceAccountToken",
            "false",
            "Mounts the API token into the pods",
        ),
    ),
    traps=(
        "The workload must set serviceAccountName with the dedicated helper, "
        "otherwise the pods run as `default`.",
        "If create is false while the workload still references the name, the "
        "pods do not start.",
    ),
)

RBAC = ComponentFamily(
    name="rbac",
    kind="Role, RoleBinding",
    api_version="rbac.authorization.k8s.io/v1",
    summary="Minimal rights within the namespace, bound to the component account",
    selection="addon",
    details=(
        "Generated together with the `serviceaccount` addon: a Role only makes "
        "sense with a subject. No cluster-scoped resource is produced."
    ),
    values=(
        ValueKey("rbac.create", "false", "Creates the Role and its RoleBinding"),
        ValueKey("rbac.rules", "[]", "Rules; empty = neither Role nor RoleBinding"),
    ),
    requires=("serviceaccount",),
    traps=(
        "roleRef is immutable: changing the Role it points at makes every "
        "`helm upgrade` fail.",
        "A subject of kind ServiceAccount requires an explicit `namespace`.",
        "apiGroups must contain the empty string for the resources of the core "
        "group (pods, configmaps, secrets).",
        "Do not generate a Role with empty rules: schema-valid, but useless and "
        "misleading.",
    ),
)

NETWORKPOLICY = ComponentFamily(
    name="networkpolicy",
    kind="NetworkPolicy",
    api_version="networking.k8s.io/v1",
    summary="Restricts the ingress and egress traffic of the component pods",
    selection="addon",
    details=(
        "Closed by default, opened explicitly. DNS resolution is preserved: "
        "without it the component can no longer reach anything."
    ),
    values=(
        ValueKey("networkPolicy.enabled", "false", "Applies the restriction"),
        ValueKey("networkPolicy.allowFromSameNamespace", "true", "Traffic from the same namespace"),
        ValueKey("networkPolicy.allowFromNamespaces", "[]", "Allowed namespaces, by name"),
        ValueKey("networkPolicy.allowDNS", "true", "Allows outgoing DNS resolution"),
    ),
    requires=("deployment",),
    traps=(
        "podSelector is required even when empty, and must target the component "
        "alone.",
        "policyTypes must list Ingress and/or Egress explicitly; declaring "
        "Egress with no rule at all cuts off everything outgoing, DNS included.",
        "An empty rule `- {}` allows EVERYTHING, whereas the absence of a rule "
        "forbids everything: the two look alike, and no validator tells them apart.",
        "namespaceSelector and podSelector in the same `from` element are an AND; "
        "in two elements, an OR. The difference is one dash.",
        "The ingress rule targets the container port, not the Service one.",
    ),
)

TEST_CONNECTION = ComponentFamily(
    name="test_connection",
    kind="Pod",
    api_version="v1",
    summary="`helm test` test: checks that the first exposed component answers",
    selection="derive",
    details=(
        "A single test pod, targeting the first component carrying a non-headless "
        "Service. Generated only when the Helm tests are requested."
    ),
    traps=(
        "The pod carries the helm.sh/hook: test annotation; without it, it would "
        "be installed with the chart instead of being launched by `helm test`.",
    ),
)

#: Families, in display and generation order. **Order is significant.**
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
