"""Terraform providers used by the families of the catalogue.

A single table, so that the `required_providers` of the module and that of each
environment root declare exactly the same sources and the same version
constraints. Two diverging declarations produce no error: Terraform resolves the
intersection, and the divergence is only seen the day it becomes empty.

The constraints are in `~>`: they allow the patches and the minor versions,
never a major change. A constraint with no upper bound lets a future major
version break the project without anything having been changed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """A provider as declared in a `required_providers` block."""

    #: Local name of the provider in the configuration (`kubernetes`, `random`...).
    name: str

    #: Address in the registry (`hashicorp/kubernetes`).
    source: str

    #: Version constraint.
    version: str

    #: Reason for its presence, taken up as a comment in the generated file.
    reason: str


#: Table indexed by local name. The order is alphabetical: it is the one in
#: which `terraform fmt` leaves the entries of `required_providers`, and it makes
#: the output deterministic whatever the order of the retained families.
PROVIDERS: dict[str, Provider] = {
    "kubernetes": Provider(
        name="kubernetes",
        source="hashicorp/kubernetes",
        version="~> 2.32",
        reason="sets up the Kubernetes objects that host the service",
    ),
    "random": Provider(
        name="random",
        source="hashicorp/random",
        version="~> 3.6",
        reason="generates the passwords, never written in the specification",
    ),
    "tls": Provider(
        name="tls",
        source="hashicorp/tls",
        version="~> 4.0",
        reason="builds the self-signed certificates of the working environments",
    ),
}


def resolve(names: set[str]) -> list[Provider]:
    """Providers matching `names`, sorted by local name.

    Raises `KeyError` on an unknown name: a family that demands a provider
    absent from the table is a programming error of the plugin, not an error of
    the user.
    """
    return [PROVIDERS[name] for name in sorted(names)]
