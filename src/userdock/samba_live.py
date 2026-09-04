"""Live Samba mutations backed by sambactl's validated transaction engine."""

from __future__ import annotations

import grp
import pwd
from pathlib import Path

from sambactl.backup import BackupManager
from sambactl.models import OperationResult, ShareFilesystemPlan
from sambactl.paths import backup_directory, detect_smb_conf
from sambactl.samba.config import SambaConfig
from sambactl.samba.service import SambaServiceManager
from sambactl.samba.shares import ShareManager
from sambactl.samba.users import SambaUserManager
from sambactl.samba.validation import Validator
from sambactl.system.commands import CommandRunner
from sambactl.system.filesystem import (
    directory_metadata,
    remove_empty_directory,
    safe_create_directory,
    set_directory_metadata,
)
from sambactl.transaction import ConfigTransaction

from userdock.admin import validate_name
from userdock.samba import group_share_policy


class LiveSambaAdmin:
    def __init__(self) -> None:
        self.runner = CommandRunner()
        self.config_path = detect_smb_conf(self.runner)
        self.services = SambaServiceManager(self.runner)
        self.validator = Validator(self.runner, self.services)
        self.transaction = ConfigTransaction(
            self.config_path,
            BackupManager(self.config_path, backup_directory(self.config_path)),
            self.validator,
            self.services,
        )
        self.users = SambaUserManager(self.runner)

    @staticmethod
    def _detail(result) -> str:
        return result.stderr.strip() or result.stdout.strip() or "Command failed"

    def _share_values(self, result, *, private_user: str = "") -> dict[str, str]:
        if result.share_type == "Group Share":
            values = group_share_policy(result.group)
        else:
            values = {
                "read only": "no" if result.writable else "yes",
                "guest ok": "yes" if result.guest else "no",
            }
        values["path"] = result.path
        if private_user:
            values.update(
                {"read only": "no", "guest ok": "no", "valid users": private_user}
            )
        return values

    def save_share(
        self, original_name: str | None, result, *, private_user: str = ""
    ) -> OperationResult:
        values = self._share_values(result, private_user=private_user)
        path = Path(result.path)
        if not path.is_absolute():
            return OperationResult(False, "An absolute share path is required")
        if private_user:
            try:
                user_entry = pwd.getpwnam(private_user)
                group_entry = grp.getgrgid(user_entry.pw_gid)
            except KeyError:
                return OperationResult(False, f"Linux user {private_user!r} does not exist")
            plan = ShareFilesystemPlan(path, private_user, group_entry.gr_name, 0o0700)
            uid, gid = user_entry.pw_uid, user_entry.pw_gid
        elif result.share_type == "Group Share":
            try:
                group_entry = grp.getgrnam(result.group)
            except KeyError:
                return OperationResult(False, f"Linux group {result.group!r} does not exist")
            plan = ShareFilesystemPlan(path, "root", result.group, 0o2770)
            uid, gid = 0, group_entry.gr_gid
        else:
            plan = ShareFilesystemPlan(path, "root", "root", 0o0755)
            uid, gid = 0, 0

        proposed = SambaConfig.read(self.config_path)
        try:
            if original_name is None:
                ShareManager.create(proposed, result.name, values)
            else:
                ShareManager.update(proposed, original_name, values, result.name)
            report = self.validator.preflight_share(
                self.config_path, proposed.render(), plan, values
            )
        except (OSError, ValueError, KeyError) as exc:
            return OperationResult(False, f"Share validation failed: {exc}")
        if not report.ok:
            failed = "; ".join(
                check.detail for check in report.checks if check.status.value == "FAILED"
            )
            return OperationResult(False, failed or "Share validation failed", report)

        created = False
        metadata = None
        try:
            if path.exists():
                metadata = directory_metadata(path)
                set_directory_metadata(path, uid, gid, plan.mode)
            else:
                safe_create_directory(path, uid, gid, plan.mode)
                created = True
        except OSError as exc:
            return OperationResult(False, f"Could not prepare share directory: {exc}")

        mutation = (
            (lambda config: ShareManager.create(config, result.name, values))
            if original_name is None
            else (
                lambda config: ShareManager.update(
                    config, original_name, values, result.name
                )
            )
        )
        applied = self.transaction.apply(f"Save share [{result.name}]", mutation)
        if not applied.ok:
            try:
                if created:
                    remove_empty_directory(path)
                elif metadata is not None:
                    set_directory_metadata(path, *metadata)
            except OSError:
                applied.message += "; directory metadata rollback failed"
        return applied

    def delete_share(self, name: str) -> OperationResult:
        return self.transaction.apply(
            f"Delete share [{name}]", lambda config: ShareManager.delete(config, name)
        )

    def create_user(self, form, password: str) -> OperationResult:
        username = validate_name(form.name)
        try:
            pwd.getpwnam(username)
            linux_exists = True
        except KeyError:
            linux_exists = False
        created_linux = False
        if not linux_exists:
            if not form.create_linux:
                return OperationResult(False, "A matching Linux user is required")
            requested_home = Path(form.home)
            homes_in_use = {entry.pw_dir for entry in pwd.getpwall()}
            if form.home in homes_in_use or requested_home.exists():
                return OperationResult(False, f"Home directory is already in use: {form.home}")
            command = [
                "useradd",
                "--create-home",
                "--home-dir",
                form.home,
                "--shell",
                "/usr/sbin/nologin",
                "--",
                username,
            ]
            result = self.runner.run(command)
            if not result.ok:
                return OperationResult(False, f"Linux user creation failed: {self._detail(result)}")
            created_linux = True

        linux_password = self.runner.run(
            ("chpasswd",), input_text=f"{username}:{password}\n"
        )
        if not linux_password.ok:
            if created_linux:
                self.runner.run(("userdel", "--remove", "--", username))
            return OperationResult(False, f"Linux password failed: {self._detail(linux_password)}")
        samba_password = self.users.create(username, password)
        if not samba_password.ok:
            return OperationResult(
                False,
                "Samba account creation failed after the Linux password was set: "
                + self._detail(samba_password),
            )
        return OperationResult(True, f"Linux and Samba credentials created for {username}")

    def set_password(self, username: str, password: str) -> OperationResult:
        username = validate_name(username)
        linux_result = self.runner.run(
            ("chpasswd",), input_text=f"{username}:{password}\n"
        )
        if not linux_result.ok:
            return OperationResult(False, f"Linux password failed: {self._detail(linux_result)}")
        samba_result = self.users.change_password(username, password)
        if not samba_result.ok:
            return OperationResult(
                False,
                "Samba password failed after Linux was updated: "
                + self._detail(samba_result),
            )
        return OperationResult(True, f"Linux and Samba passwords changed for {username}")

    def create_existing_user(self, username: str, password: str) -> OperationResult:
        """Create Samba credentials for an existing Linux identity."""
        username = validate_name(username)
        result = self.users.create(username, password)
        return OperationResult(
            result.ok,
            f"Created Samba login for {username}" if result.ok else self._detail(result),
        )

    def set_samba_password(self, username: str, password: str) -> OperationResult:
        """Keep an existing Samba account synchronized with its Linux password."""
        result = self.users.change_password(validate_name(username), password)
        return OperationResult(
            result.ok,
            f"Changed Samba password for {username}" if result.ok else self._detail(result),
        )

    def rename_user(self, old_name: str, new_name: str) -> OperationResult:
        """Rename a Samba identity while preserving its existing NT password hash."""
        old_name = validate_name(old_name)
        new_name = validate_name(new_name)
        current = self.runner.run(("pdbedit", "-L", "-w", "-u", old_name))
        if not current.ok:
            return OperationResult(False, f"Could not read Samba user: {self._detail(current)}")
        line = next((line for line in current.stdout.splitlines() if line.startswith(old_name + ":")), "")
        fields = line.split(":")
        if len(fields) < 5 or not fields[3]:
            return OperationResult(False, "Could not preserve the Samba password during rename")
        nt_hash = fields[3]
        disabled = "D" in fields[4]
        created = self.runner.run(
            ("pdbedit", "-a", "-u", new_name, f"--set-nt-hash={nt_hash}")
        )
        if not created.ok:
            return OperationResult(False, f"Samba rename failed: {self._detail(created)}")
        removed = self.users.delete(old_name)
        if not removed.ok:
            self.users.delete(new_name)
            return OperationResult(False, f"Samba rename rollback: {self._detail(removed)}")
        if disabled:
            self.users.disable(new_name)
        return OperationResult(True, f"Renamed Samba user {old_name} to {new_name}")

    def set_user_enabled(self, username: str, enabled: bool) -> OperationResult:
        result = self.users.enable(username) if enabled else self.users.disable(username)
        return OperationResult(result.ok, self._detail(result) if not result.ok else "Updated")

    def delete_user(self, username: str) -> OperationResult:
        result = self.users.delete(validate_name(username))
        return OperationResult(
            result.ok,
            self._detail(result) if not result.ok else f"Deleted Samba user {username}",
        )
