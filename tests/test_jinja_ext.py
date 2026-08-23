"""Tests des filtres exposes aux gabarits.

Ces filtres fixent la mise en forme de **tous** les fichiers generes : une
regression ici se voit dans chaque projet, d'ou une couverture cas par cas.
"""

from __future__ import annotations

import jinja2
import pytest

from forge.jinja_ext import (
    ForgeExtension,
    comment,
    indent_block,
    lower_first,
    plugin_tables,
    rule,
    to_yaml,
    yaml_assign,
    yaml_scalar,
    yaml_value,
)


@pytest.mark.parametrize(
    ("value", "attendu"),
    [
        ("api", "api"),
        ("1.36", "'1.36'"),
        ("true", "'true'"),
        ("on", "'on'"),
        ("", "''"),
        (True, "true"),
        (None, "null"),
        (8080, "8080"),
    ],
)
def test_yaml_scalar_protege_ce_qui_doit_l_etre(value, attendu):
    assert yaml_scalar(value) == attendu


def test_to_yaml_rend_une_collection_vide_en_ligne():
    assert to_yaml([]) == "[]"
    assert to_yaml({}) == "{}"


def test_to_yaml_indente_un_bloc():
    assert to_yaml({"a": 1, "b": [2]}, indent=2) == "  a: 1\n  b:\n    - 2"


def test_to_yaml_conserve_l_ordre_d_insertion():
    assert to_yaml({"z": 1, "a": 2}) == "z: 1\na: 2"


def test_yaml_value_bascule_en_bloc_pour_une_collection_non_vide():
    assert yaml_value(["ALL"], indent=4) == "\n    - ALL"


def test_yaml_value_reste_en_ligne_pour_un_scalaire():
    assert yaml_value("api") == " api"
    assert yaml_value([]) == " []"


def test_yaml_assign_reste_en_ligne_pour_un_scalaire():
    assert yaml_assign("api") == " api"


def test_yaml_assign_indente_une_liste():
    assert yaml_assign(["a", "b"], indent=2) == "\n  - a\n  - b"


def test_comment_replie_et_prefixe():
    texte = "un texte assez long pour etre replie sur plusieurs lignes de commentaire"
    rendu = comment(texte, width=40)
    assert all(line.startswith("# ") for line in rendu.splitlines())
    assert max(len(line) for line in rendu.splitlines()) <= 40


def test_comment_rend_une_ligne_vide_en_diese_seul():
    assert comment("a\n\nb") == "# a\n#\n# b"


def test_comment_conserve_l_indentation_de_la_ligne_source():
    assert comment("  forge generate") == "#   forge generate"


def test_comment_indente_le_bloc_entier():
    assert comment("a", indent=4) == "    # a"


def test_comment_ne_laisse_pas_d_espace_en_fin_de_ligne():
    for line in comment("a\n\nb", indent=2).splitlines():
        assert line == line.rstrip()


def test_indent_block_laisse_la_premiere_ligne_par_defaut():
    assert indent_block("a\nb", 2) == "a\n  b"
    assert indent_block("a\nb", 2, first=True) == "  a\n  b"


def test_lower_first_epargne_les_sigles():
    assert lower_first("Boutique en ligne") == "boutique en ligne"
    assert lower_first("UTF8 impose") == "UTF8 impose"


def test_rule_produit_un_filet_de_commentaire():
    assert rule(5) == "# -----"


def test_l_extension_installe_les_filtres_du_coeur():
    env = jinja2.Environment(extensions=[ForgeExtension])
    assert "yaml_scalar" in env.filters
    assert "rule" in env.globals


def test_l_extension_charge_les_filtres_d_un_plugin(monkeypatch):
    monkeypatch.setenv("FORGE_PLUGIN_JINJA", "forge.plugins.demo.jinja_ext")
    env = jinja2.Environment(extensions=[ForgeExtension])
    assert env.filters["shout"]("abc") == "ABC"
    assert env.globals["demo_banner"]("x") == "== x =="


def test_plugin_tables_ignore_une_liste_vide():
    assert plugin_tables("") == ({}, {})
