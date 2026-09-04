from types import SimpleNamespace

from sambactl.system.commands import CommandResult

from userdock.samba_live import LiveSambaAdmin


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, args, *, input_text=None, timeout=30):
        self.calls.append((tuple(args), input_text))
        return CommandResult(tuple(args), 0)


class FakeSambaUsers:
    def __init__(self):
        self.calls = []

    def create(self, username, password):
        self.calls.append(("create", username, password))
        return CommandResult(("smbpasswd",), 0)

    def change_password(self, username, password):
        self.calls.append(("change", username, password))
        return CommandResult(("smbpasswd",), 0)


def make_admin():
    admin = LiveSambaAdmin.__new__(LiveSambaAdmin)
    admin.runner = FakeRunner()
    admin.users = FakeSambaUsers()
    return admin


def test_existing_linux_user_gets_same_linux_and_samba_password(monkeypatch):
    monkeypatch.setattr(
        "userdock.samba_live.pwd.getpwnam",
        lambda name: SimpleNamespace(pw_name=name),
    )
    admin = make_admin()
    form = SimpleNamespace(
        name="alice",
        home="/home/alice",
        create_linux=False,
    )

    result = admin.create_user(form, "shared secret")

    assert result.ok
    assert admin.runner.calls == [
        (("chpasswd",), "alice:shared secret\n"),
    ]
    assert admin.users.calls == [("create", "alice", "shared secret")]
    assert all("shared secret" not in args for args, _input in admin.runner.calls)


def test_password_change_updates_both_linux_and_samba():
    admin = make_admin()
    result = admin.set_password("alice", "new shared secret")
    assert result.ok
    assert admin.runner.calls == [
        (("chpasswd",), "alice:new shared secret\n"),
    ]
    assert admin.users.calls == [("change", "alice", "new shared secret")]
