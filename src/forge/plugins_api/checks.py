"""Cross-checks that every other plugin re-implemented identically.

A pydantic sub-model only sees **its** section: it cannot check that the
environments it names exist in `service.environments`, which lives in the shared
block. Every domain therefore wrote that check, and the four versions were the
same up to a section name.

This module adds no domain knowledge to the core: it only talks about
`service.environments`, which is core, and about keys supplied by the caller.
That is the difference with a `forge_consistency` — that one covers written
files, this one the specification, before any rendering.

A plugin remains free not to use it: the `forge_check_spec` hook asks for
nothing but a list of `Issue`.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from forge.plugins_api.types import Issue


def unknown_environments(
    spec: Any, domain: str, sections: Mapping[str, Iterable[str]]
) -> list[Issue]:
    """Refuse any environment key absent from `service.environments`.

    `sections` maps a section path — `helm.environments`, `ansible.hosts` — to
    the environment names it references. A domain declaring several of them sees
    the offending sections grouped by environment: naming `dev` in two sections
    produces a single finding naming both, rather than two findings to read
    separately.

    The order of the result is deterministic: it is printed as-is.
    """
    known = {env.name for env in spec.service.environments}
    declared = ", ".join(env.name for env in spec.service.environments)

    citing: dict[str, list[str]] = {}
    for section, names in sections.items():
        for name in names:
            if name not in known:
                citing.setdefault(name, []).append(section)

    issues: list[Issue] = []
    for name in sorted(citing):
        subject = " and ".join(citing[name])
        verb = "reference" if len(citing[name]) > 1 else "references"
        issues.append(
            Issue(
                level="error",
                message=(
                    f"{subject} {verb} environment '{name}', absent from "
                    f"service.environments (declared: {declared})."
                ),
                hint=(
                    f"Add an environment '{name}' to service.environments, or "
                    f"fix the '{name}' key in {subject}."
                ),
                domains=(domain,),
            )
        )
    return issues
