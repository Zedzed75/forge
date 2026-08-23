"""Comparaison entre une cible existante et un rendu neuf (DESIGN.md §5.5).

`pretend` n'ecrit rien du tout, il est donc inutilisable ici : forge rend dans un
repertoire temporaire puis compare les arborescences. La sortie est un **resume**
— fichiers ajoutes / supprimes / modifies et nombre de lignes changees — jamais
un diff integral (regle d'economie de contexte de CLAUDE.md).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

#: Fichiers ignores par la comparaison : ecriture interne de copier, dont le
#: `_commit` change a chaque rendu.
IGNORED_NAMES = frozenset({".copier-answers.yml"})


@dataclass
class DomainDiff:
    """Ecart constate sur un domaine."""

    domain: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[tuple[str, int]] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        """Vrai si la cible correspond exactement au rendu neuf."""
        return not (self.added or self.removed or self.modified)

    def summary(self) -> str:
        """Resume d'une ligne, sans citer le contenu des fichiers."""
        if self.empty:
            return f"{self.domain} : a jour"
        return (
            f"{self.domain} : {len(self.added)} ajout(s), "
            f"{len(self.removed)} suppression(s), {len(self.modified)} modification(s)"
        )


def _relative_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.name in IGNORED_NAMES:
            continue
        files[path.relative_to(root).as_posix()] = path
    return files


def _changed_lines(left: Path, right: Path) -> int:
    """Nombre de lignes differentes entre deux fichiers ; -1 si binaire."""
    try:
        a = left.read_text(encoding="utf-8").splitlines()
        b = right.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return -1
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    changed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changed += max(i2 - i1, j2 - j1)
    return changed


def diff_trees(domain: str, current: Path, fresh: Path) -> DomainDiff:
    """Compare la cible `current` au rendu neuf `fresh`.

    « ajoute » signifie : present dans le rendu neuf, absent de la cible.
    """
    result = DomainDiff(domain=domain)
    current_files = _relative_files(current)
    fresh_files = _relative_files(fresh)

    for name in sorted(set(fresh_files) - set(current_files)):
        result.added.append(name)
    for name in sorted(set(current_files) - set(fresh_files)):
        result.removed.append(name)
    for name in sorted(set(current_files) & set(fresh_files)):
        left, right = current_files[name], fresh_files[name]
        if left.read_bytes() == right.read_bytes():
            continue
        result.modified.append((name, _changed_lines(left, right)))
    return result
