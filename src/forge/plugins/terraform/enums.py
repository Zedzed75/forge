"""Enumerations of the Terraform domain.

They all inherit from `str`: the `domain` dict passed to copier has to stay
JSON-serialisable, and `.value` is written as-is into `.copier-answers.yml`.

`NamespaceStrategy` repeats the same three strategies as the Helm domain. That is
a **deliberate** duplication: sharing it would require putting the notion of a
namespace into the core, which must stay agnostic (DESIGN.md §2). The two domains
meet where they have to — on the `namespaces` **facet**, compared by
`forge validate`.
"""

from __future__ import annotations

from enum import Enum


class BackendKind(str, Enum):
    """Where the Terraform state is kept.

    The state contains in plain text everything the resources expose, generated
    passwords included: the choice of a backend is a security choice before being
    a convenience one.
    """

    #: A local file. Useful while exploring, never in a team: neither lock nor
    #: encryption, and nothing stops two people from applying at the same time.
    LOCAL = "local"

    #: An S3 (or compatible) bucket. Locking requires `use_lockfile` or a
    #: DynamoDB table, without which two concurrent applies overwrite each other.
    S3 = "s3"

    #: A Google Cloud Storage bucket. Native locking, encryption at rest.
    GCS = "gcs"

    #: An Azure storage account. Native locking through a blob lease.
    AZURERM = "azurerm"

    #: An HTTP service implementing the state API (GitLab managed state, Atlantis).
    HTTP = "http"


class NamespaceStrategy(str, Enum):
    """How the namespace name is derived from the environment."""

    #: One single namespace for every environment: `<service>`.
    SAME = "same"

    #: One namespace per environment: `<service>-<env>`.
    PER_ENV = "per_env"

    #: Each environment supplies its namespace explicitly.
    CUSTOM = "custom"


class KubernetesAuth(str, Enum):
    """How the Kubernetes provider authenticates."""

    #: A kubeconfig file, with a named context. The mode of workstations and of
    #: ordinary CI. With no explicit context, the provider uses the *current*
    #: context of the workstation: it is the most banal production accident.
    KUBECONFIG = "kubeconfig"

    #: Terraform runs inside a pod of the targeted cluster and reads its mounted
    #: token.
    IN_CLUSTER = "in_cluster"


class ResourceFamily(str, Enum):
    """Families of resources the module can declare.

    The declaration order is the canonical order: it fixes the order of the `.tf`
    files of the module, that of the lines of the README and that of the keys of
    `domain.resource_slots`.
    """

    #: The namespace itself. Selected, Terraform **creates** it; absent, the
    #: module attaches to an existing namespace supplied as a variable.
    NAMESPACE = "namespace"

    #: ResourceQuota + LimitRange: the budget of the namespace.
    QUOTA = "quota"

    #: Image pull secret (`kubernetes.io/dockerconfigjson`).
    REGISTRY_SECRET = "registry_secret"

    #: ServiceAccount + Role + RoleBinding for automated deployments.
    SERVICE_ACCOUNT = "service_account"

    #: NetworkPolicy closing the namespace by default.
    NETWORK_POLICY = "network_policy"

    #: Generated password (`random_password`) placed in a Secret.
    RANDOM_SECRET = "random_secret"

    #: Self-signed certificate (`tls_*`) placed in a `kubernetes.io/tls` Secret.
    TLS_CERTIFICATE = "tls_certificate"
