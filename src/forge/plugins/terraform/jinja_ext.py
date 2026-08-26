"""Filtres Jinja propres au domaine Terraform.

Charges par `forge.jinja_ext.ForgeExtension` selon la convention
`forge.plugins.<domaine>.jinja_ext` (cf. `forge.pipeline.plugin_jinja_module`) :
le coeur ne connait ni HCL ni l'alignement que `terraform fmt` impose.

Rendre du HCL depuis un gabarit Jinja pose deux problemes que les gabarits YAML
n'ont pas :

* **la citation** — une valeur venue de la specification peut contenir un
  guillemet, ou la sequence `${` qui ouvre une interpolation HCL ;
* **l'alignement** — `terraform fmt` aligne le `=` de lignes d'affectation
  consecutives, et `terraform fmt -check` fait partie des validateurs du
  domaine. Un gabarit ne peut pas aligner des cles dont il ignore la longueur ;
  la projection, elle, les connait toutes.
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

#: Filtres exposes aux gabarits du domaine.
FILTERS = {
    "hcl": hcl_value,
    "hcl_key": hcl_key,
    "hcl_string": hcl_string,
    "hcl_align": align,
    "hcl_align_map": align_map,
    "hcl_args": args,
}

#: Aucune globale : tout ce dont les gabarits ont besoin passe par `domain`.
GLOBALS: dict[str, object] = {}
