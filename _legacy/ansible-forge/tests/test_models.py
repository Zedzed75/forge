"""Tests du modèle de spécification (validation, défauts, cohérence)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ansible_forge.models.enums import OSFamily
from ansible_forge.models.spec import (
    SPEC_VERSION,
    EnvironmentSpec,
    GroupSpec,
    HostSpec,
    ProjectSpec,
    RoleConfig,
)
from tests.conftest import build_spec


class TestHostSpec:
    def test_accepte_une_adresse_ip(self):
        host = HostSpec(name="web-dev-01", ansible_host="10.0.0.5")
        assert host.ansible_host == "10.0.0.5"
        assert host.ansible_port is None

    def test_accepte_un_fqdn(self):
        assert HostSpec(name="web01", ansible_host="web01.example.com").ansible_host

    def test_refuse_une_adresse_invalide(self):
        with pytest.raises(ValidationError, match="ni une adresse IP ni un nom de domaine"):
            HostSpec(name="web01", ansible_host="257.1.1.1 ou pas")

    def test_refuse_un_nom_en_majuscules(self):
        with pytest.raises(ValidationError, match="Nom d'hôte invalide"):
            HostSpec(name="WEB01", ansible_host="10.0.0.5")

    def test_refuse_un_port_hors_bornes(self):
        with pytest.raises(ValidationError, match="entre 1 et 65535"):
            HostSpec(name="web01", ansible_host="10.0.0.5", ansible_port=70000)

    def test_refuse_un_nom_de_variable_invalide(self):
        with pytest.raises(ValidationError, match="Nom de variable"):
            HostSpec(name="web01", ansible_host="10.0.0.5", vars={"Mauvais-Nom": 1})

    def test_refuse_un_champ_inconnu(self):
        with pytest.raises(ValidationError):
            HostSpec(name="web01", ansible_host="10.0.0.5", ansibl_port=22)


class TestGroupSpec:
    def test_role_common_par_defaut(self):
        assert GroupSpec(name="webservers").roles == ["common"]

    def test_refuse_un_tiret_dans_le_nom(self):
        with pytest.raises(ValidationError, match="le tiret est interdit"):
            GroupSpec(name="web-servers")

    def test_refuse_un_nom_reserve(self):
        with pytest.raises(ValidationError, match="réservé par Ansible"):
            GroupSpec(name="all")

    def test_refuse_un_role_hors_catalogue(self):
        with pytest.raises(ValidationError, match="Rôle inconnu"):
            GroupSpec(name="webservers", roles=["kubernetes"])

    def test_refuse_une_liste_de_roles_vide(self):
        with pytest.raises(ValidationError, match="au moins un rôle"):
            GroupSpec(name="webservers", roles=[])

    def test_refuse_les_roles_en_double(self):
        with pytest.raises(ValidationError, match="en double"):
            GroupSpec(name="webservers", roles=["common", "common"])

    def test_trie_les_roles_selon_l_ordre_du_catalogue(self):
        group = GroupSpec(name="webservers", roles=["nginx", "common", "firewall"])
        assert group.roles == ["common", "firewall", "nginx"]


class TestEnvironmentSpec:
    def test_refuse_deux_hotes_de_meme_nom(self):
        with pytest.raises(ValidationError, match="déclaré\\(s\\) plusieurs fois"):
            EnvironmentSpec(
                name="dev",
                hosts={
                    "webservers": [{"name": "web01", "ansible_host": "10.0.0.1"}],
                    "dbservers": [{"name": "web01", "ansible_host": "10.0.0.2"}],
                },
            )

    def test_all_hosts_est_trie_par_nom(self):
        env = EnvironmentSpec(
            name="dev",
            hosts={
                "webservers": [
                    {"name": "web02", "ansible_host": "10.0.0.2"},
                    {"name": "web01", "ansible_host": "10.0.0.1"},
                ],
            },
        )
        assert [host.name for host in env.all_hosts()] == ["web01", "web02"]

    def test_refuse_un_nom_avec_tiret(self):
        with pytest.raises(ValidationError, match="Nom d'environnement invalide"):
            EnvironmentSpec(name="pre-prod")


class TestRoleConfig:
    def test_complete_les_options_manquantes_avec_les_defauts(self):
        config = RoleConfig(name="common")
        assert config.options["timezone"] == "Europe/Paris"
        assert config.options["packages"] == ["ca-certificates", "curl", "htop", "vim"]

    def test_conserve_les_options_fournies(self):
        config = RoleConfig(name="common", options={"timezone": "UTC"})
        assert config.options["timezone"] == "UTC"
        assert config.options["enable_ntp"] is True

    def test_refuse_une_option_inconnue(self):
        with pytest.raises(ValidationError, match="Option\\(s\\) inconnue\\(s\\)"):
            RoleConfig(name="common", options={"timezon": "UTC"})

    def test_refuse_un_type_d_option_incorrect(self):
        with pytest.raises(ValidationError, match="attend un booléen"):
            RoleConfig(name="common", options={"enable_ntp": "oui"})

    def test_refuse_une_valeur_hors_des_choix(self):
        with pytest.raises(ValidationError, match="parmi"):
            RoleConfig(name="firewall", options={"backend": "iptables"})

    def test_options_ordonnees_comme_le_catalogue(self):
        config = RoleConfig(name="common", options={"enable_ntp": False, "timezone": "UTC"})
        assert list(config.options) == [
            "timezone",
            "packages",
            "manage_timezone",
            "enable_ntp",
            "manage_motd",
        ]


class TestProjectSpec:
    def test_construit_une_spec_valide(self, spec: ProjectSpec):
        assert spec.project_name == "demo-infra"
        assert spec.spec_version == SPEC_VERSION
        assert spec.os_family is OSFamily.DEBIAN
        assert spec.become is True

    def test_complete_automatiquement_les_roles_utilises(self, spec: ProjectSpec):
        assert [config.name for config in spec.roles] == ["common", "nginx"]

    def test_les_roles_sont_ordonnes_selon_le_catalogue(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["postgresql", "nginx", "common"]}]
        )
        assert [config.name for config in spec.roles] == ["common", "nginx", "postgresql"]

    def test_ordered_used_roles(self, spec: ProjectSpec):
        assert spec.ordered_used_roles() == ["common", "nginx"]

    def test_refuse_un_nom_de_projet_invalide(self):
        with pytest.raises(ValidationError, match="Nom de projet invalide"):
            build_spec(project_name="Mon Projet")

    def test_refuse_l_absence_d_environnement(self):
        with pytest.raises(ValidationError, match="au moins un environnement"):
            build_spec(environments=[])

    def test_refuse_l_absence_de_groupe(self):
        with pytest.raises(ValidationError, match="au moins un groupe"):
            build_spec(groups=[])

    def test_refuse_un_hote_dans_un_groupe_inconnu(self):
        with pytest.raises(ValidationError, match="groupes inconnus"):
            build_spec(
                environments=[
                    {
                        "name": "dev",
                        "hosts": {"dbservers": [{"name": "db01", "ansible_host": "10.0.0.9"}]},
                    }
                ]
            )

    def test_refuse_des_group_vars_pour_un_groupe_inconnu(self):
        with pytest.raises(ValidationError, match="variables pour des groupes"):
            build_spec(
                environments=[{"name": "dev", "group_vars": {"dbservers": {"foo": 1}}}]
            )

    def test_accepte_group_vars_all(self):
        spec = build_spec(
            environments=[{"name": "dev", "group_vars": {"all": {"ntp_server": "10.0.0.1"}}}]
        )
        assert spec.environments[0].group_vars["all"]["ntp_server"] == "10.0.0.1"

    def test_refuse_des_environnements_en_double(self):
        with pytest.raises(ValidationError, match="Environnement\\(s\\) en double"):
            build_spec(environments=[{"name": "dev"}, {"name": "dev"}])

    def test_refuse_des_groupes_en_double(self):
        with pytest.raises(ValidationError, match="Groupe\\(s\\) en double"):
            build_spec(groups=[{"name": "webservers"}, {"name": "webservers"}])

    def test_refuse_une_version_de_spec_inconnue(self):
        with pytest.raises(ValidationError, match="non supportée"):
            build_spec(spec_version=99)

    def test_role_options_retourne_les_options_resolues(self, spec: ProjectSpec):
        assert spec.role_options("nginx")["server_name"] == "example.local"

    def test_role_options_retourne_les_defauts_pour_un_role_non_utilise(self, spec: ProjectSpec):
        assert spec.role_options("docker")["channel"] == "stable"
