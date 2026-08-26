"""Rendu de valeurs HCL, et alignement des blocs d'affectation.

`terraform fmt` aligne le signe `=` de lignes d'affectation consecutives. Un
gabarit qui ecrit des cles de longueurs differentes produit donc un fichier que
`terraform fmt -check` refuse — et ce validateur fait partie du contrat du
domaine. Les cles etant connues au moment de la projection, l'alignement se
calcule ici plutot que de se deviner dans le gabarit.

Ces fonctions sont exposees aux gabarits comme filtres de plugin, par la
convention `forge.plugins.<domaine>.jinja_ext` (cf. `forge/pipeline.py`).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

#: Indentation d'un niveau de bloc HCL.
INDENT = "  "


def hcl_value(value: Any) -> str:
    """Rend une valeur Python en litteral HCL.

    Les listes et les maps sont rendues sur une seule ligne : elles servent de
    valeurs par defaut de variables, ou la forme compacte est celle que
    `terraform fmt` conserve.
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
        paires = ", ".join(f"{hcl_key(k)} = {hcl_value(v)}" for k, v in value.items())
        return "{ " + paires + " }"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return "[" + ", ".join(hcl_value(v) for v in value) + "]"
    return hcl_string(str(value))


def hcl_string(value: str) -> str:
    """Rend une chaine en litteral HCL entre guillemets.

    Les sequences `${` et `%{` ouvrent une interpolation dans une chaine HCL :
    les echapper est indispensable des qu'une valeur vient de la specification,
    faute de quoi Terraform tente d'evaluer ce que l'utilisateur a ecrit.
    """
    echappe = (
        value.replace(chr(92), chr(92) * 2)
        .replace('"', chr(92) + '"')
        .replace(chr(10), chr(92) + "n")
        .replace(chr(9), chr(92) + "t")
        .replace("${", "$${")
        .replace("%{", "%%{")
    )
    return f'"{echappe}"'


def hcl_key(key: str) -> str:
    """Rend une cle de map : nue si elle est un identifiant, citee sinon.

    Un label Kubernetes comme `app.kubernetes.io/name` contient des points et
    des barres obliques : HCL ne l'accepte que cite.
    """
    if key and (key[0].isalpha() or key[0] == "_"):
        if all(c.isalnum() or c in "_-" for c in key):
            return key
    return hcl_string(key)


def align(pairs: Iterable[tuple[str, str]], indent: int = 1) -> str:
    """Rend des affectations `cle = valeur` alignees comme `terraform fmt`.

    `pairs` porte des valeurs **deja rendues** en HCL : l'appelant decide si
    une valeur est un litteral, une reference (`var.namespace`) ou une
    expression.
    """
    items = list(pairs)
    if not items:
        return ""
    largeur = max(len(cle) for cle, _ in items)
    marge = INDENT * indent
    return "\n".join(f"{marge}{cle.ljust(largeur)} = {valeur}" for cle, valeur in items)


def align_map(values: Mapping[str, Any], indent: int = 1) -> str:
    """Comme :func:`align`, mais rend les valeurs en litteraux HCL."""
    return align(((hcl_key(cle), hcl_value(valeur)) for cle, valeur in values.items()), indent)


def args(items: Iterable[Mapping[str, str]], indent: int = 1) -> str:
    """Rend une liste de `{name, value}` en affectations alignees.

    Forme employee par les arguments d'appel de module, les cles de backend et
    le `terraform.tfvars` : trois blocs dont les cles ne sont connues qu'a la
    projection, donc trois blocs qu'un gabarit ne saurait pas aligner seul.
    """
    return align(((item["name"], item["value"]) for item in items), indent)
