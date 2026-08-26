"""Tests du plugin Ansible : modele, controles croises, validateurs, entretien.

La parite avec le generateur d'origine a servi pendant tout le portage, puis a
ete retiree en phase 10 avec `_legacy/` : elle mesurait une ressemblance a un
outil qui n'existe plus, et le projet genere l'a depuis depassee — il passe
`ansible-lint` en profil production, ce que la suite d'origine n'avait jamais
verifie. La non-regression est desormais tenue par `tests/golden/` seul.

Ce module couvre ce que ni l'un ni l'autre ne dit : les refus, les messages, et
les garde-fous propres au domaine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge import pipeline
from forge.errors import SpecValidationError
from forge.plugins.ansible import answers as answers_module
from forge.plugins.ansible import tree, validators
from forge.plugins.ansible.spec import AnsibleSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from tests.scripted_prompter import ScriptedPrompter

ANSIBLE_PLUGIN = "forge.plugins.ansible.plugin"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(ANSIBLE_PLUGIN)
    return instance


def _spec_data(**surcharges) -> dict:
    """Specification minimale valide du domaine Ansible."""
    data = {
        "forge_version": 1,
        "service": {
            "name": "passerelle",
            "description": "Passerelle applicative",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "prod", "production": True}],
        },
        "ansible": {
            "groups": [{"name": "gateways", "roles": ["common"]}],
            "hosts": {"prod": {"gateways": [{"name": "gw-01", "ansible_host": "10.0.0.1"}]}},
        },
    }
    for chemin, valeur in surcharges.items():
        cible = data
        *parents, feuille = chemin.split(".")
        for parent in parents:
            cible = cible[parent]
        cible[feuille] = valeur
    return data


# ---------------------------------------------------------------------------
# Modele
# ---------------------------------------------------------------------------


def test_un_nom_de_groupe_a_tiret_est_refuse():
    """Ansible interdit le tiret dans un nom de groupe."""
    with pytest.raises(SpecValidationError, match="tirets sont interdits"):
        validate_spec(
            _spec_data(**{"ansible.groups": [{"name": "web-servers"}]}), _manager()
        )


def test_un_nom_de_groupe_reserve_est_refuse():
    with pytest.raises(SpecValidationError, match="reserve par Ansible"):
        validate_spec(_spec_data(**{"ansible.groups": [{"name": "all"}]}), _manager())


def test_un_role_inconnu_est_refuse():
    with pytest.raises(SpecValidationError, match="Role inconnu"):
        validate_spec(
            _spec_data(**{"ansible.groups": [{"name": "g", "roles": ["kubernetes"]}]}),
            _manager(),
        )


def test_un_groupe_sans_role_est_refuse():
    with pytest.raises(SpecValidationError, match="au moins un role"):
        validate_spec(
            _spec_data(**{"ansible.groups": [{"name": "g", "roles": []}]}), _manager()
        )


def test_les_hotes_citant_un_groupe_inconnu_sont_refuses():
    with pytest.raises(SpecValidationError, match="groupes inconnus"):
        validate_spec(
            _spec_data(**{"ansible.hosts": {"prod": {"absent": []}}}), _manager()
        )


def test_un_hote_declare_deux_fois_dans_un_environnement_est_refuse():
    data = _spec_data()
    data["ansible"]["groups"].append({"name": "autres", "roles": ["common"]})
    data["ansible"]["hosts"]["prod"]["autres"] = [
        {"name": "gw-01", "ansible_host": "10.0.0.2"}
    ]
    with pytest.raises(SpecValidationError, match="plusieurs fois"):
        validate_spec(data, _manager())


def test_un_nom_de_variable_libre_invalide_est_refuse():
    with pytest.raises(SpecValidationError, match="Nom de variable invalide"):
        validate_spec(
            _spec_data(
                **{"ansible.groups": [{"name": "g", "roles": ["common"], "vars": {"Ma-Var": 1}}]}
            ),
            _manager(),
        )


def test_les_options_de_role_absentes_prennent_le_defaut_du_catalogue():
    """C'est ce qui rend une spec partielle equivalente a une spec complete."""
    spec = validate_spec(_spec_data(), _manager())
    options = spec.ansible.role_options("common")
    assert options, "les options du catalogue devraient etre presentes"
    assert "common_timezone" not in options, "les cles sont nues, sans prefixe de role"


