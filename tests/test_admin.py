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


def test_refuses_unsafe_home_removal():
    admin = RootAdmin(recorder([]))
    with pytest.raises(AdminError, match="unsafe home"):
        admin.delete_user("alice", remove_home=True, home="/home")


def test_user_commands_include_supplementary_groups():
    commands: list[tuple[str, ...]] = []
    admin = RootAdmin(recorder(commands))
    admin.create_user(
        "alice", "Alice Example", "/bin/bash", True, ("developers", "video")
    )
    admin.update_user("alice", "Alice Example", "/bin/bash", ("developers",))
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
