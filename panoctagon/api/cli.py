from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any, Optional

import httpx
import questionary
import typer

DEFAULT_API_URL = "http://localhost:8000"


class OutputFormat(str, Enum):
    json = "json"
    table = "table"


class SortBy(str, Enum):
    win_rate = "win_rate"
    sig_strikes = "sig_strikes"
    strike_accuracy = "strike_accuracy"
    takedowns = "takedowns"
    knockdowns = "knockdowns"
    ko_wins = "ko_wins"
    sub_wins = "sub_wins"
    opp_win_rate = "opp_win_rate"


def get_api_url() -> str:
    import os

    return os.environ.get("PANOCTAGON_API_URL", DEFAULT_API_URL)


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def select_fighter(name: str, prompt: Optional[str] = None) -> dict[str, Any]:
    fighters = api_request("/fighter", {"name": name, "limit": 20})

    if not fighters:
        typer.echo(f"No fighter found matching '{name}'", err=True)
        raise typer.Exit(1)

    if len(fighters) == 1:
        return fighters[0]

    if not is_interactive():
        return fighters[0]

    prompt_text = prompt or f"Multiple fighters match '{name}'. Select one:"
    choices = []
    for f in fighters:
        record = f"{f['wins']}-{f['losses']}-{f['draws']}"
        division = format_division(f.get("division"))
        label = f"{f['full_name']} ({record}) - {division}"
        choices.append(questionary.Choice(title=label, value=f))

    selected = questionary.select(
        prompt_text,
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask()

    if selected is None:
        raise typer.Exit(0)

    return selected


def select_event(name: str) -> dict[str, Any]:
    events = api_request("/event/search", {"name": name, "limit": 20})

    if not events:
        typer.echo(f"No event found matching '{name}'", err=True)
        raise typer.Exit(1)

    if len(events) == 1:
        return events[0]

    if not is_interactive():
        return events[0]

    choices = []
    for e in events:
        label = f"{e['title']} ({e['event_date']}) - {e['event_location']}"
        choices.append(questionary.Choice(title=label, value=e))

    selected = questionary.select(
        f"Multiple events match '{name}'. Select one:",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask()

    if selected is None:
        raise typer.Exit(0)

    return selected


def select_fight_from_fighter(fighter: dict[str, Any]) -> dict[str, Any]:
    fights = api_request(f"/fighter/{fighter['fighter_uid']}/fights", {"limit": 15})

    if not fights:
        typer.echo(f"No fights found for {fighter['full_name']}", err=True)
        raise typer.Exit(1)

    if not is_interactive():
        return fights[0]

    choices = []
    for f in fights:
        result = f.get("result") or "UPCOMING"
        decision = f.get("decision") or ""
        result_str = f"{result} ({decision})" if decision else result
        label = f"{f['event_date']} vs {f['opponent_name']} - {result_str}"
        choices.append(questionary.Choice(title=label, value=f))

    selected = questionary.select(
        f"Select a fight for {fighter['full_name']}:",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask()

    if selected is None:
        raise typer.Exit(0)

    return selected


def select_division() -> str:
    divisions = api_request("/divisions")

    if not divisions:
        typer.echo("No divisions found", err=True)
        raise typer.Exit(1)

    if not is_interactive():
        return divisions[0]

    choices = [questionary.Choice(title=format_division(d), value=d) for d in divisions]

    selected = questionary.select(
        "Select a division:",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask()

    if selected is None:
        raise typer.Exit(0)

    return selected


def format_table(data: list[dict[str, Any]], columns: Optional[list[str]] = None) -> str:
    from rich.console import Console
    from rich.table import Table

    if not data:
        return "No data found."

    if columns:
        data = [{k: row.get(k) for k in columns} for row in data]

    headers = list(data[0].keys())

    table = Table(show_header=True, header_style="bold", show_lines=True, padding=(0, 1))

    for header in headers:
        table.add_column(header)

    for row in data:
        cells = []
        for h in headers:
            val = row.get(h)
            cells.append("-" if val is None else str(val))
        table.add_row(*cells)

    console = Console()
    with console.capture() as capture:
        console.print(table)

    return capture.get().rstrip()


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
        typer.echo("Start the API server first: uv run panoctagon serve", err=True)
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", "Not found")
            typer.echo(f"Error: {detail}", err=True)
        else:
            typer.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        raise typer.Exit(1)


def format_division(div: Optional[str]) -> str:
    if not div:
        return "Unknown"
    return div.replace("_", " ").title()


def upcoming_impl(fmt: OutputFormat) -> None:
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

        rows = []
        for fight in event["fights"]:
            division = format_division(fight.get("fight_division"))
            title_marker = (
                " \\[TITLE]"
                if fight.get("fight_type") and "title" in fight["fight_type"].lower()
                else ""
            )
            rows.append(
                {
                    "fighter 1": f"[bold]{fight['fighter1_name']}[/bold]",
                    "f1\nrecord": fight["fighter1_record"],
                    "fighter 2": f"[bold]{fight['fighter2_name']}[/bold]",
                    "f2\nrecord": fight["fighter2_record"],
                    "division": f"{division}{title_marker}",
                }
            )

        typer.echo(format_table(rows))


def leaderboard_impl(
    division: Optional[str],
    min_fights: int,
    limit: int,
    fmt: OutputFormat,
    interactive: bool = False,
    sort_by: SortBy = SortBy.win_rate,
) -> None:
    if interactive and division is None and is_interactive():
        division = select_division()

    data = api_request(
        "/rankings",
        {"division": division, "min_fights": min_fights, "limit": limit, "sort_by": sort_by.value},
    )

    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    if not data:
        typer.echo("No rankings found.")
        return

    excluded_divisions = {"catch_weight", "open_weight"}
    data = [f for f in data if f.get("division") not in excluded_divisions]

    current_division = None
    rows: list[dict[str, Any]] = []
    for fighter in data:
        if fighter["division"] != current_division:
            if rows:
                typer.echo(format_table(rows))
            current_division = fighter["division"]
            div_display = format_division(current_division)
            typer.echo(f"\n{div_display}")
            rows = []

        record = f"{fighter['wins']}-{fighter['losses']}-{fighter['draws']}"
        rows.append(
            {
                "rank": fighter["rank"],
                "fighter": f"[bold]{fighter['full_name']}[/bold]",
                "record": record,
                "win%": f"{fighter['win_rate']:.1f}",
                "sig\nstrikes": f"{fighter['avg_sig_strikes']:.1f}",
                "strike\nacc%": f"{fighter['strike_accuracy']:.1f}",
                "TDs": f"{fighter['avg_takedowns']:.1f}",
                "KOs": fighter["ko_wins"],
                "subs": fighter["sub_wins"],
                "KDs": fighter["total_knockdowns"],
                "opp\nwin%": f"{fighter['opp_win_rate']:.1f}",
            }
        )

    if rows:
        typer.echo(format_table(rows))


def search_impl(name: str, division: Optional[str], limit: int, fmt: OutputFormat) -> None:
    data = api_request("/fighter", {"name": name, "division": division, "limit": limit})
    columns = ["full_name", "nickname", "stance", "division", "wins", "losses", "draws"]
    typer.echo(format_output(data, fmt, columns))


def fighter_impl(name: str, fmt: OutputFormat) -> None:
    fighter = select_fighter(name)
    data = api_request(f"/fighter/{fighter['fighter_uid']}")

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


def record_impl(name: str, fmt: OutputFormat) -> None:
    fighter = select_fighter(name)

    if fmt == OutputFormat.json:
        record_data = {
            "name": fighter["full_name"],
            "record": f"{fighter['wins']}-{fighter['losses']}-{fighter['draws']}",
            "wins": fighter["wins"],
            "losses": fighter["losses"],
            "draws": fighter["draws"],
        }
        typer.echo(json.dumps(record_data, indent=2))
        return

    record = f"{fighter['wins']}-{fighter['losses']}-{fighter['draws']}"
    typer.echo(f"{fighter['full_name']}: {record}")


def history_impl(name: str, limit: int, fmt: OutputFormat) -> None:
    fighter = select_fighter(name)
    data = api_request(f"/fighter/{fighter['fighter_uid']}")

    if fmt == OutputFormat.json:
        typer.echo(json.dumps(data["recent_fights"][:limit], indent=2, default=str))
        return

    bio = data["bio"]
    fights = data["recent_fights"][:limit]

    typer.echo(f"\n{bio['full_name']} - Fight History")
    typer.echo("=" * 70)

    for fight in fights:
        result = fight.get("result") or "UPCOMING"
        decision = fight.get("decision") or ""
        rd = f"R{fight['decision_round']}" if fight.get("decision_round") else ""

        result_str = f"{result}"
        if decision:
            result_str += f" ({decision}"
            if rd:
                result_str += f" {rd}"
            result_str += ")"

        typer.echo(f"{fight['event_date']}  vs {fight['opponent_name']:<25} {result_str}")


def compare_impl(fighter1: str, fighter2: str, fmt: OutputFormat) -> None:
    f1 = select_fighter(fighter1, prompt=f"Select first fighter ('{fighter1}'):")
    f2 = select_fighter(fighter2, prompt=f"Select second fighter ('{fighter2}'):")

    f1_detail = api_request(f"/fighter/{f1['fighter_uid']}")
    f2_detail = api_request(f"/fighter/{f2['fighter_uid']}")

    if fmt == OutputFormat.json:
        typer.echo(
            json.dumps({"fighter1": f1_detail, "fighter2": f2_detail}, indent=2, default=str)
        )
        return

    b1, r1 = f1_detail["bio"], f1_detail["record"]
    b2, r2 = f2_detail["bio"], f2_detail["record"]

    typer.echo(f"\n{'=' * 60}")
    typer.echo(f"{'TALE OF THE TAPE':^60}")
    typer.echo(f"{'=' * 60}")

    def compare_row(label: str, v1: Any, v2: Any) -> None:
        v1_str = str(v1) if v1 is not None else "-"
        v2_str = str(v2) if v2 is not None else "-"
        typer.echo(f"{v1_str:>25}  {label:^8}  {v2_str:<25}")

    compare_row("NAME", b1["full_name"], b2["full_name"])
    compare_row(
        "RECORD",
        f"{r1['wins']}-{r1['losses']}-{r1['draws']}",
        f"{r2['wins']}-{r2['losses']}-{r2['draws']}",
    )
    compare_row("STANCE", b1.get("stance"), b2.get("stance"))
    compare_row(
        "HEIGHT", f"{b1.get('height_inches') or '-'} in", f"{b2.get('height_inches') or '-'} in"
    )
    compare_row(
        "REACH", f"{b1.get('reach_inches') or '-'} in", f"{b2.get('reach_inches') or '-'} in"
    )

    win_pct_1 = round(r1["wins"] * 100 / r1["total_fights"], 1) if r1["total_fights"] > 0 else 0
    win_pct_2 = round(r2["wins"] * 100 / r2["total_fights"], 1) if r2["total_fights"] > 0 else 0
    compare_row("WIN %", f"{win_pct_1}%", f"{win_pct_2}%")

    typer.echo(f"{'=' * 60}")


def fight_impl(query: str, fmt: OutputFormat) -> None:
    fighter = select_fighter(query)
    fight = select_fight_from_fighter(fighter)
    fight_uid = fight["fight_uid"]

    data = api_request(f"/fight/{fight_uid}")

    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    typer.echo(f"\n{data['event_title']} - {data['event_date']}")
    typer.echo(f"{format_division(data.get('fight_division'))}")
    typer.echo("=" * 60)

    f1 = data["fighter1"]
    f2 = data["fighter2"]

    typer.echo(
        f"\n{f1['fighter_name']} ({f1['result'] or 'TBD'}) vs {f2['fighter_name']} ({f2['result'] or 'TBD'})"
    )

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
                    typer.echo(
                        f"  {fighter['fighter_name']}: Strikes {strikes}, TD {tds}, Ctrl {ctrl_str}"
                    )


def event_impl(name: Optional[str], upcoming_only: bool, limit: int, fmt: OutputFormat) -> None:
    if name:
        event = select_event(name)
        data = api_request(f"/event/{event['event_uid']}")

        if fmt == OutputFormat.json:
            typer.echo(format_output(data, fmt))
            return

        typer.echo(f"\n{data['title']}")
        typer.echo(f"{data['event_date']} - {data['event_location']}")
        typer.echo("=" * 60)

        for fight in data["fights"]:
            division = format_division(fight.get("fight_division"))
            fight_type = (
                " [TITLE]"
                if fight.get("fight_type") and "title" in fight["fight_type"].lower()
                else ""
            )

            r1 = fight.get("fighter1_result") or "TBD"
            r2 = fight.get("fighter2_result") or "TBD"
            decision = fight.get("decision") or ""

            typer.echo(f"\n{division}{fight_type}")
            typer.echo(f"  {fight['fighter1_name']} ({r1})")
            typer.echo("    vs")
            typer.echo(f"  {fight['fighter2_name']} ({r2})")
            if decision:
                rd = f" R{fight['decision_round']}" if fight.get("decision_round") else ""
                typer.echo(f"  Result: {decision}{rd}")
    else:
        data = api_request("/events", {"upcoming_only": upcoming_only, "limit": limit})
        columns = ["title", "event_date", "event_location", "num_fights"]
        typer.echo(format_output(data, fmt, columns))


def roster_impl(
    stance: Optional[str],
    division: Optional[str],
    min_fights: int,
    min_win_rate: Optional[float],
    max_win_rate: Optional[float],
    limit: int,
    fmt: OutputFormat,
) -> None:
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
