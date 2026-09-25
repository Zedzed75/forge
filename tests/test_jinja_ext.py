"""Tests of the filters exposed to the templates.

These filters set the formatting of **every** generated file: a regression here
shows up in every project, hence the case-by-case coverage.
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
    ("value", "expected"),
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
def test_yaml_scalar_protects_what_needs_protecting(value, expected):
    assert yaml_scalar(value) == expected


def test_to_yaml_renders_an_empty_collection_inline():
    assert to_yaml([]) == "[]"
    assert to_yaml({}) == "{}"


def test_to_yaml_indents_a_block():
    assert to_yaml({"a": 1, "b": [2]}, indent=2) == "  a: 1\n  b:\n    - 2"


def test_to_yaml_keeps_insertion_order():
    assert to_yaml({"z": 1, "a": 2}) == "z: 1\na: 2"


def test_yaml_value_switches_to_a_block_for_a_non_empty_collection():
    assert yaml_value(["ALL"], indent=4) == "\n    - ALL"


def test_yaml_value_stays_inline_for_a_scalar():
    assert yaml_value("api") == " api"
    assert yaml_value([]) == " []"


def test_yaml_assign_stays_inline_for_a_scalar():
    assert yaml_assign("api") == " api"


def test_yaml_assign_indents_a_list():
    assert yaml_assign(["a", "b"], indent=2) == "\n  - a\n  - b"


def test_comment_wraps_and_prefixes():
    text = "a text long enough to be wrapped over several comment lines here"
    rendered = comment(text, width=40)
    assert all(line.startswith("# ") for line in rendered.splitlines())
    assert max(len(line) for line in rendered.splitlines()) <= 40


def test_comment_renders_a_blank_line_as_a_lone_hash():
    assert comment("a\n\nb") == "# a\n#\n# b"


def test_comment_keeps_the_indentation_of_the_source_line():
    assert comment("  forge generate") == "#   forge generate"


def test_comment_indents_the_whole_block():
    assert comment("a", indent=4) == "    # a"


def test_comment_leaves_no_trailing_space():
    for line in comment("a\n\nb", indent=2).splitlines():
        assert line == line.rstrip()


def test_indent_block_leaves_the_first_line_alone_by_default():
    assert indent_block("a\nb", 2) == "a\n  b"
    assert indent_block("a\nb", 2, first=True) == "  a\n  b"


def test_lower_first_spares_acronyms():
    assert lower_first("Online store") == "online store"
    assert lower_first("UTF8 required") == "UTF8 required"


def test_rule_produces_a_comment_rule():
    assert rule(5) == "# -----"


def test_the_extension_installs_the_core_filters():
    env = jinja2.Environment(extensions=[ForgeExtension])
    assert "yaml_scalar" in env.filters
    assert "rule" in env.globals


def test_the_extension_loads_a_plugin_s_filters(monkeypatch):
    monkeypatch.setenv("FORGE_PLUGIN_JINJA", "forge.plugins.demo.jinja_ext")
    env = jinja2.Environment(extensions=[ForgeExtension])
    assert env.filters["shout"]("abc") == "ABC"
    assert env.globals["demo_banner"]("x") == "== x =="


def test_plugin_tables_ignores_an_empty_list():
    assert plugin_tables("") == ({}, {})
