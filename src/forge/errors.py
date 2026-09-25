"""Error hierarchy shared by the core and the plugins.

Merge of the two legacy hierarchies (`ansible_forge.errors` and
`helm_forge.errors`, cf. MIGRATION.md §5.1): a single implementation survives.

Every expected error derives from `ForgeError`: the CLI catches it and prints
`str(e)` with no Python traceback. An exception that does not derive from it is
a bug.
"""

from __future__ import annotations


class ForgeError(Exception):
    """An expected error, presentable to the user as it is."""


class SpecFileError(ForgeError):
    """The specification file is missing, unreadable or malformed."""


class SpecValidationError(ForgeError):
    """The specification content violates the assembled model."""


class PluginError(ForgeError):
    """A plugin is misdeclared, missing, or violates the hook contract."""


class RenderError(ForgeError):
    """The copier render failed."""


# Two classes were removed in phase 10, after checking that no code path raised
# them:
#
# * `ToolMissingError` — `forge.validate.tools.missing_message()` composes the
#   same message, and the core reports a missing tool through a validation
#   report, never through an exception: one skipped command does not interrupt
#   the others.
# * `ValidationFailed` — `ValidationResult.ok` carries the verdict and the CLI
#   derives its exit code from it. Raising would have lost the report, which is
#   precisely what the user wants to read.
