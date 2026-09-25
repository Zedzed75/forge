"""Fake domain whose package provides **no** filter module at all.

It lives at the root of `tests/` — and not in `tests/fake_domains/`, which
does have a `jinja_ext` — in order to exercise the case of a plugin that does
not enrich copier's Jinja environment.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo
from tests.fake_domains import TrivialSection


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(name="isolated", title="Isolated", summary="Fake domain with no filters")


@hookimpl
def forge_spec_model() -> type[TrivialSection]:
    return TrivialSection


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.isolated.enabled}
