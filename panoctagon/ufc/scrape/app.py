import random
import time
from pathlib import Path
from typing import Optional

import typer
from sqlmodel import col

from panoctagon.common import (
    create_header,
    delete_existing_records,
    get_table_uids,
    report_stats,
    setup_panoctagon,
    write_data_to_db,
    write_parsing_timestamp,
)
from panoctagon.models import RunStats
from panoctagon.tables import UFCEvent
from panoctagon.ufc.scrape.bios import (
    get_fighter_bio,
    get_fighters_to_download,
    get_unparsed_fighters,
)
from panoctagon.ufc.scrape.events import get_events
from panoctagon.ufc.scrape.fighters import (
    FighterToScrape,
    get_all_fighter_uids,
    scrape_fighter,
)
from panoctagon.ufc.scrape.fights import (
    EventToParse,
    get_fights_from_event,
    read_event_uids,
)

app = typer.Typer()


@app.command()
def events(force: bool = False) -> int:
    setup = setup_panoctagon(title="Panoctagon UFC Event Scraper")
    existing_events = get_table_uids(col(UFCEvent.event_uid))

    if force and existing_events is not None:
        delete_existing_records(UFCEvent, col(UFCEvent.event_uid), uids=existing_events)
        existing_events = None

    all_events = existing_events is None or force
    scraped_events = get_events(all_events)

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
def bios(force: bool = False, n: Optional[int] = None) -> int:
    setup = setup_panoctagon(title="Panoctagon Fighter Bio Scraper")
    output_dir = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "fighter_bios"
    output_dir.mkdir(exist_ok=True, parents=True)

    fighters_to_download = get_unparsed_fighters()

    fighters_to_download = get_fighters_to_download(fighters_to_download, output_dir, force)
    if n:
        fighters_to_download = random.sample(fighters_to_download, n)

    n_fighters_to_download = len(fighters_to_download)

    start_header = create_header(80, f"SCRAPING n={n_fighters_to_download} Fighter Bios", True, "-")
    print(start_header)
    start_time = time.time()
    results = [
        get_fighter_bio(fighter, output_dir, i, len(fighters_to_download))
        for i, fighter in enumerate(fighters_to_download, 1)
    ]

    end_time = time.time()
    bios_downloaded = 0
    bios_deleted = 0
    for result in results:
        if result.write is None:
            continue
        for write in result.write:
            if write.success:
                bios_downloaded += 1
            else:
                bios_deleted += 1

    report_stats(
        RunStats(
            start=start_time,
            end=end_time,
            n_ops=n_fighters_to_download,
            op_name="fighter bio",
            successes=bios_downloaded,
            failures=bios_deleted,
        )
    )
    print(setup.footer)
    return bios_downloaded


@app.command()
def fighters() -> int:
    setup = setup_panoctagon(
        "Panoctagon UFC Fighter Scraper",
    )

    output_dir = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "fighters"
    output_dir.mkdir(exist_ok=True, parents=True)

    all_fighter_uids = get_all_fighter_uids()

    scraped_fighters = [i.stem for i in output_dir.glob("*.html")]
    unscraped_fighters = [i for i in all_fighter_uids if i not in scraped_fighters]

    n_fighters = len(unscraped_fighters)

    if n_fighters == 0:
        print("no new fighters!")
        report_stats(
            RunStats(
                start=setup.start_time,
                end=time.time(),
                successes=0,
                failures=0,
                n_ops=None,
                op_name="fighter",
            )
        )
        print(setup.footer)
        return 0

    fighters_to_scrape = [
        FighterToScrape(uid=uid, i=i, n_fighters=n_fighters, base_dir=output_dir)
        for i, uid in enumerate(unscraped_fighters)
    ]

    print(create_header(80, f"SCRAPING n={n_fighters} fighters", True, "-"))
    results = [scrape_fighter(i) for i in fighters_to_scrape]

    successes = [i for i in results if i.success]
    n_successes = len(successes)
    failures = len(results) - n_successes

    report_stats(
        RunStats(
            start=setup.start_time,
            end=time.time(),
            successes=n_successes,
            failures=failures,
            n_ops=n_fighters,
            op_name="fighter",
        )
    )
    print(setup.footer)
    return n_successes


@app.command()
def fights(force: bool = False) -> int:
    setup = setup_panoctagon(title="Panoctagon UFC Fight Scraper")

    output_dir = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "fights"
    output_dir.mkdir(exist_ok=True, parents=True)

    event_uids = read_event_uids(force)
    n_events = len(event_uids)
    if n_events == 0:
        print("No events to parse. Exiting!")
        print(setup.footer)
        return 0

    events_to_parse = [
        EventToParse(uid=uid, i=i, n_events=n_events, base_dir=output_dir)
        for i, uid in enumerate(event_uids)
    ]

    start_header = create_header(80, f"SCRAPING n={len(events_to_parse)} UFC EVENTS", True, "-")
    print(start_header)
    start_time = time.time()

    results = [get_fights_from_event(event, force) for event in events_to_parse]
    end_time = time.time()

    fights_downloaded = 0
    fights_deleted = 0
    for result in results:
        if result.write is None:
            continue
        if result.message in ["no fight uids parsed", "no files to download"]:
            continue
        for write in result.write:
            if write.success:
                fights_downloaded += 1
            else:
                fights_deleted += 1

    report_stats(
        RunStats(
            start=start_time,
            end=end_time,
            n_ops=n_events,
            op_name="event",
            successes=fights_downloaded,
            failures=fights_deleted,
        )
    )

    successful_results = [i for i in results if i.success and i.message is None]
    if len(successful_results) > 0:
        print(create_header(80, "UPDATING UFC_EVENTS", True, "-"))
        success_uids = [i.event.uid for i in successful_results]
        write_parsing_timestamp(UFCEvent, "downloaded_ts", col(UFCEvent.event_uid), success_uids)

    print(setup.footer)
    return len(successful_results)
