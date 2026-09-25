"""Reading and writing `forge.yml`.

Port of `ansible_forge.spec_io` (MIGRATION.md §3, duplicate §5.2) made
domain-agnostic: validation belongs to `assembly`, this module only does
deterministic YAML — key order fixed by the model (never alphabetical), no flow
style, LF line endings, UTF-8. Saving then reloading a spec must give back an
identical object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge.errors import SpecFileError

#: Default specification file name.
SPEC_FILENAME = "forge.yml"

# The header below is written into the user's `forge.yml`, so it is generated
# output and not source prose: translating it would move every golden fixture.
# It is translated with the templates and the goldens, not here.
_HEADER_TOP = """\
---
# ---------------------------------------------------------------------------
# forge.yml - Specification du service
# ---------------------------------------------------------------------------
# Ce fichier decrit entierement ce qui doit etre genere. Il est rejouable :
#   forge generate --spec forge.yml
# produit exactement la meme arborescence, octet pour octet.
#
# Editez-le a la main puis relancez la generation ; ne modifiez pas
# 'forge_version' manuellement.
"""

_HEADER_BOTTOM = """\
# ---------------------------------------------------------------------------
"""


class _ForgeDumper(yaml.SafeDumper):
    """YAML dumper that indents lists, more readable for a human."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def build_header(sections: list[str]) -> str:
    """Commented header, enriched with the list of domains present."""
    lines = [_HEADER_TOP]
    if sections:
        # Generated output, like `_HEADER_TOP` above: left in French on purpose.
        lines.append("#\n# Domaines generes par cette specification :\n")
        for name in sections:
            lines.append(f"#   - {name}\n")
    lines.append(_HEADER_BOTTOM)
    return "".join(lines)


def dump_yaml(data: dict[str, Any]) -> str:
    """Serialise `data` to deterministic YAML, without the header."""
    return yaml.dump(
        data,
        Dumper=_ForgeDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )


def dump_spec(data: dict[str, Any], *, sections: list[str] | None = None) -> str:
    """Serialise a complete spec, header included."""
    header = build_header(sections if sections is not None else [])
    return header + dump_yaml(data)


def save_spec(
    data: dict[str, Any], path: Path, *, sections: list[str] | None = None
) -> Path:
    """Write the spec to `path` (UTF-8, LF line endings) and return the path."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            dump_spec(data, sections=sections), encoding="utf-8", newline="\n"
        )
    except OSError as exc:
        raise SpecFileError(f"cannot write {path}: {exc}") from exc
    return path


def _check_string_keys(node: Any, source: str, path: str = "") -> None:
    """Refuse any mapping key that is not a string.

    YAML 1.1 reads `on:`, `yes:`, `no:` and `1.2:` as a boolean or a number. The
    key is then no longer a string, and everything else in the core (comparing
    against known sections, formatting messages) would break on a Python
    traceback. Better to say so here, with the offending line.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str):
                where = f" under {path}" if path else " at the root"
                raise SpecFileError(
                    f"non-textual YAML key{where} in {source}: {key!r} "
                    f"({type(key).__name__}).\n"
                    "  YAML 1.1 converts on/off/yes/no/true/false to booleans and "
                    "1.2 to a number: quote the key."
                )
            _check_string_keys(value, source, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _check_string_keys(item, source, f"{path}[{index}]")


def parse_spec(text: str, *, source: str = "<string>") -> dict[str, Any]:
    """Parse a YAML text and return the raw dict, without validating it."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecFileError(f"invalid YAML in {source}: {exc}") from None
    if data is None:
        raise SpecFileError(f"Specification {source} is empty.")
    if not isinstance(data, dict):
        raise SpecFileError(
            f"Specification {source} must be a YAML mapping, "
            f"found: {type(data).__name__}."
        )
    _check_string_keys(data, source)
    return data


def load_spec_data(path: Path) -> dict[str, Any]:
    """Load the raw dict of the spec located at `path`."""
    path = Path(path)
    if not path.exists():
        raise SpecFileError(f"Specification file not found: {path}")
    if not path.is_file():
        raise SpecFileError(f"The specification path is not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecFileError(f"Cannot read {path}: {exc}") from None
    return parse_spec(text, source=str(path))