def test_les_roles_sont_ordonnes_par_le_catalogue_pas_par_l_alphabet():
    data = _spec_data(
        **{
            "ansible.groups": [{"name": "g", "roles": ["nginx", "users", "common"]}],
            "ansible.hosts": {},
        }
    )
    spec = validate_spec(data, _manager())
    assert [role.name for role in spec.ansible.roles] == ["common", "users", "nginx"]
    assert spec.ansible.groups[0].roles == ["common", "users", "nginx"]


def test_un_role_applique_mais_non_configure_est_ajoute():
    spec = validate_spec(_spec_data(), _manager())
    assert [role.name for role in spec.ansible.roles] == ["common"]


# ---------------------------------------------------------------------------
# Controles croises — ce que le sous-modele ne peut pas voir
# ---------------------------------------------------------------------------


def test_un_environnement_inconnu_dans_hosts_est_signale():
    """`AnsibleSpec` ne voit pas `service.environments` : le controle croise, si."""
    data = _spec_data()
    data["ansible"]["hosts"]["recette"] = {"gateways": []}
    spec = validate_spec(data, _manager())
    issues = answers_module.cross_check(spec)
    assert [issue.level for issue in issues] == ["error"]
    assert "recette" in issues[0].message
    assert issues[0].hint


def test_un_nom_d_environnement_a_tiret_est_signale():
    """Le coeur accepte le tiret (label DNS), Ansible non (nom de groupe)."""
    data = _spec_data()
    data["service"]["environments"] = [{"name": "pre-prod"}]
    data["ansible"]["hosts"] = {"pre-prod": {"gateways": []}}
    spec = validate_spec(data, _manager())
    issues = answers_module.cross_check(spec)
    assert any("pre-prod" in issue.message for issue in issues)
    assert any("souligne" in issue.hint for issue in issues)


def test_une_specification_saine_ne_produit_aucun_constat():
    spec = validate_spec(_spec_data(), _manager())
    assert answers_module.cross_check(spec) == []


# ---------------------------------------------------------------------------
# Validateurs
# ---------------------------------------------------------------------------


def test_une_verification_de_syntaxe_par_environnement_plus_le_linter():
    data = _spec_data()
    data["service"]["environments"] = [{"name": "dev"}, {"name": "prod", "production": True}]
    data["ansible"]["hosts"] = {}
    spec = validate_spec(data, _manager())
    commandes = validators.commands(spec, Path("ansible"))
    assert [c.label for c in commandes] == [
        "syntax-check (dev)",
        "syntax-check (prod)",
        "ansible-lint",
    ]
    assert all(c.requires_linux for c in commandes)


def test_les_commandes_transmettent_le_chemin_des_collections(monkeypatch):
    """Sans les collections Galaxy, `--syntax-check` echoue sur des modules absents."""
    monkeypatch.setenv(validators.COLLECTIONS_ENV_VAR, "/ailleurs/collections")
    spec = validate_spec(_spec_data(), _manager())
    commande = validators.commands(spec, Path("ansible"))[0]
    assert dict(commande.env)["ANSIBLE_COLLECTIONS_PATH"] == "/ailleurs/collections"
    assert dict(commande.env)["ANSIBLE_FORCE_COLOR"] == "0"


# ---------------------------------------------------------------------------
# Arborescence annoncee par le README
# ---------------------------------------------------------------------------


