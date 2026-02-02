from typing import Optional

import typer

import panoctagon.one.one as one
import panoctagon.ufc.app as ufc
from panoctagon.api.cli import (
    OutputFormat,
    compare_impl,
    event_impl,
    fight_impl,
    fighter_impl,
    history_impl,
    rankings_impl,
    record_impl,
    roster_impl,
    search_impl,
    upcoming_impl,
)

app = typer.Typer(pretty_exceptions_enable=False)
app.add_typer(ufc.app, name="ufc")
app.add_typer(one.app, name="one")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
) -> None:
    """Start the Panoctagon API server."""
    import uvicorn

    uvicorn.run(
        "panoctagon.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def upcoming(
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Show upcoming UFC events and matchups."""
    upcoming_impl(fmt)


@app.command()
def rankings(
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by weight class"),
    min_fights: int = typer.Option(5, "--min-fights", "-m", help="Minimum UFC fights"),
    limit: int = typer.Option(15, "--limit", "-l", help="Top N per division"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Show fighter rankings by win rate within each division."""
    rankings_impl(division, min_fights, limit, fmt)


@app.command()
def search(
    name: str = typer.Argument(..., help="Fighter name to search"),
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by weight class"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Search for fighters by name."""
    search_impl(name, division, limit, fmt)


@app.command()
def fighter(
    name: str = typer.Argument(..., help="Fighter name"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get detailed information about a fighter."""
    fighter_impl(name, fmt)


@app.command()
def record(
    name: str = typer.Argument(..., help="Fighter name"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get a fighter's win-loss-draw record."""
    record_impl(name, fmt)


@app.command()
def history(
    name: str = typer.Argument(..., help="Fighter name"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of fights to show"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Show a fighter's fight history."""
    history_impl(name, limit, fmt)


@app.command()
def compare(
    fighter1: str = typer.Argument(..., help="First fighter name"),
    fighter2: str = typer.Argument(..., help="Second fighter name"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Compare two fighters side-by-side."""
    compare_impl(fighter1, fighter2, fmt)


@app.command()
def fight(
    fight_uid: str = typer.Argument(..., help="Fight UID"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get detailed statistics for a specific fight."""
    fight_impl(fight_uid, fmt)


@app.command()
def event(
    upcoming_only: bool = typer.Option(False, "--upcoming", "-u", help="Only show upcoming events"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum events"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """List UFC events."""
    event_impl(upcoming_only, limit, fmt)


@app.command()
def roster(
    stance: Optional[str] = typer.Option(None, "--stance", "-s", help="Filter by stance"),
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by weight class"),
    min_fights: int = typer.Option(5, "--min-fights", "-m", help="Minimum UFC fights"),
    min_win_rate: Optional[float] = typer.Option(None, "--min-win-rate", help="Minimum win rate %"),
    max_win_rate: Optional[float] = typer.Option(None, "--max-win-rate", help="Maximum win rate %"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Search the UFC roster with filters."""
    roster_impl(stance, division, min_fights, min_win_rate, max_win_rate, limit, fmt)


if __name__ == "__main__":
    app()
