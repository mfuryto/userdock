import asyncio
from pathlib import Path

from textual.containers import VerticalScroll
from textual.widgets import Button, Select, SelectionList

from userdock.samba import parse_samba_users
from userdock.screens import (
    ConfirmDialog,
    PasswordDialog,
    SambaShareDialog,
    UserDialog,
    UserFormResult,
)
from userdock.tui import UserDockApp


def test_tui_starts_in_read_only_mode():
    async def run() -> None:
        app = UserDockApp()
        async with app.run_test() as pilot:
            status = app.query_one("#status-line")
            assert "Read-only mode" in str(status.renderable)
            assert len(app.query_one("#users-table").columns) == 6
            assert len(app.query_one("#samba-shares-table").columns) == 6
            assert not app.query("#samba-users-table")
            assert app.show_system is False
            await pilot.press("s")
            assert app.show_system is True
            await pilot.press("right")
            assert app.query_one("TabbedContent").active == "groups-tab"
            assert app.query_one("#groups-table").has_focus

    asyncio.run(run())


def test_delete_has_mac_friendly_shortcut():
    delete_keys = {
        binding.key
        for binding in UserDockApp.BINDINGS
        if binding.action == "delete_record"
    }
    assert delete_keys == {"d", "delete"}


def test_user_dialog_fits_small_terminal():
    async def run() -> None:
        app = UserDockApp()
        async with app.run_test(size=(80, 16)) as pilot:
            app.push_screen(
                UserDialog(
                    "Edit user",
                    ("/bin/bash", "/bin/sh"),
                    "/usr/sbin/nologin",
                    name="testuser",
                    shell="/bin/bash",
                    editing=True,
                    groups=tuple(f"group-{number:02}" for number in range(30)),
                )
            )
            await pilot.pause()
            assert isinstance(app.screen, UserDialog)
            apply_button = app.screen.query_one("#apply", Button)
            groups = app.screen.query_one("#groups", SelectionList)
            shell = app.screen.query_one("#shell", Select)
            home = app.screen.query_one("#home", Select)
            form = app.screen.query_one("#user-form", VerticalScroll)
            assert app.screen.has_class("user-dialog")
            assert form.allow_vertical_scroll
            assert shell.virtual_region.bottom <= groups.virtual_region.y
            shell.value = "/usr/sbin/nologin"
            assert shell.value == "/usr/sbin/nologin"
            assert home.disabled
            assert groups.virtual_region.bottom <= apply_button.parent.virtual_region.y
            assert groups.virtual_size.height > groups.size.height

            groups.focus()
            await pilot.press(*(["down"] * 15))
            assert groups.highlighted == 15
            assert groups.scroll_y > 0

            apply_button.focus()
            await pilot.pause()
            assert apply_button.region.y >= 0
            assert apply_button.region.y < app.screen.size.height

    asyncio.run(run())


def test_password_dialog_masks_both_password_fields():
    async def run() -> None:
        app = UserDockApp()
        async with app.run_test() as pilot:
            app.push_screen(PasswordDialog("alice"))
            await pilot.pause()
            assert app.screen.query_one("#password").password
            assert app.screen.query_one("#confirm-password").password

    asyncio.run(run())


def test_successful_user_creation_opens_password_dialog(monkeypatch):
    app = UserDockApp()
    opened = []
    monkeypatch.setattr(app, "_change", lambda operation, success: True)
    monkeypatch.setattr(
        app,
        "push_screen",
        lambda screen, callback=None: opened.append((screen, callback)),
    )

    app._perform_create_user(
        UserFormResult("alice", "Alice", "/bin/bash", True, ())
    )

    assert len(opened) == 1
    assert isinstance(opened[0][0], PasswordDialog)
    assert opened[0][0].username == "alice"


def test_samba_share_tab_opens_share_dialogs(monkeypatch):
    fixture_dir = Path(__file__).parent / "fixtures"
    monkeypatch.setenv("USERDOCK_SAMBA_CONFIG", str(fixture_dir / "smb.conf"))
    samba_users = parse_samba_users(
        (fixture_dir / "pdbedit.txt").read_text(encoding="utf-8")
    )
    monkeypatch.setattr("userdock.tui.list_samba_users", lambda: samba_users)

    async def run() -> None:
        app = UserDockApp(samba_admin=object())
        async with app.run_test() as pilot:
            await pilot.press("right", "right", "n")
            assert isinstance(app.screen, SambaShareDialog)
            await pilot.press("escape", "e")
            assert isinstance(app.screen, SambaShareDialog)
            await pilot.press("escape", "d")
            assert isinstance(app.screen, ConfirmDialog)
            await pilot.press("escape", "right")
            assert app.query_one("TabbedContent").active == "system-tab"

    asyncio.run(run())
