from typer.testing import CliRunner

from panoctagon.admin import app


runner = CliRunner()


def test_admin_help_lists_boxing() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "boxing" in result.stdout


def test_boxing_scrape_help_lists_commands() -> None:
    result = runner.invoke(app, ["boxing", "scrape", "--help"])

    assert result.exit_code == 0
    assert "events" in result.stdout
    assert "event-pages" in result.stdout
    assert "fighters" in result.stdout


def test_boxing_parse_help_lists_commands() -> None:
    result = runner.invoke(app, ["boxing", "parse", "--help"])

    assert result.exit_code == 0
    assert "events" in result.stdout
    assert "fighters" in result.stdout
