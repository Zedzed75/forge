"""Tests du moteur de génération : filtres, planificateur, écriture."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from ansible_forge.engine.artifact import Artifact, sort_artifacts
from ansible_forge.engine.filters import (
    comment,
    jinja_expr,
    jinja_string,
    lower_first,
    to_yaml_assign,
    to_yaml_scalar,
)
from ansible_forge.engine.planner import plan, plan_paths
from ansible_forge.engine.renderer import list_templates, render
from ansible_forge.engine.role_planner import ROLE_FILES, implemented_roles, plan_role
from ansible_forge.errors import ForgeError, OutputDirError
from ansible_forge.models.enums import OSFamily
from ansible_forge.models.spec import ProjectSpec
from ansible_forge.engine.writer import build_tree, check_output_dir, write_artifacts
from tests.conftest import build_spec


class TestFiltres:
    def test_scalaire_texte(self):
        assert to_yaml_scalar("Europe/Paris") == "Europe/Paris"

    def test_scalaire_ambigu_est_cite(self):
        """« yes » serait relu comme un booléen sans guillemets."""
        assert to_yaml_scalar("yes") == "'yes'"

    def test_scalaire_booleen(self):
        assert to_yaml_scalar(True) == "true"

    def test_scalaire_vide_est_cite(self):
        assert to_yaml_scalar("") == "''"

    def test_affectation_scalaire_reste_sur_la_ligne(self):
        assert to_yaml_assign(22) == " 22"

    def test_affectation_liste_passe_en_bloc(self):
        assert to_yaml_assign(["a", "b"], 2) == "\n  - a\n  - b"

    def test_affectation_liste_vide(self):
        assert to_yaml_assign([]) == " []"

    def test_affectation_dictionnaire_vide(self):
        assert to_yaml_assign({}) == " {}"

    def test_affectation_dictionnaire(self):
        assert to_yaml_assign({"a": 1}, 2) == "\n  a: 1"

    def test_commentaire_replie_les_lignes_longues(self):
        result = comment("mot " * 40)
        assert all(line.startswith("# ") for line in result.splitlines())
        assert all(len(line) <= 88 for line in result.splitlines())

    def test_commentaire_indente(self):
        assert comment("texte", 4) == "    # texte"

    def test_commentaire_conserve_les_paragraphes(self):
        assert comment("un\n\ndeux") == "# un\n#\n# deux"

    def test_expression_jinja(self):
        assert jinja_expr("common_packages") == "{{ common_packages }}"

    def test_expression_jinja_citee(self):
        assert jinja_string("x") == '"{{ x }}"'

    def test_lower_first_abaisse_la_premiere_lettre(self):
        assert lower_first("Liste de paquets") == "liste de paquets"

    def test_lower_first_preserve_les_sigles(self):
        assert lower_first("UTF8 uniquement") == "UTF8 uniquement"


class TestArtifact:
    def test_refuse_un_chemin_absolu(self):
        with pytest.raises(ValueError, match="doit être relatif"):
            Artifact(path=PurePosixPath("/etc/passwd"), content="")

    def test_tri_par_chemin(self):
        artifacts = [
            Artifact(path=PurePosixPath("b.yml"), content=""),
            Artifact(path=PurePosixPath("a.yml"), content=""),
        ]
        assert [item.posix_path for item in sort_artifacts(artifacts)] == ["a.yml", "b.yml"]


class TestRenderer:
    def test_les_templates_sont_embarques(self):
        templates = list_templates()
        assert "project/ansible.cfg.j2" in templates
        assert "roles/_shared/defaults.yml.j2" in templates

    def test_une_variable_manquante_echoue(self):
        """StrictUndefined évite les fichiers silencieusement incomplets."""
        with pytest.raises(Exception, match="undefined|spec"):
            render("project/ansible.cfg.j2", {})

    def test_le_rendu_se_termine_par_un_seul_saut_de_ligne(self, spec: ProjectSpec):
        content = render("project/playbooks/ping.yml.j2", {"spec": spec})
        assert content.endswith("\n")
        assert not content.endswith("\n\n")

    def test_le_rendu_ne_laisse_pas_d_espaces_de_fin(self, spec: ProjectSpec):
        content = render("project/playbooks/ping.yml.j2", {"spec": spec})
        assert all(line == line.rstrip() for line in content.splitlines())


class TestPlanner:
    def test_produit_les_fichiers_attendus(self):
        paths = plan_paths(build_spec(groups=[{"name": "webservers", "roles": ["common"]}]))
        for expected in [
            "ansible.cfg",
            "requirements.yml",
            "README.md",
            "forge.yml",
            ".ansible-lint",
            "group_vars/all.yml",
            "group_vars/webservers.yml",
            "inventories/dev/hosts.yml",
            "inventories/dev/group_vars/all/main.yml",
            "inventories/dev/group_vars/all/vault.yml.example",
            "inventories/dev/group_vars/webservers.yml",
            "inventories/dev/host_vars/web-dev-01.yml",
            "playbooks/site.yml",
            "playbooks/ping.yml",
            "playbooks/webservers.yml",
            "roles/common/tasks/main.yml",
            "roles/common/defaults/main.yml",
            "roles/common/meta/main.yml",
            "roles/common/README.md",
            "roles/common/templates/motd.j2",
        ]:
            assert expected in paths, f"{expected} devrait être généré"

    def test_les_chemins_sont_uniques(self):
        paths = plan_paths(build_spec(groups=[{"name": "webservers", "roles": ["common"]}]))
        assert len(paths) == len(set(paths))

    def test_sans_configuration_de_lint(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"]}],
            options={"write_lint_config": False},
        )
        paths = plan_paths(spec)
        assert ".ansible-lint" not in paths
        assert ".yamllint" not in paths

    def test_sans_vault(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"]}],
            options={"use_vault": False},
        )
        assert not [path for path in plan_paths(spec) if "vault" in path]

    def test_avec_workflow_ci(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"]}],
            options={"write_ci": True},
        )
        content = _content(spec, ".github/workflows/ansible-lint.yml")
        assert "ansible-lint" in content
        assert "inventories/dev" in content

    def test_sans_workflow_ci_par_defaut(self):
        spec = build_spec(groups=[{"name": "webservers", "roles": ["common"]}])
        assert ".github/workflows/ansible-lint.yml" not in plan_paths(spec)

    def test_sans_copie_de_la_spec(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"]}],
            options={"embed_spec": False},
        )
        assert "forge.yml" not in plan_paths(spec)

    def test_les_options_surchargees_apparaissent_dans_group_vars_all(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"]}],
            roles=[{"name": "common", "options": {"timezone": "UTC"}}],
        )
        content = _content(spec, "group_vars/all.yml")
        assert "common_timezone: UTC" in content

    def test_les_options_par_defaut_ne_sont_pas_dupliquees(self):
        """Une valeur inchangée reste documentée dans defaults/main.yml uniquement."""
        spec = build_spec(groups=[{"name": "webservers", "roles": ["common"]}])
        assert "common_timezone" not in _content(spec, "group_vars/all.yml")
        assert "common_timezone: Europe/Paris" in _content(spec, "roles/common/defaults/main.yml")

    def test_les_variables_libres_sont_signalees_a_documenter(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"], "vars": {"web_workers": 4}}],
        )
        content = _content(spec, "group_vars/webservers.yml")
        assert "web_workers: 4" in content
        assert "TODO" in content

    def test_un_groupe_sans_machine_reste_declare(self):
        spec = build_spec(
            groups=[{"name": "webservers", "roles": ["common"]}, {"name": "dbservers"}],
        )
        content = _content(spec, "inventories/dev/hosts.yml")
        assert "dbservers:" in content
        assert "hosts: {}" in content

    def test_le_readme_contient_l_arborescence(self):
        spec = build_spec(groups=[{"name": "webservers", "roles": ["common"]}])
        content = _content(spec, "README.md")
        assert "ansible.cfg" in content
        assert "roles/" in content


class TestRolePlanner:
    def test_role_non_implemente_est_signale(self, monkeypatch: pytest.MonkeyPatch):
        """Un rôle du catalogue sans templates doit produire une erreur claire."""
        monkeypatch.delitem(ROLE_FILES, "common")
        with pytest.raises(ForgeError, match="ne sont pas encore disponibles"):
            plan_role("common", author="A", os_family=OSFamily.DEBIAN, example_group="webservers")

    def test_plateformes_selon_la_famille_d_os(self):
        artifacts = plan_role(
            "common", author="A", os_family=OSFamily.REDHAT, example_group="webservers"
        )
        meta = next(item for item in artifacts if item.posix_path.endswith("meta/main.yml"))
        assert "EL" in meta.content
        assert "Debian" not in meta.content

    def test_common_est_implemente(self):
        assert "common" in implemented_roles()


class TestWriter:
    def test_arborescence_lisible(self):
        tree = build_tree(["ansible.cfg", "roles/common/tasks/main.yml"], "demo")
        assert tree.splitlines()[0] == "demo/"
        assert "roles/" in tree
        assert "ansible.cfg" in tree

    def test_les_repertoires_precedent_les_fichiers(self):
        lines = build_tree(["z.yml", "a/b.yml"], "demo").splitlines()
        assert lines[1].endswith("a/")

    def test_refuse_un_repertoire_non_vide(self, tmp_path: Path):
        (tmp_path / "existant.txt").write_text("x", encoding="utf-8")
        with pytest.raises(OutputDirError, match="n'est pas vide"):
            check_output_dir(tmp_path)

    def test_accepte_un_repertoire_non_vide_avec_force(self, tmp_path: Path):
        (tmp_path / "existant.txt").write_text("x", encoding="utf-8")
        check_output_dir(tmp_path, force=True)

    def test_refuse_un_fichier_comme_sortie(self, tmp_path: Path):
        target = tmp_path / "fichier"
        target.write_text("x", encoding="utf-8")
        with pytest.raises(OutputDirError, match="n'est pas un répertoire"):
            check_output_dir(target)

    def test_ecrit_en_fins_de_ligne_lf(self, tmp_path: Path):
        spec = build_spec(groups=[{"name": "webservers", "roles": ["common"]}])
        write_artifacts(plan(spec), tmp_path / "projet")
        for path in (tmp_path / "projet").rglob("*"):
            if path.is_file():
                assert b"\r\n" not in path.read_bytes(), f"{path} contient des CRLF"

    def test_ecrit_tous_les_artefacts(self, tmp_path: Path):
        spec = build_spec(groups=[{"name": "webservers", "roles": ["common"]}])
        artifacts = plan(spec)
        written = write_artifacts(artifacts, tmp_path / "projet")
        assert len(written) == len(artifacts)


def _content(spec: ProjectSpec, path: str) -> str:
    """Retourne le contenu généré d'un fichier donné."""
    for artifact in plan(spec):
        if artifact.posix_path == path:
            return artifact.content
    raise AssertionError(f"{path} n'a pas été généré")
