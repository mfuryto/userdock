import subprocess

import pytest

from userdock.admin import AccountAdmin, AdminError, validate_name


class RootAdmin(AccountAdmin):
    @property
    def can_change(self) -> bool:
        return True


def recorder(commands: list[tuple[str, ...]]):
    def run(command):
        commands.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    return run


def test_rejects_unsafe_names():
    with pytest.raises(AdminError):
        validate_name("bad;name")


def test_group_commands_are_argument_lists():
    commands: list[tuple[str, ...]] = []
    admin = RootAdmin(recorder(commands))
    admin.create_group("developers")
    admin.rename_group("developers", "engineering")
    admin.delete_group("engineering")
    assert commands == [
        ("groupadd", "--", "developers"),
        ("groupmod", "--new-name", "engineering", "--", "developers"),
        ("groupdel", "--", "engineering"),
    ]


def test_user_lock_and_delete_commands():
    commands: list[tuple[str, ...]] = []
    admin = RootAdmin(recorder(commands))
    admin.set_locked("alice", True)
    admin.set_locked("alice", False)
    admin.delete_user("alice", remove_home=True, home="/home/alice")
    assert commands == [
        ("usermod", "--lock", "--", "alice"),
        ("usermod", "--unlock", "--", "alice"),
        ("userdel", "--remove", "--", "alice"),
    ]


def test_password_is_sent_only_through_standard_input():
    commands: list[tuple[str, ...]] = []
    secret_calls: list[tuple[tuple[str, ...], str]] = []

    def run_secret(command, secret_input):
        secret_calls.append((tuple(command), secret_input))
        return subprocess.CompletedProcess(command, 0, "", "")

    admin = RootAdmin(recorder(commands), run_secret)
    admin.set_password("alice", "correct horse battery staple", True)

    assert secret_calls == [
        (("chpasswd",), "alice:correct horse battery staple\n")
    ]
    assert commands == [("chage", "--lastday", "0", "--", "alice")]
    assert all("correct horse" not in argument for command in commands for argument in command)


def test_password_cannot_be_empty():
    admin = RootAdmin(recorder([]))
    with pytest.raises(AdminError, match="cannot be empty"):
        admin.set_password("alice", "")


def test_refuses_unsafe_home_removal():
    admin = RootAdmin(recorder([]))
    with pytest.raises(AdminError, match="unsafe home"):
        admin.delete_user("alice", remove_home=True, home="/home")


def test_user_commands_include_supplementary_groups(monkeypatch):
    monkeypatch.setattr("userdock.admin.grp.getgrnam", lambda name: (_ for _ in ()).throw(KeyError(name)))
    commands: list[tuple[str, ...]] = []
    admin = RootAdmin(recorder(commands))
    admin.create_user(
        "alice", "Alice Example", "/bin/bash", True, ("developers", "video")
    )
    admin.update_user(
        "alice", "alice", "Alice Example", "/bin/bash", ("developers",), "/home/alice"
    )
    assert commands == [
        (
            "useradd",
            "--comment",
            "Alice Example",
            "--shell",
            "/bin/bash",
            "--groups",
            "developers,video",
            "--create-home",
            "--",
            "alice",
        ),
        (
            "usermod",
            "--comment",
            "Alice Example",
            "--shell",
            "/bin/bash",
            "--groups",
            "developers",
            "--",
            "alice",
        ),
    ]
