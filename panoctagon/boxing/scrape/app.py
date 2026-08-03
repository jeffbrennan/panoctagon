import time
from pathlib import Path
from typing import Optional

import typer
from sqlmodel import col

from panoctagon.boxing.scrape.events import download_results, download_schedule, get_event_pages
from panoctagon.boxing.scrape.fighters import download_boxer_pages
from panoctagon.common import (
    create_header,
    get_table_uids,
    report_stats,
    setup_panoctagon,
    write_data_to_db,
    write_parsing_timestamp,
)
from panoctagon.models import RunStats
from panoctagon.tables import BoxingEvent

app = typer.Typer()


@app.command()
def events() -> int:
    setup = setup_panoctagon(title="Panoctagon Boxing Event Scraper")
    existing_events = get_table_uids(col(BoxingEvent.event_uid))

    scraped_events_by_uid = {}
    for event in download_schedule() + download_results():
        if event.event_uid not in scraped_events_by_uid or event.title:
            scraped_events_by_uid[event.event_uid] = event
    scraped_events = list(scraped_events_by_uid.values())

    if existing_events is None:
        new_events = scraped_events
    else:
        new_events = [i for i in scraped_events if i.event_uid not in existing_events]

    if len(new_events) == 0:
        print("no new events. exiting early")
        print(setup.footer)
        return 0

    write_data_to_db(new_events)
    print(setup.footer)
    return len(new_events)


@app.command()
def event_pages(force: bool = False, max_downloads: Optional[int] = None) -> int:
    setup = setup_panoctagon(title="Panoctagon Boxing Event Page Scraper")

    start_time = time.time()
    n_downloaded = get_event_pages(force=force, max_downloads=max_downloads)
    end_time = time.time()

    report_stats(
        RunStats(
            start=start_time,
            end=end_time,
            n_ops=n_downloaded,
            op_name="event page",
            successes=n_downloaded,
            failures=0,
        )
    )

    if n_downloaded > 0:
        print(create_header(80, "UPDATING BOXING_EVENTS", True, "-"))
        updated_uids = [
            path.stem
            for path in (Path(__file__).parents[3] / "data/raw/boxing/events").glob("*.html")
            if path.stat().st_mtime >= start_time
        ]
        write_parsing_timestamp(
            BoxingEvent, "downloaded_ts", col(BoxingEvent.event_uid), updated_uids
        )

    print(setup.footer)
    return n_downloaded


@app.command()
def fighters(force: bool = False, max_downloads: Optional[int] = None) -> int:
    setup = setup_panoctagon(title="Panoctagon Boxing Fighter Scraper")

    start_time = time.time()
    n_downloaded = download_boxer_pages(force=force, max_downloads=max_downloads)
    end_time = time.time()

    report_stats(
        RunStats(
            start=start_time,
            end=end_time,
            n_ops=n_downloaded,
            op_name="boxer page",
            successes=n_downloaded,
            failures=0,
        )
    )

    print(setup.footer)
    return n_downloaded
