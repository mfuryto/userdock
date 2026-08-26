import asyncio

from textual.widgets import Button, SelectionList

from userdock.screens import UserDialog
from userdock.tui import UserDockApp


def test_tui_starts_in_read_only_mode():
    async def run() -> None:
        app = UserDockApp()
        async with app.run_test() as pilot:
            status = app.query_one("#status-line")
            assert "Read-only mode" in str(status.renderable)
            assert app.show_system is False
            await pilot.press("s")
            assert app.show_system is True
            await pilot.press("right")
            assert app.query_one("TabbedContent").active == "groups-tab"
            assert app.query_one("#groups-table").has_focus

    asyncio.run(run())


def test_user_dialog_fits_small_terminal():
    async def run() -> None:
        app = UserDockApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("n")
            assert isinstance(app.screen, UserDialog)
            apply_button = app.screen.query_one("#apply", Button)
            groups = app.screen.query_one("#groups", SelectionList)
            assert apply_button.region.bottom <= app.screen.size.height
            assert groups.region.bottom <= app.screen.size.height

    asyncio.run(run())
