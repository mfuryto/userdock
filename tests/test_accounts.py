import grp
import pwd

from userdock.accounts import classify_group, list_users, login_allowed
from userdock.models import GroupCategory, PlatformInfo

PLATFORM = PlatformInfo("test", "Test Linux", "debian", 1000, 1000)


def test_login_status_recognizes_common_disabled_shells():
    assert login_allowed("/bin/bash") is True
    assert login_allowed("/usr/sbin/nologin") is False
    assert login_allowed("/sbin/nologin") is False
    assert login_allowed("/bin/false") is False


def test_access_group_is_not_hidden_by_low_gid():
    assert classify_group("sudo", 27, PLATFORM) is GroupCategory.ACCESS


def test_high_gid_group_is_a_user_group():
    assert classify_group("developers", 1200, PLATFORM) is GroupCategory.USER


def test_unknown_low_gid_group_is_internal():
    assert classify_group("service-daemon", 220, PLATFORM) is GroupCategory.INTERNAL


def test_reserved_high_gid_group_is_internal():
    platform = PlatformInfo("test", "Test Linux", "debian", 1000, 1000, 60000, 60000)
    assert classify_group("nobody", 65534, platform) is GroupCategory.INTERNAL


def test_user_memberships_include_primary_and_supplementary_groups():
    users = [
        pwd.struct_passwd(
            ("alice", "x", 1001, 1001, "", "/home/alice", "/bin/bash")
        )
    ]
    groups = [
        grp.struct_group(("alice", "x", 1001, [])),
        grp.struct_group(("developers", "x", 1200, ["alice"])),
    ]
    result = list_users(PLATFORM, users, groups)
    assert result[0].groups == ("alice", "developers")
    assert result[0].is_system is False
