"""Wrapper around the copier calls (DESIGN.md §5).

Rendering and updating **always** go through copier in library mode: forge never
writes a generated file itself. This module concentrates the constraints found
during the spike (MIGRATION.md §2):

* `src_path` = forge repository root + `_subdirectory` (otherwise `copier update`
  fails for lack of a versioned template reference);
* `defaults=True` is mandatory (otherwise an interactive prompt, which breaks
  under Git Bash);
* `unsafe=True` is required as soon as `_jinja_extensions` is declared;
* `vcs_ref="HEAD"` by default, so the render follows the working tree;
* `core.longpaths` forced through environment variables around the call, without
  touching the user's git configuration;
* `_src_path` rewritten before any `update`, because copier records it as an
  absolute path.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import forge
from forge.errors import RenderError

#: Git reference used by default: the working tree, uncommitted templates
#: included (decision DESIGN.md §8 Q8).
DEFAULT_REF = "HEAD"

#: Environment variable forcing the template root (tests, installed usage).
TEMPLATE_SRC_ENV_VAR = "FORGE_TEMPLATE_SRC"

#: Answers file copier writes in every domain directory.
ANSWERS_FILENAME = ".copier-answers.yml"

#: Git setting forced around the copier calls: it neutralises the Windows path
#: length limit inside the temporary clone (MIGRATION.md §2.7).
LONGPATHS_SETTING = ("core.longpaths", "true")


def template_root() -> Path:
    """Root of the template repository, the one carrying the single `copier.yml`."""
    forced = os.environ.get(TEMPLATE_SRC_ENV_VAR)
    if forced:
        root = Path(forced).resolve()
        if not (root / "copier.yml").is_file():
            raise RenderError(
                f"{TEMPLATE_SRC_ENV_VAR}={root} contains no copier.yml"
            )
        return root
    root = Path(forge.__file__).resolve().parents[2]
    if (root / "copier.yml").is_file():
        return root
    raise RenderError(
        "template root not found: forge must be used from its repository, "
        f"or {TEMPLATE_SRC_ENV_VAR} must point at a copy of that repository."
    )


def _git_config_overrides() -> dict[str, str]:
    """Add `core.longpaths` **without erasing** the caller's git configuration.

    `GIT_CONFIG_COUNT` is a shared channel: blindly writing `COUNT=1` and `KEY_0`
    would wipe out the settings the user or the CI put there (safe.directory,
    proxy...). forge's setting is therefore appended at the next free index.
    """
    try:
        base = int(os.environ.get("GIT_CONFIG_COUNT", "0") or 0)
    except ValueError:
        base = 0
    base = max(base, 0)
    key, value = LONGPATHS_SETTING
    return {
        "GIT_CONFIG_COUNT": str(base + 1),
        f"GIT_CONFIG_KEY_{base}": key,
        f"GIT_CONFIG_VALUE_{base}": value,
    }


@contextmanager
def _copier_env(plugin_jinja: str = "") -> Iterator[None]:
    """Install the environment variables the copier calls expect."""
    from forge.jinja_ext import PLUGIN_JINJA_ENV_VAR

    overrides = _git_config_overrides()
    overrides[PLUGIN_JINJA_ENV_VAR] = plugin_jinja
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def build_data(
    *,
    plugin: str,
    template_subdir: str,
    forge_version: int,
    service: dict[str, Any],
    domain: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the five answers declared in the root copier.yml (§5.1)."""
    return {
        "plugin": plugin,
        "template_subdir": template_subdir,
        "forge_version": forge_version,
        "service": service,
        "domain": domain,
    }


def ensure_directory(path: Path, what: str) -> None:
    """Create `path` if needed, translating any system error into `RenderError`."""
    if path.exists() and not path.is_dir():
        raise RenderError(f"invalid {what}: {path} is not a directory")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RenderError(f"cannot create {what} {path}: {exc}") from exc


