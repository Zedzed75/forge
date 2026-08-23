"""Tests du questionnaire interactif, rejoué avec un prompter scripté."""

from __future__ import annotations

from typing import Any

import pytest

from ansible_forge.models.enums import OSFamily
from ansible_forge.models.spec import ProjectSpec
from ansible_forge.prompts.flow import run_interview
from tests.scripted_prompter import BASE_ANSWERS, ScriptedPrompter


def interview(**answers: Any) -> ProjectSpec:
    """Déroule un entretien en n'écrasant que les réponses fournies."""
    return run_interview(ScriptedPrompter({**BASE_ANSWERS, **answers}))


@pytest.fixture(scope="module", name="spec")
def default_spec() -> ProjectSpec:
    """Spec issue d'un entretien où toutes les valeurs par défaut sont acceptées."""
    return interview()


class TestEntretienParDefaut:
    def test_produit_une_spec_valide(self, spec: ProjectSpec):
        assert spec.project_name == "mon-projet"
        assert spec.os_family is OSFamily.DEBIAN
        assert spec.remote_user == "ansible"
        assert spec.ssh_port == 22
        assert spec.become is True

    def test_trois_environnements(self, spec: ProjectSpec):
        assert [env.name for env in spec.environments] == ["dev", "staging", "prod"]

    def test_un_groupe_webservers_avec_common(self, spec: ProjectSpec):
        assert [group.name for group in spec.groups] == ["webservers"]
        assert spec.groups[0].roles == ["common"]

    def test_une_machine_par_environnement(self, spec: ProjectSpec):
        for env in spec.environments:
            assert [host.name for host in env.all_hosts()] == [f"webservers-{env.name}-01"]

    def test_les_options_de_role_restent_par_defaut(self, spec: ProjectSpec):
        assert spec.role_options("common")["timezone"] == "Europe/Paris"

    def test_options_de_generation_par_defaut(self, spec: ProjectSpec):
        assert spec.options.use_vault is True
        assert spec.options.write_lint_config is True
        assert spec.options.embed_spec is True


class TestReponsesPersonnalisees:
    def test_nom_de_projet(self):
        assert interview(**{"Nom du projet": "infra-prod"}).project_name == "infra-prod"

    def test_famille_d_os(self):
        spec = interview(**{"Famille de système": "redhat"})
        assert spec.os_family is OSFamily.REDHAT

    def test_port_ssh(self):
        assert interview(**{"Port SSH des machines": "2222"}).ssh_port == 2222

    def test_environnements_selectionnes(self):
        spec = interview(**{"Environnements à générer": ["dev", "prod"]})
        assert [env.name for env in spec.environments] == ["dev", "prod"]

    def test_environnements_supplementaires(self):
        spec = interview(
            **{"Environnements à générer": ["prod"], "Environnements supplémentaires": "qa, uat"}
        )
        assert [env.name for env in spec.environments] == ["prod", "qa", "uat"]

    def test_aucun_environnement_retombe_sur_dev(self):
        spec = interview(**{"Environnements à générer": [], "Environnements supplémentaires": ""})
        assert [env.name for env in spec.environments] == ["dev"]

    def test_aucun_role_retombe_sur_common(self):
        spec = interview(**{"Rôles appliqués": []})
        assert spec.groups[0].roles == ["common"]

    def test_plusieurs_groupes(self):
        """La boucle de saisie des groupes s'arrête au premier refus."""
        remaining = {"additions": 1}

        class DeuxGroupes(ScriptedPrompter):
            def confirm(self, message: str, default: bool = True) -> bool:
                if "Ajouter un autre groupe" in message:
                    accepted = remaining["additions"] > 0
                    remaining["additions"] -= 1
                    return accepted
                return super().confirm(message, default)

        spec = run_interview(
            DeuxGroupes(
                {
                    **BASE_ANSWERS,
                    "Nom du groupe n°1": "webservers",
                    "Nom du groupe n°2": "dbservers",
                }
            )
        )
        assert [group.name for group in spec.groups] == ["webservers", "dbservers"]

    def test_machines_multiples(self):
        spec = interview(**{"Nombre de machines": "2"})
        assert len(spec.environments[0].all_hosts()) == 2

    def test_groupe_sans_machine(self):
        spec = interview(**{"Nombre de machines": "0"})
        assert spec.environments[0].all_hosts() == []

    def test_reglages_de_role_personnalises(self):
        spec = interview(
            **{
                "Personnaliser les réglages des rôles": True,
                "Fuseau horaire des machines": "UTC",
                "Paquets de base": "curl, vim",
                "Activer la synchronisation NTP": False,
            }
        )
        options = spec.role_options("common")
        assert options["timezone"] == "UTC"
        assert options["packages"] == ["curl", "vim"]
        assert options["enable_ntp"] is False

    def test_desactiver_le_vault(self):
        spec = interview(**{"Générer les modèles de fichiers vault": False})
        assert spec.options.use_vault is False


class TestValidationDesReponses:
    def test_un_nom_de_projet_invalide_est_rejete(self):
        with pytest.raises(AssertionError, match="Nom de projet invalide"):
            interview(**{"Nom du projet": "Mon Projet"})

    def test_un_nom_de_groupe_avec_tiret_est_rejete(self):
        with pytest.raises(AssertionError, match="le tiret est interdit"):
            interview(**{"Nom du groupe": "web-servers"})

    def test_un_nom_de_groupe_reserve_est_rejete(self):
        with pytest.raises(AssertionError, match="réservé par Ansible"):
            interview(**{"Nom du groupe": "all"})

    def test_une_adresse_invalide_est_rejetee(self):
        with pytest.raises(AssertionError, match="ni une adresse IP ni un nom de domaine"):
            interview(**{"Adresse IP": "pas une adresse"})

    def test_un_port_hors_bornes_est_rejete(self):
        with pytest.raises(AssertionError, match="entre 1 et 65535"):
            interview(**{"Port SSH des machines": "99999"})

    def test_un_port_non_numerique_est_rejete(self):
        with pytest.raises(AssertionError, match="entier est attendu"):
            interview(**{"Port SSH des machines": "ssh"})

    def test_un_nombre_de_machines_absurde_est_rejete(self):
        with pytest.raises(AssertionError, match="Au-delà de 100 machines"):
            interview(**{"Nombre de machines": "500"})

    def test_un_environnement_avec_tiret_est_rejete(self):
        with pytest.raises(AssertionError, match="Nom d'environnement invalide"):
            interview(**{"Environnements supplémentaires": "pre-prod"})
