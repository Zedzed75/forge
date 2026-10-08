"""Answer the question "is there French in here?" — mechanically, on real bytes.

ZED-10 translated `src/forge/` outside `plugins/`, ZED-11 translated
`src/forge/plugins/<domain>/`, and ~2100 French lines survived both, because
nothing in the repository could measure the claim. This module is that
measurement; `test_french_guard.py` turns it into a gate.

Three signals, and the words deliberately left out of each
----------------------------------------------------------

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

**One French content word in a prose-shaped value.** The two signals above are
strong on French *prose* and were blind to French *values* — the short noun
phrases a `description` or an `owner` field holds. `Boutique en ligne` carries
no accent and exactly one function word (`en`, which is rejected anyway);
`Equipe Plateforme` carries none at all. ZED-69 measured the gap: eleven test
modules held 32 such lines that the first two signals reported as clean, and
every one of them was found by a human reading the diff rather than by the
gate. Lowering `MIN_WORDS_PER_LINE` to 1 is not the fix — ZED-50 tried it and
got 75 English false positives. This signal is a *different* list (French
content words, not function words) read in a *narrower place* (the value side
of a line, not the whole line), which is what makes a threshold of one safe:
see `CONTENT_WORDS` for the list and `_prose_values` for the place.

Scope, and why `tests/` is in it
--------------------------------

`src/forge/**/*.py` and `src/forge/plugins/*/template/**` — the templates are
where the French that *reaches users* lives. `tests/**/*.py` is in scope too,
and the reason is stronger than ZED-50 thought: the fixtures in `tests/` are
copied verbatim into the golden trees, so a French `description` there *is*
French in generated output. ZED-50 claimed `tests/` carried "exactly one French
line"; that was true of what it could detect and false of the tree, which held
32 more. ZED-69 added the third signal and that sentence is now gone.

On the tree this landed on, all three signals report zero across `src/forge/`
and every plugin template, so `tests/french_baseline.txt` ships with an empty
`[baseline]` section. That is the first measured answer the repository has ever
had to the question in the first line, and it is why this is a gate rather than
a backlog.

What none of the three detects
------------------------------

Stated here so that "the baseline is empty" is never read as "there is no
French left". `test_the_blind_spot_is_known` and
`test_the_value_blind_spots_are_known` pin these on real lines:

* **De-accented French built only from rejected words.** `Definitions des roles
  du catalogue, un module par role` is French and fires nothing, because every
  word in it is on `REJECTED_WORDS`. That is the price of zero false positives.
* **French identifiers.** `boutique`, `passerelle` and `plateforme` are the
  fixture service names, and they appear in ~60 paths, hostnames and slugs
  (`helm/charts/boutique/`, `plateforme@example.net`, `boutique-prod`).
  `_prose_values` skips identifier-shaped values for exactly that reason, so
  `"name": "boutique"` is clean by design — renaming those is ZED-59's job, not
  a signal's. The cost is that a French value which is *only* an identifier,
  like `"Boutique_Web"` in `test_spec.py`, is missed too.
* **Content words that are also English.** `demonstration`, `service`,
  `applicative` and `catalogue` are spelled the same in both languages and are
  on `REJECTED_CONTENT_WORDS`. `Boutique en ligne de demonstration` is caught by
  `ligne`, not by `demonstration`.
* **Anything spanning two lines.** Every signal is line-oriented. For `words`
  that loses any French sentence wrapped across a concatenation; for `nouns`
  the gap is narrower — it takes a concatenation through the middle of a noun,
  since the phrase on one line still fires.

A reviewer who reads the prose is still the last word. These signals catch
regressions; they do not certify a tree.

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

#: French content words — nouns and adjectives, not grammar — with no English
#: spelling at all. These are what a `description` or an `owner` field is made
#: of, and one of them inside a prose-shaped value is enough (see
#: `_prose_values` for why one is safe here and not on a whole line). Plurals
#: are listed rather than stemmed: `_WORD_RX` matches whole runs of letters, so
#: `passerelles` would not match `passerelle`, and a stemmer would start
#: matching English words that merely end in `s`.
#:
#: A term is deleted from this list once the tree holds no French using it —
#: it costs nothing to keep, but a list that never shrinks stops describing
#: anything. Add one when the gate misses French you had to find by reading.
CONTENT_WORDS = frozenset(
    {
        "domaine",
        "domaines",
        "environnement",
        "environnements",
        "equipe",
        "equipes",
        "exemple",
        "exemples",
        "ligne",
        "lignes",
        "passerelle",
        "passerelles",
        "plateforme",
        "plateformes",
        "serveur",
        "serveurs",
        "utilisateur",
        "utilisateurs",
    }
)

#: French-looking content words kept out of `CONTENT_WORDS`, and why. Same role
#: as `REJECTED_WORDS`: the obvious candidates are missing on purpose.
REJECTED_CONTENT_WORDS = frozenset(
    {
        "applicative",  # English too ("applicative functor")
        "boutique",  # English too, and the fixture service name in ~60 paths
        "catalogue",  # spelled the same in both languages
        "demonstration",  # spelled the same in both languages
        "service",  # spelled the same, and a first-class spec key
        "version",  # spelled the same
    }
)

#: Content words needed in one prose-shaped value before it counts. One, which
#: is the whole point of this third signal: the French it hunts is two words
#: long and only one of them is ever French vocabulary.
MIN_CONTENT_WORDS_PER_VALUE = 1

#: Word boundaries that also break on `-` and `_`, so `role-doit-pour` in an
#: identifier is three words rather than one unmatched blob, and `value` never
#: matches inside `valuereference`.
_WORD_RX = re.compile(r"[A-Za-z]+")

#: Quoted spans on one line, single or double. Deliberately non-greedy per
#: quote character so `"description": "Boutique en ligne"` yields two values
#: (`description` and `Boutique en ligne`) rather than one blob spanning the
#: colon.
_QUOTED_RX = re.compile(r"'([^']*)'|\"([^\"]*)\"")

#: The value side of a YAML-ish `key: value` line, so that a French default in
#: a plugin template is caught even unquoted — `description: Passerelle
#: applicative` in a `template/**` file reaches users exactly like a quoted one.
#: The key side is allowed to hold copier delimiters, since half the template
#: keys are `[[ name ]]`-shaped.
_YAML_VALUE_RX = re.compile(r"^\s*-?\s*[\w.\[\]{} -]+:[ \t]+(\S.*?)\s*$")

#: A value with no uppercase letter and no whitespace is an identifier, a path,
#: a hostname or a slug — never prose. This is the filter that makes a
#: threshold of one content word safe: it drops `boutique-prod`,
#: `plateforme@example.net`, `helm/charts/boutique/Chart.yaml` and
#: `fins-de-ligne.txt` while keeping `Equipe`, `Boutique en ligne` and
#: `domaine de demonstration`.
_IDENTIFIER_RX = re.compile(r"[^A-Z\s]*")

#: The three signals, by the name they carry in the baseline file.
ACCENT = "accent"
WORDS = "words"
NOUNS = "nouns"
SIGNALS = (ACCENT, WORDS, NOUNS)

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
    #: `ACCENT`, `WORDS` or `NOUNS`.
    signal: str
    #: What fired — the accented letters found, or the French words found.
    evidence: str
    #: The line itself, stripped and truncated for the failure message.
    excerpt: str


def _prose_values(line: str) -> list[str]:
    """The prose-shaped values on one line, as candidate French noun phrases.

    Two places are read — every quoted span, and the value side of a YAML-ish
    `key: value` — and each is kept only if it does not look like an
    identifier. The narrowing is what buys `MIN_CONTENT_WORDS_PER_VALUE = 1`:
    on a whole line, one content word means `"name": "boutique"` and
    `charts/boutique/Chart.yaml` fire; restricted to prose-shaped values, the
    same word list flagged 32 lines on the ZED-69 tree and not one false
    positive.
    """
    # `finditer` rather than `findall`: with two alternative groups `findall`
    # returns `''` for the one that did not match, which is indistinguishable
    # from an empty string literal and would drop every double-quoted value.
    candidates = [
        match.group(1) if match.group(1) is not None else match.group(2)
        for match in _QUOTED_RX.finditer(line)
    ]
    yaml_value = _YAML_VALUE_RX.match(line)
    if yaml_value:
        candidates.append(yaml_value.group(1))
    return [
        value for value in candidates if not _IDENTIFIER_RX.fullmatch(value)
    ]


def _content_words(line: str) -> list[str]:
    """The `CONTENT_WORDS` found in this line's prose-shaped values."""
    found: set[str] = set()
    for value in _prose_values(line):
        found.update(
            word.lower()
            for word in _WORD_RX.findall(value)
            if word.lower() in CONTENT_WORDS
        )
    return sorted(found)


def scan_text(text: str, path: str = "<text>") -> list[Hit]:
    """Run all three signals over one already-decoded string."""
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
        nouns = _content_words(line)
        if len(nouns) >= MIN_CONTENT_WORDS_PER_VALUE:
            hits.append(
                Hit(path, number, NOUNS, " ".join(nouns), _excerpt(line))
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
    """Run all three signals over the whole in-scope tree.

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
