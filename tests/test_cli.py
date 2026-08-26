from userdock.cli import main


def test_cli_help(capsys):
    try:
        main(["--help"])
    except SystemExit as error:
        assert error.code == 0

    assert "Manage local Linux users and groups" in capsys.readouterr().out


def test_cli_reports_version(capsys):
    try:
        main(["--version"])
    except SystemExit as error:
        assert error.code == 0

    assert "userdock 1.0.2" in capsys.readouterr().out


def test_cli_requires_administrator_privileges(monkeypatch, capsys):
    monkeypatch.setattr("userdock.cli.os.geteuid", lambda: 1000)
    assert main(["system", "doctor"]) == 1
    assert "requires administrator privileges" in capsys.readouterr().err
