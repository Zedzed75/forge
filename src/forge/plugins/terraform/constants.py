"""Constantes du domaine Terraform : plafonds et exigences des backends."""

from __future__ import annotations

import re
from typing import Final

#: Longueur maximale d'un nom de namespace Kubernetes (RFC 1123, label DNS).
MAX_NAMESPACE_LENGTH: Final[int] = 63

#: Contrainte de version acceptee pour `required_version`. Terraform accepte une
#: liste de contraintes separees par des virgules ; une version nue (`1.9.8`)
#: est valide mais fige le projet sur un correctif precis, ce que le modele
#: refuse : c'est presque toujours une erreur de saisie.
VERSION_CONSTRAINT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:~>|>=|<=|>|<|=|!=)\s*\d+(?:\.\d+){0,2}"
    r"(?:\s*,\s*(?:~>|>=|<=|>|<|=|!=)\s*\d+(?:\.\d+){0,2})*\s*$"
)

#: Cles indispensables a chaque type de backend. Terraform ne les reclame qu'au
#: `init`, c'est-a-dire longtemps apres la generation : les exiger ici evite un
#: projet qui se rend parfaitement et refuse de s'initialiser.
#:
#: Le backend `local` n'exige rien : `path` a une valeur par defaut. Les cles
#: `key` et `prefix` n'y figurent pas non plus : elles sont **derivees par
#: environnement** (cf. `derive_env._state_key`), pour que deux racines
#: n'ecrivent jamais le meme etat.
REQUIRED_BACKEND_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "local": (),
    "s3": ("bucket", "region"),
    "gcs": ("bucket",),
    "azurerm": ("resource_group_name", "storage_account_name", "container_name"),
    "http": ("address",),
}

#: Cles de backend a ne jamais ecrire dans un fichier genere : elles portent un
#: secret. Terraform les accepte par `-backend-config` ou par variable
#: d'environnement, ce qui est la seule forme admissible.
SECRET_BACKEND_KEYS: Final[frozenset[str]] = frozenset(
    {
        "access_key",
        "secret_key",
        "token",
        "password",
        "sas_token",
        "client_secret",
        "credentials",
    }
)

#: Nom du fichier d'etat local par defaut.
DEFAULT_STATE_FILE: Final[str] = "terraform.tfstate"
