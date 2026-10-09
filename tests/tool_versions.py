"""Expected version of every `integration` validator.

Comments in this module are in English, for the same reason as in
`tests/test_fail_closed_tools.py`: new test infrastructure, no French
precedent, and no effect on generated output.

`FORGE_REQUIRE_TOOLS=1` proves that a validator binary answered. It does not
prove it is the binary the pins asked for, and those are two different claims.
The chain as it stood was: `.github/workflows/ci.yml` **requests** pinned
versions, each install step **prints** whatever answered, and
`require_tools` **asserts** only that something answered. Nothing compared the
print to the request, and a printed version nobody compares is a comment in a
log nobody reads.

That gap is not hypothetical. A pin protects against a version moving under a
stable request; it does not protect against the request resolving to something
else. `get-helm-3` is a shell script fetched from `main` and handed
`--version v3.16.3`: a changed tarball member layout, or a fallback path inside
that script, can land *a* helm on PATH and still exit 0. A future base image
that preinstalls one of these nine under an earlier PATH directory ends the
same way. In both cases the suite is green, the validators ran, and what they
proved is not what the pins say.

So this table is the comparison. It is read by `tests/conftest.py::require_tools`
under the same flag and with the same posture as the presence check: the
Windows development loop, where several of these cannot run natively at all, is
left exactly as it was.

The third declaration
---------------------
These numbers already live in `.github/workflows/ci.yml` and in
`scripts/docker/{Dockerfile.ci-matrix,run-matrix.sh}`. This is a *third* copy,
and the comment heading `verify_pins` in `scripts/docker-matrix.sh` already says
the quiet part -- "a second declaration rots". A third one rots faster, so
`./scripts/docker-matrix.sh --verify-pins-only` requires every version below to
appear verbatim in the workflow *and* in the container files. One bump breaks
all three or none.
"""

from __future__ import annotations

from typing import NamedTuple


class ExpectedVersion(NamedTuple):
    """What one validator must report, and how to ask it."""

    #: Substring that the reported version line must contain, or None for a
    #: tool pinned nowhere (see `UNPINNED` below). A **substring**, never an
    #: equality: `helm version --short` answers `v3.16.3+g<sha>` and the sha
    #: changes per build, `ansible-lint --version` answers a four-field banner,
    #: `tflint --version` answers `TFLint version 0.59.1`. An equality check
    #: would pass today only because nobody tried it, and would be wrong on the
    #: next bump -- the worst moment to discover the comparison was shaped for
    #: one tool's output format.
    version: str | None

    #: Arguments that make the tool print its version. The default is what
    #: `forge.validate.tools.probe` already uses, and it is wrong for exactly
    #: two of the nine: `helm --version` answers `Error: unknown flag` and
    #: `kubeconform --version` answers `flag provided but not defined`, both on
    #: stderr and both with the version nowhere in sight. Those two get the
    #: arguments the workflow's own install step uses.
    args: tuple[str, ...] = ("--version",)


#: Marker for a tool that no file pins, kept as a readable name rather than a
#: bare None at the call site. No row uses it today -- all nine validators are
#: pinned -- and it exists so that the day one is not, the table says so out
#: loud. A tool silently absent from this table would be the same hole one
#: level up: an unasserted tool in the file whose job is asserting. That is why
#: `require_tools` fails on a name it cannot find here, instead of passing it.
UNPINNED = None


#: Every validator a shipped plugin declares, by binary name.
#:
#: `tests/test_fail_closed_tools.py` asserts that this set is exactly the set of
#: `tool=` values across `src/forge/plugins/*/validators.py`, so a sixth domain
#: cannot add a validator without adding its row here.
EXPECTED_VERSIONS: dict[str, ExpectedVersion] = {
    # Domain ansible. Pinned as `ansible-core==2.19.13`; the binary reports
    # `ansible-playbook [core 2.19.13]`.
    "ansible-playbook": ExpectedVersion("2.19.13"),
    # `ansible-lint 26.9.0 using ansible-core:2.19.13 ansible-compat:... ruamel-yaml:...`
    "ansible-lint": ExpectedVersion("26.9.0"),
    # Domain helm. `helm version --short` -> `v3.16.3+gcfd0749`: the build sha
    # is why this is a substring match and not an equality.
    "helm": ExpectedVersion("3.16.3", ("version", "--short")),
    # `kubeconform -v` -> `v0.6.7`. `-v` and not `--version`, as in CI.
    "kubeconform": ExpectedVersion("0.6.7", ("-v",)),
    # Domain terraform. `Terraform v1.9.8`, then a platform line.
    "terraform": ExpectedVersion("1.9.8"),
    # `TFLint version 0.59.1`, then the bundled ruleset.
    "tflint": ExpectedVersion("0.59.1"),
    # Domain monitoring. promtool ships inside the prometheus archive, pinned
    # there as 3.6.0; it reports `promtool, version 3.6.0 (branch: ...)`.
    "promtool": ExpectedVersion("3.6.0"),
    # Domain pipeline. actionlint prints the bare number on its first line.
    "actionlint": ExpectedVersion("1.7.7"),
    # `yamllint 1.38.0`.
    "yamllint": ExpectedVersion("1.38.0"),
}
