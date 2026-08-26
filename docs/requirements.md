# Requirements

This file is intentionally short while UserDock's first feature set is being
defined.

## Agreed scope

- Local Linux users and groups
- User groups and relevant system access groups
- Both TUI and CLI usage
- Multiple Linux distributions, starting with the most widely used families
- Debian and Ubuntu packages first, followed by other package formats
- Future GitHub repository

## Distribution support

UserDock should avoid assuming that every Linux system has Debian-specific
tools or defaults. Support is planned in tiers so that each advertised platform
can be tested honestly.

### Tier 1: initial development and CI

- Debian
- Ubuntu
- Fedora

### Tier 2: same-family compatibility

- Linux Mint and Pop!_OS
- RHEL-compatible systems such as Rocky Linux and AlmaLinux
- Arch Linux
- openSUSE

### Later evaluation

- Alpine Linux
- NixOS
- Other distributions requested by users

The portable core should use standard system interfaces for reading users and
groups. Changes must go through a platform capability layer that detects the
available account-management tools and their behavior. Distribution-specific
defaults, privilege handling, home-directory creation, shells, administrative
groups, and packaging must not leak into the shared domain logic.

UserDock must report unsupported capabilities clearly and must never guess a
mutation command on an unknown platform.

## Account and group boundaries

UserDock classifies groups by purpose and permitted operations rather than by
GID alone. Group classification must use platform capabilities, local account
policy, known group semantics, and conservative fallbacks.

### User groups

Normal user-created groups are visible and fully manageable. Users may create,
rename, delete, and change membership in these groups, subject to the normal
safety checks.

### Access groups

Relevant system groups that grant administrative, device, virtualization,
container, logging, or similar access are shown in a separate protected
category. Examples may include `sudo` or `wheel`, `docker`, `libvirt`, `kvm`,
`dialout`, `audio`, `video`, `render`, `plugdev`, `lpadmin`, `adm`,
`systemd-journal`, `sambashare`, and `wireshark`, when they exist on the host.

UserDock may add or remove members from a recognized access group after showing
the access granted and an appropriate risk warning. It must not rename or
delete these groups. Highly privileged memberships must require explicit
confirmation.

### Internal system groups

Groups owned by services or the operating system are hidden from normal TUI and
CLI listings and are read-only. An explicit diagnostic option may list them,
but UserDock must not modify them.

If a group cannot be classified safely, UserDock must treat it as an internal
read-only group. The interface must explain why a requested operation is not
available.

## Before implementation

Define the first supported operations, privilege model, safety confirmations,
output formats, TUI navigation, platform detection, and the compatibility test
matrix.

## Interaction model

The TUI should minimize keystrokes. Arrow keys are the primary navigation:
up/down moves through records and left/right changes the main section. The
relevant list receives focus automatically.

Editing must not require a separate save command or save screen. A completed
low-risk edit is applied immediately. Destructive operations and changes that
grant or remove highly privileged access still require a concise, explicit
confirmation immediately before execution.

## Login access

User editing must provide an explicit `No login` option. UserDock must detect
the host's supported `nologin` executable, such as `/usr/sbin/nologin` or
`/sbin/nologin`, instead of assuming one fixed path.

`No login` is distinct from locking an account:

- `No login` assigns the supported nologin shell and prevents interactive shell
  sessions.
- `Locked` disables password authentication for the account.

The interface must show these as separate states and must not describe one as
the other. When interactive login is enabled again, the user must select a
valid shell from the host's available login shells; UserDock must not guess
which shell to restore.
