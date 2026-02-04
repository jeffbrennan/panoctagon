from __future__ import annotations

import json
import sys
from enum import Enum, StrEnum, auto
from typing import Any, Optional

import httpx
import questionary
import typer

from panoctagon.enums import format_decision, format_division

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
    full_name = "full_name"


class Division(StrEnum):
    LIGHTWEIGHT = auto()
    WELTERWEIGHT = auto()
    MIDDLEWEIGHT = auto()
    LIGHT_HEAVYWEIGHT = auto()
    HEAVYWEIGHT = auto()
    FLYWEIGHT = auto()
    BANTAMWEIGHT = auto()
    FEATHERWEIGHT = auto()
    STRAWWEIGHT = auto()
    WOMENS_STRAWWEIGHT = auto()
    WOMENS_FLYWEIGHT = auto()
    WOMENS_BANTAMWEIGHT = auto()
    WOMENS_FEATHERWEIGHT = auto()


def get_api_url() -> str:
    import os

    return os.environ.get("PANOCTAGON_API_URL", DEFAULT_API_URL)


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def select_fighter(name: str | None, prompt: Optional[str] = None) -> dict[str, Any]:
    fighters = api_request("/fighter", {"name": name, "limit": 20})

    if not fighters:
        typer.echo(f"No fighter found matching '{name}'", err=True)
        raise typer.Exit(1)

    if len(fighters) == 1:
        return fighters[0]

    if not is_interactive():
        return fighters[0]

    if name is not None:
        prompt_text = prompt or f"Multiple fighters match '{name}'. Select one:"
    else:
        prompt_text = prompt or "Select a fighter"

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


def select_division() -> Division:
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

    return Division(selected)


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
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", "Not found")
            typer.echo(f"Error: {detail}", err=True)
        else:
            typer.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        raise typer.Exit(1)


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
    division: Division | None,
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
    data = [f for f in data if f.get("division").lower() not in excluded_divisions]

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


def fighter_impl(name: str, fmt: OutputFormat, history_limit: Optional[int] = None) -> None:
    from rich.console import Console
    from rich.table import Table

    fighter = select_fighter(name)
    fighter_uid = fighter["fighter_uid"]
    data = api_request(f"/fighter/{fighter_uid}")
    stats = api_request(f"/fighter/{fighter_uid}/stats")

    if history_limit:
        fights = api_request(f"/fighter/{fighter_uid}/fights", {"limit": history_limit})
    else:
        fights = data["recent_fights"]

    if fmt == OutputFormat.json:
        output = {**data, "stats": stats}
        if history_limit:
            output["fights"] = fights
        typer.echo(format_output(output, fmt))
        return

    bio = data["bio"]
    record = data["record"]

    console = Console()

    console.print(f"\n[bold]{bio['full_name']}[/bold]")
    if bio.get("nickname"):
        console.print(f'[dim]"{bio["nickname"]}"[/dim]')

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column(style="dim")
    info_table.add_column()

    info_table.add_row("Record", f"{record['wins']}-{record['losses']}-{record['draws']}")
    if record.get("no_contests"):
        info_table.add_row("No Contests", str(record["no_contests"]))
    info_table.add_row("Stance", bio.get("stance") or "-")
    info_table.add_row("Height", f"{bio.get('height_inches') or '-'} in")
    info_table.add_row("Reach", f"{bio.get('reach_inches') or '-'} in")
    if bio.get("dob"):
        info_table.add_row("DOB", bio["dob"])
    if bio.get("place_of_birth"):
        info_table.add_row("From", bio["place_of_birth"])

    console.print(info_table)

    def stat_val(v: Any, suffix: str = "") -> str:
        return f"{v}{suffix}" if v is not None else "-"

    console.print("\n[bold]Career Stats:[/bold]")
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column(style="dim")
    stats_table.add_column()

    stats_table.add_row("Sig Strikes/Rd", stat_val(stats.get("avg_sig_strikes")))
    stats_table.add_row("Strike Accuracy", stat_val(stats.get("strike_accuracy"), "%"))
    stats_table.add_row("Takedowns/Rd", stat_val(stats.get("avg_takedowns")))
    stats_table.add_row("KO Wins", str(stats.get("ko_wins", 0)))
    stats_table.add_row("Sub Wins", str(stats.get("sub_wins", 0)))
    stats_table.add_row("Dec Wins", str(stats.get("dec_wins", 0)))
    stats_table.add_row("Knockdowns", str(stats.get("total_knockdowns", 0)))
    stats_table.add_row("Opp Win Rate", stat_val(stats.get("avg_opp_win_rate"), "%"))

    console.print(stats_table)

    if history_limit:
        console.print(f"\n[bold]Fight History[/bold] ({len(fights)} fights):")
    else:
        console.print("\n[bold]Recent Fights:[/bold]")

    if fights:
        rows = []
        for fight in fights:
            result = fight.get("result") or "UPCOMING"
            decision = fight.get("decision") or "-"
            rd = f"R{fight.get('decision_round')}" if fight.get("decision_round") else "-"

            result_style = (
                "[green]WIN[/green]"
                if result == "WIN"
                else "[red]LOSS[/red]"
                if result == "LOSS"
                else result
            )
            rows.append(
                {
                    "date": fight.get("event_date"),
                    "opponent": f"[bold]{fight.get('opponent_name')}[/bold]",
                    "result": result_style,
                    "decision": format_decision(decision),
                    "round": rd,
                }
            )
        typer.echo(format_table(rows))


