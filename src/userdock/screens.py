"""Modal editing screens used by the terminal interface."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Label,
    Select,
    SelectionList,
    Static,
)


class Dialog(ModalScreen[object]):
    DEFAULT_CSS = """
    .dialog { align: center middle; background: $background 60%; }
    .dialog > Vertical {
        width: 90%; max-width: 72; height: auto; max-height: 100%; padding: 0 1;
        border: round $primary; background: $surface;
    }
    .dialog .dialog-title { text-style: bold; }
    .dialog .field-row { height: 4; }
    .dialog .field { width: 1fr; height: 4; margin-right: 1; }
    .dialog .check-row { height: 1; }
    .dialog .check-row Checkbox { width: 1fr; height: 1; }
    .dialog SelectionList { height: 3; border: round $panel; }
    .dialog Horizontal { height: 3; }
    .dialog Button { margin-right: 1; }
    .user-dialog > #user-form {
        width: 100%; max-width: 100%; height: 100%; max-height: 100%;
        padding: 0 1; border: none; background: $surface;
    }
    .user-dialog #groups { height: 8; min-height: 3; }
    """

    def __init__(self) -> None:
        super().__init__(classes="dialog")

    def key_escape(self) -> None:
        self.dismiss(None)


class NameDialog(Dialog):
    def __init__(self, title: str, value: str = "") -> None:
        super().__init__()
        self.dialog_title = title
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.dialog_title, classes="dialog-title")
            yield Input(value=self.value, placeholder="Name", id="name")
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._apply()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            self._apply()
        else:
            self.dismiss(None)

    def _apply(self) -> None:
        self.dismiss(self.query_one("#name", Input).value.strip())


@dataclass(frozen=True, slots=True)
class UserFormResult:
    name: str
    full_name: str
    shell: str
    create_home: bool
    supplementary_groups: tuple[str, ...]


class UserDialog(Dialog):
    def __init__(
        self,
        title: str,
        shells: tuple[str, ...],
        nologin: str | None,
        *,
        name: str = "",
        full_name: str = "",
        shell: str = "",
        editing: bool = False,
        groups: tuple[str, ...] = (),
        selected_groups: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.add_class("user-dialog")
        self.dialog_title = title
        self.shells = shells
        self.nologin = nologin
        self.username = name
        self.full_name = full_name
        self.shell = shell
        self.editing = editing
        self.groups = groups
        self.selected_groups = frozenset(selected_groups)

    def compose(self) -> ComposeResult:
        choices = [(path, path) for path in self.shells if path != self.nologin]
        if self.nologin is not None:
            choices.append((f"No interactive login ({self.nologin})", self.nologin))
        choice_values = {value for _, value in choices}
        selected = self.shell if self.shell in choice_values else Select.BLANK
        with VerticalScroll(id="user-form"):
            yield Label(self.dialog_title, classes="dialog-title")
            with Horizontal(classes="field-row"):
                with Vertical(classes="field"):
                    yield Label("Username")
                    yield Input(
                        value=self.username, id="username", disabled=self.editing
                    )
                with Vertical(classes="field"):
                    yield Label("Full name")
                    yield Input(value=self.full_name, id="full-name")
            yield Label("Home directory")
            yield Select(
                (("Create /home/USERNAME", True), ("Do not create", False)),
                value=True,
                allow_blank=False,
                disabled=self.editing,
                id="home",
            )
            yield Label("Login shell")
            yield Select(choices, value=selected, allow_blank=False, id="shell")
            yield Label("Additional groups")
            yield SelectionList[str](
                *(
                    (group, group, group in self.selected_groups)
                    for group in self.groups
                ),
                id="groups",
            )
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "apply":
            self.dismiss(None)
            return
        shell = self.query_one("#shell", Select).value
        if not isinstance(shell, str):
            self.notify("Select a login shell", severity="error")
            return
        self.dismiss(
            UserFormResult(
                name=self.query_one("#username", Input).value.strip(),
                full_name=self.query_one("#full-name", Input).value.strip(),
                shell=shell,
                create_home=self.query_one("#home", Select).value is True,
                supplementary_groups=tuple(
                    sorted(self.query_one("#groups", SelectionList).selected)
                ),
            )
        )


class ConfirmDialog(Dialog):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.dialog_title = title
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.dialog_title, classes="dialog-title")
            yield Static(self.message)
            with Horizontal():
                yield Button("Apply", id="apply", variant="warning")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "apply")


@dataclass(frozen=True, slots=True)
class DeleteResult:
    confirmed: bool
    remove_home: bool = False


class ConfirmDeleteDialog(Dialog):
    def __init__(self, message: str, *, user: bool = False) -> None:
        super().__init__()
        self.message = message
        self.user = user

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Confirm deletion", classes="dialog-title")
            yield Static(self.message)
            if self.user:
                yield Checkbox("Also delete the home directory", id="remove-home")
            with Horizontal():
                yield Button("Delete", id="delete", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete":
            remove_home = (
                self.query_one("#remove-home", Checkbox).value if self.user else False
            )
            self.dismiss(DeleteResult(True, remove_home))
        else:
            self.dismiss(None)


class LockDialog(Dialog):
    def __init__(self, username: str) -> None:
        super().__init__()
        self.username = username

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Password access: {self.username}", classes="dialog-title")
            yield Static("Choose the account password state.")
            with Horizontal():
                yield Button("Lock", id="lock", variant="warning")
                yield Button("Unlock", id="unlock", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "lock":
            self.dismiss(True)
        elif event.button.id == "unlock":
            self.dismiss(False)
        else:
            self.dismiss(None)


class MembershipDialog(Dialog):
    """Toggle group membership with an extra step for access groups."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("space", "toggle_member", "Toggle membership"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(
        self,
        group: str,
        users: tuple[str, ...],
        members: set[str],
        access_group: bool,
        on_change: Callable[[str, bool], str | None],
    ) -> None:
        super().__init__()
        self.group = group
        self.users = users
        self.members = members
        self.access_group = access_group
        self.on_change = on_change
        self.pending: tuple[str, bool] | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Members of {self.group}", classes="dialog-title")
            yield Static("↑/↓ Select  •  Space Toggle  •  Esc Close", id="hint")
            yield DataTable(id="member-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#member-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Member", "User")
        self._fill()
        table.focus()

    def _fill(self) -> None:
        table = self.query_one("#member-table", DataTable)
        cursor = table.cursor_row
        table.clear()
        for username in self.users:
            table.add_row("✓" if username in self.members else "", username)
        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1))

    def action_toggle_member(self) -> None:
        table = self.query_one("#member-table", DataTable)
        if not table.row_count:
            return
        username = str(table.get_row_at(table.cursor_row)[1])
        member = username not in self.members
        requested = (username, member)
        if self.access_group and self.pending != requested:
            self.pending = requested
            action = "grant" if member else "remove"
            self.query_one("#hint", Static).update(
                f"Critical access: press Space again to {action} access for {username}"
            )
            return
        error = self.on_change(username, member)
        if error:
            self.notify(error, title="Change not applied", severity="error")
            return
        if member:
            self.members.add(username)
        else:
            self.members.discard(username)
        self.pending = None
        self.query_one("#hint", Static).update(
            "Saved • ↑/↓ Select  •  Space Toggle  •  Esc Close"
        )
        self._fill()

    def action_close(self) -> None:
        self.dismiss(None)
