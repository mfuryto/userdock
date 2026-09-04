"""Read-only Samba discovery for the integrated UserDock test interface."""

from __future__ import annotations

import os
import pwd
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SECTION_RE = re.compile(r"^\s*\[([^]]+)]\s*(?:[#;].*)?$")
OPTION_RE = re.compile(r"^\s*([^#;\s][^=]*?)\s*=\s*(.*?)\s*$")


@dataclass(frozen=True, slots=True)
class SambaShare:
    name: str
    path: str
    read_only: bool
    guest_ok: bool
    share_type: str = "Private Share"
    group: str = ""
    policy: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SambaUser:
    name: str
    uid: int | None
    enabled: bool
    home: str


def detect_samba_config() -> Path | None:
    override = os.environ.get("USERDOCK_SAMBA_CONFIG") or os.environ.get(
        "SAMBACTL_CONFIG"
    )
    if override:
        return Path(override).expanduser().resolve()
    for candidate in (Path("/etc/samba/smb.conf"), Path("/usr/local/etc/smb.conf")):
        if candidate.is_file():
            return candidate
    return None


def group_share_policy(group: str) -> dict[str, str]:
    """Return sambactl's collaborative group-share permission policy."""
    return {
        "read only": "no",
        "guest ok": "no",
        "valid users": f"@{group}",
        "force group": group,
        "create mask": "0660",
        "directory mask": "2770",
        "force create mode": "0660",
        "force directory mode": "2770",
    }


def suggest_home_directory(username: str, used: set[str]) -> str:
    """Suggest the first unused conventional home directory."""
    base = Path("/home") / username
    candidate = base
    suffix = 2
    while str(candidate) in used or candidate.exists():
        candidate = Path(f"{base}-{suffix}")
        suffix += 1
    return str(candidate)


def list_samba_shares(path: Path | None = None) -> list[SambaShare]:
    config_path = path or detect_samba_config()
    if config_path is None:
        return []
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in lines:
        if match := SECTION_RE.match(line):
            current = match.group(1).strip()
            sections.setdefault(current, {})
        elif current is not None and (match := OPTION_RE.match(line)):
            sections[current][match.group(1).strip().casefold()] = match.group(2).strip()

    return [
        SambaShare(
            name=name,
            path=options.get("path", "—"),
            read_only=options.get("read only", "yes").casefold()
            not in {"no", "false", "0"},
            guest_ok=options.get("guest ok", "no").casefold()
            in {"yes", "true", "1"},
            share_type=(
                "Group Share"
                if options.get("force group")
                else (
                    "Public Read Only"
                    if options.get("guest ok", "no").casefold()
                    in {"yes", "true", "1"}
                    and options.get("read only", "yes").casefold()
                    not in {"no", "false", "0"}
                    else (
                        "Public Read/Write"
                        if options.get("guest ok", "no").casefold()
                        in {"yes", "true", "1"}
                        else "Private Share"
                    )
                )
            ),
            group=options.get("force group", ""),
            policy=tuple(options.items()),
        )
        for name, options in sections.items()
        if name.casefold() != "global"
    ]


def parse_samba_users(output: str) -> list[SambaUser]:
    users: list[SambaUser] = []
    current: dict[str, str] = {}

    def append_current() -> None:
        name = current.get("Unix username")
        if not name:
            return
        try:
            uid = int(current.get("Unix user ID", ""))
        except ValueError:
            uid = None
        flags = current.get("Account Flags", "").strip("[] ")
        home = current.get("Home Directory", "")
        if not home:
            try:
                home = pwd.getpwnam(name).pw_dir
            except KeyError:
                home = "—"
        users.append(SambaUser(name, uid, "D" not in flags, home))

    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key == "Unix username" and current:
            append_current()
            current = {}
        current[key] = value
    append_current()
    return users


def list_samba_users() -> list[SambaUser]:
    try:
        result = subprocess.run(
            ("pdbedit", "-L", "-v"),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_samba_users(result.stdout) if result.returncode == 0 else []
