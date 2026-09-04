# Changelog

## 1.1.1 - 2026-09-04

- Verified optional Samba behavior in clean Ubuntu build environments
- Fixed the release test setup when Samba is not installed

## 1.1.0 - 2026-09-04

- Integrated optional Samba account controls directly into the Users view
- Added live Samba share administration without requiring Samba to be installed
- Reused sambactl validation, backup, reload, and rollback for share changes
- Added collaborative group-share permissions and optional private user shares
- Synchronized Linux and Samba passwords through protected standard input
- Added safe username, home-directory, Samba-account, and private-share renaming
- Removed private Samba shares when their Linux user and home are deleted
- Added new users to the `users` group when that group exists
- Disabled controls that do not apply to the active view

## 1.0.7 - 2026-08-26

- Added a Login Yes/No column to the user list
- Recognized common `nologin` and `false` shell paths across distributions

## 1.0.6 - 2026-08-26

- Added secure password setting and password confirmation for regular users
- Added an option to require a password change at the next login
- Opened password setup automatically after successful user creation
- Added `d` as a Mac-friendly delete shortcut while retaining the Delete key

## 1.0.5 - 2026-08-26

- Made the user form vertically scrollable on short terminal screens
- Made the additional-groups list independently scrollable for many groups
- Moved nologin into the login-shell selector
- Replaced the home-directory checkbox with a clear create/do-not-create selector

## 1.0.4 - 2026-08-26

- Fixed the nologin checkbox overlapping the additional-groups list
- Added a small-terminal regression test that rejects overlapping controls

## 1.0.3 - 2026-08-26

- Added a native AMD64 Debian package for Ubuntu 22.04 LTS and newer
- Installed the packaged command system-wide in `/usr/bin`
- Added Debian package metadata and a `userdock(1)` manual page

## 1.0.2 - 2026-08-26

- Changed user creation and editing to a full-screen terminal view
- Kept login shell, nologin, supplementary groups, and actions visible in an
  80×20 terminal

## 1.0.1 - 2026-08-26

- Restored compatibility with Python 3.10
- Built the standalone Linux binary on Ubuntu 22.04 LTS
- Added a release workflow that keeps future Linux binaries compatible with
  Jammy and newer glibc-based distributions
- Added Ubuntu 22.04 and Python 3.10 to continuous integration

## 1.0.0 - 2026-08-26

- Terminal interface for local Linux users and groups
- Arrow-key navigation designed for small terminal windows
- User creation, editing, locking, unlocking, and deletion
- Optional nologin shell and supplementary group membership
- Group creation, renaming, membership management, and deletion
- Protected access-group handling and read-only internal system groups
- Conservative distribution and account-policy detection
- Administrator-only execution and guarded home-directory removal
- Script-friendly read-only CLI commands
