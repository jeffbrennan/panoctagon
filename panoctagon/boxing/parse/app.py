import typer
from sqlmodel import col

from panoctagon.boxing.parse.events import (
    apply_match_results,
    parse_event_page,
    parse_match_page,
    write_fight_results_to_db,
)
from panoctagon.boxing.parse.fighters import parse_fighter, write_fighter_results_to_db
from panoctagon.boxing.paths import events_dir, fighters_dir, matches_dir
from panoctagon.common import get_html_files, setup_panoctagon
from panoctagon.tables import BoxingFight, BoxingFighter

app = typer.Typer()


@app.command(name="events")
def events(force: bool = False) -> int:
    setup = setup_panoctagon(title="Panoctagon Boxing Event Page Parser")

    event_pages = get_html_files(
        path=events_dir(),
        uid_col=col(BoxingFight.event_uid),
        where_clause=None,
        force_run=force,
    )

    if len(event_pages) == 0:
        print("no event pages to parse. exiting early")
        print(setup.footer)
        return 0

    results = [parse_event_page(event_page) for event_page in event_pages]
    match_pages = get_html_files(
        path=matches_dir(),
        uid_col=col(BoxingFight.match_uid),
        where_clause=None,
        force_run=True,
    )
    match_results = [parse_match_page(match_page) for match_page in match_pages]
    for result in results:
        apply_match_results(result.result, match_results)
    write_fight_results_to_db(results, force)

    print(setup.footer)
    return len(results)


@app.command(name="fighters")
def fighters(force: bool = False) -> int:
    setup = setup_panoctagon(title="Panoctagon Boxing Fighter Parser")

    fighter_pages = get_html_files(
        path=fighters_dir(),
        uid_col=col(BoxingFighter.fighter_uid),
        where_clause=None,
        force_run=force,
    )

    if len(fighter_pages) == 0:
        print("no fighters to parse. exiting early")
        print(setup.footer)
        return 0

    results = [parse_fighter(fighter_page) for fighter_page in fighter_pages]
    write_fighter_results_to_db(results, force)

    print(setup.footer)
    return len(results)
