"""Tests of the Ansible plugin: model, cross-checks, validators, interview.

Parity with the original generator served throughout the port, then was removed
in phase 10 along with `_legacy/`: it measured a resemblance to a tool that no
longer exists, and the generated project has since gone past it — it passes
`ansible-lint` in production profile, which the original suite had never
checked. Non-regression is now held by `tests/golden/` alone.

This module covers what neither of them says: the refusals, the messages, and
the guards specific to the domain.

The plugin's own messages are still French: the domains are translated with
their templates, so the `match=` patterns below quote them as they are.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge import pipeline
from forge.errors import SpecValidationError
from forge.plugins.ansible import answers as answers_module
from forge.plugins.ansible import derive, tree, validators
from forge.plugins.ansible.catalog import collections as catalog_collections
from forge.plugins.ansible.catalog import registry
from forge.plugins.ansible.spec import AnsibleSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from tests.scripted_prompter import ScriptedPrompter

ANSIBLE_PLUGIN = "forge.plugins.ansible.plugin"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(ANSIBLE_PLUGIN)
    return instance


def _spec_data(**overrides) -> dict:
    """Minimal valid specification of the Ansible domain."""
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
    for path, value in overrides.items():
        target = data
        *parents, leaf = path.split(".")
        for parent in parents:
            target = target[parent]
        target[leaf] = value
    return data


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_a_group_name_with_a_hyphen_is_refused():
    """Ansible forbids the hyphen in a group name."""
    with pytest.raises(SpecValidationError, match="tirets sont interdits"):
        validate_spec(
            _spec_data(**{"ansible.groups": [{"name": "web-servers"}]}), _manager()
        )


def test_a_reserved_group_name_is_refused():
    with pytest.raises(SpecValidationError, match="reserve par Ansible"):
        validate_spec(_spec_data(**{"ansible.groups": [{"name": "all"}]}), _manager())


def test_an_unknown_role_is_refused():
    with pytest.raises(SpecValidationError, match="Role inconnu"):
        validate_spec(
            _spec_data(**{"ansible.groups": [{"name": "g", "roles": ["kubernetes"]}]}),
            _manager(),
        )


def test_a_group_without_a_role_is_refused():
    with pytest.raises(SpecValidationError, match="au moins un role"):
        validate_spec(
            _spec_data(**{"ansible.groups": [{"name": "g", "roles": []}]}), _manager()
        )


def test_hosts_naming_an_unknown_group_are_refused():
    with pytest.raises(SpecValidationError, match="groupes inconnus"):
        validate_spec(
            _spec_data(**{"ansible.hosts": {"prod": {"absent": []}}}), _manager()
        )


def test_a_host_declared_twice_in_an_environment_is_refused():
    data = _spec_data()
    data["ansible"]["groups"].append({"name": "autres", "roles": ["common"]})
    data["ansible"]["hosts"]["prod"]["autres"] = [
        {"name": "gw-01", "ansible_host": "10.0.0.2"}
    ]
    with pytest.raises(SpecValidationError, match="plusieurs fois"):
        validate_spec(data, _manager())


def test_an_invalid_free_variable_name_is_refused():
    with pytest.raises(SpecValidationError, match="Nom de variable invalide"):
        validate_spec(
            _spec_data(
                **{"ansible.groups": [{"name": "g", "roles": ["common"], "vars": {"Ma-Var": 1}}]}
            ),
            _manager(),
        )


def test_absent_role_options_take_the_catalogue_default():
    """This is what makes a partial spec equivalent to a complete one."""
    spec = validate_spec(_spec_data(), _manager())
    options = spec.ansible.role_options("common")
    assert options, "the catalogue options should be present"
    assert "common_timezone" not in options, "the keys are bare, with no role prefix"


def test_the_roles_are_ordered_by_the_catalogue_not_alphabetically():
    data = _spec_data(
        **{
            "ansible.groups": [{"name": "g", "roles": ["nginx", "users", "common"]}],
            "ansible.hosts": {},
        }
    )
    spec = validate_spec(data, _manager())
    assert [role.name for role in spec.ansible.roles] == ["common", "users", "nginx"]
    assert spec.ansible.groups[0].roles == ["common", "users", "nginx"]


def test_a_role_applied_but_not_configured_is_added():
    spec = validate_spec(_spec_data(), _manager())
    assert [role.name for role in spec.ansible.roles] == ["common"]


# ---------------------------------------------------------------------------
# Cross-checks — what the sub-model cannot see
# ---------------------------------------------------------------------------


def test_an_unknown_environment_in_hosts_is_reported():
    """`AnsibleSpec` does not see `service.environments`: the cross-check does."""
    data = _spec_data()
    data["ansible"]["hosts"]["recette"] = {"gateways": []}
    spec = validate_spec(data, _manager())
    issues = answers_module.cross_check(spec)
    assert [issue.level for issue in issues] == ["error"]
    assert "recette" in issues[0].message
    assert issues[0].hint


def test_an_environment_name_with_a_hyphen_is_reported():
    """The core accepts the hyphen (DNS label), Ansible does not (group name)."""
    data = _spec_data()
    data["service"]["environments"] = [{"name": "pre-prod"}]
    data["ansible"]["hosts"] = {"pre-prod": {"gateways": []}}
    spec = validate_spec(data, _manager())
    issues = answers_module.cross_check(spec)
    assert any("pre-prod" in issue.message for issue in issues)
    assert any("souligne" in issue.hint for issue in issues)


def test_a_sound_specification_produces_no_finding():
    spec = validate_spec(_spec_data(), _manager())
    assert answers_module.cross_check(spec) == []


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_one_syntax_check_per_environment_plus_the_linter():
    data = _spec_data()
    data["service"]["environments"] = [{"name": "dev"}, {"name": "prod", "production": True}]
    data["ansible"]["hosts"] = {}
    spec = validate_spec(data, _manager())
    commands = validators.commands(spec, Path("ansible"))
    assert [c.label for c in commands] == [
        "syntax-check (dev)",
        "syntax-check (prod)",
        "ansible-lint",
    ]
    assert all(c.requires_linux for c in commands)


def test_the_commands_pass_the_collections_path(monkeypatch):
    """Without the Galaxy collections, `--syntax-check` fails on missing modules."""
    monkeypatch.setenv(validators.COLLECTIONS_ENV_VAR, "/elsewhere/collections")
    spec = validate_spec(_spec_data(), _manager())
    command = validators.commands(spec, Path("ansible"))[0]
    assert dict(command.env)["ANSIBLE_COLLECTIONS_PATH"] == "/elsewhere/collections"
    assert dict(command.env)["ANSIBLE_FORCE_COLOR"] == "0"


# ---------------------------------------------------------------------------
# Version constraints of the Galaxy collections
# ---------------------------------------------------------------------------


def _bounds(constraint: str) -> tuple[tuple[int, ...], int]:
    """Split a `>=x.y.z,<M.0.0` constraint into a floor and a ceiling major."""
    floor, ceiling = constraint.split(",")
    assert floor.startswith(">="), constraint
    assert ceiling.startswith("<") and ceiling.endswith(".0.0"), constraint
    return (
        tuple(int(part) for part in floor[2:].split(".")),
        int(ceiling[1:].removesuffix(".0.0")),
    )


def test_every_catalogue_collection_carries_a_version_constraint():
    """A role naming a collection absent from the table breaks the plugin import.

    This is the ZED-7 guard: without it, adding a role would be enough to
    reintroduce an unversioned Galaxy dependency, and the drift would only show
    up at the user's, months after the generation.
    """
    named = {
        name for role in registry.all_roles() for name in role.collections
    }
    assert named <= set(catalog_collections.COLLECTION_REQUIREMENTS)


def test_a_collection_outside_the_table_is_refused():
    """The refusal is a specification error, not a bare KeyError."""
    with pytest.raises(SpecValidationError, match="sans contrainte de version"):
        catalog_collections.requirement_for("community.inventee")


def test_every_constraint_has_a_floor_and_a_ceiling():
    """A floor alone would not have prevented the community.postgresql 5.0.0 breakage.

    Decision ZED-7: both bounds, always. This test forbids writing an entry
    without a major ceiling, which would give Galaxy the last word again.
    """
    for requirement in catalog_collections.COLLECTION_REQUIREMENTS.values():
        floor, ceiling = _bounds(requirement.version)
        validated = tuple(int(part) for part in requirement.validated.split("."))
        assert floor <= validated, requirement.name
        assert validated[0] < ceiling, requirement.name


def test_the_community_postgresql_constraint_covers_alter_system():
    """The postgresql role uses `postgresql_alter_system`, added in 3.13.0.

    A lower floor would allow installing a version where the module does not
    exist; the generated project would fail at run time, not at install time.
    """
    requirement = catalog_collections.requirement_for("community.postgresql")
    assert _bounds(requirement.version)[0] >= (3, 13, 0)


def test_the_derived_collections_all_carry_a_version():
    """What the `requirements.yml` template reads: never a name without a range."""
    spec = validate_spec(_spec_data(), _manager())
    derived = derive.collections(spec.ansible)
    assert derived, "the reference case applies roles with collections"
    assert all(requirement["version"] for requirement in derived)


# ---------------------------------------------------------------------------
# The tree the README announces
# ---------------------------------------------------------------------------


def test_the_readme_announces_exactly_the_generated_files(tmp_path):
    """`tree.py` duplicates knowledge of the tree: this test attests to it.

    copier cannot know in advance the list of files it will write, and the
    generated README displays it. A template added without updating
    `expected_paths` would therefore make the README wrong — silently, without
    this test.
    """
    manager = _manager()
    data = _spec_data()
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    produced = {
        path.relative_to(tmp_path / "ansible").as_posix()
        for path in (tmp_path / "ansible").rglob("*")
        if path.is_file()
    }
    announced = set(tree.expected_paths(spec))
    # Accepted differences, documented in tree.py: copier's plumbing is not
    # announced, and forge.yml now lives at the root of the target repository.
    assert produced - announced <= {".copier-answers.yml"}
    assert announced - produced <= {"forge.yml"}


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

#: Minimal interview: connection, one group, one environment, one machine.
MINIMAL_INTERVIEW = [
    "debian", "ansible", "22", True, "auto_silent",
    "gateways", "Passerelles exposees", ["common"], False,
    False,
    "1", "gw-prod-01", "10.30.0.11",
    False,
    True, True, False,
]


def test_the_interview_produces_a_valid_section():
    from forge.plugins.ansible import interview
    from forge.spec.service import ServiceSpec

    service = ServiceSpec(
        name="passerelle",
        description="Passerelle applicative",
        owner="Equipe Plateforme",
        environments=[{"name": "prod", "production": True}],
    )
    prompter = ScriptedPrompter(list(MINIMAL_INTERVIEW))
    section = interview.run(prompter, service)

    assert prompter.exhausted
    assert section is not None
    model = AnsibleSpec.model_validate(section)
    assert [group.name for group in model.groups] == ["gateways"]
    assert model.hosts["prod"]["gateways"][0].name == "gw-prod-01"


def test_the_interview_does_not_repeat_the_service_block_questions():
    """Identity and environments belong to the core, not to the domain."""
    from forge.plugins.ansible import interview
    from forge.spec.service import ServiceSpec

    service = ServiceSpec(
        name="passerelle",
        description="Passerelle applicative",
        owner="Equipe Plateforme",
        environments=[{"name": "prod", "production": True}],
    )
    prompter = ScriptedPrompter(list(MINIMAL_INTERVIEW))
    interview.run(prompter, service)

    asked = " ".join(prompter.asked).lower()
    for core_question in (
        "nom du service",
        "nom du projet",
        "responsable",
        "environnements, separes",
        "adresse de contact",
    ):
        assert core_question not in asked, (
            f"the domain interview repeats a core question: {core_question}"
        )


# ---------------------------------------------------------------------------
# Real validation of the generated project
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_generated_project_passes_its_own_validators(tmp_path):
    """Hard rule from CLAUDE.md: the generated project must pass its validators.

    The original generator had never checked it — its suite skipped
    ansible-lint, for lack of an installed tool. This test runs both tools for
    real (natively, or through the WSL bridge under Windows) on the richest case
    of the catalogue.
    """
    from tests.conftest import require_tools

    require_tools("ansible", "ansible-playbook", "ansible-lint")

    manager = _manager()
    data = _spec_data()
    data["ansible"]["groups"] = [
        {"name": "gateways", "roles": ["common", "users", "ssh_hardening", "firewall"]}
    ]
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    result = pipeline.validate(spec, manager, tmp_path)
    failures = [check.label for report in result.reports for check in report.failures()]
    assert not failures, (
        f"failing validators: {', '.join(failures)}\n"
        + "\n".join(
            check.detail
            for report in result.reports
            for check in report.failures()
        )[:2000]
    )
