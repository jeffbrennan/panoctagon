from typing import Optional

import typer

from panoctagon.api.cli import (
    Division,
    OutputFormat,
    SortBy,
    compare_impl,
    event_impl,
    fight_impl,
    fighter_impl,
    leaderboard_impl,
    roster_impl,
    upcoming_impl,
)

app = typer.Typer(pretty_exceptions_enable=False)


@app.command()
def upcoming(
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Show upcoming UFC events and matchups."""
    upcoming_impl(fmt)


@app.command()
def leaderboard(
    division: Division | None = typer.Option(
        None, "--division", "-d", help="Filter by weight class"
    ),
    min_fights: int = typer.Option(5, "--min-fights", "-m", help="Minimum UFC fights"),
    limit: int = typer.Option(15, "--limit", "-l", help="Top N per division"),
    sort_by: SortBy = typer.Option(SortBy.win_rate, "--sort", "-s", help="Metric to sort by"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactively select division"
    ),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Show fighters ranked by win rate within each division."""
    leaderboard_impl(division, min_fights, limit, fmt, interactive, sort_by)


@app.command()
def fighter(
    name: str = typer.Argument(..., help="Fighter name"),
    history: int = typer.Option(
        None, "--history", "-H", help="Show extended fight history (specify number of fights)"
    ),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get detailed information about a fighter. Use --history to see extended fight history."""
    fighter_impl(name, fmt, history)


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
    name: str = typer.Argument(..., help="Fighter name to look up fights for"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get detailed statistics for a fight. Search by fighter name, then select a fight."""
    fight_impl(name, fmt)


@app.command()
def event(
    name: Optional[str] = typer.Argument(None, help="Event name to search for"),
    upcoming_only: bool = typer.Option(False, "--upcoming", "-u", help="Only show upcoming events"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum events"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """List UFC events, or view a specific event's card by name."""
    event_impl(name, upcoming_only, limit, fmt)


@app.command()
def roster(
    division: Division | None = typer.Option(
        None, "--division", "-d", help="Filter by weight class"
    ),
    min_fights: int = typer.Option(5, "--min-fights", "-m", help="Minimum UFC fights"),
    min_win_rate: Optional[float] = typer.Option(None, "--min-win-rate", help="Minimum win rate %"),
    max_win_rate: Optional[float] = typer.Option(None, "--max-win-rate", help="Maximum win rate %"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
    sort_by: SortBy = typer.Option(SortBy.full_name, "--sort", "-s", help="Metric to sort by"),
) -> None:
    """Search the UFC roster with filters."""
    roster_impl(division, min_fights, min_win_rate, max_win_rate, limit, fmt, sort_by)


if __name__ == "__main__":
    app()
