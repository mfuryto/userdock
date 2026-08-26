"""Read-only access to local users and groups."""

import grp
import pwd
from collections.abc import Iterable

from userdock.models import GroupCategory, LocalGroup, LocalUser, PlatformInfo

ACCESS_GROUPS = frozenset({
    "adm", "audio", "cdrom", "dialout", "dip", "docker", "input", "kvm",
    "libvirt", "lpadmin", "lxd", "netdev", "optical", "plugdev", "podman",
    "render", "sambashare", "scanner", "storage", "sudo", "systemd-journal",
    "vboxusers", "video", "wheel", "wireshark",
})


def classify_group(name: str, gid: int, platform: PlatformInfo) -> GroupCategory:
    if name in ACCESS_GROUPS:
        return GroupCategory.ACCESS
    if (
        platform.user_gid_min is not None
        and gid >= platform.user_gid_min
        and (platform.user_gid_max is None or gid <= platform.user_gid_max)
    ):
        return GroupCategory.USER
    return GroupCategory.INTERNAL


def list_groups(
    platform: PlatformInfo, entries: Iterable[grp.struct_group] | None = None
) -> list[LocalGroup]:
    source = grp.getgrall() if entries is None else entries
    groups = [
        LocalGroup(entry.gr_name, entry.gr_gid, tuple(sorted(entry.gr_mem)),
                   classify_group(entry.gr_name, entry.gr_gid, platform))
        for entry in source
    ]
    return sorted(groups, key=lambda group: (group.category, group.name))


def list_users(
    platform: PlatformInfo,
    user_entries: Iterable[pwd.struct_passwd] | None = None,
    group_entries: Iterable[grp.struct_group] | None = None,
) -> list[LocalUser]:
    users_source = list(pwd.getpwall() if user_entries is None else user_entries)
    groups_source = list(grp.getgrall() if group_entries is None else group_entries)
    memberships: dict[str, set[str]] = {entry.pw_name: set() for entry in users_source}
    primary_names = {entry.gr_gid: entry.gr_name for entry in groups_source}
    for user in users_source:
        if primary := primary_names.get(user.pw_gid):
            memberships[user.pw_name].add(primary)
    for group in groups_source:
        for member in group.gr_mem:
            if member in memberships:
                memberships[member].add(group.gr_name)
    uid_min = platform.user_uid_min
    uid_max = platform.user_uid_max
    return sorted(
        (LocalUser(
            entry.pw_name, entry.pw_gecos.split(",", 1)[0], entry.pw_uid,
            entry.pw_gid, primary_names.get(entry.pw_gid), entry.pw_dir,
            entry.pw_shell, tuple(sorted(memberships[entry.pw_name])),
            uid_min is None
            or entry.pw_uid < uid_min
            or (uid_max is not None and entry.pw_uid > uid_max),
        ) for entry in users_source),
        key=lambda user: user.name,
    )


def get_user(name: str, platform: PlatformInfo) -> LocalUser | None:
    return next((user for user in list_users(platform) if user.name == name), None)
