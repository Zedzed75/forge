"""Answer the question "is there French in here?" — mechanically, on real bytes.

ZED-10 translated `src/forge/` outside `plugins/`, ZED-11 translated
`src/forge/plugins/<domain>/`, and ~2100 French lines survived both, because
nothing in the repository could measure the claim. This module is that
measurement; `test_french_guard.py` turns it into a gate.

Two signals, and a list of words deliberately left out of both
----------------------------------------------------------------

**Accented characters.** Cheap and almost noise-free, but it has to be read as
*text*, not as bytes: `git grep '[éèê…]'` in the C locale matches `—`, `§` and
`──` because they share lead bytes with the accented letters. That is what once
made a scan of the `helm` branch look like 74 problems. Every file here is
decoded as UTF-8 first, and `test_em_dash_is_not_an_accent` pins the
distinction.

**Unambiguous French function words, two or more distinct ones on one line.**
A single French-looking word proves nothing: `role` and `roles` are Ansible's
own nouns, `present` and `absent` are module states, `on` is an English
preposition and `le` is the PromQL bucket label. Those, plus `la`, `les`,
`des`, `une`, `du`, `est`, `sont`, `il`, `si`, `car`, `ou`, `plus` and
`section`, are too common in English, in identifiers or in PromQL to use at
all — a scan built on them flagged 75 lines across the five ZED-24 branches
and every single one was an English false positive. Requiring **two** distinct
words from a conservative list is what separates real French prose from those.

Scope, and why `tests/` is in it
--------------------------------

`src/forge/**/*.py` and `src/forge/plugins/*/template/**` — the templates are
where the French that *reaches users* lives. `tests/**/*.py` is in scope too:
ZED-50 left that call open, and the measurement settles it. Outside this
module's own two files, which necessarily spell the alphabet and the word list
they detect, `tests/` carries exactly one French line — a rejected-input
fixture that has to stay French to mean anything — so including it costs one
allowlist entry and stops the next French docstring landing here instead of in
`src/`.

On the tree this landed on, both signals report zero across `src/forge/` and
every plugin template, so `tests/french_baseline.txt` ships with an empty
`[baseline]` section. That is the first measured answer the repository has ever
had to the question in the first line, and it is why this is a gate rather than
a backlog.

Everything else stays French by the hard rule in `CLAUDE.md` ("Comments/docs in
French; identifiers, keys and file names in English"): `.github/`, `DESIGN.md`,
`MIGRATION.md`, `PLAN.md`, `CHANGELOG.md`, `pyproject.toml` and the repository
`copier.yml` are **not** scanned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Root of the forge repository. Kept local rather than imported from
#: `conftest`, so the scan can be run as a plain script on any checkout.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The accented letters French actually uses, lower and upper case. `œ`/`Œ` are
#: in; the typographic signs that share their UTF-8 lead bytes (`—`, `§`, `─`)
#: are deliberately out, and tested to be out.
ACCENTED_LETTERS = "éèêëàâäîïôöùûüçœÉÈÊËÀÂÄÎÏÔÖÙÛÜÇŒ"

_ACCENT_RX = re.compile(f"[{ACCENTED_LETTERS}]")

#: French function words with no plausible English or IaC reading. Shortness is
#: not the criterion — ambiguity is: `aux` and `qui` stay because no English
#: word or Ansible/Helm/PromQL identifier spells them, while `des` and `une`
#: are out because `--des`-style flags and `une`-containing identifiers exist.
FUNCTION_WORDS = frozenset(
    {
        "afin",
        "ainsi",
        "aux",
        "avec",
        "cette",
        "champ",
        "chaque",
        "chemin",
        "dans",
        "doit",
        "donc",
        "fichier",
        "gabarit",
        "genere",
        "inconnu",
        "lorsque",
        "peut",
        "pour",
        "qui",
        "rendu",
        "sans",
        "valeur",
    }
)

#: Words that look French and are not, or are too common to tell apart. Never
#: add one of these to `FUNCTION_WORDS`; the list is here so the next reader
#: does not have to rediscover why the obvious candidates are missing.
REJECTED_WORDS = frozenset(
    {
        "absent",  # Ansible module state
        "car",
        "des",
        "du",
        "est",
        "il",
        "la",
        "le",  # PromQL histogram bucket label (`le="0.5"`)
        "les",
        "on",  # English preposition
        "ou",
        "plus",
        "present",  # Ansible module state
        "role",  # Ansible's own noun
        "roles",
        "section",
        "si",
        "sont",
        "une",
    }
)

#: Distinct words from `FUNCTION_WORDS` needed on one line before it counts.
#: One is noise (see the module docstring); two was the threshold that left
#: zero false positives across the five ZED-24 branches.
MIN_WORDS_PER_LINE = 2

#: Word boundaries that also break on `-` and `_`, so `role-doit-pour` in an
#: identifier is three words rather than one unmatched blob, and `value` never
#: matches inside `valuereference`.
_WORD_RX = re.compile(r"[A-Za-z]+")

#: The two signals, by the name they carry in the baseline file.
ACCENT = "accent"
WORDS = "words"
SIGNALS = (ACCENT, WORDS)

#: Globs scanned, relative to `REPO_ROOT`. `template/**/*` deliberately takes
#: every extension: a `.jinja`, a `.yml` and a `.txt` under `template/` all
#: end up in a generated project.
SCANNED_GLOBS = (
    "src/forge/**/*.py",
    "src/forge/plugins/*/template/**/*",
    "tests/**/*.py",
)


@dataclass(frozen=True)
class Hit:
    """One suspect line: where it is, which signal fired, and on what."""

    #: Path relative to `REPO_ROOT`, with forward slashes on every platform.
    path: str
    #: 1-indexed line number.
    line: int
    #: `ACCENT` or `WORDS`.
    signal: str
    #: What fired — the accented letters found, or the French words found.
    evidence: str
    #: The line itself, stripped and truncated for the failure message.
    excerpt: str


def scan_text(text: str, path: str = "<text>") -> list[Hit]:
    """Run both signals over one already-decoded string."""
    hits: list[Hit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        accents = sorted(set(_ACCENT_RX.findall(line)))
        if accents:
            hits.append(
                Hit(path, number, ACCENT, "".join(accents), _excerpt(line))
            )
        words = sorted(
            {
                word.lower()
                for word in _WORD_RX.findall(line)
                if word.lower() in FUNCTION_WORDS
            }
        )
        if len(words) >= MIN_WORDS_PER_LINE:
            hits.append(
                Hit(path, number, WORDS, " ".join(words), _excerpt(line))
            )
    return hits


def scanned_files(root: Path | None = None) -> list[Path]:
    """Every in-scope file, de-duplicated and ordered for reproducibility."""
    base = root or REPO_ROOT
    found: set[Path] = set()
    for glob in SCANNED_GLOBS:
        found.update(path for path in base.glob(glob) if path.is_file())
    return sorted(found)


def scan_tree(root: Path | None = None) -> list[Hit]:
    """Run both signals over the whole in-scope tree.

    A file that is not valid UTF-8 is not French by either signal — it is
    skipped rather than raising, so a future binary fixture under `template/`
    cannot break the gate.
    """
    base = root or REPO_ROOT
    hits: list[Hit] = []
    for path in scanned_files(base):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(base).as_posix()
        hits.extend(scan_text(text, relative))
    return hits


def counts_by_file(hits: list[Hit]) -> dict[tuple[str, str], int]:
    """Collapse hits into the `(path, signal) -> number of lines` of a baseline."""
    counts: dict[tuple[str, str], int] = {}
    for hit in hits:
        key = (hit.path, hit.signal)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _excerpt(line: str, width: int = 100) -> str:
    stripped = line.strip()
    return stripped if len(stripped) <= width else stripped[: width - 1] + "…"


# ---------------------------------------------------------------------------
# The baseline file
# ---------------------------------------------------------------------------

#: Data file holding the ratchet and the permanent exemptions.
BASELINE_FILE = Path(__file__).with_name("french_baseline.txt")

_BASELINE_SECTION = "baseline"
_ALLOWED_SECTION = "allowed"


class BaselineError(ValueError):
    """The baseline file does not parse. Always quotes the offending line."""


@dataclass(frozen=True)
class Baseline:
    """What the guard tolerates, split by why it tolerates it."""

    #: `(path, signal) -> maximum number of lines`, for French still to be
    #: translated. An upper bound that must only ever come down.
    limits: dict[tuple[str, str], int]
    #: `(path, signal) -> justification`, for French that has to stay.
    allowed: dict[tuple[str, str], str]
    #: `(path, signal) -> owning issue and note`, for the `limits` entries.
    notes: dict[tuple[str, str], str]

    def tolerated(self, key: tuple[str, str]) -> bool:
        """Is this `(path, signal)` known at all?"""
        return key in self.limits or key in self.allowed


def load_baseline(path: Path | None = None) -> Baseline:
    """Parse the pipe-separated baseline file.

    Pipes rather than whitespace because template paths contain spaces — a
    `str.split()` parser would silently truncate
    `template/[[ _copier_conf.answers_file ]].jinja` and quietly stop guarding
    it.
    """
    source = path or BASELINE_FILE
    limits: dict[tuple[str, str], int] = {}
    allowed: dict[tuple[str, str], str] = {}
    notes: dict[tuple[str, str], str] = {}
    section: str | None = None

    for number, raw in enumerate(
        source.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            if section not in (_BASELINE_SECTION, _ALLOWED_SECTION):
                raise BaselineError(f"{source.name}:{number}: unknown section {line}")
            continue
        if section is None:
            raise BaselineError(f"{source.name}:{number}: entry before any section")

        fields = [field.strip() for field in line.split("|")]
        expected = 4 if section == _BASELINE_SECTION else 3
        if len(fields) != expected:
            raise BaselineError(
                f"{source.name}:{number}: [{section}] wants {expected} "
                f"pipe-separated fields, got {len(fields)}: {line}"
            )

        if section == _BASELINE_SECTION:
            signal, count, file_path, note = fields
        else:
            signal, file_path, note = fields
            count = ""
        if signal not in SIGNALS:
            raise BaselineError(
                f"{source.name}:{number}: unknown signal {signal!r}, "
                f"expected one of {SIGNALS}"
            )
        key = (file_path, signal)
        if key in limits or key in allowed:
            raise BaselineError(f"{source.name}:{number}: duplicate entry: {line}")

        if section == _BASELINE_SECTION:
            if not count.isdigit() or int(count) == 0:
                raise BaselineError(
                    f"{source.name}:{number}: the count must be a positive "
                    f"integer, got {count!r} (delete the entry instead of "
                    f"writing 0): {line}"
                )
            limits[key] = int(count)
            notes[key] = note
        else:
            allowed[key] = note

    return Baseline(limits=limits, allowed=allowed, notes=notes)
