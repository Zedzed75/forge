#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One cell of the CI matrix, inside the container (decision D6).
# ---------------------------------------------------------------------------
# Baked into `forge-ci-matrix` by `Dockerfile.ci-matrix`. It replays the steps
# of `.github/workflows/ci.yml` that happen *after* the toolchain is in place:
# get the sources, install forge from the lockfile against one interpreter,
# install the two tool sets the workflow installs with `uv pip` rather than into
# the image, and run the suite with `FORGE_REQUIRE_TOOLS=1`.
#
# Usage (not meant to be typed by hand -- `scripts/docker-matrix.sh` drives it):
#   docker run --rm -i forge-ci-matrix:<tag> 3.12 < repo.bundle
#
# The sources arrive as a git bundle on stdin rather than a bind mount. Three
# reasons, all of them about fidelity: a bundle carries the full history copier
# needs (the workflow checks out with `fetch-depth: 0`), cloning it yields a
# pristine tree so no host-side edit can leak into the evidence, and it does not
# depend on the host's Docker file sharing -- which on Windows cannot mount a
# mapped network drive, where this repository happens to live.
# ---------------------------------------------------------------------------
set -euo pipefail

PYTHON_VERSION="${1:?usage: run-matrix.sh <python-version> < repo.bundle}"

echo "::group::forge local CI matrix -- Python ${PYTHON_VERSION}"
echo "container: $(. /etc/os-release && echo "${PRETTY_NAME}") ($(uname -m))"
echo "uv:        $(uv --version)"
echo "::endgroup::"

# Reading from a pipe, so write it out before handing it to git: `git clone`
# needs to seek inside the bundle.
cat > /tmp/forge.bundle
# A bundle of a named branch carries that branch and no `HEAD`, so a bare clone
# has nothing to check out. The host script passes the name it bundled;
# `FORGE_MATRIX_BRANCH` is empty only when it bundled `HEAD` itself.
if [ -n "${FORGE_MATRIX_BRANCH:-}" ]; then
  git clone --quiet --branch "${FORGE_MATRIX_BRANCH}" /tmp/forge.bundle /work
else
  git clone --quiet /tmp/forge.bundle /work
fi
cd /work

# What the evidence is actually about. A bundle of a dirty worktree silently
# omits the uncommitted part, so the host script refuses to build one; printing
# the commit here is what lets a reader match a matrix result to a PR head.
echo "commit:    $(git rev-parse HEAD)"
echo "subject:   $(git log -1 --format=%s)"

# `uv sync --locked`, exactly as the workflow does it, and for the same reason:
# `--locked` installs `uv.lock` without resolving anything and fails if the
# lockfile has fallen behind `pyproject.toml`. `--python` is what `setup-uv`'s
# `python-version:` input does per matrix job -- without it the three cells
# would share one interpreter and the matrix would be decoration.
echo "::group::Install forge (Python ${PYTHON_VERSION})"
uv sync --locked --extra dev --python "${PYTHON_VERSION}"
echo "::endgroup::"

# Domain Ansible. These live here and not in the image because they install
# into the project environment, which only exists once `uv sync` has run.
# Versions are pinned identically to the workflow; `--verify-pins` in the host
# script is what keeps the two copies honest.
echo "::group::Install the Ansible domain tools"
uv pip install 'ansible-core==2.19.13' 'ansible-lint==26.9.0'
# galaxy.ansible.com resets the connection when several matrix cells query it at
# once. Three attempts, then fail for real -- the workflow's posture, kept so a
# network hiccup is not readable as a regression of this repository.
ok=
for attempt in 1 2 3; do
  if uv run ansible-galaxy collection install \
       community.general:13.4.0 \
       ansible.posix:2.2.2 \
       community.postgresql:5.0.0 \
       -p "$HOME/.ansible/collections"; then
    ok=1
    break
  fi
  echo "ansible-galaxy failed (attempt ${attempt}/3), retrying in 15 s"
  sleep 15
done
test -n "$ok"
export FORGE_ANSIBLE_COLLECTIONS="$HOME/.ansible/collections"
uv run ansible --version
uv run ansible-lint --version
echo "::endgroup::"

# Domain pipeline's Python half. `actionlint` is in the image; `yamllint` is a
# wheel the workflow puts in the project environment.
echo "::group::Install the pipeline domain tools"
uv pip install 'yamllint==1.38.0'
uv run yamllint --version
echo "::endgroup::"

# `terraform init` downloads providers once per environment root; the workflow
# points them at a shared cache and so does this.
mkdir -p "$HOME/.terraform.d/plugin-cache"
export FORGE_TF_PLUGIN_CACHE="$HOME/.terraform.d/plugin-cache"

echo "::group::Interpreter"
uv run python -c "import sys; print(sys.version)"
echo "::endgroup::"

# The point of the whole exercise. `FORGE_REQUIRE_TOOLS=1` turns a missing
# validator -- and, since the second rule landed, any skip of an `integration`
# test -- from a silent pass into a failure. Without it a container whose
# toolchain had quietly degraded would still go green while asserting nothing
# about the generated projects, which is precisely the evidence D6 claims to
# relocate rather than weaken. `-rs` lists the skips by reason, so "nothing
# skipped" is readable instead of inferred.
export FORGE_REQUIRE_TOOLS=1
echo "::group::Run the test suite (Python ${PYTHON_VERSION})"
uv run pytest -rs
echo "::endgroup::"