def _has_content(path: Path) -> bool:
    """True if `path` holds at least one file."""
    return path.is_dir() and any(entry.is_file() for entry in path.rglob("*"))


def _copier_copy(
    *,
    src: Path,
    dst: Path,
    data: dict[str, Any],
    ref: str,
    force: bool,
    pretend: bool,
    plugin_jinja: str,
) -> None:
    """Bare copier call, with no pre-check and no normalisation."""
    from copier import run_copy as copier_run_copy

    with _copier_env(plugin_jinja):
        try:
            copier_run_copy(
                src_path=str(src),
                dst_path=str(dst),
                data=data,
                defaults=True,
                unsafe=True,
                quiet=True,
                overwrite=force,
                pretend=pretend,
                vcs_ref=ref,
            )
        except Exception as exc:  # copier raises varied types depending on the cause
            raise RenderError(f"copier render to {dst} failed: {exc}") from exc


def _refuse_conflicts(
    *,
    src: Path,
    dst: Path,
    data: dict[str, Any],
    ref: str,
    plugin_jinja: str,
) -> None:
    """Refuse to overwrite modified files, with the list and what to do next.

    Without this check copier opens a confirmation prompt; under Git Bash it has
    no console and the user gets an incomprehensible terminal message instead of
    learning that `--force` is what they are missing.
    """
    from forge.render.diff import diff_trees

    with tempfile.TemporaryDirectory(prefix="forge-conflicts-") as tmp:
        fresh = Path(tmp) / dst.name
        ensure_directory(fresh, "temporary directory")
        _copier_copy(
            src=src,
            dst=fresh,
            data=data,
            ref=ref,
            force=True,
            pretend=False,
            plugin_jinja=plugin_jinja,
        )
        normalise_tree(fresh)
        difference = diff_trees(dst.name, dst, fresh)

    if not difference.modified:
        return
    listing = "\n".join(f"    {name}" for name, _ in difference.modified)
    raise RenderError(
        f"{len(difference.modified)} file(s) in {dst} differ from the expected render:\n"
        f"{listing}\n"
        "  rerun with --force to overwrite them, or set your changes aside "
        "(`forge diff` summarises the difference)."
    )


def run_copy(
    *,
    dst: Path,
    data: dict[str, Any],
    src: Path | None = None,
    ref: str = DEFAULT_REF,
    force: bool = False,
    pretend: bool = False,
    plugin_jinja: str = "",
) -> Path:
    """Generate `dst` from the template designated by `data['template_subdir']`."""
    src = src or template_root()
    dst = Path(dst)
    if not force and not pretend and _has_content(dst):
        _refuse_conflicts(src=src, dst=dst, data=data, ref=ref, plugin_jinja=plugin_jinja)
    ensure_directory(dst, "target directory")
    _copier_copy(
        src=src,
        dst=dst,
        data=data,
        ref=ref,
        force=force,
        pretend=pretend,
        plugin_jinja=plugin_jinja,
    )
    if not pretend:
        normalise_tree(dst)
    return dst


