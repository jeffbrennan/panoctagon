import typer
from sqlmodel import col

from panoctagon.boxing.parse.events import parse_event_page, write_fight_results_to_db
from panoctagon.boxing.paths import events_dir
from panoctagon.common import get_html_files, setup_panoctagon
from panoctagon.tables import BoxingFight

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
    write_fight_results_to_db(results, force)

    print(setup.footer)
    return len(results)
