"""Tests of loading, validating and assembling the specification."""

from __future__ import annotations

import pytest

from forge.errors import SpecFileError, SpecValidationError
from forge.plugins_api.manager import ForgeManager
from forge.spec import io
from forge.spec.assembly import build_spec_model, resolve_domains, validate_spec
from forge.spec.names import find_duplicates, require_unique
from forge.spec.service import ServiceSpec

# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def test_find_duplicates_keeps_the_order_of_first_appearance():
    assert find_duplicates(["a", "b", "a", "c", "b"]) == ["a", "b"]


def test_require_unique_raises_on_a_duplicate():
    with pytest.raises(ValueError, match="duplicate names"):
        require_unique(["a", "a"], "names")


# ---------------------------------------------------------------------------
# The service block
# ---------------------------------------------------------------------------


def test_service_refuses_a_non_dns_name(spec_data, manager):
    spec_data["service"]["name"] = "Boutique_Web"
    with pytest.raises(SpecValidationError, match="DNS label"):
        validate_spec(spec_data, manager)


def test_service_refuses_two_production_environments(spec_data, manager):
    spec_data["service"]["environments"][0]["production"] = True
    with pytest.raises(SpecValidationError, match="only one environment"):
        validate_spec(spec_data, manager)


def test_service_refuses_duplicate_environments(spec_data, manager):
    spec_data["service"]["environments"][1]["name"] = "dev"
    with pytest.raises(SpecValidationError, match="duplicate"):
        validate_spec(spec_data, manager)


def test_service_exposes_its_environments_in_order():
    service = ServiceSpec(
        name="boutique",
        description="d",
        owner="o",
        environments=[{"name": "dev"}, {"name": "prod", "production": True}],
    )
    assert service.environment_names == ("dev", "prod")
    assert service.environment("prod").production is True


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def test_the_assembled_model_exposes_one_section_per_domain(manager):
    model = build_spec_model(manager)
    assert "demo" in model.model_fields
    assert "service" in model.model_fields


def test_without_a_plugin_a_domain_section_is_refused(spec_data):
    with pytest.raises(SpecValidationError, match="unknown section\\(s\\)"):
        validate_spec(spec_data, ForgeManager())


def test_an_absent_section_means_the_domain_is_not_generated(spec_data, manager):
    spec_data.pop("demo")
    spec = validate_spec(spec_data, manager)
    assert spec.domain_names() == ()
    assert spec.section("demo") is None


def test_an_unknown_forge_version_is_refused(spec_data, manager):
    spec_data["forge_version"] = 99
    with pytest.raises(SpecValidationError, match="unsupported"):
        validate_spec(spec_data, manager)


def test_an_unknown_key_inside_a_section_is_refused(spec_data, manager):
    spec_data["demo"]["inconnu"] = True
    with pytest.raises(SpecValidationError, match="inconnu"):
        validate_spec(spec_data, manager)


def test_the_plugin_sub_model_is_really_applied(spec_data, manager):
    spec_data["demo"]["widgets"][0]["kind"] = "sonar"
    with pytest.raises(SpecValidationError, match="unknown kind"):
        validate_spec(spec_data, manager)


# ---------------------------------------------------------------------------
# Domain selection
# ---------------------------------------------------------------------------


def test_resolve_domains_without_only_returns_the_domains_present(spec, manager):
    assert resolve_domains(spec, manager, None) == ["demo"]


def test_resolve_domains_refuses_an_unknown_domain(spec, manager):
    with pytest.raises(SpecValidationError, match="unknown"):
        resolve_domains(spec, manager, ["terraform"])


def test_resolve_domains_refuses_a_domain_absent_from_the_spec(spec_data, manager):
    spec_data.pop("demo")
    spec = validate_spec(spec_data, manager)
    with pytest.raises(SpecValidationError, match="absent"):
        resolve_domains(spec, manager, ["demo"])


# ---------------------------------------------------------------------------
# YAML input / output
# ---------------------------------------------------------------------------


def test_saving_then_reloading_gives_back_the_same_structure(tmp_path, spec_data):
    path = io.save_spec(spec_data, tmp_path / "forge.yml", sections=["demo"])
    assert io.load_spec_data(path) == spec_data


def test_the_header_names_the_generated_domains(tmp_path, spec_data):
    path = io.save_spec(spec_data, tmp_path / "forge.yml", sections=["demo"])
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "#   - demo" in text


def test_the_dump_does_not_sort_the_keys(spec_data):
    text = io.dump_yaml(spec_data)
    assert text.index("forge_version") < text.index("service") < text.index("demo")


def test_a_missing_file_gives_a_readable_error(tmp_path):
    with pytest.raises(SpecFileError, match="not found"):
        io.load_spec_data(tmp_path / "absent.yml")


def test_a_yaml_that_is_not_a_mapping_is_refused(tmp_path):
    path = tmp_path / "forge.yml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(SpecFileError, match="YAML mapping"):
        io.load_spec_data(path)


def test_an_empty_yaml_is_refused(tmp_path):
    path = tmp_path / "forge.yml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(SpecFileError, match="empty"):
        io.load_spec_data(path)


def test_a_non_textual_yaml_key_gives_a_readable_error(tmp_path):
    """YAML 1.1 reads `on:` as a boolean: without a guard, a bare Python traceback."""
    path = tmp_path / "forge.yml"
    path.write_text("forge_version: 1\non: true\n", encoding="utf-8")
    with pytest.raises(SpecFileError, match="non-textual YAML key"):
        io.load_spec_data(path)


def test_a_nested_non_textual_key_is_reported_too(tmp_path):
    path = tmp_path / "forge.yml"
    path.write_text("service:\n  labels:\n    yes: x\n", encoding="utf-8")
    with pytest.raises(SpecFileError, match="service.labels"):
        io.load_spec_data(path)


def test_an_impossible_write_gives_a_readable_error(tmp_path):
    occupied = tmp_path / "occupied"
    occupied.write_text("x", encoding="utf-8")
    with pytest.raises(SpecFileError, match="cannot write"):
        io.save_spec({"forge_version": 1}, occupied / "forge.yml")
