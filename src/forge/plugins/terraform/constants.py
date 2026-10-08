"""Terraform domain constants: caps and backend requirements."""

from __future__ import annotations

import re
from typing import Final

#: Maximum length of a Kubernetes namespace name (RFC 1123, a DNS label).
MAX_NAMESPACE_LENGTH: Final[int] = 63

#: Version constraint accepted for `required_version`. Terraform accepts a list
#: of constraints separated by commas; a bare version (`1.9.8`) is valid but
#: freezes the project on one precise patch, which the model refuses: it is
#: almost always a typo.
VERSION_CONSTRAINT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:~>|>=|<=|>|<|=|!=)\s*\d+(?:\.\d+){0,2}"
    r"(?:\s*,\s*(?:~>|>=|<=|>|<|=|!=)\s*\d+(?:\.\d+){0,2})*\s*$"
)

#: Keys each backend type cannot do without. Terraform only asks for them at
#: `init`, that is to say long after generation: requiring them here avoids a
#: project that renders perfectly and refuses to initialise.
#:
#: The `local` backend requires nothing: `path` has a default value. The `key`
#: and `prefix` keys do not appear there either: they are **derived per
#: environment** (cf. `derive_env._state_key`), so that two roots never write the
#: same state.
REQUIRED_BACKEND_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "local": (),
    "s3": ("bucket", "region"),
    "gcs": ("bucket",),
    "azurerm": ("resource_group_name", "storage_account_name", "container_name"),
    "http": ("address",),
}

#: Backend keys never to write into a generated file: they carry a secret.
#: Terraform accepts them through `-backend-config` or through an environment
#: variable, which is the only admissible form.
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

#: Name of the default local state file.
DEFAULT_STATE_FILE: Final[str] = "terraform.tfstate"
