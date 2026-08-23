"""Fixtures communes et harnais golden.

Le plugin `demo` sert de domaine de reference : il n'est pas enregistre en
production, les tests le declarent explicitement. C'est lui qui exerce les
mecanismes reels (yield imbriques, filtres de plugin, filtrage de fichier).
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data

#: Module du plugin de demonstration, tel que `FORGE_PLUGINS` l'attend.
DEMO_PLUGIN = "forge.plugins.demo.plugin"

#: Racine du depot forge, qui porte le copier.yml unique.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Specs de reference et arborescences golden correspondantes.
SPECS_DIR = REPO_ROOT / "tests" / "specs"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"

#: Lignes du fichier de reponses qui varient d'une machine et d'un rendu a
#: l'autre : elles sont neutralisees avant comparaison golden.
_VOLATILE_ANSWERS = (
    (re.compile(r"^_commit:.*$", re.MULTILINE), "_commit: <commit>"),
    (re.compile(r"^_src_path:.*$", re.MULTILINE), "_src_path: <src>"),
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Reecrit les references golden au lieu de les comparer.",
    )


@pytest.fixture
def regen_golden(request: pytest.FixtureRequest) -> bool:
    """Vrai si la campagne demande la re-benediction des references."""
    return bool(request.config.getoption("--regen-golden"))


@pytest.fixture
def manager() -> ForgeManager:
    """Gestionnaire ne contenant que le plugin de demonstration."""
    instance = ForgeManager()
    instance.register_module(DEMO_PLUGIN)
    return instance


@pytest.fixture
def demo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare le plugin demo pour les appels passant par `default_manager()`."""
    monkeypatch.setenv("FORGE_PLUGINS", DEMO_PLUGIN)


@pytest.fixture
def spec_data() -> dict[str, Any]:
    """Specification minimale valide, modifiable par chaque test."""
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne de demonstration",
            "owner": "Equipe Plateforme",
            "owner_email": "plateforme@example.net",
            "labels": {"tier": "frontend"},
            "environments": [
                {"name": "dev", "domain": "dev.example.net"},
                {"name": "prod", "domain": "example.net", "production": True},
            ],
        },
        "demo": {
            "greeting": "bonjour",
            "widgets": [
                {"name": "cpu", "kind": "gauge", "detailed": True},
                {"name": "requetes", "kind": "counter"},
            ],
        },
    }


@pytest.fixture
def spec(spec_data: dict[str, Any], manager: ForgeManager):
    """Instance validee correspondant a `spec_data`."""
    return validate_spec(spec_data, manager)


# ---------------------------------------------------------------------------
# Harnais golden
# ---------------------------------------------------------------------------


def spec_files() -> list[Path]:
    """Specs de reference, triees : l'ordre des cas de test est deterministe."""
    return sorted(SPECS_DIR.glob("*.yml"))


def load_case(path: Path, manager: ForgeManager) -> tuple[dict[str, Any], Any]:
    """Charge une spec de reference et la valide."""
    data = load_spec_data(path)
    return data, validate_spec(data, manager)


def stable_text(path: Path) -> str:
    """Contenu d'un fichier genere, debarrasse de ce qui varie par machine."""
    text = path.read_text(encoding="utf-8")
    if path.name == ".copier-answers.yml":
        for pattern, replacement in _VOLATILE_ANSWERS:
            text = pattern.sub(replacement, text)
    return text


def tree_files(root: Path) -> list[str]:
    """Chemins relatifs de tous les fichiers de `root`, tries."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )


def bless(source: Path, destination: Path) -> None:
    """Remplace l'arborescence golden `destination` par `source`."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            path.write_text(stable_text(path), encoding="utf-8", newline="\n")


def template_is_dirty() -> bool:
    """Vrai si le depot de gabarit porte des modifications non committees.

    `copier update` compare deux references git : un projet rendu depuis un
    arbre de travail sale reference un commit temporaire, introuvable ensuite.
    Les tests de mise a jour sont donc ignores tant que le depot n'est pas propre.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return True
    return bool(result.stdout.strip())


def build_project(target: Path, spec_name: str = "demo-complet") -> tuple[Any, ForgeManager]:
    """Genere un projet de demonstration dans `target` (rendu copier reel)."""
    from forge import pipeline

    instance = ForgeManager()
    instance.register_module(DEMO_PLUGIN)
    data, model = load_case(SPECS_DIR / f"{spec_name}.yml", instance)
    pipeline.generate(data, model, instance, target)
    return model, instance


@pytest.fixture(scope="session")
def projet_demo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any, ForgeManager]:
    """Projet genere une seule fois pour la session : le rendu copier est lent."""
    target = tmp_path_factory.mktemp("projet-demo")
    model, instance = build_project(target)
    return target, model, instance


@pytest.fixture(autouse=True)
def _clean_forge_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isole chaque test des variables d'environnement de la session."""
    for name in ("FORGE_PLUGINS", "FORGE_TEMPLATE_SRC", "FORGE_PLUGIN_JINJA"):
        monkeypatch.delenv(name, raising=False)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
