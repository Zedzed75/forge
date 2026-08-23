"""Enveloppe des appels copier (DESIGN.md §5).

Le rendu et la mise a jour passent **toujours** par copier en mode bibliotheque :
forge n'ecrit jamais un fichier genere lui-meme. Ce module concentre les
contraintes decouvertes pendant le spike (MIGRATION.md §2) :

* `src_path` = racine du depot forge + `_subdirectory` (sinon `copier update`
  echoue faute de reference de gabarit versionnee) ;
* `defaults=True` obligatoire (sinon prompt interactif, qui casse sous Git Bash) ;
* `unsafe=True` requis des qu'on declare `_jinja_extensions` ;
* `vcs_ref="HEAD"` par defaut, pour que le rendu suive l'arbre de travail ;
* `core.longpaths` force par variables d'environnement autour de l'appel, sans
  toucher a la configuration git de l'utilisateur ;
* `_src_path` reecrit avant tout `update`, car copier l'enregistre en absolu.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import forge
from forge.errors import RenderError

#: Reference git utilisee par defaut : l'arbre de travail, gabarits non
#: committes compris (decision DESIGN.md §8 Q8).
DEFAULT_REF = "HEAD"

#: Variable d'environnement forcant la racine de gabarit (tests, usage installe).
TEMPLATE_SRC_ENV_VAR = "FORGE_TEMPLATE_SRC"

#: Fichier de reponses ecrit par copier dans chaque repertoire de domaine.
ANSWERS_FILENAME = ".copier-answers.yml"

#: Variables d'environnement neutralisant la limite de chemin de Windows dans le
#: clone temporaire de copier (MIGRATION.md §2.7).
_LONGPATHS_ENV = {
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "core.longpaths",
    "GIT_CONFIG_VALUE_0": "true",
}


def template_root() -> Path:
    """Racine du depot de gabarit, celle qui porte le `copier.yml` unique."""
    forced = os.environ.get(TEMPLATE_SRC_ENV_VAR)
    if forced:
        root = Path(forced).resolve()
        if not (root / "copier.yml").is_file():
            raise RenderError(
                f"{TEMPLATE_SRC_ENV_VAR}={root} ne contient pas de copier.yml"
            )
        return root
    root = Path(forge.__file__).resolve().parents[2]
    if (root / "copier.yml").is_file():
        return root
    raise RenderError(
        "racine de gabarit introuvable : forge doit etre utilise depuis son depot, "
        f"ou {TEMPLATE_SRC_ENV_VAR} doit designer une copie de ce depot."
    )


@contextmanager
def _copier_env(plugin_jinja: str = "") -> Iterator[None]:
    """Installe les variables d'environnement attendues par les appels copier."""
    from forge.jinja_ext import PLUGIN_JINJA_ENV_VAR

    overrides = dict(_LONGPATHS_ENV)
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
    """Assemble les cinq reponses declarees dans le copier.yml racine (§5.1)."""
    return {
        "plugin": plugin,
        "template_subdir": template_subdir,
        "forge_version": forge_version,
        "service": service,
        "domain": domain,
    }


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
    """Genere `dst` a partir du gabarit designe par `data['template_subdir']`."""
    from copier import run_copy as copier_run_copy

    src = src or template_root()
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
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
        except Exception as exc:  # copier leve des types varies selon la cause
            raise RenderError(f"echec du rendu copier vers {dst} : {exc}") from exc
    if not pretend:
        normalise_tree(dst)
    return dst


def rewrite_src_path(answers_file: Path, src: Path) -> None:
    """Reecrit `_src_path` du fichier de reponses vers la racine de gabarit locale.

    copier enregistre un chemin absolu : sans cette reecriture, un projet genere
    resterait lie au poste qui l'a produit (MIGRATION.md §2.8).

    La reecriture n'a lieu que si le chemin enregistre designe **un autre**
    repertoire : recrire une valeur equivalente salirait le depot cible, et
    copier refuse de mettre a jour un depot sale.
    """
    if not answers_file.is_file():
        return
    text = answers_file.read_text(encoding="utf-8")
    current = re.search(r"^_src_path:[ \t]*(.*)$", text, flags=re.MULTILINE)
    if current is not None:
        recorded = current.group(1).strip().strip("\"'")
        try:
            if recorded and Path(recorded).resolve() == Path(src).resolve():
                return
        except OSError:  # pragma: no cover - chemin invalide sur ce poste
            pass
    wanted = src.as_posix()
    new_text = re.sub(
        r"^_src_path:.*$", f"_src_path: {wanted}", text, count=1, flags=re.MULTILINE
    )
    if new_text != text:
        answers_file.write_text(new_text, encoding="utf-8", newline="\n")


def run_update(
    *,
    dst: Path,
    src: Path | None = None,
    ref: str = DEFAULT_REF,
    conflict: str = "inline",
    plugin_jinja: str = "",
) -> Path:
    """Rejoue `copier update` sur un domaine deja genere."""
    from copier import run_update as copier_run_update

    src = src or template_root()
    dst = Path(dst)
    answers = dst / ANSWERS_FILENAME
    if not answers.is_file():
        raise RenderError(
            f"{dst} n'a pas de {ANSWERS_FILENAME} : ce repertoire n'a pas ete genere "
            "par forge, la mise a jour est impossible."
        )
    rewrite_src_path(answers, src)
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
                f"echec de la mise a jour copier de {dst} : {exc}\n"
                "  rappel : la mise a jour compare deux references git. Elle exige un "
                "gabarit committe — un projet rendu depuis un arbre de travail sale "
                "reference un commit temporaire, introuvable ensuite — et un depot "
                "cible sans modification non committee."
            ) from exc
    normalise_tree(dst)
    return dst


# ---------------------------------------------------------------------------
# Normalisation de sortie
# ---------------------------------------------------------------------------

#: Fichiers laisses intacts : ecriture interne de copier.
_SKIP_NAMES = frozenset({ANSWERS_FILENAME})

_BLANK_RUN_RE = re.compile(r"\n{3,}")


def normalise_text(text: str) -> str:
    """Normalise un fichier rendu : LF, pas d'espace en fin de ligne, un saut final.

    Union des deux normalisations legacy (MIGRATION.md §5.6) : helm gerait les
    CRLF et les lignes vides multiples, ansible le rstrip par ligne.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _BLANK_RUN_RE.sub("\n\n", text)
    text = text.rstrip("\n")
    return text + "\n" if text else ""


def normalise_tree(root: Path) -> int:
    """Normalise tous les fichiers texte de `root` ; retourne le nombre modifie."""
    changed = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _SKIP_NAMES:
            continue
        if ".git" in path.parts:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binaire ou illisible : laisse tel quel
        normalised = normalise_text(original)
        if normalised != original:
            path.write_text(normalised, encoding="utf-8", newline="\n")
            changed += 1
    return changed
