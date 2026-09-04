"""Validated system mutations for local users and groups."""

import grp
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]{0,30}\$?$", re.ASCII)
CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
SecretCommandRunner = Callable[[Sequence[str], str], subprocess.CompletedProcess[str]]


class AdminError(RuntimeError):
    """A safe, user-facing account administration error."""


def validate_name(name: str) -> str:
    if not NAME_PATTERN.fullmatch(name):
        raise AdminError(
            "Names must start with a lowercase letter or underscore and contain "
            "only lowercase letters, numbers, underscores, or hyphens."
        )
    return name


def available_shells(path: Path = Path("/etc/shells")) -> tuple[str, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    return tuple(
        line.strip()
        for line in lines
        if line.strip().startswith("/") and not line.lstrip().startswith("#")
    )


def detect_nologin() -> str | None:
    for candidate in ("/usr/sbin/nologin", "/sbin/nologin"):
        if Path(candidate).is_file():
            return candidate
    return None


def validate_home_removal(username: str, home: str) -> None:
    path = Path(home)
    protected = {Path("/"), Path("/home"), Path("/root"), Path("/var"), Path("/srv")}
    if (
        not path.is_absolute()
        or path in protected
        or path.name != username
        or path.parent == Path("/")
    ):
        raise AdminError(f"Refusing to remove unsafe home directory: {home}")


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _run_secret(
    command: Sequence[str], secret_input: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        input=secret_input,
    )


@dataclass(slots=True)
class AccountAdmin:
    """Execute narrowly scoped account tools; the TUI never constructs commands."""

    runner: CommandRunner = _run
    secret_runner: SecretCommandRunner = _run_secret

    @property
    def can_change(self) -> bool:
        return os.geteuid() == 0

    def _execute(self, command: Sequence[str]) -> None:
        if not self.can_change:
            raise AdminError("Administrator access is required to make changes.")
        result = self.runner(tuple(command))
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or "Command failed"
            raise AdminError(message)

    def create_group(self, name: str) -> None:
        self._execute(("groupadd", "--", validate_name(name)))

    def rename_group(self, old_name: str, new_name: str) -> None:
        self._execute(
            ("groupmod", "--new-name", validate_name(new_name), "--", validate_name(old_name))
        )

    def delete_group(self, name: str) -> None:
        self._execute(("groupdel", "--", validate_name(name)))

    def create_user(
        self,
        name: str,
        full_name: str,
        shell: str,
        create_home: bool = True,
        supplementary_groups: Sequence[str] = (),
    ) -> None:
        if shell not in available_shells() and shell != detect_nologin():
            raise AdminError("Select a shell supported by this host.")
        command = ["useradd", "--comment", full_name, "--shell", shell]
        requested_groups = list(supplementary_groups)
        try:
            grp.getgrnam("users")
        except KeyError:
            pass
        else:
            if "users" not in requested_groups:
                requested_groups.append("users")
        if requested_groups:
            groups = ",".join(validate_name(group) for group in requested_groups)
            command.extend(("--groups", groups))
        command.append("--create-home" if create_home else "--no-create-home")
        command.extend(("--", validate_name(name)))
        self._execute(command)

    def update_user(
        self,
        old_name: str,
        new_name: str,
        full_name: str,
        shell: str,
        supplementary_groups: Sequence[str],
        old_home: str,
    ) -> None:
        if shell not in available_shells() and shell != detect_nologin():
            raise AdminError("Select a shell supported by this host.")
        groups = ",".join(validate_name(group) for group in supplementary_groups)
        old_name = validate_name(old_name)
        new_name = validate_name(new_name)
        command = ["usermod", "--comment", full_name, "--shell", shell,
                   "--groups", groups]
        if new_name != old_name:
            command.extend(("--login", new_name))
            if Path(old_home) == Path("/home") / old_name:
                command.extend(("--home", str(Path("/home") / new_name), "--move-home"))
        command.extend(("--", old_name))
        self._execute(command)

    def set_locked(self, name: str, locked: bool) -> None:
        option = "--lock" if locked else "--unlock"
        self._execute(("usermod", option, "--", validate_name(name)))

    def set_password(
        self, name: str, password: str, expire_on_next_login: bool = False
    ) -> None:
        username = validate_name(name)
        if not password:
            raise AdminError("Password cannot be empty.")
        if not self.can_change:
            raise AdminError("Administrator access is required to make changes.")
        result = self.secret_runner(("chpasswd",), f"{username}:{password}\n")
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or "Command failed"
            raise AdminError(message)
        if expire_on_next_login:
            self._execute(("chage", "--lastday", "0", "--", username))

    def delete_user(
        self, name: str, remove_home: bool = False, home: str | None = None
    ) -> None:
        command = ["userdel"]
        if remove_home:
            if home is None:
                raise AdminError("The home directory must be verified before removal.")
            validate_home_removal(name, home)
            command.append("--remove")
        command.extend(("--", validate_name(name)))
        self._execute(command)

    def set_group_member(self, user: str, group: str, member: bool) -> None:
        option = "--add" if member else "--delete"
        self._execute(
            ("gpasswd", option, validate_name(user), "--", validate_name(group))
        )
