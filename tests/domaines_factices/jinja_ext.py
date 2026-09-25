"""Filters of the fake domains.

They reuse the `demo` plugin's template, hence its filters. This module exists
because the core's convention is **per plugin package**:
`forge.pipeline.plugin_jinja_module` looks for `<plugin-package>.jinja_ext`.
"""

from __future__ import annotations

from forge.plugins.demo.jinja_ext import FILTERS, GLOBALS

__all__ = ["FILTERS", "GLOBALS"]
