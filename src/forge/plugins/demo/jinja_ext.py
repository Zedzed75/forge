"""Filters belonging to the `demo` domain.

Shows how a plugin enriches copier's Jinja environment **without** touching the
core nor the root copier.yml: it exposes `FILTERS` and/or `GLOBALS`, which
`forge.jinja_ext.ForgeExtension` loads from the `FORGE_PLUGIN_JINJA`
environment variable set by the copier runner.
"""

from __future__ import annotations

#: Symbol displayed at the head of a file, per kind of widget.
KIND_SYMBOLS = {"gauge": "~", "counter": "#", "log": ">"}


def shout(value: str) -> str:
    """Upper-case a string: witness filter, checked by the tests."""
    return str(value).upper()


def widget_symbol(kind: str) -> str:
    """Symbol associated with a kind of widget, `?` when the kind is unknown."""
    return KIND_SYMBOLS.get(kind, "?")


def demo_banner(service_name: str) -> str:
    """Witness global: proves that a plugin's `GLOBALS` really is loaded."""
    return f"== {service_name} =="


#: Filters exposed to the templates of the demo domain.
FILTERS = {
    "shout": shout,
    "widget_symbol": widget_symbol,
}

#: Global functions exposed to the templates of the demo domain.
GLOBALS = {
    "demo_banner": demo_banner,
}
