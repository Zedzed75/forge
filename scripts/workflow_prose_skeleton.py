#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# The behavioural skeleton of one GitHub workflow file (decision D7, clause C1).
# ---------------------------------------------------------------------------
# `scripts/workflow-diff-is-prose.sh` is the entry point; this is the part that
# decides what "prose" means, one file at a time. It reads a workflow file and
# prints a normalised form of it in which exactly three things are erased:
#
#   * comments -- YAML comments, and shell comments inside a `run:` block,
#   * the *value* of a **step-level** `name:`,
#   * the literal text inside an already-quoted string in a `run:` block.
#
# Everything else is printed verbatim. The caller then compares the skeleton of
# the base revision with the skeleton of the head revision: if they are equal,
# every changed line fell into one of those three categories and the diff is
# prose. If they differ, something behavioural moved -- and the difference
# between the two skeletons names it.
#
# Writing the test this way round is what makes it fail closed. There is no list
# of forbidden keys to keep in sync with the workflow syntax: a key this script
# has never heard of is simply copied, so a change to it shows up as a skeleton
# difference. The same is true of a line whose quoting does not close, of a
# block scalar that is not a `run:`, and of anything else the normaliser cannot
# confidently classify -- the fallback is always "copy it", never "assume it is
# text".
#
# Two erasures are deliberately *not* performed, both of them named in D7:
#
#   * a **job-level** `name:` is kept. Check-run identity derives from it, and
#     D4's six-checks clause depends on that identity, so renaming a job is a
#     behavioural change even when the new name is a translation of the old.
#   * a line that writes to `$GITHUB_OUTPUT`, `$GITHUB_ENV`, `$GITHUB_PATH` or
#     `$GITHUB_STATE` is kept whole, quotes included. There the text inside the
#     quotes is not prose: it is the key and the value of a variable another
#     step reads. `echo "tag=${tag} built version=${built}"` is a log line and
#     is prose; the same string with `>> "$GITHUB_OUTPUT"` after it is an
#     interface.
#
# Usage: workflow_prose_skeleton.py <file>   (prints the skeleton on stdout)
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
import sys

# A single marker stands in for every comment and every blank line, and
# consecutive markers collapse into one. Comments are free under C1, including
# the right to be reflowed: a translation that turns five lines of French into
# six lines of English must not read as a behavioural change.
PROSE = "<prose>"

# The placeholder for the value of a step-level `name:`.
NAME = "<step-name>"

# `key:`, optionally introduced by one or more YAML sequence dashes
# (`- name: ...`). The dashes are part of the indentation as far as the key's
# nesting level is concerned, which is how a step's own keys are told apart from
# the keys of the mapping that contains the step.
KEY_RE = re.compile(
    r"^(?P<indent> *)(?P<dash>(?:- +)*)(?P<key>[A-Za-z_][A-Za-z0-9_.-]*) *:(?P<rest>.*)$"
)

# A block scalar header: `|`, `>`, and their chomping/indentation variants.
BLOCK_RE = re.compile(r"^[|>][+-]?[0-9]*$")

# Shell expansions are kept when the text around them is erased: the prose of a
# log line may be rewritten, but the variables it interpolates may not quietly
# change along with it.
EXPANSION_RE = re.compile(
    r"\$\{\{.*?\}\}"  # a GitHub expression, which is never prose
    r"|\$\{[^}]*\}"  # ${var}, ${var#prefix}, ...
    r"|\$\([^)]*\)"  # a command substitution
    r"|\$[A-Za-z_][A-Za-z0-9_]*"  # $var
    r"|\$[0-9?@*#!$-]"  # the positional and special parameters
)

# A line that touches one of these is an interface between steps, never prose.
PROTECTED = ("GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_PATH", "GITHUB_STATE")

# A pinned version is never prose either, and it is not always outside the
# quotes: the Ansible tooling and the Galaxy collections are pinned *inside*
# `run:` blocks (`uv pip install 'ansible-core==2.19.13'`). Erasing quoted text
# wholesale would therefore let a translation move a pin, which C1 forbids by
# name. Any shell line that looks like it carries a version is compared
# verbatim. A log string that happens to quote a number pays for this with a
# refusal, which is the direction a fail-closed test errs in.
PIN_RE = re.compile(r"[0-9]+\.[0-9]+|==|@[0-9a-f]{7,}")


def split_quotes(text: str) -> list[tuple[str, str]] | None:
    """Split a shell line into quoted and unquoted segments.

    Returns a list of `(quote_char, content)` pairs, where `quote_char` is `""`
    for the parts outside any quotes. Returns `None` when the quoting does not
    close on this line, which the caller treats as "unclassifiable, copy it".
    """
    segments: list[tuple[str, str]] = []
    buf: list[str] = []
    quote = ""
    i = 0
    while i < len(text):
        char = text[i]
        if quote == "":
            if char == "\\" and i + 1 < len(text):
                # An escaped character outside quotes is structure (a line
                # continuation, an escaped space); keep both characters.
                buf.append(text[i : i + 2])
                i += 2
                continue
            if char in ("'", '"'):
                segments.append(("", "".join(buf)))
                buf = []
                quote = char
                i += 1
                continue
        elif char == "\\" and quote == '"' and i + 1 < len(text):
            buf.append(text[i : i + 2])
            i += 2
            continue
        elif char == quote:
            segments.append((quote, "".join(buf)))
            buf = []
            quote = ""
            i += 1
            continue
        buf.append(char)
        i += 1
    if quote != "":
        return None
    segments.append(("", "".join(buf)))
    return segments


