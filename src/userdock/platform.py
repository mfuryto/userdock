"""Conservative Linux platform and account-policy detection."""

import os
import shlex
from pathlib import Path

from userdock.models import PlatformInfo

_DISTRO_FAMILIES = {
    "debian": "debian", "ubuntu": "debian", "linuxmint": "debian",
    "pop": "debian", "fedora": "fedora", "rhel": "fedora",
    "rocky": "fedora", "almalinux": "fedora", "centos": "fedora",
    "arch": "arch", "manjaro": "arch", "opensuse-leap": "suse",
    "opensuse-tumbleweed": "suse", "sles": "suse", "alpine": "alpine",
    "nixos": "nixos",
}


def _read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        try:
            parts = shlex.split(raw_value, comments=True)
        except ValueError:
            continue
        values[key.strip()] = parts[0] if parts else ""
    return values


def _read_login_defs(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw_line in lines:
        fields = raw_line.split("#", 1)[0].split()
        if len(fields) < 2 or fields[0] not in {
            "UID_MIN", "UID_MAX", "GID_MIN", "GID_MAX"
        }:
            continue
        try:
            values[fields[0]] = int(fields[1])
        except ValueError:
            continue
    return values


def detect_platform(
    os_release: Path = Path("/etc/os-release"),
    login_defs: Path = Path("/etc/login.defs"),
) -> PlatformInfo:
    release = _read_key_values(os_release)
    policy = _read_login_defs(login_defs)
    distro_id = release.get("ID", "unknown").lower()
    id_like = release.get("ID_LIKE", "").lower().split()
    family = _DISTRO_FAMILIES.get(distro_id)
    if family is None:
        family = next(
            (_DISTRO_FAMILIES[item] for item in id_like if item in _DISTRO_FAMILIES),
            "unknown",
        )
    return PlatformInfo(
        distro_id=distro_id,
        distro_name=release.get("PRETTY_NAME", distro_id),
        distro_family=family,
        user_gid_min=policy.get("GID_MIN"),
        user_uid_min=policy.get("UID_MIN"),
        user_gid_max=policy.get("GID_MAX"),
        user_uid_max=policy.get("UID_MAX"),
    )


def is_linux() -> bool:
    return os.name == "posix" and Path("/proc").is_dir()
