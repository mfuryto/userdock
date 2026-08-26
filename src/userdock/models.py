"""Domain models used by both the CLI and the future TUI."""

from dataclasses import dataclass
from enum import Enum


class GroupCategory(str, Enum):
    USER = "user"
    ACCESS = "access"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class LocalUser:
    name: str
    full_name: str
    uid: int
    primary_gid: int
    primary_group: str | None
    home: str
    shell: str
    groups: tuple[str, ...]
    is_system: bool


@dataclass(frozen=True, slots=True)
class LocalGroup:
    name: str
    gid: int
    members: tuple[str, ...]
    category: GroupCategory


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    distro_id: str
    distro_name: str
    distro_family: str
    user_gid_min: int | None
    user_uid_min: int | None
    user_gid_max: int | None = None
    user_uid_max: int | None = None
