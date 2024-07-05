import argparse
import datetime
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import bs4
import requests
from sqlmodel import Session, and_, col, select

from panoctagon.common import (
    create_header,
    get_engine,
    get_table_rows,
    report_stats,
    scrape_page,
)
from panoctagon.enums import Symbols
from panoctagon.models import RunStats, ScrapingConfig, ScrapingWriteResult
from panoctagon.tables import UFCEvent


@dataclass
class EventToParse:
    uid: str
    i: int
    n_events: int
    base_dir: Path


@dataclass
class FightScrapingResult:
    event: EventToParse
    success: bool
    n_fight_links: Optional[int]
    write: Optional[list[ScrapingWriteResult]]
    message: Optional[str]


def read_event_uids(force_run: bool) -> list[str]:
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    if force_run:
        cmd = select(UFCEvent.event_uid).where(col(UFCEvent.event_date) < now)
    else:

        cmd = select(UFCEvent.event_uid).where(
            and_(col(UFCEvent.downloaded_ts).is_(None), UFCEvent.event_date < now)
        )

    engine = get_engine()
    with Session(engine) as session:
        uids = session.exec(cmd).all()
    return list(uids)


def get_list_of_fights(soup: bs4.BeautifulSoup) -> list[str]:
    rows = get_table_rows(soup)
    fight_uids: list[str] = []

    for row in rows:
        if row.a is None:
            continue

        row_href = row.a["href"]

        if not isinstance(row_href, str):
            continue

        fight_uid = row_href.split("/")[-1]
        fight_uids.append(fight_uid)

    return fight_uids


@dataclass
class FightUidResult:
    success: bool
    uids: Optional[list[str]]
    message: Optional[str]


def get_fight_uids(event: EventToParse) -> FightUidResult:
    url = f"http://www.ufcstats.com/event-details/{event.uid}"
    success = False
    event_attempts = 0
    max_attempts = 5

    response = None
    while not success and event_attempts < max_attempts:
        response = requests.get(url)
        success = response.status_code == 200
        time.sleep(1)

    if not success or response is None:
        return FightUidResult(success=False, uids=None, message="could not load page")

    soup = bs4.BeautifulSoup(response.content, "html.parser")
    try:
        fight_uids = get_list_of_fights(soup)
    except IndexError as e:
        print(e)
        return FightUidResult(success=False, uids=None, message="html parsing error")

    return FightUidResult(success=True, uids=fight_uids, message=None)


def get_fights_from_event(event: EventToParse) -> FightScrapingResult:
    header_title = f"[{event.i:03d}/{event.n_events:03d}] {event.uid}"
    fight_uid_result = get_fight_uids(event)
    if not fight_uid_result.success or fight_uid_result.uids is None:
        return FightScrapingResult(
            event=event,
            write=None,
            n_fight_links=None,
            success=fight_uid_result.success,
            message=fight_uid_result.message,
        )

    downloaded_fights = [i.stem for i in event.base_dir.glob("*.html")]
    configs = [
        ScrapingConfig(
            uid=fight_uid,
            description="fight",
            base_url="http://www.ufcstats.com/fight-details",
            base_dir=event.base_dir,
            path=event.base_dir / f"{event.uid}_{fight_uid}.html",
        )
        for fight_uid in fight_uid_result.uids
        if fight_uid not in downloaded_fights
    ]

    if len(configs) == 0:
        event_header = create_header(80, header_title, False, ".")
        print(event_header)
        write_result = ScrapingWriteResult(
            config=None, path=None, success=True, attempts=1
        )
        return FightScrapingResult(
            event=event,
            write=[write_result],
            n_fight_links=0,
            success=True,
            message="no files to download",
        )

    write_results = [scrape_page(config) for config in configs]
    bad_writes = [i for i in write_results if not i.success]

    fights_deleted = len(bad_writes)
    fights_downloaded = len(write_results) - fights_deleted

    results = f"{Symbols.DOWN_ARROW.value} {fights_downloaded:02d} | {Symbols.DELETED.value} {fights_deleted:02d}"
    event_header = create_header(80, header_title + " | " + results, False, " ")
    print(event_header)
    message = None
    if len(bad_writes) > 0:
        message = f"{len(bad_writes)} fights failed to download"

        for bad_write in bad_writes:
            if bad_write.config is None or bad_write.path is None:
                continue
            print(f"deleting {bad_write.config.uid}")
            bad_write.path.unlink()

    success = len(write_results) == len(configs) and len(bad_writes) == 0
    return FightScrapingResult(
        event=event,
        write=write_results,
        n_fight_links=len(configs),
        success=success,
        message=message,
    )


def write_parsing_timestamp(results: list[FightScrapingResult]) -> None:
    current_timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"updating {len(results)} rows")
    start = time.time()
    engine = get_engine()
    with Session(engine) as session:
        for result in results:
            event = session.exec(
                select(UFCEvent).where(UFCEvent.event_uid == result.event.uid)
            ).one()
            event.downloaded_ts = current_timestamp
            session.add(event)
            session.commit()
    end = time.time()
    print(f"elapsed time: {end-start:.2f} seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Panoctagon UFC Fight Scraper")
    parser.add_argument(
        "-f",
        "--force",
        help="force existing parsed fights to be reprocessed",
        action="store_true",
        required=False,
        default=False,
    )

    parser.add_argument(
        "-s",
        "--sequential",
        help="scrape fights sequentially",
        action="store_true",
        required=False,
        default=False,
    )
    args = parser.parse_args()

    print(create_header(80, "PANOCTAGON", True, "="))
    footer = create_header(80, "", True, "=")
    cpu_count = os.cpu_count()
    if cpu_count is None:
        cpu_count = 4

    base_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fights"
    base_dir.mkdir(exist_ok=True, parents=True)

    event_uids = read_event_uids(args.force)
    n_events = len(event_uids)
    if n_events == 0:
        print("No events to parse. Exiting!")
        print(footer)
        return

    events_to_parse = [
        EventToParse(uid=uid, i=i, n_events=n_events, base_dir=base_dir)
        for i, uid in enumerate(event_uids)
    ]

    n_workers = cpu_count
    if len(events_to_parse) < cpu_count:
        n_workers = len(events_to_parse)

    start_header = create_header(
        80, f"SCRAPING n={len(events_to_parse)} UFC EVENTS", True, "-"
    )
    print(start_header)
    start_time = time.time()
    if args.sequential or len(events_to_parse) < cpu_count:
        results = [get_fights_from_event(event) for event in events_to_parse]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            results = list(executor.map(get_fights_from_event, events_to_parse))
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
        write_parsing_timestamp(successful_results)

    print(footer)


if __name__ == "__main__":
    main()
