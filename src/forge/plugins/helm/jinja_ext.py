"""Jinja2 filters and globals specific to the Helm domain.

Loaded by `forge.jinja_ext.ForgeExtension` (MIGRATION.md §5): a plugin adds its
identifier factories without the root `copier.yml` being touched.

This module holds **naming only**. Everything to do with YAML formatting or with
comments lives in the core (`forge.jinja_ext`), where the two legacy
implementations were merged.

The critical piece is :func:`values_ref` (MIGRATION.md §4, port of
`engine/naming.py`): Go's dotted notation refuses hyphens, so `.Values.my-api`
is a **Helm syntax error**. Without this global, a component named with a hyphen
produces a chart that does not compile.

The component contexts exposed by `derive.py` already carry `values_ref` and
`helper` precomputed: inside the body of a template one therefore writes
`[[ c.values_ref ]]` instead. These globals remain necessary for expressions
built on the fly (a values key that is not a component, for instance) and to
stay faithful to the legacy contract.
"""

from __future__ import annotations

import re
from typing import Any, Final

#: Identifier acceptable in the dotted notation of Go/Helm templates.
#: Literal port of `helm_forge.engine.naming._GO_FIELD`.
_GO_FIELD: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def values_ref(name: str, prefix: str = ".Values") -> str:
    """Helm expression accessing a values key.

    `values_ref("api")` renders `.Values.api`; `values_ref("my-api")` renders
    `(index .Values "my-api")`, the only form Go accepts for a key containing a
    hyphen.
    """
    if _GO_FIELD.match(name):
        return f"{prefix}.{name}"
    return f'(index {prefix} "{name}")'


def helper_name(chart: str, *parts: str) -> str:
    """Name of a Helm helper: `helper_name("shop", "api", "labels")` renders
    `shop.api.labels`."""
    return ".".join([chart, *parts])


def resource_filename(resource: str, component: Any) -> str:
    """File name of a resource, always suffixed by the component.

    Port of `helm_forge.engine.planner.resource_filename`. The suffix is
    systematic, including for a single-component chart: the rule then stays the
    same whatever the project, and adding a second component renames no existing
    file.

    `component` accepts the component context produced by `derive.py` (a dict
    carrying `name`) or a name directly, which spares the template from knowing
    the exact shape of the context.
    """
    name = component["name"] if isinstance(component, dict) else str(component)
    return f"{resource}-{name}.yaml"


def camel(value: str) -> str:
    """Convert `liveness_path` into `livenessPath`.

    Port of `helm_forge.engine.filters.camel`: values keys follow the camelCase
    convention of the Helm ecosystem, whereas the Python model follows the
    snake_case one.
    """
    head, *rest = value.split("_")
    return head + "".join(part.capitalize() for part in rest)


#: Filters added by the Helm domain (`| camel`).
FILTERS = {
    "camel": camel,
}

#: Global functions added by the Helm domain.
GLOBALS = {
    "values_ref": values_ref,
    "helper_name": helper_name,
    "resource_filename": resource_filename,
}
