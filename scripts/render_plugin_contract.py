#!/usr/bin/env python3
"""Render `docs/PLUGIN-CONTRACT.md` from the two modules that *are* the contract.

`DESIGN.md` §2.1 and §2.2 used to carry a hand-copied reproduction of
`src/forge/plugins_api/types.py` and `src/forge/plugins_api/hookspecs.py`. D13
("reference, do not restate") predicted how that ends and it ended that way: by
the time ZED-233 measured it, the copy declared `Command.argv` as `list[str]`
where the module says `tuple[str, ...]`, omitted `DomainInfo.deploy_order`,
`CatalogEntry`, `DomainSummary` and `GenerationContext` outright, and never
mentioned the `forge_deploy` hook at all. `PLAN.md` R1 had even recorded "bring
`DESIGN.md` §2.1 up to date" as an action, and it was never done.

Relocating that copy would have moved where it goes stale. Generating it is the
only option that makes it *safe*, so this script exists and
`tests/test_plugin_contract_doc.py` fails the build when the committed document
and the modules disagree.

The embedding is **verbatim and whole-module** rather than a rendering of
signatures. Two reasons:

* the inline comments are the content. `# "ansible" - section key in forge.yml`
  next to `name: str` is why §2.1 was worth reading; an AST re-render of the
  signatures would drop exactly the part a reader came for.
* slicing requires judgement about what belongs, and that judgement is itself a
  thing that can drift. Taking the file whole has no such knob.

Usage:

    python scripts/render_plugin_contract.py            # write the document
    python scripts/render_plugin_contract.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DOC_REL = "docs/PLUGIN-CONTRACT.md"

# (section id, title, module path, what the section is for).
# The section ids match `DESIGN.md`, whose §2.1/§2.2 point here, so that the
# many `DESIGN.md §2.2` citations in `src/` keep resolving.
SECTIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "2.1",
        "Exchanged types",
        "src/forge/plugins_api/types.py",
        "The dataclasses the core and a plugin pass between them. Every field "
        "carries its own comment; those comments are the specification.",
    ),
    (
        "2.2",
        "Hookspecs",
        "src/forge/plugins_api/hookspecs.py",
        "The pluggy hook specifications. `forge_domain` is mandatory; the rest "
        "are optional, and a domain implements the ones it needs.",
    ),
)

_PREAMBLE = """# The plugin contract

**This file is generated. Do not edit it by hand.**

It is produced by `scripts/render_plugin_contract.py` from the modules quoted
below, and `tests/test_plugin_contract_doc.py` fails if the two disagree. To
change the contract, change the module and re-run:

```bash
python scripts/render_plugin_contract.py
```

This was `DESIGN.md` §2.1 and §2.2 until ZED-233. Those sections held a
hand-maintained copy of the same two modules, and the copy had drifted: it
declared `Command.argv` as `list[str]` where the module says
`tuple[str, ...]`, omitted `DomainInfo.deploy_order`, `CatalogEntry`,
`DomainSummary` and `GenerationContext`, and did not mention the
`forge_deploy` hook. That is D13's failure mode, so the fix is a generator
rather than a correction - a correction would only have reset the clock.

The section numbers are unchanged, so an existing citation of "DESIGN.md §2.1"
or "§2.2" resolves here, and `DESIGN.md` §2.1/§2.2 are pointers to this file.
§2.3 and §2.4 stay in `DESIGN.md`: they are prose about *using* the contract,
not a reproduction of it.

This file is named in `TRACKED_PROSE` in `scripts/check_file_sizes.py`, so it
caps itself at the same thresholds as the other registers. Being generated, it
grows only when the contract does - which is the signal that cap is for.
"""


def _read_module(repo_root: Path, rel: str) -> str:
    """Return the module's text with newlines normalised and no trailing blanks."""
    text = (repo_root / rel).read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def render(repo_root: Path = REPO_ROOT) -> str:
    """Build the whole document. Pure: same inputs, same bytes."""
    parts = [_PREAMBLE]
    for section, title, rel, blurb in SECTIONS:
        parts.append(
            f"---\n\n## {section} {title}\n\n"
            f"{blurb}\n\n"
            f"Source: [`{rel}`]({_doc_to_repo(rel)})\n\n"
            f"```python\n{_read_module(repo_root, rel)}\n```\n"
        )
    return "\n".join(parts)


def _doc_to_repo(rel: str) -> str:
    """Link target relative to `docs/`, where this document lives."""
    return f"../{rel}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the committed document is stale",
    )
    args = parser.parse_args(argv)

    expected = render(REPO_ROOT)
    target = REPO_ROOT / DOC_REL

    if args.check:
        current = (
            target.read_text(encoding="utf-8").replace("\r\n", "\n")
            if target.exists()
            else ""
        )
        if current == expected:
            return 0
        print(
            f"{DOC_REL} is out of date with the plugin_api modules.\n"
            "Re-run: python scripts/render_plugin_contract.py",
            file=sys.stderr,
        )
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(expected, encoding="utf-8", newline="\n")
    print(f"wrote {DOC_REL} ({expected.count(chr(10)) + 1} lines)")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via the test module
    raise SystemExit(main())
