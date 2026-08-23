"""Tests du moteur de rendu : déterminisme, hygiène et conventions.

Ces tests portent sur des propriétés qui doivent tenir pour *tout* projet
généré, indépendamment de la spécification. Les tests de référence
(``test_golden.py``) vérifient le contenu exact ; ceux-ci vérifient les
invariants.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from helm_forge.engine import FileSet, plan, render, tree, write
from helm_forge.engine.environment import JINJA_DELIMITERS, build_environment
from helm_forge.engine.filters import to_yaml, yaml_scalar, yaml_value
from helm_forge.engine.naming import values_ref
from helm_forge.errors import TargetExistsError
from helm_forge.models import (
    AddonKind,
    AppMeta,
    ComponentSpec,
    EnvironmentSpec,
    ProjectSpec,
)


@pytest.fixture
def rendered(minimal_spec: ProjectSpec) -> FileSet:
    return render(minimal_spec)


# ---------------------------------------------------------------------------
# Déterminisme
# ---------------------------------------------------------------------------


def test_rendu_deterministe(minimal_spec: ProjectSpec) -> None:
    """Exigence centrale de CLAUDE.md : même spec, même sortie, octet pour octet."""
    first = render(minimal_spec)
    second = render(minimal_spec)
    assert first.files == second.files
    assert first.paths == second.paths


def test_ordre_des_fichiers_stable(full_spec: ProjectSpec) -> None:
    spec = ProjectSpec(
        app=AppMeta(name="shop", description="x"),
        environments=[EnvironmentSpec(name="dev"), EnvironmentSpec(name="prod")],
        components=[
            ComponentSpec(name="api", addons=[AddonKind.SERVICE]),
            ComponentSpec(name="worker", addons=[]),
        ],
    )
    assert render(spec).paths == render(spec).paths


# ---------------------------------------------------------------------------
# Hygiène des fichiers générés
# ---------------------------------------------------------------------------


def test_aucun_delimiteur_jinja_residuel(rendered: FileSet) -> None:
    """Un délimiteur qui survit au rendu trahit une balise mal fermée."""
    openers = (
        JINJA_DELIMITERS["variable_start_string"],
        JINJA_DELIMITERS["block_start_string"],
    )
    for path, content in rendered.files.items():
        for opener in openers:
            assert opener not in content, f"{path} contient un {opener} non rendu"


def test_syntaxe_helm_preservee(rendered: FileSet) -> None:
    """La syntaxe Go des gabarits Helm doit traverser Jinja2 intacte."""
    deployment = rendered["charts/shop/templates/deployment-api.yaml"]
    assert '{{ include "shop.api.fullname" . }}' in deployment
    assert "{{- if .Values.api.enabled }}" in deployment


def test_toutes_les_lignes_en_lf(rendered: FileSet) -> None:
    for path, content in rendered.files.items():
        assert "\r" not in content, f"{path} contient un retour chariot"


def test_pas_d_espaces_en_fin_de_ligne(rendered: FileSet) -> None:
    """Les espaces en fin de ligne trahissent une balise de contrôle mal trimée."""
    for path, content in rendered.files.items():
        for number, line in enumerate(content.splitlines(), start=1):
            assert line == line.rstrip(), f"{path}:{number} finit par un espace"


def test_pas_de_double_ligne_vide(rendered: FileSet) -> None:
    """Un bloc optionnel écarté ne doit pas laisser derrière lui deux lignes
    vides consécutives."""
    for path, content in rendered.files.items():
        assert "\n\n\n" not in content, f"{path} contient deux lignes vides de suite"


def test_chaque_fichier_finit_par_un_saut_de_ligne(rendered: FileSet) -> None:
    for path, content in rendered.files.items():
        assert content.endswith("\n"), f"{path} ne finit pas par un saut de ligne"
        assert not content.endswith("\n\n"), f"{path} finit par une ligne vide"


def test_chaque_fichier_porte_un_en_tete(rendered: FileSet) -> None:
    """Convention CLAUDE.md : tout fichier généré s'explique en tête.

    Deux formes de commentaire coexistent : le dièse du YAML et du Makefile, et
    le commentaire Go des gabarits Helm, qui ne doit pas atteindre le cluster.
    """
    for path, content in rendered.files.items():
        head = "\n".join(content.splitlines()[:6])
        assert ("#" in head) or ("/*" in head), f"{path} n'a pas d'en-tête"
        assert "helm-forge" in content, f"{path} ne mentionne pas son origine"


def test_les_fichiers_yaml_sont_du_yaml_valide(rendered: FileSet) -> None:
    """values.yaml et Chart.yaml ne contiennent aucune balise Helm : ils
    doivent donc être analysables tels quels."""
    for path in ("charts/shop/Chart.yaml", "charts/shop/values.yaml"):
        parsed = yaml.safe_load(rendered[path])
        assert isinstance(parsed, dict), f"{path} n'est pas un objet YAML"


def test_values_par_environnement_analysables(rendered: FileSet) -> None:
    for env in ("dev", "prod"):
        parsed = yaml.safe_load(rendered[f"charts/shop/values-{env}.yaml"])
        assert parsed["global"]["environment"] == env


def test_valeurs_attendues_dans_values(rendered: FileSet) -> None:
    values = yaml.safe_load(rendered["charts/shop/values.yaml"])
    assert values["global"]["imageRegistry"] == "ghcr.io"
    assert values["api"]["image"]["repository"] == "acme/shop"
    assert values["api"]["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert values["api"]["resources"]["requests"]["cpu"] == "50m"


def test_surcharges_de_production(rendered: FileSet) -> None:
    prod = yaml.safe_load(rendered["charts/shop/values-prod.yaml"])
    assert prod["api"]["replicaCount"] == 3
    assert prod["api"]["resources"]["requests"]["cpu"] == "100m"


def test_makefile_utilise_des_tabulations(rendered: FileSet) -> None:
    """Une recette de Makefile indentée avec des espaces est un échec certain."""
    lines = rendered["Makefile"].splitlines()
    recipes = [line for line in lines if line.startswith("\t")]
    assert recipes, "aucune ligne de recette indentée par une tabulation"
    assert not any(line.startswith("    ") for line in lines)


# ---------------------------------------------------------------------------
# Filtres et fabriques d'identifiants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "true"), (False, "false"), (None, "null"), (3, "3"), ([], "[]"), ({}, "{}")],
)
def test_to_yaml_scalaires(value: object, expected: str) -> None:
    assert to_yaml(value) == expected


def test_yaml_scalar_protege_les_valeurs_ambigues() -> None:
    assert yaml_scalar("api") == "api"
    assert yaml_scalar("1.36") == "'1.36'"
    assert yaml_scalar("true") == "'true'"
    assert yaml_scalar("") == "''"


def test_yaml_value_bascule_en_bloc_pour_les_collections() -> None:
    """YAML refuse « drop: - ALL » : le filtre doit passer à la ligne.

    Le séparateur fait partie du rendu, sans quoi le passage en bloc laisserait
    une espace en fin de ligne derrière le deux-points.
    """
    assert yaml_value(["ALL"], 4) == "\n    - ALL"
    assert yaml_value([], 4) == " []"
    assert yaml_value("api") == " api"


def test_values_ref_gere_les_tirets() -> None:
    """La notation pointée de Go refuse les tirets : il faut passer par index."""
    assert values_ref("api") == ".Values.api"
    assert values_ref("mon-api") == '(index .Values "mon-api")'


def test_composant_au_nom_avec_tiret_rend_un_chart_valide() -> None:
    spec = ProjectSpec(
        app=AppMeta(name="shop", description="x"),
        environments=[EnvironmentSpec(name="dev")],
        components=[ComponentSpec(name="mon-api", addons=[AddonKind.SERVICE])],
    )
    deployment = render(spec)["charts/shop/templates/deployment-mon-api.yaml"]
    assert '(index .Values "mon-api").enabled' in deployment
    assert ".Values.mon-api" not in deployment


def test_variable_absente_fait_echouer_le_rendu() -> None:
    """StrictUndefined : jamais de trou silencieux dans un manifeste."""
    from jinja2 import UndefinedError

    template = build_environment().from_string("[[ inconnue ]]")
    with pytest.raises(UndefinedError):
        template.render()


# ---------------------------------------------------------------------------
# Écriture sur disque
# ---------------------------------------------------------------------------


def test_ecriture_complete(tmp_path: Path, rendered: FileSet) -> None:
    written = write(rendered, tmp_path)
    assert len(written) == len(rendered)
    assert (tmp_path / "charts/shop/Chart.yaml").is_file()
    assert b"\r\n" not in (tmp_path / "Makefile").read_bytes()


def test_refus_d_ecraser_un_repertoire_non_vide(
    tmp_path: Path, rendered: FileSet
) -> None:
    (tmp_path / "deja-la.txt").write_text("contenu", encoding="utf-8")
    with pytest.raises(TargetExistsError):
        write(rendered, tmp_path)
    write(rendered, tmp_path, force=True)  # --force lève le garde-fou
    assert (tmp_path / "charts/shop/Chart.yaml").is_file()


def test_un_depot_git_ne_compte_pas_comme_occupation(
    tmp_path: Path, rendered: FileSet
) -> None:
    """Générer dans un dépôt fraîchement initialisé doit rester possible."""
    (tmp_path / ".git").mkdir()
    write(rendered, tmp_path)
    assert (tmp_path / "forge.yml").is_file()


# ---------------------------------------------------------------------------
# Arborescence affichée par --dry-run
# ---------------------------------------------------------------------------


def test_arborescence_lisible(minimal_spec: ProjectSpec) -> None:
    output = tree(plan(minimal_spec))
    assert "forge.yml" in output
    assert "charts/" in output
    assert "        Chart.yaml" in output
