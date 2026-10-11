"""The three reductions for files no parser can read: template, prose, text.

The other half of "what counts as structure, and what counts as prose", split
out of `tests/fingerprint.py` (ZED-223); the first half, for documents that do
parse, is `tests/fingerprint_structured.py`. The contract all of them serve is
in the docstring of `tests/fingerprint.py`.

Nothing here has a parser to lean on, so each reduction is a text filter, and
each one is written to be obviously conservative rather than clever.

`template` -- Helm chart templates (anything under a chart's `templates/`
    directory, plus `.tpl` helpers). These are Go templates, not YAML: they do
    not parse, so there is no structure to compare and the text is kept. Only
    `{{/* ... */}}` Go-template comments and `{# ... #}` Jinja comments are
    removed, because those two forms are unambiguous -- they cannot mean
    anything but a comment. Full-line `#` comments are deliberately **not**
    stripped here: in an unparseable YAML file a `#` line may be a manifest
    comment or data inside a block scalar, and the two cannot be told apart
    without a parser. That costs nothing today (the generated chart templates
    carry no `#` comments at all, and a test asserts it) and it avoids a
    silently loose rule if they ever do.

`prose` -- `.md` and `.txt` files. These are documentation: their body is prose
    from the first line to the last, so a digest of the whole content would trip
    on every translation and the harness would be useless for exactly the files
    the translation touches most. What is kept is the part that is *not* prose:
    * every template expression (`{{ ... }}`, `{% ... %}`), in order. This is
      what makes Helm's `NOTES.txt` still checkable -- a broken expression there
      breaks `helm template`.
    * for Markdown: the verbatim content of fenced code blocks with their info
      string, every inline code span, every link destination, and the sequence
      of heading levels. Commands a reader copy-pastes, paths a link points at,
      and document shape are structure; the sentences around them are not.
    This is the loosest normalisation in the harness, and it is loose on
    purpose: a generated README has no effect on any validator or on any
    deployed system. Its consequence is explicit -- the prose of a generated
    `.md`/`.txt` is unchecked, and a change confined to it is invisible here.

`text` -- everything else: `.tf`, `.tfvars`, `.hcl`, `Makefile`, `ansible.cfg`,
    `.gitignore`, `.gitattributes`, `.helmignore`, Jinja `.j2` templates
    deposited on managed hosts. Full-line comments are removed using the syntax
    of the file type (`#` everywhere, plus `//` and `/* ... */` for HCL), blank
    lines are dropped and trailing whitespace is stripped; the rest is kept
    verbatim. One prose field is normalised: a `description = "..."` argument
    inside a top-level `variable` or `output` block of an HCL file. Terraform
    variable and output descriptions are documentation, and nothing else in
    these files is. A `description` anywhere else -- a resource attribute sent
    to a provider API, for instance -- is left alone.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.fingerprint_kinds import PROSE

#: Comment forms that cannot mean anything else, and are therefore safe to
#: remove from any file type: Go-template comments and Jinja comments.
#: Both Go-template spellings occur in the generated charts: `{{/* ... */}}` and
#: `{{- /* ... */}}` with the whitespace-trim marker and a space.
_UNAMBIGUOUS_COMMENTS = (
    re.compile(r"\{\{-?\s*/\*.*?\*/\s*-?\}\}", re.DOTALL),
    re.compile(r"\{#.*?#\}", re.DOTALL),
)

#: Template expressions, kept in order for prose files: they are the only
#: load-bearing thing a `.txt` deliverable contains.
_EXPRESSIONS = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)

#: Suffixes using HCL comment syntax on top of `#`.
_HCL_SUFFIXES = frozenset({".tf", ".tfvars", ".hcl"})

#: Suffixes with no comment syntax at all.
_NO_COMMENT_SUFFIXES = frozenset({".json"})

#: An HCL top-level block header, e.g. `variable "namespace" {`. Generated HCL
#: is formatted by `terraform fmt`, so a top-level block always starts in
#: column 0 and closes with a `}` in column 0 -- no brace counting needed, and
#: no risk of miscounting a brace inside a string.
_HCL_BLOCK_HEADER = re.compile(r"^([a-z_]+)\b.*\{\s*$")

#: A one-line HCL `description` argument. A multi-line form is left untouched:
#: conservative is the safe direction here.
_HCL_DESCRIPTION = re.compile(r'^(\s*description\s*=\s*)".*"\s*$')

#: HCL blocks whose `description` is documentation and nothing else.
_HCL_DOCUMENTED_BLOCKS = frozenset({"variable", "output"})

#: Markdown pieces that are structure rather than prose.
_MD_FENCE = re.compile(r"^\s*(?:```|~~~)(.*)$")
_MD_HEADING = re.compile(r"^(#{1,6})\s")
_MD_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\]\(([^)\s]+)")


# ---------------------------------------------------------------------------
# Text and template documents
# ---------------------------------------------------------------------------


def strip_unambiguous_comments(text: str) -> str:
    for pattern in _UNAMBIGUOUS_COMMENTS:
        text = pattern.sub("", text)
    return text


def _tidy(lines: list[str]) -> str:
    """Drop blank lines and trailing whitespace: neither is behaviour here."""
    kept = [line.rstrip() for line in lines]
    return "\n".join(line for line in kept if line)


def template_canonical(text: str) -> str:
    """Go/Jinja template text: only its own comment forms are removed."""
    return _tidy(strip_unambiguous_comments(text).splitlines())


def text_canonical(text: str, relative: Path) -> str:
    """Config or code: full-line comments removed, one prose field normalised."""
    suffix = relative.suffix
    if suffix == ".example":
        suffix = Path(relative.stem).suffix

    body = strip_unambiguous_comments(text)
    hcl = suffix in _HCL_SUFFIXES
    if hcl:
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)

    hashes = suffix not in _NO_COMMENT_SUFFIXES
    block: str | None = None
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if hashes and stripped.startswith("#"):
            continue
        if hcl:
            if stripped.startswith("//"):
                continue
            if line.startswith("}"):
                block = None
            else:
                header = _HCL_BLOCK_HEADER.match(line)
                if header:
                    block = header.group(1)
            if block in _HCL_DOCUMENTED_BLOCKS:
                line = _HCL_DESCRIPTION.sub(rf'\1"{PROSE}"', line)
        kept.append(line)
    return _tidy(kept)


# ---------------------------------------------------------------------------
# Prose documents
# ---------------------------------------------------------------------------


def prose_canonical(text: str, relative: Path) -> str:
    """Documentation: keep the parts that are not prose, forget the rest."""
    # Comments first: `{{/* ... */}}` would otherwise be collected as an
    # expression, and Helm's NOTES.txt opens with exactly that.
    text = strip_unambiguous_comments(text)
    pieces: list[str] = [
        f"expression: {match.group(0).strip()}" for match in _EXPRESSIONS.finditer(text)
    ]
    if relative.suffix != ".md":
        return "\n".join(pieces)

    fence: str | None = None
    fenced: list[str] = []
    for line in text.splitlines():
        marker = _MD_FENCE.match(line)
        if marker and fence is None:
            fence = marker.group(1).strip()
            fenced = []
            pieces.append(f"fence-open: {fence}")
            continue
        if marker and fence is not None:
            pieces.append("fence-body: " + "\n".join(fenced))
            pieces.append("fence-close")
            fence = None
            continue
        if fence is not None:
            fenced.append(line.rstrip())
            continue
        heading = _MD_HEADING.match(line)
        if heading:
            pieces.append(f"heading: level {len(heading.group(1))}")
        pieces.extend(f"code: {span}" for span in _MD_INLINE_CODE.findall(line))
        pieces.extend(f"link: {target}" for target in _MD_LINK.findall(line))
    if fence is not None:  # unterminated fence: keep what was read
        pieces.append("fence-body: " + "\n".join(fenced))
    return "\n".join(pieces)
