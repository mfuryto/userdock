"""Textual terminal interface for UserDock."""

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from userdock.accounts import get_user, list_groups, list_users
from userdock.admin import AccountAdmin, AdminError, available_shells, detect_nologin
from userdock.models import GroupCategory
from userdock.platform import detect_platform, is_linux
from userdock.screens import (
    ConfirmDeleteDialog,
    ConfirmDialog,
    DeleteResult,
    LockDialog,
    MembershipDialog,
    NameDialog,
    UserDialog,
    UserFormResult,
)


class UserDockApp(App[None]):
    """Read-only terminal interface for local account inspection."""

    TITLE = "UserDock"
    SUB_TITLE = "Local users and groups"
    CSS = """
    Screen {
        background: $surface;
    }

    #status-line {
        height: 3;
        padding: 1 2;
        background: $boost;
        color: $text-muted;
    }

    DataTable {
        height: 1fr;
    }

    TabPane {
        padding: 1;
    }

    .system-card {
        width: 100%;
        padding: 1 2;
        border: round $primary;
    }

    .dialog { align: center middle; background: $background 60%; }
    .dialog > Vertical {
        width: 90%; max-width: 72; height: auto; max-height: 100%; padding: 0 1;
        border: round $primary; background: $surface;
    }
    .dialog .dialog-title { text-style: bold; }
    .dialog .field-row { height: 4; }
    .dialog .field { width: 1fr; height: 4; margin-right: 1; }
    .dialog .check-row { height: 1; }
    .dialog .check-row Checkbox { width: 1fr; }
    .dialog SelectionList { height: 3; border: round $panel; }
    .dialog Horizontal { height: 3; }
    .dialog Button { margin-right: 1; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("s", "toggle_system", "System entries"),
        Binding("n", "new_record", "New"),
        Binding("e", "edit_record", "Edit"),
        Binding("l", "lock_user", "Lock / unlock"),
        Binding("delete", "delete_record", "Delete"),
        Binding("enter", "open_record", "Open"),
        Binding("left", "previous_tab", "Previous tab", show=False, priority=True),
        Binding("right", "next_tab", "Next tab", show=False, priority=True),
    ]

    def __init__(self, admin: AccountAdmin | None = None) -> None:
        super().__init__()
        self.show_system = False
        self.admin = admin or AccountAdmin()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading", id="status-line")
        with TabbedContent(initial="users-tab"):
            with TabPane("Users", id="users-tab"):
                yield DataTable(id="users-table", zebra_stripes=True)
            with TabPane("Groups", id="groups-tab"):
                yield DataTable(id="groups-table", zebra_stripes=True)
            with TabPane("System", id="system-tab"):
                yield Static(id="system-details", classes="system-card")
        yield Footer()

    def on_mount(self) -> None:
        users = self.query_one("#users-table", DataTable)
        users.cursor_type = "row"
        users.add_columns("Name", "UID", "Type", "Groups")
        groups = self.query_one("#groups-table", DataTable)
        groups.cursor_type = "row"
        groups.add_columns("Name", "GID", "Category", "Members")
        self.refresh_data()
        users.focus()

    def refresh_data(self) -> None:
        platform = detect_platform()
        users_table = self.query_one("#users-table", DataTable)
        users_table.clear()
        for user in list_users(platform):
            if user.is_system and not self.show_system:
                continue
            users_table.add_row(
                user.name,
                str(user.uid),
                "System" if user.is_system else "User",
                ", ".join(user.groups) or "—",
                key=user.name,
            )

        groups_table = self.query_one("#groups-table", DataTable)
        groups_table.clear()
        for group in list_groups(platform):
            if group.category is GroupCategory.INTERNAL and not self.show_system:
                continue
            groups_table.add_row(
                group.name,
                str(group.gid),
                group.category.value.title(),
                ", ".join(group.members) or "—",
                key=group.name,
            )

        support = "Ready" if is_linux() and platform.distro_family != "unknown" else "Limited"
        self.query_one("#system-details", Static).update(
            "\n".join(
                (
                    f"Distribution   {platform.distro_name}",
                    f"Family         {platform.distro_family}",
                    f"User IDs       {platform.user_uid_min or '?'}–{platform.user_uid_max or '?'}",
                    f"Group IDs      {platform.user_gid_min or '?'}–{platform.user_gid_max or '?'}",
                    f"Read support   {support}",
                    f"Changes        {'Enabled' if self.admin.can_change else 'Disabled'}",
                )
            )
        )
        mode = (
            "including internal system entries"
            if self.show_system
            else "user and access entries"
        )
        access = (
            "Admin mode"
            if self.admin.can_change
            else "Read-only mode • run with sudo to edit"
        )
        self.query_one("#status-line", Static).update(f"{access} • Showing {mode}")

    def action_refresh_data(self) -> None:
        self.refresh_data()
        self.notify("Account data refreshed")

    def action_toggle_system(self) -> None:
        self.show_system = not self.show_system
        self.refresh_data()

    def _select_tab(self, offset: int) -> None:
        if len(self.screen_stack) > 1:
            return
        tabs = self.query_one(TabbedContent)
        tab_ids = ("users-tab", "groups-tab", "system-tab")
        current = tab_ids.index(tabs.active)
        tabs.active = tab_ids[(current + offset) % len(tab_ids)]
        if tabs.active == "users-tab":
            self.query_one("#users-table", DataTable).focus()
        elif tabs.active == "groups-tab":
            self.query_one("#groups-table", DataTable).focus()
        else:
            self.query_one("#system-details", Static).focus()

    def action_previous_tab(self) -> None:
        self._select_tab(-1)

    def action_next_tab(self) -> None:
        self._select_tab(1)

    def _active_tab(self) -> str:
        return self.query_one(TabbedContent).active

    def _selected_name(self, table_id: str) -> str | None:
        table = self.query_one(table_id, DataTable)
        if not table.row_count:
            return None
        return str(table.get_row_at(table.cursor_row)[0])

    def _change(self, operation, success: str) -> None:
        try:
            operation()
        except AdminError as error:
            self.notify(str(error), title="Change not applied", severity="error")
            return
        self.refresh_data()
        self.notify(success)

    def action_new_record(self) -> None:
        if self._active_tab() == "groups-tab":
            self.push_screen(NameDialog("New group"), self._create_group)
        elif self._active_tab() == "users-tab":
            groups = self._manageable_groups()
            self.push_screen(
                UserDialog(
                    "New user",
                    available_shells(),
                    detect_nologin(),
                    shell="/bin/bash",
                    groups=groups,
                ),
                self._create_user,
            )

    def _manageable_groups(self) -> tuple[str, ...]:
        return tuple(
            group.name
            for group in list_groups(detect_platform())
            if group.category is not GroupCategory.INTERNAL
        )

    def _access_groups(self) -> set[str]:
        return {
            group.name
            for group in list_groups(detect_platform())
            if group.category is GroupCategory.ACCESS
        }

    def _create_group(self, name: str | None) -> None:
        if name:
            self._change(lambda: self.admin.create_group(name), f"Created group {name}")

    def _create_user(self, result: UserFormResult | None) -> None:
        if result is None:
            return
        critical = sorted(set(result.supplementary_groups) & self._access_groups())
        if critical:
            self.push_screen(
                ConfirmDialog(
                    "Confirm privileged access",
                    f"Create {result.name} with access through: {', '.join(critical)}?",
                ),
                lambda confirmed: self._perform_create_user(result) if confirmed else None,
            )
            return
        self._perform_create_user(result)

    def _perform_create_user(self, result: UserFormResult) -> None:
        self._change(
            lambda: self.admin.create_user(
                result.name,
                result.full_name,
                result.shell,
                result.create_home,
                result.supplementary_groups,
            ),
            f"Created user {result.name}",
        )

    def action_edit_record(self) -> None:
        if self._active_tab() == "groups-tab":
            name = self._selected_name("#groups-table")
            if not name:
                return
            group = next(group for group in list_groups(detect_platform()) if group.name == name)
            if group.category is not GroupCategory.USER:
                self.notify("Access and internal groups cannot be renamed", severity="warning")
                return
            self.push_screen(
                NameDialog("Rename group", name),
                lambda new_name: self._rename_group(name, new_name),
            )
        elif self._active_tab() == "users-tab":
            name = self._selected_name("#users-table")
            user = get_user(name, detect_platform()) if name else None
            if user is None or user.is_system:
                self.notify("System users are read-only", severity="warning")
                return
            self.push_screen(
                UserDialog(
                    f"Edit {user.name}",
                    available_shells(),
                    detect_nologin(),
                    name=user.name,
                    full_name=user.full_name,
                    shell=user.shell,
                    editing=True,
                    groups=self._manageable_groups(),
                    selected_groups=tuple(
                        group
                        for group in user.groups
                        if group in self._manageable_groups()
                        and group != user.primary_group
                    ),
                ),
                lambda result: self._update_user(user, result),
            )

    def _rename_group(self, old_name: str, new_name: str | None) -> None:
        if new_name and new_name != old_name:
            self._change(
                lambda: self.admin.rename_group(old_name, new_name),
                f"Renamed {old_name} to {new_name}",
            )

    def _update_user(self, user, result: UserFormResult | None) -> None:
        if result is None:
            return
        manageable = set(self._manageable_groups())
        old_supplementary = set(user.groups) - {user.primary_group}
        preserved = old_supplementary - manageable
        final_groups = tuple(sorted(preserved | set(result.supplementary_groups)))
        critical_changes = sorted(
            (old_supplementary ^ set(result.supplementary_groups))
            & self._access_groups()
        )
        if critical_changes:
            self.push_screen(
                ConfirmDialog(
                    "Confirm privileged access change",
                    "Change membership in: " + ", ".join(critical_changes) + "?",
                ),
                lambda confirmed: self._perform_update_user(
                    result, final_groups
                ) if confirmed else None,
            )
            return
        self._perform_update_user(result, final_groups)

    def _perform_update_user(
        self, result: UserFormResult, supplementary_groups: tuple[str, ...]
    ) -> None:
        self._change(
            lambda: self.admin.update_user(
                result.name,
                result.full_name,
                result.shell,
                supplementary_groups,
            ),
            f"Updated user {result.name}",
        )

    def action_lock_user(self) -> None:
        if self._active_tab() != "users-tab":
            return
        name = self._selected_name("#users-table")
        user = get_user(name, detect_platform()) if name else None
        if user is None or user.is_system:
            self.notify("System users are read-only", severity="warning")
            return
        self.push_screen(LockDialog(user.name), lambda locked: self._set_locked(user.name, locked))

    def _set_locked(self, name: str, locked: bool | None) -> None:
        if locked is not None:
            action = "Locked" if locked else "Unlocked"
            self._change(lambda: self.admin.set_locked(name, locked), f"{action} {name}")

    def action_delete_record(self) -> None:
        if self._active_tab() == "groups-tab":
            name = self._selected_name("#groups-table")
            if not name:
                return
            group = next(group for group in list_groups(detect_platform()) if group.name == name)
            if group.category is not GroupCategory.USER:
                self.notify("Access and internal groups cannot be deleted", severity="warning")
                return
            self.push_screen(
                ConfirmDeleteDialog(f"Delete group {name}?"),
                lambda result: self._delete_group(name, result),
            )
        elif self._active_tab() == "users-tab":
            name = self._selected_name("#users-table")
            user = get_user(name, detect_platform()) if name else None
            if user is None or user.is_system:
                self.notify("System users are read-only", severity="warning")
                return
            self.push_screen(
                ConfirmDeleteDialog(
                    f"Delete {user.name}?\nHome: {user.home}", user=True
                ),
                lambda result: self._delete_user(user.name, user.home, result),
            )

    def _delete_group(self, name: str, result: DeleteResult | None) -> None:
        if result and result.confirmed:
            self._change(lambda: self.admin.delete_group(name), f"Deleted group {name}")

    def _delete_user(
        self, name: str, home: str, result: DeleteResult | None
    ) -> None:
        if result and result.confirmed:
            self._change(
                lambda: self.admin.delete_user(name, result.remove_home, home),
                f"Deleted user {name}",
            )

    def action_open_record(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if self._active_tab() != "groups-tab":
            return
        name = self._selected_name("#groups-table")
        if not name:
            return
        platform = detect_platform()
        group = next(group for group in list_groups(platform) if group.name == name)
        if group.category is GroupCategory.INTERNAL:
            self.notify("Internal groups are read-only", severity="warning")
            return
        usernames = tuple(
            user.name for user in list_users(platform) if not user.is_system
        )
        self.push_screen(
            MembershipDialog(
                group.name,
                usernames,
                set(group.members),
                group.category is GroupCategory.ACCESS,
                lambda user, member: self._set_membership(
                    user, group.name, member
                ),
            ),
            lambda _: self.refresh_data(),
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "groups-table":
            self.action_open_record()

    def _set_membership(self, user: str, group: str, member: bool) -> str | None:
        try:
            self.admin.set_group_member(user, group, member)
        except AdminError as error:
            return str(error)
        return None


def run_tui() -> None:
    """Launch the UserDock terminal interface."""
    UserDockApp().run()
