from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

import httpx
import typer

app = typer.Typer(
    name="data",
    help="Query UFC fight data from the API",
    pretty_exceptions_enable=False,
)

DEFAULT_API_URL = "http://localhost:8000"


class OutputFormat(str, Enum):
    json = "json"
    table = "table"


def get_api_url() -> str:
    import os

    return os.environ.get("PANOCTAGON_API_URL", DEFAULT_API_URL)


def format_table(data: list[dict[str, Any]], columns: Optional[list[str]] = None) -> str:
    if not data:
        return "No data found."

    if columns:
        data = [{k: row.get(k) for k in columns} for row in data]

    headers = list(data[0].keys())

    col_widths = {}
    for header in headers:
        max_width = len(str(header))
        for row in data:
            val = row.get(header)
            val_str = "-" if val is None else str(val)
            max_width = max(max_width, len(val_str))
        col_widths[header] = min(max_width, 40)

    header_row = "| " + " | ".join(str(h).ljust(col_widths[h]) for h in headers) + " |"
    separator = "|-" + "-|-".join("-" * col_widths[h] for h in headers) + "-|"

    rows = []
    for row in data:
        cells = []
        for h in headers:
            val = row.get(h)
            val_str = "-" if val is None else str(val)
            if len(val_str) > 40:
                val_str = val_str[:37] + "..."
            cells.append(val_str.ljust(col_widths[h]))
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_row, separator] + rows)


def format_output(data: Any, fmt: OutputFormat, columns: Optional[list[str]] = None) -> str:
    if fmt == OutputFormat.json:
        return json.dumps(data, indent=2, default=str)

    if isinstance(data, list):
        return format_table(data, columns)
    elif isinstance(data, dict):
        return format_table([data], columns)
    else:
        return str(data)


def api_request(endpoint: str, params: Optional[dict[str, Any]] = None) -> Any:
    url = f"{get_api_url()}{endpoint}"
    params = {k: v for k, v in (params or {}).items() if v is not None}

    try:
        response = httpx.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        typer.echo(f"Error: Could not connect to API at {get_api_url()}", err=True)
        typer.echo("Make sure the API server is running: uv run panoctagon serve", err=True)
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", "Not found")
            typer.echo(f"Error: {detail}", err=True)
        else:
            typer.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        raise typer.Exit(1)


