from pathlib import Path

from userdock.samba import (
    group_share_policy,
    list_samba_shares,
    parse_samba_users,
    suggest_home_directory,
)

FIXTURE = Path(__file__).parent / "fixtures" / "smb.conf"


def test_lists_shares_without_treating_global_as_a_share():
    shares = list_samba_shares(FIXTURE)
    assert [(share.name, share.read_only, share.guest_ok) for share in shares] == [
        ("Documents", False, False),
        ("Public", True, True),
    ]
    assert [share.share_type for share in shares] == [
        "Private Share",
        "Public Read Only",
    ]


def test_parses_samba_users_without_password_hashes():
    users = parse_samba_users(
        """Unix username: alice
Unix user ID: 1001
Account Flags: [U          ]
Unix username: bob
Unix user ID: 1002
Account Flags: [DU         ]
"""
    )
    assert [(user.name, user.uid, user.enabled, user.home) for user in users] == [
        ("alice", 1001, True, "—"),
        ("bob", 1002, False, "—"),
    ]


def test_group_share_policy_gives_all_group_members_read_write_access():
    assert group_share_policy("editors") == {
        "read only": "no",
        "guest ok": "no",
        "valid users": "@editors",
        "force group": "editors",
        "create mask": "0660",
        "directory mask": "2770",
        "force create mode": "0660",
        "force directory mode": "2770",
    }


def test_home_suggestion_avoids_paths_already_in_use():
    assert suggest_home_directory("alice", {"/home/alice"}) == "/home/alice-2"
