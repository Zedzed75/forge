"""`docs/PLUGIN-CONTRACT.md` - the generated copy, tested rather than trusted.

This module is the thing that makes the generated document safe. Without it the
generator is just a nicer way to produce the same stale copy D13 warns about:
nothing would notice that `src/forge/plugins_api/types.py` moved and the
document did not, which is precisely how `DESIGN.md` §2.1 came to declare
`Command.argv` as `list[str]` for several phases while the module said
`tuple[str, ...]`.

So the drift branch is driven here against a mutated copy of the tree, not
assumed from a green run of the happy path - the same reasoning
`tests/test_file_size_gate.py` gives for the gate it covers.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = REPO_ROOT / "scripts" / "render_plugin_contract.py"
DOC_PATH = REPO_ROOT / "docs" / "PLUGIN-CONTRACT.md"
DESIGN_PATH = REPO_ROOT / "DESIGN.md"


def _load_renderer():
    """Import the script by path: `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("render_plugin_contract", RENDERER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = _load_renderer()


def _committed_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_committed_document_matches_the_modules() -> None:
    """The point of the whole exercise: the copy is in step with `src/`."""
    assert _committed_doc() == renderer.render(REPO_ROOT), (
        "docs/PLUGIN-CONTRACT.md is stale. Re-run: "
        "python scripts/render_plugin_contract.py"
    )


def test_check_mode_passes_on_the_real_repository() -> None:
    assert renderer.main(["--check"]) == 0


def test_drift_is_detected(tmp_path: Path) -> None:
    """Change a signature in the module, leave the document: it must go red.

    ZED-233's acceptance criterion in full - the one that separates a drift
    check from a decorative one.
    """
    fake_root = tmp_path / "repo"
    for section in renderer.SECTIONS:
        rel = section[2]
        (fake_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, fake_root / rel)

    assert renderer.render(fake_root) == _committed_doc()

    victim = fake_root / renderer.SECTIONS[0][2]
    mutated = victim.read_text(encoding="utf-8").replace(
        "argv: tuple[str, ...] = ()", "argv: list[str] = []"
    )
    assert mutated != victim.read_text(encoding="utf-8"), (
        "the signature this test mutates has itself moved; point it at a "
        "field that still exists in types.py"
    )
    victim.write_text(mutated, encoding="utf-8", newline="\n")

    assert renderer.render(fake_root) != _committed_doc()


def test_document_caps_itself() -> None:
    """A register outside SCAN_DIRS is capped only because it is named."""
    gate_source = (REPO_ROOT / "scripts" / "check_file_sizes.py").read_text(
        encoding="utf-8"
    )
    assert '"docs/PLUGIN-CONTRACT.md"' in gate_source