def rewrite_src_path(answers_file: Path, src: Path) -> bool:
    """Rewrite the answers file's `_src_path` towards the local template root.

    copier records an absolute path: without this rewrite, a generated project
    would stay tied to the machine that produced it (MIGRATION.md §2.8).

    The rewrite only happens when the recorded path designates **another**
    directory: rewriting an equivalent value would dirty the target repository,
    and copier refuses to update a dirty repository.

    Returns True when the file was actually modified. The caller must then stop
    and ask for a commit: forge never commits into the user's repository, and
    copier cannot update a dirty one.
    """
    if not answers_file.is_file():
        return False
    text = answers_file.read_text(encoding="utf-8")
    current = re.search(r"^_src_path:[ \t]*(.*)$", text, flags=re.MULTILINE)
    if current is not None:
        recorded = current.group(1).strip().strip("\"'")
        try:
            if recorded and Path(recorded).resolve() == Path(src).resolve():
                return False
        except OSError:  # pragma: no cover - invalid path on this machine
            pass
    wanted = src.as_posix()
    new_text = re.sub(
        r"^_src_path:.*$", f"_src_path: {wanted}", text, count=1, flags=re.MULTILINE
    )
    if new_text == text:
        return False
    try:
        answers_file.write_text(new_text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise RenderError(f"cannot write {answers_file}: {exc}") from exc
    return True


def run_update(
    *,
    dst: Path,
    src: Path | None = None,
    ref: str = DEFAULT_REF,
    conflict: str = "inline",
    plugin_jinja: str = "",
) -> Path:
    """Replay `copier update` on an already generated domain."""
    from copier import run_update as copier_run_update

    src = src or template_root()
    dst = Path(dst)
    answers = dst / ANSWERS_FILENAME
    if not answers.is_file():
        raise RenderError(
            f"{dst} has no {ANSWERS_FILENAME}: this directory was not generated by "
            "forge, it cannot be updated."
        )
    if rewrite_src_path(answers, src):
        # The project comes from another machine: copier re-renders the OLD
        # template from the recorded path, so the fix has to be real and
        # committed. forge writes it, then stops: committing in the user's
        # repository on their behalf is not its job.
        raise RenderError(
            f"the template path recorded in {answers} pointed elsewhere; "
            f"it has been corrected to {src}.\n"
            "  commit that change (copier refuses a dirty target repository), "
            "then rerun `forge update`."
        )
    with _copier_env(plugin_jinja):
        try:
            copier_run_update(
                dst_path=str(dst),
                defaults=True,
                unsafe=True,
                quiet=True,
                overwrite=True,
                conflict=conflict,
                vcs_ref=ref,
            )
        except Exception as exc:
            raise RenderError(
                f"copier update of {dst} failed: {exc}\n"
                "  reminder: the update compares two git references. It requires a "
                "committed template — a project rendered from a dirty working tree "
                "references a temporary commit, unreachable afterwards — and a target "
                "repository with no uncommitted change."
            ) from exc
    normalise_tree(dst)
    return dst


# ---------------------------------------------------------------------------
# Output normalisation
# ---------------------------------------------------------------------------

#: Files left untouched: copier's own bookkeeping.
_SKIP_NAMES = frozenset({ANSWERS_FILENAME})


def normalise_text(text: str) -> str:
    """Normalise a rendered file: LF line endings and a single trailing newline.

    **Deliberately minimal.** The two legacy normalisations went further — a
    per-line rstrip (ansible-forge) and collapsing consecutive blank lines
    (helm-forge) — but neither transformation is neutral: in a quoted multi-line
    YAML scalar a blank line encodes a literal newline, and in a `|` block
    trailing spaces are part of the value. Applied blindly after rendering, they
    therefore modified the delivered CONTENT without saying so, and the golden
    references, blessed after normalisation, enshrined the corruption.

    Cleaning up the whitespace left by `[% if %]` blocks is the template's job
    (`trim_blocks` / `lstrip_blocks`, enabled in the root copier.yml), not the
    core's: the core cannot know what, in a file, carries meaning.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n")
    return text + "\n" if text else ""


def normalise_tree(root: Path) -> int:
    """Normalise every text file under `root`; return how many changed."""
    changed = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _SKIP_NAMES:
            continue
        if ".git" in path.parts:
            continue
        try:
            # Read as bytes: `read_text` already translates CRLF to LF, which
            # would blind the normalisation to what it is meant to fix.
            original = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: left as-is
        normalised = normalise_text(original)
        if normalised != original:
            try:
                path.write_text(normalised, encoding="utf-8", newline="\n")
            except OSError as exc:
                raise RenderError(f"cannot write {path}: {exc}") from exc
            changed += 1
    return changed
