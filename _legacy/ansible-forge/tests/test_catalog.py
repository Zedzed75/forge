"""Tests du catalogue de rôles."""

from __future__ import annotations

import pytest

from ansible_forge.catalog.definition import OptionKind
from ansible_forge.catalog.registry import (
    ROLE_CATALOG,
    collections_for,
    get_role,
    role_names,
    sort_roles,
    validate_options,
)
from ansible_forge.errors import CatalogError

EXPECTED_ROLES = [
    "common",
    "users",
    "ssh_hardening",
    "firewall",
    "nginx",
    "docker",
    "postgresql",
]


def test_le_catalogue_contient_les_sept_roles():
    assert role_names() == EXPECTED_ROLES


def test_l_ordre_du_catalogue_est_fige():
    """L'ordre pilote l'application des rôles : le figer protège le rendu déterministe."""
    assert list(ROLE_CATALOG) == EXPECTED_ROLES


@pytest.mark.parametrize("name", EXPECTED_ROLES)
def test_chaque_role_est_documente(name: str):
    role = get_role(name)
    assert role.summary, f"Le rôle {name} doit avoir un résumé."
    for option in role.options:
        assert option.question, f"{name}.{option.name} doit avoir une question."
        assert option.description, f"{name}.{option.name} doit avoir une description."
        assert option.allowed, f"{name}.{option.name} doit documenter ses valeurs admises."


@pytest.mark.parametrize("name", EXPECTED_ROLES)
def test_les_defauts_sont_valides_pour_leur_type(name: str):
    """Les valeurs par défaut doivent passer leur propre validation."""
    assert validate_options(name, {}) == get_role(name).default_options()


@pytest.mark.parametrize("name", EXPECTED_ROLES)
def test_les_options_de_type_choice_declarent_leurs_choix(name: str):
    for option in get_role(name).options:
        if option.kind is OptionKind.CHOICE:
            assert option.choices, f"{name}.{option.name} doit déclarer des choix."
            assert option.default in option.choices


@pytest.mark.parametrize("name", EXPECTED_ROLES)
def test_les_options_de_type_records_declarent_leurs_champs(name: str):
    for option in get_role(name).options:
        if option.kind is OptionKind.RECORDS:
            assert option.fields, f"{name}.{option.name} doit déclarer ses champs."


def test_get_role_leve_une_erreur_explicite():
    with pytest.raises(CatalogError, match="Rôle inconnu : 'k8s'"):
        get_role("k8s")


def test_sort_roles_respecte_l_ordre_du_catalogue():
    assert sort_roles(["postgresql", "common", "nginx"]) == ["common", "nginx", "postgresql"]


def test_collections_for_deduplique_et_trie():
    assert collections_for(["firewall", "common"]) == ["ansible.posix", "community.general"]


def test_collections_for_sans_role_retourne_une_liste_vide():
    assert collections_for([]) == []


def test_validate_options_refuse_une_cle_inconnue():
    with pytest.raises(CatalogError, match="Option\\(s\\) inconnue\\(s\\)"):
        validate_options("nginx", {"servername": "x"})


def test_validate_options_refuse_un_entier_booleen():
    """True est un int en Python : la validation doit tout de même le refuser."""
    with pytest.raises(CatalogError, match="attend un entier"):
        validate_options("nginx", {"listen_port": True})


def test_validate_options_refuse_une_liste_pour_une_chaine():
    with pytest.raises(CatalogError, match="attend une chaîne"):
        validate_options("nginx", {"server_name": ["a", "b"]})


def test_validate_options_refuse_des_records_mal_formes():
    with pytest.raises(CatalogError, match="liste de dictionnaires"):
        validate_options("users", {"accounts": ["alice"]})


def test_validate_options_copie_les_listes():
    """Les valeurs par défaut du catalogue ne doivent jamais être partagées par référence."""
    first = validate_options("common", {})
    first["packages"].append("nano")
    assert "nano" not in validate_options("common", {})["packages"]
