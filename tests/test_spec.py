"""Tests du chargement, de la validation et de l'assemblage de la specification."""

from __future__ import annotations

import pytest

from forge.errors import SpecFileError, SpecValidationError
from forge.plugins_api.manager import ForgeManager
from forge.spec import io
from forge.spec.assembly import build_spec_model, resolve_domains, validate_spec
from forge.spec.names import find_duplicates, require_unique
from forge.spec.service import ServiceSpec

# ---------------------------------------------------------------------------
# Nommage
# ---------------------------------------------------------------------------


def test_find_duplicates_conserve_l_ordre_de_premiere_apparition():
    assert find_duplicates(["a", "b", "a", "c", "b"]) == ["a", "b"]


def test_require_unique_leve_sur_doublon():
    with pytest.raises(ValueError, match="noms en double"):
        require_unique(["a", "a"], "noms")


# ---------------------------------------------------------------------------
# Bloc service
# ---------------------------------------------------------------------------


def test_service_refuse_un_nom_non_dns(spec_data, manager):
    spec_data["service"]["name"] = "Boutique_Web"
    with pytest.raises(SpecValidationError, match="label DNS"):
        validate_spec(spec_data, manager)


def test_service_refuse_deux_environnements_de_production(spec_data, manager):
    spec_data["service"]["environments"][0]["production"] = True
    with pytest.raises(SpecValidationError, match="un seul environnement"):
        validate_spec(spec_data, manager)


def test_service_refuse_les_environnements_en_double(spec_data, manager):
    spec_data["service"]["environments"][1]["name"] = "dev"
    with pytest.raises(SpecValidationError, match="en double"):
        validate_spec(spec_data, manager)


def test_service_expose_ses_environnements_dans_l_ordre():
    service = ServiceSpec(
        name="boutique",
        description="d",
        owner="o",
        environments=[{"name": "dev"}, {"name": "prod", "production": True}],
    )
    assert service.environment_names == ("dev", "prod")
    assert service.environment("prod").production is True


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------


def test_le_modele_assemble_expose_une_section_par_domaine(manager):
    model = build_spec_model(manager)
    assert "demo" in model.model_fields
    assert "service" in model.model_fields


def test_sans_plugin_une_section_de_domaine_est_refusee(spec_data):
    with pytest.raises(SpecValidationError, match="section\\(s\\) inconnue"):
        validate_spec(spec_data, ForgeManager())


def test_une_section_absente_signifie_domaine_non_genere(spec_data, manager):
    spec_data.pop("demo")
    spec = validate_spec(spec_data, manager)
    assert spec.domain_names() == ()
    assert spec.section("demo") is None


def test_forge_version_inconnue_est_refusee(spec_data, manager):
    spec_data["forge_version"] = 99
    with pytest.raises(SpecValidationError, match="non supportee"):
        validate_spec(spec_data, manager)


def test_une_cle_inconnue_dans_une_section_est_refusee(spec_data, manager):
    spec_data["demo"]["inconnu"] = True
    with pytest.raises(SpecValidationError, match="inconnu"):
        validate_spec(spec_data, manager)


def test_le_sous_modele_du_plugin_est_bien_applique(spec_data, manager):
    spec_data["demo"]["widgets"][0]["kind"] = "sonar"
    with pytest.raises(SpecValidationError, match="type inconnu"):
        validate_spec(spec_data, manager)


# ---------------------------------------------------------------------------
# Selection des domaines
# ---------------------------------------------------------------------------


def test_resolve_domains_sans_only_retourne_les_domaines_presents(spec, manager):
    assert resolve_domains(spec, manager, None) == ["demo"]


def test_resolve_domains_refuse_un_domaine_inconnu(spec, manager):
    with pytest.raises(SpecValidationError, match="inconnu"):
        resolve_domains(spec, manager, ["terraform"])


def test_resolve_domains_refuse_un_domaine_absent_de_la_spec(spec_data, manager):
    spec_data.pop("demo")
    spec = validate_spec(spec_data, manager)
    with pytest.raises(SpecValidationError, match="absent"):
        resolve_domains(spec, manager, ["demo"])


# ---------------------------------------------------------------------------
# Entrees / sorties YAML
# ---------------------------------------------------------------------------


def test_sauver_puis_recharger_redonne_la_meme_structure(tmp_path, spec_data):
    path = io.save_spec(spec_data, tmp_path / "forge.yml", sections=["demo"])
    assert io.load_spec_data(path) == spec_data


def test_l_entete_cite_les_domaines_generes(tmp_path, spec_data):
    path = io.save_spec(spec_data, tmp_path / "forge.yml", sections=["demo"])
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "#   - demo" in text


def test_le_dump_ne_trie_pas_les_cles(spec_data):
    text = io.dump_yaml(spec_data)
    assert text.index("forge_version") < text.index("service") < text.index("demo")


def test_un_fichier_absent_donne_une_erreur_lisible(tmp_path):
    with pytest.raises(SpecFileError, match="introuvable"):
        io.load_spec_data(tmp_path / "absent.yml")


def test_un_yaml_qui_n_est_pas_un_dictionnaire_est_refuse(tmp_path):
    path = tmp_path / "forge.yml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(SpecFileError, match="dictionnaire"):
        io.load_spec_data(path)


def test_un_yaml_vide_est_refuse(tmp_path):
    path = tmp_path / "forge.yml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(SpecFileError, match="vide"):
        io.load_spec_data(path)


def test_une_cle_yaml_non_textuelle_donne_une_erreur_lisible(tmp_path):
    """YAML 1.1 relit `on:` comme un booleen : sans garde-fou, trace Python nue."""
    path = tmp_path / "forge.yml"
    path.write_text("forge_version: 1\non: true\n", encoding="utf-8")
    with pytest.raises(SpecFileError, match="cle YAML non textuelle"):
        io.load_spec_data(path)


def test_une_cle_non_textuelle_imbriquee_est_aussi_signalee(tmp_path):
    path = tmp_path / "forge.yml"
    path.write_text("service:\n  labels:\n    yes: x\n", encoding="utf-8")
    with pytest.raises(SpecFileError, match="service.labels"):
        io.load_spec_data(path)


def test_une_ecriture_impossible_donne_une_erreur_lisible(tmp_path):
    fichier = tmp_path / "occupe"
    fichier.write_text("x", encoding="utf-8")
    with pytest.raises(SpecFileError, match="ecriture impossible"):
        io.save_spec({"forge_version": 1}, fichier / "forge.yml")
