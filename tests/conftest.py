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


# ---------------------------------------------------------------------------
# Fail-closed validators
# ---------------------------------------------------------------------------
# Comments in this module are in English: test infrastructure, no French
# precedent, and no effect on generated output.
#
# The project's central claim is "the generated project passes its own real
# validators". Seven integration tests assert it, and each of them used to skip
# when its tool was missing. That is right on a Windows workstation, where
# ansible-core and promtool cannot run natively -- and wrong in CI, where a
# degraded install step (a moved release URL, a renamed tarball member) turned
# those tests into no-ops while the build stayed green. `FORGE_REQUIRE_TOOLS=1`
# closes that hole: the skip becomes a failure, and a green CI check positively
# proves every domain's validators actually ran.
# ---------------------------------------------------------------------------

#: Environment variable that forbids skipping on a missing validator.
REQUIRE_TOOLS_ENV = "FORGE_REQUIRE_TOOLS"

#: Values of `FORGE_REQUIRE_TOOLS` read as "required". Anything else is off, so
#: `FORGE_REQUIRE_TOOLS=0` disables the flag rather than enabling it by mere
#: presence.
_REQUIRE_TOOLS_TRUTHY = frozenset({"1", "true", "yes", "on"})


def tools_are_required() -> bool:
    """True when a missing validator must fail the run instead of skipping it."""
    return os.environ.get(REQUIRE_TOOLS_ENV, "").strip().lower() in _REQUIRE_TOOLS_TRUTHY


def require_tools(domain: str, *names: str, requires_linux: bool = True) -> None:
    """Check that every validator of `domain` is available, or stop the test.

    Unset flag: skips, exactly as the seven call sites did before -- the local
    development loop is unchanged. Flag set: fails, naming the domain and every
    missing tool.

    One shared helper on purpose. A fail-closed switch that seven call sites can
    each opt out of is not a switch, and the drift would be invisible: a site
    left behind keeps skipping and the build stays green.
    """
    from forge.validate import tools

    missing = [name for name in names if not tools.probe(name, requires_linux).available]
    if not missing:
        return

    reason = f"domain {domain}: validator(s) missing, natively and in WSL: {', '.join(missing)}"
    if tools_are_required():
        pytest.fail(
            f"{reason}\n"
            f"{REQUIRE_TOOLS_ENV} is set: skipping is forbidden here. This run is "
            "supposed to prove that the generated project passes its real "
            "validators; without the tool it proves nothing, so it fails instead "
            "of reporting a reduced success. Install the tool, or unset "
            f"{REQUIRE_TOOLS_ENV} to get the development behaviour back.",
            pytrace=False,
        )
    pytest.skip(reason)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Reecrit les references golden au lieu de les comparer.",
    )
    # Deliberately a separate flag from --regen-golden. Re-blessing the golden
    # trees is routine after an intended template change; re-blessing a
    # structural fingerprint means claiming the structure was *meant* to move,
    # which is exactly the claim a reviewer is supposed to examine.
    parser.addoption(
        "--regen-fingerprints",
        action="store_true",
        default=False,
        help="Rewrites the stored structural fingerprints instead of comparing them.",
    )


@pytest.fixture
def regen_golden(request: pytest.FixtureRequest) -> bool:
    """Vrai si la campagne demande la re-benediction des references."""
    return bool(request.config.getoption("--regen-golden"))


@pytest.fixture
def regen_fingerprints(request: pytest.FixtureRequest) -> bool:
    """True when the run is asked to rewrite the stored fingerprints."""
    return bool(request.config.getoption("--regen-fingerprints"))


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
    """Contenu d'un fichier genere, debarrasse de ce qui varie par machine.

    Lecture en **octets** : `read_text` traduit les CRLF en LF a la lecture, ce
    qui rendrait la comparaison golden aveugle a une regression de fins de ligne
    — precisement ce que la normalisation est censee garantir.
    """
    text = path.read_bytes().decode("utf-8")
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


def render_all_plugins(spec_path: Path, target: Path) -> Path:
    """Render one reference spec with the demo plugin and every shipped domain.

    Shared by the golden harness and the fingerprint harness so both observe the
    exact same rendering. A spec that does not declare a section simply does not
    generate that domain, so registering every plugin is harmless.
    """
    from forge import pipeline
    from forge.plugins_api.manager import BUILTIN_PLUGINS

    manager = ForgeManager()
    for module in (DEMO_PLUGIN, *BUILTIN_PLUGINS):
        manager.register_module(module)
    data, model = load_case(spec_path, manager)
    pipeline.generate(data, model, manager, target)
    return target


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
    # `monkeypatch` restaure la valeur d'origine en fin de test : aucune fuite
    # d'etat d'un test vers le suivant, contrairement a un os.environ direct.
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
