"""Jinja2 extension loaded by copier (`_jinja_extensions` of the root copier.yml).

copier does not accept filters passed in Python: only an importable extension can
enrich its environment (MIGRATION.md §2.2). This module therefore concentrates
the shared filters, coming from the merge of the two legacy tables
(MIGRATION.md §5.5):

* `yaml_scalar`, `yaml_assign`, `comment`, `lower_first`, `rule` — from ansible-forge;
* `to_yaml`, `yaml_value`, `indent_block` — from helm-forge.

Arbitration of the two divergent implementations:

* `yaml_scalar`: the ansible-forge version was kept (it accepts any scalar, not
  only strings; identical rendering on strings).
* `comment`: the ansible-forge version was kept (it preserves the indentation of
  the source line and renders blank lines as `#`), completed by helm-forge's
  `prefix` parameter. Signature: `comment(text, indent=0, width=88,
  prefix="# ")`; the helm templates that passed the width positionally as the 2nd
  argument have to name it (`| comment(width=76)`).

A plugin adds its own filters without touching the core: it provides a module
`forge.plugins.<domain>.jinja_ext` exposing `FILTERS` and/or `GLOBALS`, which the
copier runner declares through the `FORGE_PLUGIN_JINJA` environment variable
(cf. `forge.render.copier_runner`).
"""

from __future__ import annotations

import importlib
import os
import textwrap
from typing import Any

import yaml
from jinja2.ext import Extension

#: Maximum width of a generated comment line.
COMMENT_WIDTH = 88

#: Width of the separator rules in headers.
RULE_WIDTH = 75

#: Environment variable listing the plugin filter modules.
PLUGIN_JINJA_ENV_VAR = "FORGE_PLUGIN_JINJA"


class _BlockDumper(yaml.SafeDumper):
    """YAML dumper that indents lists under their parent key."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def _plain(value: Any) -> Any:
    """Recursively convert non-native objects into safe YAML types."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def yaml_scalar(value: Any) -> str:
    """Render a scalar value as YAML, with the quoting it needs.

    It goes through dumping a key/value pair: PyYAML decides on the quoting,
    which avoids any divergence with the target parser. `api` stays bare;
    `1.36`, `true` or `on` are protected.
    """
    dumped = yaml.dump(
        {"_": _plain(value)},
        Dumper=_BlockDumper,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
        sort_keys=False,
    )
    return dumped.rstrip("\n").removeprefix("_: ")


def to_yaml(value: Any, indent: int = 0) -> str:
    """Render a Python value as YAML, ready to be inserted into a template.

    Scalars on one line, lists and dicts as blocks indented by `indent` spaces.
    Key order follows insertion order, never alphabetical order: that is what
    makes the render reproducible.
    """
    if not isinstance(value, (list, tuple, dict)):
        return yaml_scalar(value)
    if not value:
        # Empty collection: the inline form reads better than an empty block.
        return "[]" if isinstance(value, (list, tuple)) else "{}"
    text = yaml.dump(
        _plain(value),
        Dumper=_BlockDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    ).rstrip("\n")
    return textwrap.indent(text, " " * indent) if indent else text


def yaml_value(value: Any, indent: int = 0) -> str:
    """Render a value meant to sit to the right of a YAML key.

    A non-empty collection cannot stay on its key's line: YAML refuses
    `drop: - ALL`. The filter therefore switches to an indented block, while
    scalars and empty collections stay inline. It produces the separator itself,
    a space or a newline; the template sticks the tag to the colon
    (`drop:[[ items | yaml_value(8) ]]`) so as never to leave a trailing space.
    """
    if isinstance(value, (list, tuple, dict)) and value:
        return "\n" + to_yaml(value, indent=indent)
    return " " + to_yaml(value)


def yaml_assign(value: Any, indent: int = 0) -> str:
    """Variant of `yaml_value` that also switches multi-line scalars.

    To be used like this: `[[ name ]]:[[ value | yaml_assign(2) ]]`.
    """
    if isinstance(value, (list, tuple, dict)) and not value:
        return " []" if isinstance(value, (list, tuple)) else " {}"
    if not isinstance(value, (list, tuple, dict)):
        scalar = yaml_scalar(value)
        if "\n" not in scalar:
            return f" {scalar}"
    dumped = yaml.dump(
        _plain(list(value) if isinstance(value, tuple) else value),
        Dumper=_BlockDumper,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
        sort_keys=False,
    ).rstrip("\n")
    pad = " " * indent
    return "\n" + "\n".join(f"{pad}{line}" if line else "" for line in dumped.splitlines())


def comment(
    text: str, indent: int = 0, width: int = COMMENT_WIDTH, prefix: str = "# "
) -> str:
    """Turn a text into a block of comments, wrapped at `width`.

    Blank lines in the source text become lone `#` lines, which makes it possible
    to write paragraphs in catalogue descriptions. The indentation of a source
    line is preserved: it carries meaning in the command examples quoted in file
    headers.
    """
    pad = " " * indent
    available = max(width - indent - len(prefix), 20)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        stripped = paragraph.strip()
        if not stripped:
            lines.append(f"{pad}{prefix}".rstrip())
            continue
        lead = paragraph[: len(paragraph) - len(paragraph.lstrip())]
        chunks = textwrap.wrap(
            stripped, width=available, initial_indent=lead, subsequent_indent=lead
        )
        lines.extend(f"{pad}{prefix}{chunk}".rstrip() for chunk in chunks)
    return "\n".join(lines)


def indent_block(text: str, spaces: int, first: bool = False) -> str:
    """Indent an already rendered block of text.

    `first` left false leaves the first line untouched, the common case where the
    template has already written the starting indentation.
    """
    if not text:
        return text
    indented = textwrap.indent(text, " " * spaces)
    return indented if first else indented[spaces:]


def lower_first(text: str) -> str:
    """Lowercase the first letter, to continue after a colon.

    Leaves alone texts starting with an acronym or a proper noun in capitals
    (`UTF8`, `Ansible`), recognised by their second letter.
    """
    if len(text) >= 2 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


def rule(width: int = RULE_WIDTH) -> str:
    """Return a separator rule as a comment."""
    return "# " + "-" * width


#: Filters exposed to the templates, under the name used in the `| filter` calls.
FILTERS = {
    "yaml_scalar": yaml_scalar,
    "yaml_assign": yaml_assign,
    "yaml_value": yaml_value,
    "to_yaml": to_yaml,
    "comment": comment,
    "indent_block": indent_block,
    "lower_first": lower_first,
}

#: Global functions exposed to the templates.
GLOBALS = {
    "rule": rule,
}


def plugin_tables(dotted_paths: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the `FILTERS`/`GLOBALS` tables of the named modules, in order."""
    filters: dict[str, Any] = {}
    globals_: dict[str, Any] = {}
    for dotted in (part.strip() for part in dotted_paths.split(",")):
        if not dotted:
            continue
        module = importlib.import_module(dotted)
        filters.update(getattr(module, "FILTERS", {}))
        globals_.update(getattr(module, "GLOBALS", {}))
    return filters, globals_


class ForgeExtension(Extension):
    """Inject forge's filters into copier's Jinja2 environment."""

    def __init__(self, environment: Any) -> None:
        super().__init__(environment)
        environment.filters.update(FILTERS)
        environment.globals.update(GLOBALS)
        extra_filters, extra_globals = plugin_tables(
            os.environ.get(PLUGIN_JINJA_ENV_VAR, "")
        )
        environment.filters.update(extra_filters)
        environment.globals.update(extra_globals)
