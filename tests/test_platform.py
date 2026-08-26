from pathlib import Path

from userdock.platform import detect_platform


def test_detects_distribution_family_and_policy(tmp_path: Path):
    os_release = tmp_path / "os-release"
    os_release.write_text('ID="ubuntu"\nPRETTY_NAME="Ubuntu Test"\n', encoding="utf-8")
    login_defs = tmp_path / "login.defs"
    login_defs.write_text(
        "UID_MIN 1000\nUID_MAX 60000\nGID_MIN 1000\nGID_MAX 60000\n",
        encoding="utf-8",
    )
    result = detect_platform(os_release, login_defs)
    assert result.distro_family == "debian"
    assert result.distro_name == "Ubuntu Test"
    assert result.user_uid_min == 1000
    assert result.user_gid_min == 1000
    assert result.user_uid_max == 60000
    assert result.user_gid_max == 60000