def test_le_readme_annonce_exactement_les_fichiers_generes(tmp_path):
    """`tree.py` duplique la connaissance de l'arborescence : ce test l'atteste.

    copier ne peut pas connaitre a l'avance la liste des fichiers qu'il ecrira,
    et le README genere l'affiche. Un gabarit ajoute sans mise a jour de
    `expected_paths` rendrait donc le README faux — en silence, sans ce test.
    """
    manager = _manager()
    data = _spec_data()
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    produits = {
        chemin.relative_to(tmp_path / "ansible").as_posix()
        for chemin in (tmp_path / "ansible").rglob("*")
        if chemin.is_file()
    }
    annonces = set(tree.expected_paths(spec))
    # Ecarts assumes et documentes dans tree.py : la plomberie de copier n'est
    # pas annoncee, et forge.yml vit desormais a la racine du depot cible.
    assert produits - annonces <= {".copier-answers.yml"}
    assert annonces - produits <= {"forge.yml"}


# ---------------------------------------------------------------------------
# Entretien
# ---------------------------------------------------------------------------

#: Entretien minimal : connexion, un groupe, un environnement, une machine.
ENTRETIEN_MINIMAL = [
    "debian", "ansible", "22", True, "auto_silent",
    "gateways", "Passerelles exposees", ["common"], False,
    False,
    "1", "gw-prod-01", "10.30.0.11",
    False,
    True, True, False,
]


def test_l_entretien_produit_une_section_valide():
    from forge.plugins.ansible import interview
    from forge.spec.service import ServiceSpec

    service = ServiceSpec(
        name="passerelle",
        description="Passerelle applicative",
        owner="Equipe Plateforme",
        environments=[{"name": "prod", "production": True}],
    )
    prompter = ScriptedPrompter(list(ENTRETIEN_MINIMAL))
    section = interview.run(prompter, service)

    assert prompter.exhausted
    assert section is not None
    modele = AnsibleSpec.model_validate(section)
    assert [groupe.name for groupe in modele.groups] == ["gateways"]
    assert modele.hosts["prod"]["gateways"][0].name == "gw-prod-01"


def test_l_entretien_ne_repose_pas_les_questions_du_bloc_service():
    """L'identite et les environnements appartiennent au coeur, pas au domaine."""
    from forge.plugins.ansible import interview
    from forge.spec.service import ServiceSpec

    service = ServiceSpec(
        name="passerelle",
        description="Passerelle applicative",
        owner="Equipe Plateforme",
        environments=[{"name": "prod", "production": True}],
    )
    prompter = ScriptedPrompter(list(ENTRETIEN_MINIMAL))
    interview.run(prompter, service)

    posees = " ".join(prompter.asked).lower()
    for question_du_coeur in (
        "nom du service",
        "nom du projet",
        "responsable",
        "environnements, separes",
        "adresse de contact",
    ):
        assert question_du_coeur not in posees, (
            f"l'entretien du domaine repose une question du coeur : {question_du_coeur}"
        )


# ---------------------------------------------------------------------------
# Validation reelle du projet genere
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_le_projet_genere_passe_ses_propres_validateurs(tmp_path):
    """Regle dure de CLAUDE.md : le projet genere doit passer ses validateurs.

    Le generateur d'origine ne l'avait jamais verifie — sa suite ignorait
    ansible-lint, faute d'outil installe. Ce test lance les deux outils pour de
    vrai (nativement, ou via le pont WSL sous Windows) sur le cas le plus riche
    du catalogue.
    """
    from forge.validate import tools

    if not tools.probe("ansible-playbook", True).available:
        pytest.skip("ansible-playbook introuvable, nativement comme dans WSL")
    if not tools.probe("ansible-lint", True).available:
        pytest.skip("ansible-lint introuvable, nativement comme dans WSL")

    manager = _manager()
    data = _spec_data()
    data["ansible"]["groups"] = [
        {"name": "gateways", "roles": ["common", "users", "ssh_hardening", "firewall"]}
    ]
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    resultat = pipeline.validate(spec, manager, tmp_path)
    echecs = [check.label for rapport in resultat.reports for check in rapport.failures()]
    assert not echecs, (
        f"validateurs en echec : {', '.join(echecs)}\n"
        + "\n".join(
            check.detail
            for rapport in resultat.reports
            for check in rapport.failures()
        )[:2000]
    )
