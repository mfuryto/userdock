# UserDock

UserDock 1.0 is a terminal interface and CLI for managing local Linux users and
groups. It is designed for fast keyboard operation and conservative handling
of privileged access.

The 1.0 release is built on Ubuntu 22.04 LTS and targets Jammy and newer
Debian-compatible systems on x86-64.
The account core also detects Fedora/RHEL, Arch, SUSE, Alpine, and NixOS
families, but these platforms are not advertised as verified until their test
matrices and native packages are complete.

## Features

- Create, edit, lock, unlock, and delete local users
- Select login shells or disable interactive login with `nologin`
- Assign supplementary groups while creating or editing users
- Create, rename, manage membership in, and delete user groups
- Protect privileged access groups and hide internal system groups by default
- Preserve hidden group membership during user edits
- Guard removal of home directories and validate all account names
- Navigate with arrow keys in small terminal windows
- Inspect the host through script-friendly CLI commands

## Administrator access

UserDock intentionally requires effective root privileges for every run. It is
never installed setuid. Start it with:

```bash
sudo userdock
```

## Install on Debian or Ubuntu

Download `userdock_1.0.3_amd64.deb` from the GitHub release, then install it
with APT:

```bash
sudo rm -f /usr/local/bin/userdock  # only when replacing the old standalone install
sudo apt install ./userdock_1.0.3_amd64.deb
sudo userdock
```

APT registers the package and can later remove it with
`sudo apt remove userdock`. UserDock still requires administrator privileges
when it runs. The first command removes only the older manually installed
standalone copy; omit it on a new installation.

## Install the standalone Linux release

Download `userdock-linux-x86_64` from the GitHub release, then install it for
root-only execution:

```bash
sudo install -o root -g root -m 0750 userdock-linux-x86_64 /usr/local/bin/userdock
sudo userdock
```

The standalone x86-64 binary contains its Python runtime and dependencies.

## Keyboard controls

- `↑` / `↓`: move through records and form choices
- `←` / `→`: change the main section
- `n`: create a user or group
- `e`: edit the selected user or group
- `Enter`: manage membership in the selected group
- `Space`: toggle a selection or group membership
- `l`: lock or unlock the selected user
- `Delete`: delete the selected editable record
- `s`: show or hide internal system entries
- `r`: refresh account data
- `q`: quit

## CLI

```bash
sudo userdock system doctor
sudo userdock users list
sudo userdock users show USERNAME
sudo userdock groups list
```

## Development

UserDock requires Python 3.10 or newer.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Project layout

```text
src/userdock/   Application package
tests/          Automated tests
docs/           Requirements and design notes
scripts/        Release build and installation helpers
```

Security issues should be reported privately as described in `SECURITY.md`.