@app.command("fighter")
def fighter_search(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Search by fighter name"),
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by weight class"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Search for fighters by name or division."""
    data = api_request("/fighter", {"name": name, "division": division, "limit": limit})
    columns = ["full_name", "nickname", "stance", "division", "wins", "losses", "draws"]
    typer.echo(format_output(data, fmt, columns))


@app.command("fighter-detail")
def fighter_detail(
    fighter_uid: str = typer.Argument(..., help="Fighter UID"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get detailed information about a specific fighter."""
    data = api_request(f"/fighter/{fighter_uid}")

    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    bio = data["bio"]
    record = data["record"]
    fights = data["recent_fights"]

    typer.echo(f"\n{bio['full_name']}")
    if bio.get("nickname"):
        typer.echo(f'"{bio["nickname"]}"')
    typer.echo("-" * 40)

    typer.echo(f"Record: {record['wins']}-{record['losses']}-{record['draws']}")
    if record.get("no_contests"):
        typer.echo(f"No Contests: {record['no_contests']}")

    typer.echo(f"\nStance: {bio.get('stance') or '-'}")
    typer.echo(f"Height: {bio.get('height_inches') or '-'} in")
    typer.echo(f"Reach: {bio.get('reach_inches') or '-'} in")
    if bio.get("dob"):
        typer.echo(f"DOB: {bio['dob']}")
    if bio.get("place_of_birth"):
        typer.echo(f"From: {bio['place_of_birth']}")

    if fights:
        typer.echo("\nRecent Fights:")
        typer.echo("-" * 40)
        columns = ["event_date", "opponent_name", "result", "decision"]
        typer.echo(format_table(fights, columns))


@app.command("upcoming")
def upcoming_fights(
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """List upcoming UFC events and matchups."""
    data = api_request("/upcoming")

    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    if not data:
        typer.echo("No upcoming events found.")
        return

    for event in data:
        typer.echo(f"\n{event['event_title']}")
        typer.echo(f"{event['event_date']} - {event['event_location']}")
        typer.echo("=" * 60)

        for fight in event["fights"]:
            division = fight.get("fight_division") or "TBD"
            division = division.replace("_", " ").title() if division else "TBD"
            fight_type = " [TITLE]" if fight.get("fight_type") and "title" in fight["fight_type"].lower() else ""

            typer.echo(f"\n{division}{fight_type}")
            f1 = f"{fight['fighter1_name']} ({fight['fighter1_record']})"
            f2 = f"{fight['fighter2_name']} ({fight['fighter2_record']})"
            typer.echo(f"  {f1}")
            typer.echo(f"    vs")
            typer.echo(f"  {f2}")


@app.command("rankings")
def rankings(
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by weight class"),
    min_fights: int = typer.Option(5, "--min-fights", "-m", help="Minimum UFC fights"),
    limit: int = typer.Option(15, "--limit", "-l", help="Top N per division"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Show fighter rankings by win rate within each division."""
    data = api_request("/rankings", {"division": division, "min_fights": min_fights, "limit": limit})

    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    if not data:
        typer.echo("No rankings found.")
        return

    current_division = None
    for fighter in data:
        if fighter["division"] != current_division:
            current_division = fighter["division"]
            div_display = current_division.replace("_", " ").title() if current_division else "Unknown"
            typer.echo(f"\n{div_display}")
            typer.echo("-" * 50)
            typer.echo(f"{'Rank':<5} {'Fighter':<25} {'Record':<12} {'Win%':<6}")
            typer.echo("-" * 50)

        record = f"{fighter['wins']}-{fighter['losses']}-{fighter['draws']}"
        typer.echo(f"{fighter['rank']:<5} {fighter['full_name']:<25} {record:<12} {fighter['win_rate']:<6.1f}")


@app.command("roster")
def roster(
    stance: Optional[str] = typer.Option(None, "--stance", "-s", help="Filter by stance"),
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by weight class"),
    min_fights: int = typer.Option(5, "--min-fights", "-m", help="Minimum UFC fights"),
    min_win_rate: Optional[float] = typer.Option(None, "--min-win-rate", help="Minimum win rate %"),
    max_win_rate: Optional[float] = typer.Option(None, "--max-win-rate", help="Maximum win rate %"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Search the UFC roster with filters for stance, division, and statistics."""
    data = api_request(
        "/roster",
        {
            "stance": stance,
            "division": division,
            "min_fights": min_fights,
            "min_win_rate": min_win_rate,
            "max_win_rate": max_win_rate,
            "limit": limit,
        },
    )
    columns = [
        "full_name",
        "stance",
        "division",
        "wins",
        "losses",
        "win_rate",
        "avg_strikes_landed",
        "avg_strikes_absorbed",
    ]
    typer.echo(format_output(data, fmt, columns))


@app.command("events")
def events(
    upcoming_only: bool = typer.Option(False, "--upcoming", "-u", help="Only show upcoming events"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum events"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """List UFC events."""
    data = api_request("/events", {"upcoming_only": upcoming_only, "limit": limit})
    columns = ["title", "event_date", "event_location", "num_fights"]
    typer.echo(format_output(data, fmt, columns))


@app.command("fight")
def fight_detail(
    fight_uid: str = typer.Argument(..., help="Fight UID"),
    fmt: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """Get detailed statistics for a specific fight."""
    data = api_request(f"/fight/{fight_uid}")

    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    typer.echo(f"\n{data['event_title']} - {data['event_date']}")
    division = data.get("fight_division") or "Unknown"
    division = division.replace("_", " ").title() if division else "Unknown"
    typer.echo(f"{division}")
    typer.echo("=" * 60)

    f1 = data["fighter1"]
    f2 = data["fighter2"]

    typer.echo(f"\n{f1['fighter_name']} ({f1['result'] or 'TBD'}) vs {f2['fighter_name']} ({f2['result'] or 'TBD'})")

    if data.get("decision"):
        typer.echo(f"Result: {data['decision']}")
        if data.get("decision_round"):
            typer.echo(f"Round: {data['decision_round']}")

    if f1["rounds"] or f2["rounds"]:
        typer.echo("\nRound-by-Round Stats:")
        typer.echo("-" * 60)

        max_rounds = max(len(f1["rounds"]), len(f2["rounds"]))
        for r in range(max_rounds):
            typer.echo(f"\nRound {r + 1}:")
            for fighter in [f1, f2]:
                if r < len(fighter["rounds"]):
                    rd = fighter["rounds"][r]
                    strikes = f"{rd.get('total_strikes_landed') or 0}/{rd.get('total_strikes_attempted') or 0}"
                    tds = f"{rd.get('takedowns_landed') or 0}/{rd.get('takedowns_attempted') or 0}"
                    ctrl = rd.get("control_time_seconds") or 0
                    ctrl_str = f"{ctrl // 60}:{ctrl % 60:02d}" if ctrl else "-"
                    typer.echo(f"  {fighter['fighter_name']}: Strikes {strikes}, TD {tds}, Ctrl {ctrl_str}")


if __name__ == "__main__":
    app()
