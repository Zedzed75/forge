"""Jinja filters specific to the Terraform domain.

Loaded by `forge.jinja_ext.ForgeExtension` through the
`forge.plugins.<domain>.jinja_ext` convention (cf.
`forge.pipeline.plugin_jinja_module`): the core knows neither HCL nor the
alignment `terraform fmt` imposes.

Rendering HCL from a Jinja template poses two problems the YAML templates do not
have:

* **quoting** — a value coming from the specification may contain a quotation
  mark, or the `${` sequence that opens an HCL interpolation;
* **alignment** — `terraform fmt` aligns the `=` of consecutive assignment lines,
  and `terraform fmt -check` is one of the validators of the domain. A template
  cannot align keys whose length it does not know; the projection, on the other
  hand, knows them all.
"""

from __future__ import annotations

from forge.plugins.terraform.hcl import (
    align,
    align_map,
    args,
    hcl_key,
    hcl_string,
    hcl_value,
)

#: Filters exposed to the templates of the domain.
FILTERS = {
    "hcl": hcl_value,
    "hcl_key": hcl_key,
    "hcl_string": hcl_string,
    "hcl_align": align,
    "hcl_align_map": align_map,
    "hcl_args": args,
}

#: No globals: everything the templates need goes through `domain`.
GLOBALS: dict[str, object] = {}
