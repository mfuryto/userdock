"""Command-line entry point for UserDock's read-only foundation."""

import argparse
import os
import shutil
import sys
from collections.abc import Sequence

from userdock import __version__
from userdock.accounts import get_user, list_groups, list_users
from userdock.models import GroupCategory
from userdock.platform import detect_platform, is_linux


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="userdock",
        description="Manage local Linux users and groups.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command")

    system = commands.add_parser("system", help="Inspect platform support")
    system.add_subparsers(dest="system_command", required=True).add_parser(
        "doctor", help="Check platform capabilities"
    )

    users = commands.add_parser("users", help="Inspect local users")
    user_commands = users.add_subparsers(dest="users_command", required=True)
    users_list = user_commands.add_parser("list", help="List local users")
    users_list.add_argument(
        "--system", action="store_true", help="Include system users"
    )
    users_show = user_commands.add_parser("show", help="Show one local user")
    users_show.add_argument("name")

    groups = commands.add_parser("groups", help="Inspect local groups")
    group_commands = groups.add_subparsers(dest="groups_command", required=True)
    groups_list = group_commands.add_parser("list", help="List local groups")
    groups_list.add_argument(
        "--system", action="store_true", help="Include internal system groups"
    )
    return parser


def _doctor() -> int:
    platform = detect_platform()
    print(f"Linux: {'yes' if is_linux() else 'no'}")
    print(f"Distribution: {platform.distro_name}")
    print(f"Family: {platform.distro_family}")
    print(f"UID_MIN: {platform.user_uid_min or 'unknown'}")
    print(f"UID_MAX: {platform.user_uid_max or 'unknown'}")
    print(f"GID_MIN: {platform.user_gid_min or 'unknown'}")
    print(f"GID_MAX: {platform.user_gid_max or 'unknown'}")
    tools = ("useradd", "usermod", "userdel", "groupadd", "groupmod", "groupdel")
    print("Account tools: " + ", ".join(tool for tool in tools if shutil.which(tool)))
    ready = is_linux() and platform.distro_family != "unknown"
    print(f"Read-only support: {'ready' if ready else 'limited'}")
    print("Changes: disabled")
    return 0 if ready else 1


def _users_list(include_system: bool) -> int:
    print("NAME\tUID\tTYPE\tGROUPS")
    for user in list_users(detect_platform()):
        if user.is_system and not include_system:
            continue
        kind = "system" if user.is_system else "user"
        print(f"{user.name}\t{user.uid}\t{kind}\t{','.join(user.groups)}")
    return 0


def _users_show(name: str) -> int:
    user = get_user(name, detect_platform())
    if user is None:
        print(f"User not found: {name}")
        return 2
    print(f"Name: {user.name}")
    print(f"UID: {user.uid}")
    print(f"Type: {'system' if user.is_system else 'user'}")
    print(f"Primary GID: {user.primary_gid}")
    print(f"Home: {user.home}")
    print(f"Shell: {user.shell}")
    print(f"Groups: {', '.join(user.groups) or '-'}")
    return 0


def _groups_list(include_system: bool) -> int:
    print("NAME\tGID\tCATEGORY\tMEMBERS")
    for group in list_groups(detect_platform()):
        if group.category is GroupCategory.INTERNAL and not include_system:
            continue
        print(
            f"{group.name}\t{group.gid}\t{group.category.value}\t"
            f"{','.join(group.members)}"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        print(
            "UserDock requires administrator privileges. Run: sudo userdock",
            file=sys.stderr,
        )
        return 1
    if args.command is None:
        from userdock.tui import run_tui

        run_tui()
        return 0
    if args.command == "system":
        return _doctor()
    if args.command == "users" and args.users_command == "list":
        return _users_list(args.system)
    if args.command == "users" and args.users_command == "show":
        return _users_show(args.name)
    if args.command == "groups" and args.groups_command == "list":
        return _groups_list(args.system)
    parser.error("unsupported command")
    return 2