def compare_impl(fighter1: str, fighter2: str, fmt: OutputFormat) -> None:
    from rich.console import Console
    from rich.table import Table

    f1 = select_fighter(fighter1, prompt=f"Select first fighter ('{fighter1}'):")
    f2 = select_fighter(fighter2, prompt=f"Select second fighter ('{fighter2}'):")

    f1_detail = api_request(f"/fighter/{f1['fighter_uid']}")
    f2_detail = api_request(f"/fighter/{f2['fighter_uid']}")
    f1_stats = api_request(f"/fighter/{f1['fighter_uid']}/stats")
    f2_stats = api_request(f"/fighter/{f2['fighter_uid']}/stats")

    if fmt == OutputFormat.json:
        typer.echo(
            json.dumps(
                {
                    "fighter1": {**f1_detail, "stats": f1_stats},
                    "fighter2": {**f2_detail, "stats": f2_stats},
                },
                indent=2,
                default=str,
            )
        )
        return

    b1, r1 = f1_detail["bio"], f1_detail["record"]
    b2, r2 = f2_detail["bio"], f2_detail["record"]
    s1, s2 = f1_stats, f2_stats

    table = Table(title="TALE OF THE TAPE", show_header=False, show_lines=True, padding=(0, 2))
    table.add_column(justify="right", style="bold")
    table.add_column(justify="center", style="dim")
    table.add_column(justify="left", style="bold")

    def compare_vals(
        v1: Any, v2: Any, higher_better: bool = True, suffix: str = ""
    ) -> tuple[str, str]:
        if v1 is None and v2 is None:
            return "-", "-"
        if v1 is None:
            return "-", f"[green]{v2}{suffix}[/green]"
        if v2 is None:
            return f"[green]{v1}{suffix}[/green]", "-"

        s1_str = f"{v1}{suffix}"
        s2_str = f"{v2}{suffix}"

        if v1 == v2:
            return s1_str, s2_str
        if (v1 > v2) == higher_better:
            return f"[green]{s1_str}[/green]", f"[red]{s2_str}[/red]"
        return f"[red]{s1_str}[/red]", f"[green]{s2_str}[/green]"

    win_pct_1 = round(r1["wins"] * 100 / r1["total_fights"], 1) if r1["total_fights"] > 0 else 0
    win_pct_2 = round(r2["wins"] * 100 / r2["total_fights"], 1) if r2["total_fights"] > 0 else 0

    table.add_row(f"[bold]{b1['full_name']}[/bold]", "NAME", f"[bold]{b2['full_name']}[/bold]")

    r1_str = f"{r1['wins']}-{r1['losses']}-{r1['draws']}"
    r2_str = f"{r2['wins']}-{r2['losses']}-{r2['draws']}"

    table.add_row(r1_str, "RECORD", r2_str)
    table.add_row(str(b1.get("stance") or "-"), "STANCE", str(b2.get("stance") or "-"))

    h1, h2 = compare_vals(b1.get("height_inches"), b2.get("height_inches"), suffix=" in")
    table.add_row(h1, "HEIGHT", h2)

    rc1, rc2 = compare_vals(b1.get("reach_inches"), b2.get("reach_inches"), suffix=" in")
    table.add_row(rc1, "REACH", rc2)

    w1, w2 = compare_vals(win_pct_1, win_pct_2, suffix="%")
    table.add_row(w1, "WIN %", w2)

    sig1, sig2 = compare_vals(s1.get("avg_sig_strikes"), s2.get("avg_sig_strikes"))
    table.add_row(sig1, "SIG STRIKES/RD", sig2)

    acc1, acc2 = compare_vals(s1.get("strike_accuracy"), s2.get("strike_accuracy"), suffix="%")
    table.add_row(acc1, "STRIKE ACC", acc2)

    td1, td2 = compare_vals(s1.get("avg_takedowns"), s2.get("avg_takedowns"))
    table.add_row(td1, "TAKEDOWNS/RD", td2)

    ko1, ko2 = compare_vals(s1.get("ko_wins", 0), s2.get("ko_wins", 0))
    table.add_row(ko1, "KO WINS", ko2)

    sub1, sub2 = compare_vals(s1.get("sub_wins", 0), s2.get("sub_wins", 0))
    table.add_row(sub1, "SUB WINS", sub2)

    kd1, kd2 = compare_vals(s1.get("total_knockdowns", 0), s2.get("total_knockdowns", 0))
    table.add_row(kd1, "KNOCKDOWNS", kd2)

    opp1, opp2 = compare_vals(s1.get("avg_opp_win_rate"), s2.get("avg_opp_win_rate"), suffix="%")
    table.add_row(opp1, "OPP WIN RATE", opp2)

    console = Console()
    typer.echo("")
    console.print(table)


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
    division: Division | None,
    min_fights: int,
    min_win_rate: Optional[float],
    max_win_rate: Optional[float],
    limit: int,
    fmt: OutputFormat,
    sort_by: SortBy,
) -> None:
    data = api_request(
        "/roster",
        {
            "division": division,
            "min_fights": min_fights,
            "min_win_rate": min_win_rate,
            "max_win_rate": max_win_rate,
            "limit": limit,
            "sort_by": sort_by.value,
        },
    )
    if fmt == OutputFormat.json:
        typer.echo(format_output(data, fmt))
        return

    rows = []
    for record in data:
        rows.append(
            {
                "name": record["full_name"],
                "stance": record["stance"],
                "division": format_division(record["division"]),
                "wins": record["wins"],
                "losses": record["losses"],
                "win rate": record["win_rate"],
                "opponent\nwin rate": record["opp_win_rate"],
                "strike\naccuracy": record["strike_accuracy"],
                "average\nsig strikes": record["avg_sig_strikes"],
                "total\nknockdowns": record["total_knockdowns"],
                "average\ntakedowns": record["avg_takedowns"],
                "ko\nwins": record["ko_wins"],
                "sub\nwins": record["sub_wins"],
            }
        )

    typer.echo(format_table(rows))
