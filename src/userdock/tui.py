"""Textual terminal interface for UserDock."""

from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from userdock.accounts import get_user, list_groups, list_users, login_allowed
from userdock.admin import AccountAdmin, AdminError, available_shells, detect_nologin
from userdock.models import GroupCategory
from userdock.platform import detect_platform, is_linux
from userdock.samba import detect_samba_config, list_samba_shares, list_samba_users
from userdock.screens import (
    ConfirmDeleteDialog,
    ConfirmDialog,
    DeleteResult,
    LockDialog,
    MembershipDialog,
    NameDialog,
    PasswordDialog,
    PasswordResult,
    SambaShareDialog,
    SambaShareFormResult,
    SambaUserFormResult,
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
    .dialog .check-row Checkbox { width: 1fr; height: 1; }
    .dialog SelectionList { height: 3; border: round $panel; }
    .dialog Horizontal { height: 3; }
    .dialog Button { margin-right: 1; }
    .user-dialog { align: left top; }
    .user-dialog > #user-form {
        width: 100%; max-width: 100%; height: 100%; max-height: 100%;
        padding: 0 1; border: none; background: $surface;
    }
    .user-dialog #groups { height: 8; min-height: 3; }
    .user-dialog Horizontal { height: 1; }
    .user-dialog Button { height: 1; min-height: 1; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("s", "toggle_system", "System entries"),
        Binding("n", "new_record", "New"),
        Binding("e", "edit_record", "Edit"),
        Binding("l", "lock_user", "Lock / unlock"),
        Binding("p", "set_password", "Set password"),
        Binding("d", "delete_record", "Delete"),
        Binding("delete", "delete_record", "Delete", show=False),
        Binding("enter", "open_record", "Open"),
        Binding("left", "previous_tab", "Previous tab", show=False, priority=True),
        Binding("right", "next_tab", "Next tab", show=False, priority=True),
    ]

    def __init__(self, admin: AccountAdmin | None = None, samba_admin=None) -> None:
        super().__init__()
        self.show_system = False
        self.admin = admin or AccountAdmin()
        self.live_samba = samba_admin
        self.live_samba_error = ""
        if self.live_samba is None:
            try:
                from userdock.samba_live import LiveSambaAdmin

                self.live_samba = LiveSambaAdmin()
            except (ImportError, FileNotFoundError, PermissionError, OSError) as exc:
                self.live_samba_error = str(exc)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading", id="status-line")
        with TabbedContent(initial="users-tab"):
            with TabPane("Users", id="users-tab"):
                yield DataTable(id="users-table", zebra_stripes=True)
            with TabPane("Groups", id="groups-tab"):
                yield DataTable(id="groups-table", zebra_stripes=True)
            with TabPane("Samba Shares", id="samba-shares-tab"):
                yield DataTable(id="samba-shares-table", zebra_stripes=True)
            with TabPane("System", id="system-tab"):
                yield Static(id="system-details", classes="system-card")
        yield Footer()

    def on_mount(self) -> None:
        users = self.query_one("#users-table", DataTable)
        users.cursor_type = "row"
        users.add_columns("Name", "UID", "Type", "Login", "Smb login", "Groups")
        groups = self.query_one("#groups-table", DataTable)
        groups.cursor_type = "row"
        groups.add_columns("Name", "GID", "Category", "Members")
        shares = self.query_one("#samba-shares-table", DataTable)
        shares.cursor_type = "row"
        shares.add_columns("Name", "Type", "Path", "Group", "Writable", "Guest")
        self.refresh_data()
        users.focus()

    def refresh_data(self) -> None:
        platform = detect_platform()
        users_table = self.query_one("#users-table", DataTable)
        users_table.clear()
        samba_users = {user.name: user for user in list_samba_users()} if self.live_samba else {}
        for user in list_users(platform):
            if user.is_system and not self.show_system:
                continue
            users_table.add_row(
                user.name,
                str(user.uid),
                "System" if user.is_system else "User",
                "Yes" if login_allowed(user.shell) else "No",
                ("Yes" if samba_users[user.name].enabled else "No")
                if user.name in samba_users else "—",
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

        shares_table = self.query_one("#samba-shares-table", DataTable)
        shares_table.clear()
        if self.live_samba is None:
            shares_table.add_row("Samba is not installed", "", "", "", "", "")
        else:
            for share in list_samba_shares():
                shares_table.add_row(
                share.name,
                share.share_type,
                share.path,
                share.group or "—",
                "Yes" if not share.read_only else "No",
                "Yes" if share.guest_ok else "No",
                key=share.name,
                )

        support = "Ready" if is_linux() and platform.distro_family != "unknown" else "Limited"
        samba_config = detect_samba_config()
        self.query_one("#system-details", Static).update(
            "\n".join(
                (
                    f"Distribution   {platform.distro_name}",
                    f"Family         {platform.distro_family}",
                    f"User IDs       {platform.user_uid_min or '?'}–{platform.user_uid_max or '?'}",
                    f"Group IDs      {platform.user_gid_min or '?'}–{platform.user_gid_max or '?'}",
                    f"Read support   {support}",
                    f"Changes        {'Enabled' if self.admin.can_change else 'Disabled'}",
                    f"Samba config   {samba_config or 'Not found'}",
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
        tab_ids = (
            "users-tab",
            "groups-tab",
            "samba-shares-tab",
            "system-tab",
        )
        current = tab_ids.index(tabs.active)
        tabs.active = tab_ids[(current + offset) % len(tab_ids)]
        self.refresh_bindings()
        if tabs.active == "users-tab":
            self.query_one("#users-table", DataTable).focus()
        elif tabs.active == "groups-tab":
            self.query_one("#groups-table", DataTable).focus()
        elif tabs.active == "samba-shares-tab":
            self.query_one("#samba-shares-table", DataTable).focus()
        else:
            self.query_one("#system-details", Static).focus()

    def action_previous_tab(self) -> None:
        self._select_tab(-1)

    def action_next_tab(self) -> None:
        self._select_tab(1)

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        self.refresh_bindings()

    def _active_tab(self) -> str:
        return self.query_one(TabbedContent).active

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable footer actions which do not apply to the active tab."""
        tabs = self.query(TabbedContent)
        tab = tabs.first().active if len(tabs) else "users-tab"
        if action in {"set_password", "lock_user"}:
            return tab == "users-tab"
        if action == "toggle_system":
            return tab in {"users-tab", "groups-tab"}
        if action == "open_record":
            return tab == "groups-tab"
        if action in {"new_record", "edit_record", "delete_record"}:
            return tab in {"users-tab", "groups-tab"} or (
                tab == "samba-shares-tab" and self.live_samba is not None
            )
        return True

    def _selected_name(self, table_id: str) -> str | None:
        table = self.query_one(table_id, DataTable)
        if not table.row_count:
            return None
        return str(table.get_row_at(table.cursor_row)[0])

    def _change(self, operation, success: str) -> bool:
        try:
            operation()
        except AdminError as error:
            self.notify(str(error), title="Change not applied", severity="error")
            return False
        self.refresh_data()
        self.notify(success)
        return True

    def action_new_record(self) -> None:
        if self._active_tab() == "samba-shares-tab":
            self.push_screen(
                SambaShareDialog(
                    "New Samba share", groups=self._samba_shared_groups()
                ),
                lambda result: self._save_samba_share(None, result),
            )
        elif self._active_tab() == "groups-tab":
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
                    samba_available=self.live_samba is not None,
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

    def _samba_shared_groups(self) -> tuple[str, ...]:
        platform = detect_platform()
        private_groups = {
            user.primary_group
            for user in list_users(platform)
            if user.primary_group and user.primary_group == user.name
        }
        return tuple(
            group.name
            for group in list_groups(platform)
            if group.category is GroupCategory.USER
            and group.name not in private_groups
        )

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
        created = self._change(
            lambda: self.admin.create_user(
                result.name,
                result.full_name,
                result.shell,
                result.create_home,
                result.supplementary_groups,
            ),
            f"Created user {result.name}",
        )
        if created:
            self.push_screen(
                PasswordDialog(result.name),
                lambda password: self._finish_new_user(result, password),
            )

    def _finish_new_user(self, form: UserFormResult, result: PasswordResult | None) -> None:
        if result is None:
            return
        if not self._set_password(form.name, result):
            return
        if form.create_samba and self.live_samba is not None:
            changed = self.live_samba.create_existing_user(form.name, result.password)
            if changed.ok:
                self.live_samba.set_user_enabled(form.name, form.samba_enabled)
                if form.create_private_share:
                    user = get_user(form.name, detect_platform())
                    if user:
                        share = SambaShareFormResult(form.name, user.home, "Private Share", "", True, False)
                        self.live_samba.save_share(None, share, private_user=form.name)
            self.notify(changed.message, severity="information" if changed.ok else "error")
            self.refresh_data()

    def _save_samba_share(
        self, original_name: str | None, result: SambaShareFormResult | None
    ) -> None:
        if result is None:
            return
        if self.live_samba is None:
            self.notify(self.live_samba_error or "Samba is unavailable", severity="error")
            return
        applied = self.live_samba.save_share(original_name, result)
        self.notify(applied.message, severity="information" if applied.ok else "error")
        if applied.ok:
            self.refresh_data()

    def _save_samba_user(
        self, original_name: str | None, result: SambaUserFormResult | None
    ) -> None:
        if result is None:
            return
        if self.live_samba is None:
            self.notify(self.live_samba_error or "Samba is unavailable", severity="error")
            return
        if original_name is not None:
            changed = self.live_samba.set_user_enabled(original_name, result.enabled)
            self.notify(
                changed.message,
                severity="information" if changed.ok else "error",
            )
            if changed.ok:
                self.refresh_data()
            return
        self.push_screen(
            PasswordDialog(result.name, samba=True),
            lambda password: self._create_live_samba_user(result, password),
        )

    def _create_live_samba_user(
        self, form: SambaUserFormResult, password: PasswordResult | None
    ) -> None:
        if password is None or self.live_samba is None:
            return
        result = self.live_samba.create_user(form, password.password)
        if result.ok and form.create_private_share:
            share = SambaShareFormResult(
                form.name,
                form.home,
                "Private Share",
                "",
                True,
                False,
            )
            share_result = self.live_samba.save_share(
                None, share, private_user=form.name
            )
            if not share_result.ok:
                result.message += f"; private share failed: {share_result.message}"
                result.ok = False
        self.notify(result.message, severity="information" if result.ok else "error")
        self.refresh_data()

    def action_edit_record(self) -> None:
        if self._active_tab() == "samba-shares-tab":
            name = self._selected_name("#samba-shares-table")
            share = next(
                (item for item in list_samba_shares() if item.name == name), None
            )
            if share is None:
                self.notify("Select a Samba share", severity="warning")
                return
            self.push_screen(
                SambaShareDialog(
                    f"Edit [{share.name}]",
                    name=share.name,
                    path=share.path,
                    writable=not share.read_only,
                    guest=share.guest_ok,
                    share_type=share.share_type,
                    group=share.group,
                    groups=self._samba_shared_groups(),
                ),
                lambda result: self._save_samba_share(share.name, result),
            )
        elif self._active_tab() == "groups-tab":
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
                # Samba settings belong to the same Linux identity.
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
                    samba_available=self.live_samba is not None,
                    samba_exists=any(item.name == user.name for item in list_samba_users()),
                    samba_enabled=next((item.enabled for item in list_samba_users() if item.name == user.name), True),
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
                    user, result, final_groups
                ) if confirmed else None,
            )
            return
        self._perform_update_user(user, result, final_groups)

    def _perform_update_user(
        self, user, result: UserFormResult, supplementary_groups: tuple[str, ...]
    ) -> None:
        old_name = user.name
        old_home = user.home
        samba_user = next((item for item in list_samba_users() if item.name == old_name), None)
        private_share = next(
            (item for item in list_samba_shares() if item.name == old_name and item.path == old_home),
            None,
        )
        changed = self._change(
            lambda: self.admin.update_user(
                old_name,
                result.name,
                result.full_name,
                result.shell,
                supplementary_groups,
                old_home,
            ),
            f"Updated user {result.name}",
        )
        if changed and old_name != result.name and self.live_samba is not None:
            if samba_user is not None:
                renamed = self.live_samba.rename_user(old_name, result.name)
                if not renamed.ok:
                    self.notify(renamed.message, severity="error")
            if private_share is not None:
                new_home = str(Path("/home") / result.name)
                share = SambaShareFormResult(result.name, new_home, "Private Share", "", True, False)
                moved = self.live_samba.save_share(old_name, share, private_user=result.name)
                if not moved.ok:
                    self.notify(moved.message, severity="error")
        if changed and result.create_samba and self.live_samba is not None:
            exists = any(item.name == result.name for item in list_samba_users())
            if exists:
                self.live_samba.set_user_enabled(result.name, result.samba_enabled)
                self.refresh_data()
            else:
                self.push_screen(
                    PasswordDialog(result.name),
                    lambda password: self._create_samba_for_existing(result, password),
                )

    def _create_samba_for_existing(
        self, form: UserFormResult, result: PasswordResult | None
    ) -> None:
        if result is None or self.live_samba is None:
            return
        changed = self.live_samba.create_existing_user(form.name, result.password)
        if changed.ok:
            self.live_samba.set_user_enabled(form.name, form.samba_enabled)
        self.notify(changed.message, severity="information" if changed.ok else "error")
        self.refresh_data()

    def action_lock_user(self) -> None:
        if self._active_tab() != "users-tab":
            return
        name = self._selected_name("#users-table")
        user = get_user(name, detect_platform()) if name else None
        if user is None or user.is_system:
            self.notify("System users are read-only", severity="warning")
            return
        self.push_screen(LockDialog(user.name), lambda locked: self._set_locked(user.name, locked))

    def action_set_password(self) -> None:
        if self._active_tab() != "users-tab":
            return
        name = self._selected_name("#users-table")
        user = get_user(name, detect_platform()) if name else None
        if user is None or user.is_system:
            self.notify("System users are read-only", severity="warning")
            return
        self.push_screen(
            PasswordDialog(user.name),
            lambda result: self._set_password(user.name, result),
        )

    def _set_password(self, name: str, result: PasswordResult | None) -> bool:
        if result is not None:
            changed = self._change(
                lambda: self.admin.set_password(
                    name, result.password, result.expire_on_next_login
                ),
                f"Changed password for {name}",
            )
            if changed and self.live_samba is not None and any(
                item.name == name for item in list_samba_users()
            ):
                samba = self.live_samba.set_samba_password(name, result.password)
                if not samba.ok:
                    self.notify(samba.message, severity="error")
                    return False
            return changed
        return False

    def _set_live_samba_password(
        self, name: str, result: PasswordResult | None
    ) -> None:
        if result is None or self.live_samba is None:
            return
        changed = self.live_samba.set_password(name, result.password)
        self.notify(
            changed.message,
            severity="information" if changed.ok else "error",
        )

    def _set_locked(self, name: str, locked: bool | None) -> None:
        if locked is not None:
            action = "Locked" if locked else "Unlocked"
            self._change(lambda: self.admin.set_locked(name, locked), f"{action} {name}")

    def action_delete_record(self) -> None:
        if self._active_tab() == "samba-shares-tab":
            name = self._selected_name("#samba-shares-table")
            if name:
                self.push_screen(
                    ConfirmDialog("Delete Samba share", f"Delete share [{name}]?"),
                    lambda confirmed: self._delete_samba_share(name, confirmed),
                )
        elif self._active_tab() == "groups-tab":
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

    def _delete_samba_share(self, name: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        if self.live_samba is None:
            self.notify(self.live_samba_error or "Samba is unavailable", severity="error")
            return
        result = self.live_samba.delete_share(name)
        self.notify(result.message, severity="information" if result.ok else "error")
        if result.ok:
            self.refresh_data()

    def _delete_samba_user(self, name: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        if self.live_samba is None:
            self.notify(self.live_samba_error or "Samba is unavailable", severity="error")
            return
        result = self.live_samba.delete_user(name)
        self.notify(result.message, severity="information" if result.ok else "error")
        if result.ok:
            self.refresh_data()

    def _delete_group(self, name: str, result: DeleteResult | None) -> None:
        if result and result.confirmed:
            self._change(lambda: self.admin.delete_group(name), f"Deleted group {name}")

    def _delete_user(
        self, name: str, home: str, result: DeleteResult | None
    ) -> None:
        if result and result.confirmed:
            if result.remove_home and self.live_samba is not None:
                private = next(
                    (share for share in list_samba_shares() if share.name == name and share.path == home),
                    None,
                )
                if private is not None:
                    removed = self.live_samba.delete_share(name)
                    if not removed.ok:
                        self.notify(removed.message, severity="error")
                        return
                if any(item.name == name for item in list_samba_users()):
                    removed_user = self.live_samba.delete_user(name)
                    if not removed_user.ok:
                        self.notify(removed_user.message, severity="error")
                        return
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
