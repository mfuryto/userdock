"""Modal editing screens used by the terminal interface."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from textual import events
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
    create_samba: bool = False
    create_private_share: bool = False
    samba_enabled: bool = True


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
        samba_available: bool = False,
        samba_exists: bool = False,
        samba_enabled: bool = True,
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
        self.samba_available = samba_available
        self.samba_exists = samba_exists
        self.samba_enabled = samba_enabled

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
                        value=self.username, id="username"
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
            yield Checkbox(
                "Create Samba user" if not self.editing else "Samba user",
                value=self.samba_exists if self.editing else self.samba_available,
                id="create-samba",
                disabled=not self.samba_available or (self.editing and self.samba_exists),
            )
            yield Checkbox(
                "Create private share (home directory)",
                value=False,
                id="private-share",
                disabled=not self.samba_available or self.editing,
            )
            yield Checkbox(
                "Enable Samba login",
                value=self.samba_enabled,
                id="samba-enabled",
                disabled=not self.samba_available,
            )
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        event.widget.scroll_visible(animate=False, force=True)

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
                create_samba=self.query_one("#create-samba", Checkbox).value,
                create_private_share=self.query_one("#private-share", Checkbox).value,
                samba_enabled=self.query_one("#samba-enabled", Checkbox).value,
            )
        )


@dataclass(frozen=True, slots=True)
class SambaShareFormResult:
    name: str
    path: str
    share_type: str
    group: str
    writable: bool
    guest: bool


class SambaShareDialog(Dialog):
    def __init__(
        self,
        title: str,
        *,
        name: str = "",
        path: str = "",
        writable: bool = True,
        guest: bool = False,
        share_type: str = "Private Share",
        group: str = "",
        groups: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.dialog_title = title
        self.share_name = name
        self.directory_path = path
        self.writable = writable
        self.guest = guest
        self.share_type = share_type
        self.group = group
        self.groups = groups

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.dialog_title, classes="dialog-title")
            yield Label("Share name")
            yield Input(value=self.share_name, id="share-name")
            yield Label("Directory path")
            yield Input(
                value=self.directory_path,
                placeholder="/srv/samba/share",
                id="share-path",
            )
            yield Label("Share type")
            yield Select(
                (
                    ("Private Share", "Private Share"),
                    ("Group Share", "Group Share"),
                    ("Public Read Only", "Public Read Only"),
                    ("Public Read/Write", "Public Read/Write"),
                ),
                value=self.share_type,
                allow_blank=False,
                id="share-type",
            )
            yield Label("Shared Linux group")
            yield Select(
                tuple((group, group) for group in self.groups),
                value=self.group if self.group in self.groups else Select.BLANK,
                allow_blank=True,
                id="share-group",
            )
            yield Label("Access")
            yield Select(
                (("Writable", True), ("Read only", False)),
                value=self.writable,
                allow_blank=False,
                id="share-writable",
            )
            yield Label("Guest access")
            yield Select(
                (("No", False), ("Yes", True)),
                value=self.guest,
                allow_blank=False,
                id="share-guest",
            )
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "apply":
            self.dismiss(None)
            return
        name = self.query_one("#share-name", Input).value.strip()
        path = self.query_one("#share-path", Input).value.strip()
        if not name or not path.startswith("/"):
            self.notify("Enter a share name and an absolute directory path", severity="error")
            return
        share_type = self.query_one("#share-type", Select).value
        group = self.query_one("#share-group", Select).value
        if share_type == "Group Share" and not isinstance(group, str):
            self.notify("Select the Linux group that will share the files", severity="error")
            return
        self.dismiss(
            SambaShareFormResult(
                name,
                path,
                str(share_type),
                group if isinstance(group, str) else "",
                self.query_one("#share-writable", Select).value is True,
                self.query_one("#share-guest", Select).value is True,
            )
        )


@dataclass(frozen=True, slots=True)
class SambaUserFormResult:
    name: str
    home: str
    enabled: bool
    create_linux: bool
    create_private_share: bool


class SambaUserDialog(Dialog):
    def __init__(
        self,
        title: str,
        *,
        name: str = "",
        home: str = "",
        enabled: bool = True,
        editing: bool = False,
        create_linux: bool = True,
        used_homes: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.dialog_title = title
        self.username = name
        self.home = home
        self.enabled = enabled
        self.editing = editing
        self.create_linux = create_linux
        self.used_homes = set(used_homes)
        self.home_was_edited = bool(home)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.dialog_title, classes="dialog-title")
            yield Label("Linux username")
            yield Input(
                value=self.username,
                disabled=self.editing,
                id="samba-username",
            )
            yield Label("Linux account")
            yield Select(
                (("Create Linux user", True), ("Use existing Linux user", False)),
                value=self.create_linux,
                allow_blank=False,
                disabled=self.editing,
                id="create-linux-user",
            )
            if not self.editing:
                yield Checkbox(
                    "Create a private Samba share for this user",
                    value=True,
                    id="create-private-share",
                )
            yield Label("Home directory")
            yield Input(value=self.home, disabled=self.editing, id="samba-home")
            yield Label("Samba login")
            yield Select(
                (("Enabled", True), ("Disabled", False)),
                value=self.enabled,
                allow_blank=False,
                id="samba-enabled",
            )
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "apply":
            self.dismiss(None)
            return
        name = self.query_one("#samba-username", Input).value.strip()
        home = self.query_one("#samba-home", Input).value.strip()
        if not name or not home.startswith("/"):
            self.notify("Enter a username and an absolute home path", severity="error")
            return
        self.dismiss(
            SambaUserFormResult(
                name,
                home,
                self.query_one("#samba-enabled", Select).value is True,
                self.query_one("#create-linux-user", Select).value is True,
                (
                    self.query_one("#create-private-share", Checkbox).value
                    if not self.editing
                    else False
                ),
            )
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "samba-home":
            if event.input.has_focus:
                self.home_was_edited = True
            return
        if event.input.id != "samba-username" or self.editing or self.home_was_edited:
            return
        from userdock.samba import suggest_home_directory

        username = event.value.strip()
        if username:
            self.query_one("#samba-home", Input).value = suggest_home_directory(
                username, self.used_homes
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


@dataclass(frozen=True, slots=True)
class PasswordResult:
    password: str
    expire_on_next_login: bool


class PasswordDialog(Dialog):
    def __init__(self, username: str, *, samba: bool = False) -> None:
        super().__init__()
        self.username = username
        self.samba = samba

    def compose(self) -> ComposeResult:
        with Vertical():
            prefix = "Set Samba password" if self.samba else "Set password"
            yield Label(f"{prefix}: {self.username}", classes="dialog-title")
            yield Label("New password")
            yield Input(password=True, id="password")
            yield Label("Confirm password")
            yield Input(password=True, id="confirm-password")
            if not self.samba:
                yield Checkbox(
                    "Require password change at next login",
                    id="expire-password",
                )
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#password", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "confirm-password":
            self._apply()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            self._apply()
        else:
            self.dismiss(None)

    def _apply(self) -> None:
        password = self.query_one("#password", Input).value
        confirmation = self.query_one("#confirm-password", Input).value
        if not password:
            self.notify("Password cannot be empty", severity="error")
            return
        if password != confirmation:
            self.notify("Passwords do not match", severity="error")
            return
        self.dismiss(
            PasswordResult(
                password,
                (
                    self.query_one("#expire-password", Checkbox).value
                    if not self.samba
                    else False
                ),
            )
        )


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
