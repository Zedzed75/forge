"""Rendering of HCL values, and alignment of assignment blocks.

`terraform fmt` aligns the `=` sign of consecutive assignment lines. A template
that writes keys of different lengths therefore produces a file
`terraform fmt -check` refuses — and that validator is part of the contract of the
domain. The keys being known at projection time, the alignment is computed here
rather than guessed inside the template.

These functions are exposed to the templates as plugin filters, through the
`forge.plugins.<domain>.jinja_ext` convention (cf. `forge/pipeline.py`).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

#: Indentation of one HCL block level.
INDENT = "  "


def hcl_value(value: Any) -> str:
    """Render a Python value as an HCL literal.

    Lists and maps are rendered on a single line: they serve as default values of
    variables, where the compact form is the one `terraform fmt` keeps.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return hcl_string(value)
    if isinstance(value, Mapping):
        if not value:
            return "{}"
        pairs = ", ".join(f"{hcl_key(k)} = {hcl_value(v)}" for k, v in value.items())
        return "{ " + pairs + " }"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return "[" + ", ".join(hcl_value(v) for v in value) + "]"
    return hcl_string(str(value))


def hcl_string(value: str) -> str:
    """Render a string as a quoted HCL literal.

    The `${` and `%{` sequences open an interpolation inside an HCL string:
    escaping them is indispensable as soon as a value comes from the
    specification, otherwise Terraform tries to evaluate what the user wrote.
    """
    escaped = (
        value.replace(chr(92), chr(92) * 2)
        .replace('"', chr(92) + '"')
        .replace(chr(10), chr(92) + "n")
        .replace(chr(9), chr(92) + "t")
        .replace("${", "$${")
        .replace("%{", "%%{")
    )
    return f'"{escaped}"'


def hcl_key(key: str) -> str:
    """Render a map key: bare when it is an identifier, quoted otherwise.

    A Kubernetes label such as `app.kubernetes.io/name` contains dots and slashes:
    HCL only accepts it quoted.
    """
    if key and (key[0].isalpha() or key[0] == "_"):
        if all(c.isalnum() or c in "_-" for c in key):
            return key
    return hcl_string(key)


def align(pairs: Iterable[tuple[str, str]], indent: int = 1) -> str:
    """Render `key = value` assignments aligned the way `terraform fmt` does.

    `pairs` carries values **already rendered** in HCL: the caller decides whether
    a value is a literal, a reference (`var.namespace`) or an expression.
    """
    items = list(pairs)
    if not items:
        return ""
    width = max(len(key) for key, _ in items)
    margin = INDENT * indent
    return "\n".join(f"{margin}{key.ljust(width)} = {value}" for key, value in items)


def align_map(values: Mapping[str, Any], indent: int = 1) -> str:
    """Like :func:`align`, but renders the values as HCL literals."""
    return align(((hcl_key(key), hcl_value(value)) for key, value in values.items()), indent)


def args(items: Iterable[Mapping[str, str]], indent: int = 1) -> str:
    """Render a list of `{name, value}` as aligned assignments.

    The form used by the module call arguments, the backend keys and the
    `terraform.tfvars`: three blocks whose keys are only known at projection time,
    hence three blocks a template could not align on its own.
    """
    return align(((item["name"], item["value"]) for item in items), indent)
