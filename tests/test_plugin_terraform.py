"""The Terraform domain — the first one written from scratch.

No legacy generator to port, therefore **no parity snapshot**: nothing says "the
output is right" apart from this module and the real tools. The coverage is
organised differently from the other two domains:

* what the **model** refuses (constraints Terraform would only report at `init`,
  that is to say too late);
* what the **cross-check** refuses or reports;
* the **internal consistency** of the projection — catalogue, variables, outputs
  and templates must all talk about the same names;
* the **absence of any secret value** in every generated file;
* and, under the `integration` marker, the **real validators**: `terraform fmt`,
  `terraform init`, `terraform validate` and `tflint`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge import pipeline
from forge.plugins.terraform import answers, derive, tree, validators
from forge.plugins.terraform.catalog.families import FAMILIES
from forge.plugins.terraform.catalog.registry import family_names
from forge.plugins.terraform.enums import ResourceFamily
from forge.plugins.terraform.spec import TerraformSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import REPO_ROOT

PLUGIN = "forge.plugins.terraform.plugin"
COMPLETE_SPEC = REPO_ROOT / "tests" / "specs" / "terraform-full.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(PLUGIN)
    return instance


def _spec(given: dict | None = None):
    """Valid root model, from the reference spec or from a dict."""
    manager = _manager()
    data = given if given is not None else load_spec_data(COMPLETE_SPEC)
    return data, validate_spec(data, manager), manager


def _base(**terraform) -> dict:
    """Minimal specification, with the terraform section supplied."""
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Online store",
            "owner": "Platform Team",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
        "terraform": terraform or {"resources": ["namespace"]},
    }


def _generate(tmp_path: Path, given: dict | None = None):
    data, spec, manager = _spec(given)
    pipeline.generate(data, spec, manager, tmp_path)
    return spec, manager


# ---------------------------------------------------------------------------
# What the sub-model refuses
# ---------------------------------------------------------------------------


def test_a_bare_version_is_refused_as_a_constraint():
    """`1.9.8` would pin the project to one patch: almost always a mistake."""
    with pytest.raises(ValueError, match="version constraint"):
        TerraformSpec(terraform_version="1.9.8")


@pytest.mark.parametrize("constraint", ["~> 1.9", ">= 1.5, < 2.0", "~> 1.9.0"])
def test_well_formed_constraints_pass(constraint):
    assert TerraformSpec(terraform_version=constraint).terraform_version == constraint


def test_a_secret_backend_key_is_refused():
    """A generated file never carries a secret, backend included."""
    with pytest.raises(ValueError, match="secret backend keys refused"):
        TerraformSpec(backend={"kind": "s3", "config": {"bucket": "b", "region": "r", "secret_key": "x"}})


def test_a_missing_mandatory_backend_key_is_refused():
    """Otherwise the project renders perfectly and refuses to initialise."""
    with pytest.raises(ValueError, match="mandatory keys absent"):
        TerraformSpec(backend={"kind": "s3", "config": {"bucket": "b"}})


def test_the_state_key_is_not_asked_of_the_specification():
    """`key` is derived per environment: requiring it would produce a shared state."""
    spec = TerraformSpec(backend={"kind": "s3", "config": {"bucket": "b", "region": "r"}})
    assert "key" not in spec.backend.config


def test_a_repeated_family_is_refused():
    with pytest.raises(ValueError, match="resource families"):
        TerraformSpec(resources=["namespace", "namespace"])


def test_the_custom_strategy_requires_a_namespace_per_declared_environment():
    with pytest.raises(ValueError, match="custom"):
        TerraformSpec(namespace_strategy="custom", environments={"dev": {}})


def test_an_explicit_namespace_that_is_too_long_is_refused():
    with pytest.raises(ValueError, match="63"):
        TerraformSpec(environments={"dev": {"namespace": "n" * 64}})


def test_an_unknown_key_is_refused():
    """`extra="forbid"`: a typo is never a silence."""
    with pytest.raises(ValueError):
        TerraformSpec(terrraform_version="~> 1.9")


# ---------------------------------------------------------------------------
# What the cross-check refuses or reports
# ---------------------------------------------------------------------------


def _issues(given: dict) -> list:
    manager = _manager()
    spec = validate_spec(given, manager)
    return answers.cross_check(spec)


def _messages(given: dict, level: str) -> list[str]:
    return [issue.message for issue in _issues(given) if issue.level == level]


def test_an_unknown_environment_is_an_error():
    given = _base(resources=["namespace"], environments={"recette": {"namespace": "x"}})
    assert any("recette" in m for m in _messages(given, "error"))


def test_the_custom_strategy_covers_every_environment_of_the_service():
    """An environment absent from `terraform.environments` escapes the sub-model."""
    given = _base(
        resources=["namespace"],
        namespace_strategy="custom",
        environments={"dev": {"namespace": "boutique-dev"}},
    )
    errors = _messages(given, "error")
    assert any("prod" in m for m in errors)
    assert not any("'dev'" in m for m in errors)


def test_a_derived_namespace_that_is_too_long_is_an_error():
    """Neither the service nor the environment is too long on its own: the product is."""
    given = _base(resources=["namespace"])
    given["service"]["name"] = "b" * 55
    given["service"]["environments"] = [{"name": "integration"}]
    assert any("63" in m for m in _messages(given, "error"))


def test_an_override_without_its_family_is_reported():
    """A carefully tuned value silently ignored is worse than an error."""
    given = _base(
        resources=["namespace"],
        environments={"prod": {"quota": {"cpu": "8"}}},
    )
    warnings = _messages(given, "warning")
    assert any("quota" in m and "will not be applied" in m for m in warnings)


def test_a_local_state_in_production_is_reported():
    given = _base(resources=["namespace", "random_secret"])
    warnings = _messages(given, "warning")
    assert any("'local' state backend" in m for m in warnings)
    assert any("random_secret" in m for m in warnings)


def test_a_missing_cluster_context_is_reported():
    given = _base(
        resources=["namespace"],
        kubernetes={"context_per_environment": False},
    )
    assert any("current context" in m for m in _messages(given, "warning"))


def test_the_reference_specification_raises_no_error():
    _, spec, _ = _spec()
    assert [issue for issue in answers.cross_check(spec) if issue.level == "error"] == []


def test_the_cross_check_is_silent_without_a_terraform_section():
    class Without:
        pass

    assert answers.cross_check(Without()) == []


# ---------------------------------------------------------------------------
# Internal consistency of the projection
# ---------------------------------------------------------------------------


def test_the_projection_is_serialisable_and_deterministic():
    _, spec, _ = _spec()
    first = answers.build(spec)
    second = answers.build(spec)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_every_family_of_the_enumeration_is_in_the_catalogue():
    assert set(family_names()) == {family.value for family in ResourceFamily}


def test_every_family_documents_its_traps():
    """The traps explain choices in the generated code: no family without them."""
    silent = [family.name for family in FAMILIES if not family.traps]
    assert silent == [], f"families with no documented trap: {silent}"


def test_every_family_output_has_an_expression():
    """An output declared without an expression would break the render, not the test."""
    known = set(derive.OUTPUT_VALUES)
    declared = {name for family in FAMILIES for name in family.outputs}
    assert declared <= known


def test_the_families_only_ask_for_known_providers():
    _, spec, _ = _spec()
    names = {provider["name"] for provider in derive.providers(spec)}
    assert names == {"kubernetes", "random", "tls"}


def test_the_tfvars_only_names_declared_variables():
    """Terraform refuses a tfvars naming an unknown variable."""
    _, spec, _ = _spec()
    projection = answers.build(spec)
    declared = {variable["name"] for variable in projection["root_variables"]}
    for env in projection["environments"]:
        named = {entry["name"] for entry in env["tfvars"]}
        assert named <= declared, f"{env['name']}: {sorted(named - declared)}"


def test_the_tfvars_carries_no_secret_variable():
    _, spec, _ = _spec()
    projection = answers.build(spec)
    secrets = {v["name"] for v in projection["root_variables"] if v["sensitive"]}
    assert secrets, "the reference case must exercise at least one secret variable"
    for env in projection["environments"]:
        assert not secrets & {entry["name"] for entry in env["tfvars"]}


def test_the_module_call_passes_all_of_its_variables():
    """Terraform does not report a variable declared and never passed."""
    _, spec, _ = _spec()
    projection = answers.build(spec)
    expected = {variable["name"] for variable in projection["variables"]}
    for env in projection["environments"]:
        passed = {argument["name"] for argument in env["module_arguments"]}
        assert passed == expected


def test_two_environments_never_write_the_same_state():
    _, spec, _ = _spec()
    projection = answers.build(spec)
    keys = [
        tuple(sorted((e["name"], e["value"]) for e in env["backend_config"]))
        for env in projection["environments"]
    ]
    assert len(set(keys)) == len(keys)


def test_the_derived_namespaces_follow_the_strategy():
    _, spec, _ = _spec()
    projection = answers.build(spec)
    assert [env["namespace"] for env in projection["environments"]] == [
        "boutique-dev",
        "boutique-staging",
        "boutique-prod",
    ]


def test_the_declared_facet_belongs_to_the_shared_vocabulary():
    """A facet outside the vocabulary is harmless, but pointless too (phase 5)."""
    from forge.plugins.terraform import plugin as terraform_plugin
    from forge.validate.consistency import FACET_VOCABULARY

    _, spec, _ = _spec()
    projection = terraform_plugin.forge_projection(spec)
    assert set(projection.facets) <= set(FACET_VOCABULARY)
    assert projection.facets["namespaces"] == (
        "boutique-dev",
        "boutique-prod",
        "boutique-staging",
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_the_announced_tree_matches_the_generated_files(tmp_path):
    """Arbitration R3: `tree.py` stays with the plugin, but a test keeps it current."""
    spec, _ = _generate(tmp_path)
    base = tmp_path / "terraform"
    produced = {
        path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file()
    }
    assert produced == set(tree.expected_paths(spec))


def test_every_selected_family_produces_its_file(tmp_path):
    spec, _ = _generate(tmp_path)
    module = tmp_path / "terraform" / "modules" / "boutique"
    for family in FAMILIES:
        path = module / f"{family.name}.tf"
        assert path.is_file(), f"missing file: {family.name}.tf"
        content = path.read_bytes().decode("utf-8")
        for resource in family.resources:
            assert f'resource "{resource}"' in content


def test_a_family_that_was_not_selected_produces_nothing(tmp_path):
    """The choice also applies inside a domain."""
    _generate(tmp_path, _base(resources=["namespace"]))
    module = tmp_path / "terraform" / "modules" / "boutique"
    produced = sorted(path.name for path in module.glob("*.tf"))
    assert produced == ["locals.tf", "namespace.tf", "outputs.tf", "variables.tf", "versions.tf"]


def test_without_the_namespace_family_the_module_attaches_to_the_existing_one(tmp_path):
    _generate(tmp_path, _base(resources=["quota"]))
    locals_tf = (tmp_path / "terraform" / "modules" / "boutique" / "locals.tf").read_bytes()
    text = locals_tf.decode("utf-8")
    assert "namespace = var.namespace" in text
    assert "kubernetes_namespace.this" not in text


def test_every_declared_variable_is_used_by_a_template(tmp_path):
    """Lock against the tflint rule `terraform_unused_declarations`.

    It is checked here on **each family taken in isolation**: the complete case
    would satisfy it even if a variable were only used by another family.
    """
    for family in FAMILIES:
        target = tmp_path / family.name
        _generate(target, _base(resources=[family.name]))
        module = target / "terraform" / "modules" / "boutique"
        body = "\n".join(
            path.read_bytes().decode("utf-8")
            for path in module.glob("*.tf")
            if path.name != "variables.tf"
        )
        declared = {
            line.split('"')[1]
            for line in (module / "variables.tf").read_bytes().decode("utf-8").splitlines()
            if line.startswith('variable "')
        }
        unused = sorted(name for name in declared if f"var.{name}" not in body)
        assert unused == [], f"{family.name}: unused variables {unused}"


#: What no generated file may contain. The patterns are about **literal
#: assignments**, not mentions: `password = var.x` is legitimate,
#: `password = "x"` is not, and a family named `generated_secret_keys` is not a
#: secret.
FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"(?m)^\s*(?:access_key|secret_key|sas_token|client_secret|credentials)\s*=",
        "access key to the state storage",
    ),
    (
        r'(?m)^\s*\w*(?:password|token|secret)\w*\s*=\s*"',
        "literal value assigned to a secret key",
    ),
    (r"BEGIN (?:RSA )?PRIVATE KEY", "private key"),
    (r"BEGIN CERTIFICATE", "certificate"),
)


def test_no_generated_file_carries_a_secret_value(tmp_path):
    """Absolute rule of the project, checked on the output and not on the intent."""
    import re

    _generate(tmp_path)
    for path in sorted((tmp_path / "terraform").rglob("*")):
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8")
        for pattern, label in FORBIDDEN_PATTERNS:
            found = re.search(pattern, text)
            assert found is None, (
                f"{path.name} carries a {label}: {found.group(0).strip()!r}"
            )


def _assignments(path: Path) -> dict[str, str]:
    """Read an HCL assignment file into a dict, alignment ignored."""
    values: dict[str, str] = {}
    for line in path.read_bytes().decode("utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def test_the_tfvars_carry_the_values_of_their_environment(tmp_path):
    _generate(tmp_path)
    root = tmp_path / "terraform" / "environments"
    prod = _assignments(root / "prod" / "terraform.tfvars")
    dev = _assignments(root / "dev" / "terraform.tfvars")
    assert prod["namespace"] == '"boutique-prod"'
    assert prod["kube_context"] == '"plateforme-prod-eu-west-3"'
    assert prod["quota_cpu"] == '"16"'
    assert dev["quota_cpu"] == '"2"'
    # An unset context falls back to the environment name rather than to the
    # machine's current context.
    assert dev["kube_context"] == '"dev"'
    # The service labels and those of the environment are merged.
    assert "criticality" in prod["labels"] and "criticality" not in dev["labels"]


def test_the_backend_derives_one_key_per_environment(tmp_path):
    _generate(tmp_path)
    root = tmp_path / "terraform" / "environments"
    for name in ("dev", "staging", "prod"):
        content = (root / name / "backend.tf").read_bytes().decode("utf-8")
        assert f'key     = "boutique/{name}/terraform.tfstate"' in content


# ---------------------------------------------------------------------------
# Declared validators
# ---------------------------------------------------------------------------


def test_the_validators_cover_every_environment(tmp_path):
    _, spec, _ = _spec()
    commands = validators.commands(spec, tmp_path)
    labels = [command.label for command in commands]
    assert labels[0] == "terraform fmt"
    assert labels[-1] == "tflint"
    for name in ("dev", "staging", "prod"):
        assert f"terraform init ({name})" in labels
        assert f"terraform validate ({name})" in labels
    assert len(commands) == 2 + 2 * 3


def test_the_initialisation_does_not_touch_the_state_storage(tmp_path):
    """`forge validate` validates code: it joins no infrastructure."""
    _, spec, _ = _spec()
    inits = [c for c in validators.commands(spec, tmp_path) if c.label.startswith("terraform init")]
    assert inits
    for command in inits:
        assert "-backend=false" in command.argv


def test_the_provider_cache_is_only_declared_if_it_exists(tmp_path, monkeypatch):
    monkeypatch.setenv(validators.CACHE_ENV_VAR, str(tmp_path / "nonexistent"))
    _, spec, _ = _spec()
    assert not any(
        key == "TF_PLUGIN_CACHE_DIR"
        for command in validators.commands(spec, tmp_path)
        for key, _ in command.env
    )
    monkeypatch.setenv(validators.CACHE_ENV_VAR, str(tmp_path))
    assert any(
        key == "TF_PLUGIN_CACHE_DIR"
        for command in validators.commands(spec, tmp_path)
        for key, _ in command.env
    )


# ---------------------------------------------------------------------------
# Catalogue and interview
# ---------------------------------------------------------------------------


def test_the_catalogue_exposes_every_family_with_its_options():
    from forge.plugins.terraform import plugin as terraform_plugin

    entries = terraform_plugin.forge_catalog()
    assert [entry.name for entry in entries] == list(family_names())
    quota = next(entry for entry in entries if entry.name == "quota")
    assert "quota_cpu" in quota.options
    assert "requests" in quota.details


def test_the_interview_produces_a_valid_section():
    from forge.plugins.terraform import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(resources=["namespace"]), _manager()).service
    prompter = ScriptedPrompter(
        [
            ["namespace", "quota"],   # families
            "~> 1.9",                 # version constraint
            "per_env",                # namespace strategy
            "local",                  # backend
            "kubeconfig",             # authentication
            "~/.kube/config",         # kubeconfig path
            True,                     # one context per environment
            True,                     # makefile
            True,                     # .tflint.hcl
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted, f"answers not consumed: {prompter.answers}"
    model = TerraformSpec.model_validate(section)
    assert model.family_names() == ("namespace", "quota")


def test_the_interview_declines_when_no_family_is_selected():
    """Arbitration R7: `None` means "nothing to generate", not "domain refused"."""
    from forge.plugins.terraform import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(resources=["namespace"]), _manager()).service
    assert interview.run(ScriptedPrompter([[]]), service) is None


def test_the_interview_asks_for_the_namespaces_in_custom_strategy():
    from forge.plugins.terraform import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(resources=["namespace"]), _manager()).service
    prompter = ScriptedPrompter(
        [
            ["namespace"],
            "~> 1.9",
            "custom",
            "local",
            "kubeconfig",
            "~/.kube/config",
            True,
            "socle-dev",
            "socle-prod",
            False,
            False,
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted
    assert section["environments"] == {
        "dev": {"namespace": "socle-dev"},
        "prod": {"namespace": "socle-prod"},
    }


# ---------------------------------------------------------------------------
# Real validation of the generated project
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_generated_project_passes_its_own_validators(tmp_path):
    """Hard rule from CLAUDE.md, on the case enabling the seven families.

    It is the only judge of this domain: there is no parity snapshot at all.
    `terraform init` downloads providers on the first pass — the
    FORGE_TF_PLUGIN_CACHE variable avoids starting over for each environment.
    """
    from tests.conftest import require_tools

    require_tools("terraform", "terraform", "tflint")

    spec, manager = _generate(tmp_path)
    result = pipeline.validate(spec, manager, tmp_path)
    failures = [check for report in result.reports for check in report.failures()]
    assert not failures, (
        f"failing validators: {', '.join(c.label for c in failures)}\n"
        + "\n".join(c.detail for c in failures)[:2000]
    )
    launched = [c.label for report in result.reports for c in report.checks]
    assert "tflint" in launched and "terraform fmt" in launched
