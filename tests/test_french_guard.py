"""The gate: no new French in `src/`, in the plugin templates, or in `tests/`.

Two kinds of test live here, and they fail for different reasons.

*The detector tests* pin the design decisions of `french_guard.py` on real
bytes: that `—` is not an accent, that `role` alone is not French, that the
PromQL `le=` label is not an article, and — since ZED-69 — that `"owner":
"Equipe Plateforme"` is French while `helm/charts/boutique/Chart.yaml` is not.
They are the part that would have stopped the scan which once reported 74
phantom problems in `helm`.

*The ratchet tests* compare the tree against `french_baseline.txt`. Its
`[baseline]` section is empty — `src/forge/` and the plugin templates measure
clean — so today these simply fail on the next French line. The ratchet
machinery is still exercised, because it is what a widening of the scope will
need: they also fail when a baseline entry is *larger* than the tree needs, so
an entry cannot quietly rot into a permanent amnesty.

The blind-spot tests are the third kind, and they are assertions *that nothing
fires*. They exist because ZED-69 found 32 French lines the gate called clean,
and the lesson was not "add a signal" but "write down what the signals cannot
see". Deleting one of those tests because it looks like a tautology would undo
that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.french_guard import (
    ACCENT,
    ACCENTED_LETTERS,
    CONTENT_WORDS,
    FUNCTION_WORDS,
    MIN_CONTENT_WORDS_PER_VALUE,
    MIN_WORDS_PER_LINE,
    NOUNS,
    REJECTED_CONTENT_WORDS,
    REJECTED_WORDS,
    REPO_ROOT,
    WORDS,
    BaselineError,
    counts_by_file,
    load_baseline,
    scan_text,
    scan_tree,
    scanned_files,
)

#: How many offending lines a failure message quotes before it gives up. A
#: full dump of a first run would be 300 lines of noise.
_MAX_QUOTED = 12

#: The 32 French values ZED-69 measured on the pre-ZED-60 tree, kept verbatim
#: outside this module so that a `.py` file of French fixtures does not need an
#: allowlist entry of its own. See the file's own header.
_PRE_ZED60_FIXTURE = Path(__file__).with_name("french_values_pre_zed60.txt")


def _signals(text: str) -> set[str]:
    return {hit.signal for hit in scan_text(text)}


def _pre_zed60_lines() -> list[tuple[str, str]]:
    """`(origin, line)` for each French value recorded in the fixture file."""
    rows = []
    for raw in _PRE_ZED60_FIXTURE.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        origin, _, line = raw.partition("|")
        rows.append((origin, line))
    return rows


# ---------------------------------------------------------------------------
# The detector: what must fire
# ---------------------------------------------------------------------------


def test_accented_french_fires():
    assert ACCENT in _signals("#: Consommation CPU d'un pod, en cœurs.")


def test_two_function_words_fire():
    line = "Retourne un Issue de niveau error par environnement inconnu, dans"
    assert WORDS in _signals(line)


def test_unaccented_french_prose_fires():
    """The accent signal alone would miss this; half the tree is written so."""
    line = "presentes, pour qu'un gabarit ne puisse jamais referencer une clef"
    assert _signals(line) == {WORDS}


@pytest.mark.parametrize(
    "line",
    [
        'name=f"Déployer {nom}",',
        '"""Définitions des rôles du catalogue, un module par rôle."""',
        "# Pas du compteur : la derivee vaut (seuil + 1) cœurs.",
        "f\"Champ(s) inconnu(s) dans '{label}' : {', '.join(unknown)}. \"",
    ],
)
def test_real_french_lines_from_the_tree_fire(line):
    """Lines taken verbatim from `src/`, one per signal and one for both."""
    assert _signals(line)


@pytest.mark.parametrize(
    ("label", "line"),
    [
        # The two shapes that motivated the signal: one function word, and none.
        ("one function word", '            "description": "Boutique en ligne",'),
        ("no function word", '            "owner": "Equipe Plateforme",'),
        # A single-word value. `words` cannot reach this at any threshold.
        ("one word", '            "owner": "Equipe",'),
        ("keyword argument", '        description="Passerelle applicative",'),
        ("positional", '    "gateways", "Passerelles exposees", ["common"], False,'),
        ("nested dict", '                "description": "Service sans domaine",'),
        ("lowercase phrase", '    summary="domaine de demonstration",'),
        # Unquoted, the way a French default would reach a plugin template.
        ("yaml value", "description: Passerelle applicative"),
        ("yaml list item", "  - owner: Equipe Plateforme"),
    ],
)
def test_short_french_noun_phrases_fire(label, line):
    """The gap ZED-69 closed, one case per shape it takes in the tree."""
    assert NOUNS in _signals(line), label


@pytest.mark.parametrize(("origin", "line"), _pre_zed60_lines())
def test_every_pre_zed60_french_value_fires(origin, line):
    """The acceptance criterion, on the blobs at the ZED-60 merge base.

    Each of these was reported clean by `accent` and `words` together, which is
    the measurement that opened ZED-69 — so this asserts both halves: the new
    signal fires, and it is genuinely new information rather than a third
    reading of something already caught.
    """
    assert _signals(line) == {NOUNS}, origin


def test_the_fixture_still_holds_what_it_claims():
    """A fixture that silently emptied would make the test above pass on nothing."""
    rows = _pre_zed60_lines()
    assert len(rows) == 32
    assert len({origin for origin, _ in rows}) == 32
    assert len({path.split(":")[0] for path, _ in rows}) == 10


def test_a_double_quoted_value_is_not_dropped():
    """Pins a regex trap: `findall` on two alternative groups returns `''`.

    `_prose_values` has to use `finditer`, because with `findall` the
    non-matching group of `'(...)'|"(...)"` comes back as an empty string
    rather than `None` — indistinguishable from `""` — and picking the first
    group would silently skip every double-quoted value in the repository.
    """
    assert NOUNS in _signals('"Equipe Plateforme"')
    assert NOUNS in _signals("'Equipe Plateforme'")


def test_the_blind_spot_is_known():
    """Two signals are not a language detector, and should not be mistaken for one.

    De-accent that same docstring and every word left — `des`, `roles`, `la`,
    `par`, `un` — is on the rejected list, so neither signal fires. That is the
    price of zero false positives, and the reason this guard is a ratchet
    against *new* French rather than a proof that none remains. A reviewer is
    still the one who reads the prose.
    """
    assert not _signals(
        '"""Definitions des roles du catalogue, un module par role."""'
    )


def test_the_value_blind_spots_are_known():
    """What the third signal still cannot see, so "empty baseline" stays honest.

    ZED-69 added `nouns` because 32 French values were invisible. These are the
    ones that remain invisible after it, and they are listed rather than fixed
    because each would cost more in false positives than it buys:

    * a French value that is *only* an identifier has no prose shape to read;
    * a content word spelled the same in English is on
      `REJECTED_CONTENT_WORDS`, so a phrase built only from those is clean;
    * every signal is line-oriented, so a content word broken by an implicit
      concatenation falls between two clean lines.
    """
    # `test_spec.py`'s invalid-name fixture. Caught by nothing: `boutique` is
    # rejected, and the value is a single token.
    assert not _signals('    spec_data["service"]["name"] = "Boutique_Web"')
    # French, but every content word in it is also English.
    assert not _signals('            "description": "Service de demonstration",')
    # `Passerelle` split in half: neither fragment is a word in any list. The
    # phrase on one line fires, which is why this gap is narrow rather than
    # absent -- it takes a concatenation through the middle of a noun.
    assert not _signals('    description=("Passe"\n        "relle applicative"),')


# ---------------------------------------------------------------------------
# The detector: what must not fire
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "line"),
    [
        # `git grep '[éèê…]'` in the C locale matches all three of these,
        # because they share UTF-8 lead bytes with the accented letters. That
        # is the single reason this module decodes before it matches.
        ("em dash", "Version read in src/forge/__init__.py — a single source."),
        ("section sign", "Harness taken from ansible-forge (MIGRATION.md §3)."),
        ("box drawing", "# " + "─" * 70),
        # The 75 candidate lines a naive word list flagged across the five
        # ZED-24 branches. Every one was English.
        ("ansible noun", "    roles = [role for role in catalog if role.enabled]"),
        ("module states", '    state = "present" if enabled else "absent"'),
        ("preposition", "# Depends on the section the user asked for, plus one"),
        ("promql bucket", 'histogram_quantile(0.99, sum(rate(d_bucket[5m])) by (le))'),
        ("identifier", "    value = section.get('role') or present_default"),
    ],
)
def test_english_lines_are_clean(label, line):
    assert not _signals(line), label


@pytest.mark.parametrize(
    ("label", "line"),
    [
        # `boutique`, `passerelle` and `plateforme` are the fixture service
        # names. Every one of these lines is real, taken from the tree, and
        # every one would fire if the content words were read off whole lines
        # instead of out of prose-shaped values -- 60-odd false positives, in
        # files nobody is translating. Renaming them is ZED-59's job.
        ("spec key", '            "name": "boutique",'),
        ("hostname", '            "owner_email": "plateforme@example.net",'),
        ("chart path", '    templates = tmp_path / "helm" / "charts" / "boutique"'),
        ("namespace slug", '        environments={"dev": {"namespace": "boutique-dev"}},'),
        ("kube context", "    assert prod[\"kube_context\"] == '\"plateforme-prod-eu-west-3\"'"),
        ("helm helper", '        \'include "boutique.api.labels"\','),
        ("format placeholder", '    assert f\'key = "boutique/{name}/terraform.tfstate"\' in content'),
        # A French *file name*, which ZED-23 renames. A path is not prose, so
        # the signal must leave it to ZED-23 rather than double-reporting it.
        ("french file name", '    CRLF_WITNESS = "fins-de-ligne.txt"'),
        # Shout filters and banners: uppercase and spaces, so not
        # identifier-shaped -- they stay clean because `boutique` is on
        # `REJECTED_CONTENT_WORDS`, not because of the shape filter.
        ("shout filter", '    assert "BOUTIQUE" in readme'),
        ("demo banner", '    assert "== boutique ==" in readme'),
        # English values of exactly the shape the signal reads.
        ("english value", '            "description": "Online shop",'),
        ("english owner", '            "owner": "Platform Team",'),
        ("english yaml", "description: Application gateway"),
    ],
)
def test_identifiers_and_english_values_are_clean(label, line):
    assert NOUNS not in _signals(line), label


def test_content_words_are_disjoint_from_the_other_lists():
    """Three lists, no term in two of them, or a hit would be double-reported."""
    assert not (CONTENT_WORDS & FUNCTION_WORDS)
    assert not (CONTENT_WORDS & REJECTED_WORDS)
    assert not (CONTENT_WORDS & REJECTED_CONTENT_WORDS)


def test_one_content_word_is_the_threshold():
    """Stated, because it is the one place this guard allows a single word."""
    assert MIN_CONTENT_WORDS_PER_VALUE == 1
    assert MIN_WORDS_PER_LINE == 2


def test_em_dash_is_not_an_accent():
    """Stated on its own, because it is the trap this guard exists to avoid."""
    for sign in "—§─":
        assert sign not in ACCENTED_LETTERS


def test_one_function_word_is_not_enough():
    """`pour` on its own appears in `pour`-prefixed identifiers and in nothing."""
    assert WORDS not in _signals("# TODO pour review")
    assert MIN_WORDS_PER_LINE == 2


def test_rejected_words_are_kept_out_of_the_signal():
    """The two lists must not overlap, or a rejected word would gate CI."""
    assert not (FUNCTION_WORDS & REJECTED_WORDS)


# ---------------------------------------------------------------------------
# The detector: scope
# ---------------------------------------------------------------------------


def _write(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_french_added_to_a_source_file_is_caught(tmp_path):
    """The acceptance criterion, on a tree built for the purpose."""
    _write(tmp_path, "src/forge/plugins/x/derive.py", '"""Rendu du gabarit."""\n')
    assert [hit.path for hit in scan_tree(tmp_path)] == [
        "src/forge/plugins/x/derive.py"
    ]


def test_french_added_to_a_template_is_caught(tmp_path):
    """Templates of any extension: what they hold is shipped to users."""
    _write(
        tmp_path,
        "src/forge/plugins/x/template/values.yaml.jinja",
        "# Valeur appliquée pour chaque environnement\n",
    )
    hits = scan_tree(tmp_path)
    assert {hit.signal for hit in hits} == {ACCENT, WORDS}


def test_out_of_scope_french_is_left_alone(tmp_path):
    """`CLAUDE.md` keeps these French on purpose; the guard must not argue."""
    _write(tmp_path, "DESIGN.md", "Decision Q1 : les delimiteurs pour chaque gabarit\n")
    _write(tmp_path, ".github/workflows/ci.yml", "# Chaine de validation, par domaine\n")
    _write(tmp_path, "src/forge/plugins/x/README.md", "Gabarit rendu pour chaque cas\n")
    assert scan_tree(tmp_path) == []


def test_undecodable_files_do_not_break_the_scan(tmp_path):
    """A binary fixture under `template/` is not French, and must not raise."""
    target = tmp_path / "src/forge/plugins/x/template/logo.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xff")
    assert scan_tree(tmp_path) == []


def test_the_scan_actually_reaches_the_tree():
    """A glob typo would make every ratchet test below pass vacuously."""
    scanned = {path.name for path in scanned_files()}
    assert "derive.py" in scanned
    assert "conftest.py" in scanned
    assert len(scanned) > 100


# ---------------------------------------------------------------------------
# The baseline file
# ---------------------------------------------------------------------------


def test_every_baseline_entry_carries_a_justification():
    baseline = load_baseline()
    missing = [
        key
        for key, note in list(baseline.notes.items()) + list(baseline.allowed.items())
        if not note
    ]
    assert not missing, f"entries with an empty justification: {missing}"


def test_baseline_paths_still_exist():
    """An entry for a deleted file is an amnesty nobody is watching."""
    baseline = load_baseline()
    gone = sorted(
        {
            path
            for path, _ in list(baseline.limits) + list(baseline.allowed)
            if not (REPO_ROOT / path).is_file()
        }
    )
    assert not gone, f"baseline entries whose file is gone: {gone}"


def test_a_zero_count_is_rejected(tmp_path):
    """Reaching zero means deleting the entry, not writing `0`."""
    data = tmp_path / "baseline.txt"
    data.write_text("[baseline]\nwords | 0 | src/x.py | note\n", encoding="utf-8")
    with pytest.raises(BaselineError, match="positive"):
        load_baseline(data)


def test_a_path_containing_spaces_survives_parsing(tmp_path):
    """Copier template paths contain spaces; a whitespace parser loses them."""
    data = tmp_path / "baseline.txt"
    path = "src/forge/plugins/demo/template/[[ _copier_conf.answers_file ]].jinja"
    data.write_text(f"[baseline]\nwords | 3 | {path} | ZED-19\n", encoding="utf-8")
    assert load_baseline(data).limits == {(path, WORDS): 3}


# ---------------------------------------------------------------------------
# The ratchet
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def measured():
    """The tree, measured once: 61 files is enough work to not repeat it."""
    hits = scan_tree()
    return hits, counts_by_file(hits)


def test_no_french_outside_the_baseline(measured):
    """Fails on French in a file the baseline does not already list."""
    hits, counts = measured
    baseline = load_baseline()
    unknown = sorted(key for key in counts if not baseline.tolerated(key))
    quoted = [
        f"  {hit.path}:{hit.line} [{hit.signal}: {hit.evidence}] {hit.excerpt}"
        for hit in hits
        if (hit.path, hit.signal) in set(unknown)
    ]
    assert not unknown, (
        "French in files the baseline does not cover. This tree is English-first "
        "(CLAUDE.md: identifiers, keys and file names in English; src/ and "
        "tests/ prose too since ZED-10). Translate the lines — do not add them "
        "to tests/french_baseline.txt, which only ever shrinks.\n"
        + "\n".join(quoted[:_MAX_QUOTED])
        + (f"\n  ... and {len(quoted) - _MAX_QUOTED} more" if len(quoted) > _MAX_QUOTED else "")
    )


def test_no_baseline_entry_has_grown(measured):
    """Fails on French added to a file that already had some."""
    _, counts = measured
    baseline = load_baseline()
    grown = [
        f"  {signal} in {path}: baseline allows {limit}, tree has "
        f"{counts.get((path, signal), 0)}"
        for (path, signal), limit in sorted(baseline.limits.items())
        if counts.get((path, signal), 0) > limit
    ]
    assert not grown, (
        "more French than the baseline allows — new French in a file that was "
        "already on the way out:\n" + "\n".join(grown)
    )


def test_the_baseline_is_not_ahead_of_the_tree(measured):
    """The good-news failure: translation happened, so lower the numbers.

    Without this the file would still claim 38 French lines in a catalogue
    translated months ago, and `ZED-54 empties it` would have no way to be
    checked.
    """
    _, counts = measured
    baseline = load_baseline()
    stale = []
    for (path, signal), limit in sorted(baseline.limits.items()):
        actual = counts.get((path, signal), 0)
        if actual < limit:
            action = "delete the entry" if actual == 0 else f"lower it to {actual}"
            stale.append(f"  {signal} | {limit} | {path}  ->  {action}")
    assert not stale, (
        "tests/french_baseline.txt is behind the tree. Translation progressed, "
        "which is the point — record it:\n" + "\n".join(stale)
    )


def test_every_allowlist_entry_is_still_needed(measured):
    """A permanent exemption with nothing left to exempt is dead weight."""
    _, counts = measured
    baseline = load_baseline()
    dead = sorted(key for key in baseline.allowed if key not in counts)
    assert not dead, f"[allowed] entries that no longer match anything: {dead}"
