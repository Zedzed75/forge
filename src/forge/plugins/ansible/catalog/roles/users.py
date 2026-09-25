"""Definition of the ``users`` role: local accounts, sudo and SSH keys."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

USER_FIELDS = (
    RoleOption(
        name="name",
        question="Account name",
        description="Login name of the local account.",
        allowed="1 to 32 characters, lowercase letters, digits, '_' or '-'.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="groups",
        question="Secondary groups (comma-separated)",
        description="Secondary groups the account is added to.",
        allowed="List of group names, existing or created elsewhere.",
        default=[],
        kind=OptionKind.LIST,
    ),
    RoleOption(
        name="sudo",
        question="Passwordless sudo access?",
        description="Adds a NOPASSWD sudoers rule for this account.",
        allowed="true or false.",
        default=False,
        kind=OptionKind.BOOL,
    ),
    RoleOption(
        name="shell",
        question="Login shell",
        description="Shell assigned to the account.",
        allowed="Absolute path to a shell listed in /etc/shells.",
        default="/bin/bash",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="ssh_public_key",
        question="Authorised SSH public key (empty for none)",
        description="Public key installed in ~/.ssh/authorized_keys.",
        allowed="Complete OpenSSH public key, or an empty string.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="state",
        question="State of the account",
        description="Presence or removal of the account on the machine.",
        allowed="present or absent.",
        default="present",
        kind=OptionKind.CHOICE,
        choices=("present", "absent"),
    ),
)

ROLE = RoleDefinition(
    name="users",
    summary="Local accounts: creation, secondary groups, sudo and authorised SSH keys.",
    collections=("ansible.posix",),
    handlers=(),
    tags=("users", "security"),
    options=(
        RoleOption(
            name="accounts",
            question="Accounts to manage",
            description="List of the local accounts managed by the role.",
            allowed="List of dictionaries (name, groups, sudo, shell, ssh_public_key, state).",
            default=[],
            kind=OptionKind.RECORDS,
            fields=USER_FIELDS,
        ),
        RoleOption(
            name="manage_sudoers",
            question="Deploy the sudoers rules?",
            description="Writes a file in /etc/sudoers.d for the accounts marked sudo.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="remove_absent_home",
            question="Remove the home directory of 'absent' accounts?",
            description="Removes /home/<user> when the account moves to the absent state.",
            allowed="true or false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
    ),
)
