import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    scrape_page,
)
from panoctagon.enums import Symbols
from panoctagon.models import ScrapingConfig, ScrapingWriteResult
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


def get_fight_uids(event: EventToParse, session: Optional[requests.Session] = None) -> FightUidResult:
    url = f"http://www.ufcstats.com/event-details/{event.uid}"
    success = False
    event_attempts = 0
    max_attempts = 5

    response = None
    while not success and event_attempts < max_attempts:
        if session is None:
            response = requests.get(url)
        else:
            response = session.get(url)
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


def get_fights_from_event(event: EventToParse, force: bool, session: Optional[requests.Session] = None) -> FightScrapingResult:
    header_title = f"[{event.i:03d}/{event.n_events:03d}] {event.uid}"
    downloads = [i.stem for i in event.base_dir.glob("*.html")]
    downloaded_events = sorted(set([i.split("_")[0] for i in downloads]))

    if event.uid in downloaded_events and not force:
        return FightScrapingResult(
            event=event,
            write=None,
            n_fight_links=None,
            success=True,
            message="event already downloaded",
        )

    fight_uid_result = get_fight_uids(event, session)
    if not fight_uid_result.success or fight_uid_result.uids is None:
        return FightScrapingResult(
            event=event,
            write=None,
            n_fight_links=None,
            success=fight_uid_result.success,
            message=fight_uid_result.message,
        )

    downloaded_fights = sorted(set([i.split("_")[1] for i in downloads]))
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
        write_result = ScrapingWriteResult(config=None, path=None, success=True, attempts=1)
        return FightScrapingResult(
            event=event,
            write=[write_result],
            n_fight_links=0,
            success=True,
            message="no files to download",
        )

    write_results = [scrape_page(config, session=session) for config in configs]
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


def scrape_fights_parallel(
    events_to_parse: list[EventToParse], force: bool, max_workers: int = 8
) -> list[FightScrapingResult]:
    results = []

    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_event = {
                executor.submit(get_fights_from_event, event, force, session): event
                for event in events_to_parse
            }

            for future in as_completed(future_to_event):
                result = future.result()
                results.append(result)

    return results