def cut_comment(segments: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop a trailing comment, if the `#` really starts one.

    A `#` only opens a comment outside quotes and at the start of a word, so the
    fragment of `https://example.invalid/page#anchor` is left alone.
    """
    out: list[tuple[str, str]] = []
    for kind, content in segments:
        if kind != "":
            out.append((kind, content))
            continue
        match = re.search(r"(?:^|\s)#", content)
        if match is None:
            out.append((kind, content))
            continue
        out.append((kind, content[: match.start()]))
        break
    return out


def erase_quoted_prose(text: str) -> str:
    """Erase the literal text inside the quoted strings of one shell line.

    The text outside the quotes -- the command, the operators, every
    redirection, the line continuations -- is kept exactly as it is. So is the
    quote character itself: turning `'...'` into `"..."` changes how the shell
    reads the string, and is not a translation.
    """
    if any(name in text for name in PROTECTED) or PIN_RE.search(text):
        return text
    segments = split_quotes(text)
    if segments is None:
        return text
    pieces: list[str] = []
    for kind, content in cut_comment(segments):
        if kind == "":
            pieces.append(content)
        else:
            expansions = ",".join(EXPANSION_RE.findall(content))
            pieces.append(f"{kind}<text:{expansions}>{kind}")
    return "".join(pieces).rstrip()


def strip_yaml_comment(line: str) -> str:
    """Remove a trailing YAML comment from a structural line.

    The quote characters are put back: `"**"` and `**` are not the same
    pathspec to YAML, so a structural line keeps its quoting.
    """
    segments = split_quotes(line)
    if segments is None:
        return line
    return "".join(
        content if kind == "" else f"{kind}{content}{kind}"
        for kind, content in cut_comment(segments)
    ).rstrip()


def skeleton(text: str) -> list[str]:
    """Normalise a whole workflow file to its behavioural skeleton."""
    out: list[str] = []

    def emit(value: str) -> None:
        if value == PROSE and out and out[-1] == PROSE:
            return  # collapse a run of comments and blank lines into one marker
        out.append(value)

    # The stack of enclosing mapping keys, as `(indent_of_key, key)`. It answers
    # the one question the classification needs: is the `name:` on this line the
    # name of a step, or the name of a job, a workflow, or an input of a
    # `with:` block?
    stack: list[tuple[int, str]] = []
    block: tuple[int, bool] | None = None  # (indent of the key, is it a `run:`)

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if block is not None:
            block_indent, is_run = block
            if stripped == "":
                emit(PROSE)
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent > block_indent:
                if is_run and stripped.startswith("#"):
                    emit(PROSE)
                elif is_run:
                    emit(erase_quoted_prose(line))
                else:
                    # Some other block scalar: nothing in C1 says its content is
                    # prose, so it is compared as it stands.
                    emit(line)
                continue
            block = None  # the block ended; this line is structure again

        if stripped == "" or stripped.startswith("#"):
            emit(PROSE)
            continue

        match = KEY_RE.match(line)
        if match is None:
            # A sequence item, a flow collection, a continuation: structure.
            emit(strip_yaml_comment(line))
            continue

        key = match["key"]
        key_indent = len(match["indent"]) + len(match["dash"])
        rest = match["rest"].strip()
        while stack and stack[-1][0] >= key_indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        stack.append((key_indent, key))
        prefix = f"{match['indent']}{match['dash']}{key}:"

        if BLOCK_RE.match(rest):
            block = (key_indent, key == "run")
            emit(f"{prefix} {rest}")
        elif key == "name" and parent == "steps":
            # The one `name:` C1 lets through. `parent == "steps"` is what keeps
            # a job's name and a `with: name:` input out of this branch.
            emit(f"{prefix} {NAME}")
        elif key == "run":
            emit(f"{prefix} {erase_quoted_prose(rest)}")
        elif key == "uses":
            # Verbatim, trailing comment included: on a `uses:` line that
            # comment is the human-readable half of the pin.
            emit(line)
        else:
            emit(strip_yaml_comment(line))

    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: workflow_prose_skeleton.py <file>\n")
        return 2
    with open(argv[1], "rb") as handle:
        raw = handle.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        # Fail closed: a workflow this script cannot even read is not a file it
        # may declare prose.
        sys.stderr.write(f"workflow_prose_skeleton: {argv[1]}: {error}\n")
        return 1
    sys.stdout.write("\n".join(skeleton(text)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
