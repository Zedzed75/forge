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
import tempfile
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

#: Reglage git force autour des appels copier : il neutralise la limite de
#: longueur de chemin de Windows dans le clone temporaire (MIGRATION.md §2.7).
LONGPATHS_SETTING = ("core.longpaths", "true")


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


def _git_config_overrides() -> dict[str, str]:
    """Ajoute `core.longpaths` **sans effacer** la configuration git de l'appelant.

    `GIT_CONFIG_COUNT` est un canal partage : ecrire aveuglement `COUNT=1` et
    `KEY_0` ferait disparaitre les reglages que l'utilisateur ou la CI y ont
    places (safe.directory, proxy...). Le reglage de forge est donc ajoute a
    l'index libre suivant.
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
    """Installe les variables d'environnement attendues par les appels copier."""
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
    """Assemble les cinq reponses declarees dans le copier.yml racine (§5.1)."""
    return {
        "plugin": plugin,
        "template_subdir": template_subdir,
        "forge_version": forge_version,
        "service": service,
        "domain": domain,
    }


def ensure_directory(path: Path, what: str) -> None:
    """Cree `path` si besoin, en traduisant toute erreur systeme en `RenderError`."""
    if path.exists() and not path.is_dir():
        raise RenderError(f"{what} invalide : {path} n'est pas un repertoire")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RenderError(f"creation impossible de {what} {path} : {exc}") from exc


def _has_content(path: Path) -> bool:
    """Vrai si `path` contient au moins un fichier."""
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
    """Appel copier nu, sans pre-controle ni normalisation."""
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
        except Exception as exc:  # copier leve des types varies selon la cause
            raise RenderError(f"echec du rendu copier vers {dst} : {exc}") from exc


def _refuse_conflicts(
    *,
    src: Path,
    dst: Path,
    data: dict[str, Any],
    ref: str,
    plugin_jinja: str,
) -> None:
    """Refuse d'ecraser des fichiers modifies, avec la liste et la marche a suivre.

    Sans ce controle, copier ouvre un prompt de confirmation ; sous Git Bash il
    n'a pas de console et l'utilisateur recoit un message de terminal
    incomprehensible au lieu d'apprendre qu'il lui manque `--force`.
    """
    from forge.render.diff import diff_trees

    with tempfile.TemporaryDirectory(prefix="forge-conflits-") as tmp:
        fresh = Path(tmp) / dst.name
        ensure_directory(fresh, "repertoire temporaire")
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
        ecart = diff_trees(dst.name, dst, fresh)

    if not ecart.modified:
        return
    listing = "\n".join(f"    {name}" for name, _ in ecart.modified)
    raise RenderError(
        f"{len(ecart.modified)} fichier(s) de {dst} different(s) du rendu attendu :\n"
        f"{listing}\n"
        "  relancez avec --force pour les ecraser, ou mettez vos modifications de "
        "cote (`forge diff` resume l'ecart)."
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
    """Genere `dst` a partir du gabarit designe par `data['template_subdir']`."""
    src = src or template_root()
    dst = Path(dst)
    if not force and not pretend and _has_content(dst):
        _refuse_conflicts(src=src, dst=dst, data=data, ref=ref, plugin_jinja=plugin_jinja)
    ensure_directory(dst, "repertoire cible")
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
    """Reecrit `_src_path` du fichier de reponses vers la racine de gabarit locale.

    copier enregistre un chemin absolu : sans cette reecriture, un projet genere
    resterait lie au poste qui l'a produit (MIGRATION.md §2.8).

    La reecriture n'a lieu que si le chemin enregistre designe **un autre**
    repertoire : recrire une valeur equivalente salirait le depot cible, et
    copier refuse de mettre a jour un depot sale.

    Retourne True si le fichier a effectivement ete modifie. L'appelant doit
    alors s'arreter et demander un commit : forge ne committe jamais dans le
    depot de l'utilisateur, et copier ne peut pas mettre a jour un depot sale.
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
        except OSError:  # pragma: no cover - chemin invalide sur ce poste
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
        raise RenderError(f"ecriture impossible de {answers_file} : {exc}") from exc
    return True


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
    if rewrite_src_path(answers, src):
        # Le projet vient d'un autre poste : copier re-rend le gabarit ANCIEN a
        # partir du chemin enregistre, la correction doit donc etre reelle et
        # committee. forge l'ecrit, puis s'arrete : committer a la place de
        # l'utilisateur dans son depot n'est pas son role.
        raise RenderError(
            f"le chemin de gabarit enregistre dans {answers} pointait ailleurs ; "
            f"il a ete corrige vers {src}.\n"
            "  committez cette modification (copier refuse un depot cible sale), "
            "puis relancez `forge update`."
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


def normalise_text(text: str) -> str:
    """Normalise un fichier rendu : fins de ligne LF et un unique saut final.

    **Volontairement minimal.** Les deux normalisations legacy allaient plus
    loin — rstrip par ligne (ansible-forge) et ecrasement des lignes vides
    consecutives (helm-forge) — mais ces deux transformations ne sont pas
    neutres : dans un scalaire YAML quote sur plusieurs lignes, une ligne vide
    encode un saut de ligne litteral, et dans un bloc `|` les espaces de fin
    font partie de la valeur. Appliquees a l'aveugle apres le rendu, elles
    modifiaient donc le CONTENU livre sans le dire, et les references golden,
    benies apres normalisation, enterinaient la corruption.

    Le nettoyage des blancs laisses par les blocs `[% if %]` releve du gabarit
    (`trim_blocks` / `lstrip_blocks`, actifs dans le copier.yml racine), pas du
    coeur : lui ne peut pas savoir ce qui, dans un fichier, porte du sens.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
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
            # Lecture en octets : `read_text` traduit deja les CRLF en LF, ce qui
            # rendrait la normalisation aveugle a ce qu'elle est censee corriger.
            original = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binaire ou illisible : laisse tel quel
        normalised = normalise_text(original)
        if normalised != original:
            try:
                path.write_text(normalised, encoding="utf-8", newline="\n")
            except OSError as exc:
                raise RenderError(f"ecriture impossible de {path} : {exc}") from exc
            changed += 1
    return changed
