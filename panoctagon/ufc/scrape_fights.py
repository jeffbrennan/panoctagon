import datetime
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import bs4
import requests

from panoctagon.common import (
    get_con,
    get_table_rows,
    ScrapingConfig,
    create_header,
    scrape_page,
    Symbols,
    ScrapingWriteResult,
    report_stats,
)


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
    _, cur = get_con()
    if force_run:
        cmd = "select event_uid from ufc_events where event_date < date('now')"
    else:
        cmd = "select event_uid from ufc_events where downloaded_ts is null and event_date < date('now')"

    cur.execute(cmd)
    uids = [i[0] for i in cur.fetchall()]
    return uids


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
            path=event.base_dir / f"{fight_uid}.html",
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
    con, cur = get_con()
    current_timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    update_info = (
        {"downloaded_uid": i.event.uid, "downloaded_ts": current_timestamp}
        for i in results
    )

    print(f"updating {len(results)} rows")
    cur.executemany(
        "UPDATE ufc_events SET downloaded_ts=:downloaded_ts WHERE event_uid=:downloaded_uid",
        update_info,
    )
    con.commit()


def main() -> None:
    print(create_header(80, "PANOCTAGON", True, "="))
    footer = create_header(80, "", True, "=")
    n_cores = os.cpu_count()

    # todo make these cli args
    sequential = False
    force_run = True

    if n_cores is None:
        n_cores = 4

    base_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fights"
    base_dir.mkdir(exist_ok=True, parents=True)

    event_uids = read_event_uids(force_run)
    n_events = len(event_uids)
    if n_events == 0:
        print("No events to parse. Exiting!")
        print(footer)
        return

    events_to_parse = [
        EventToParse(uid=uid, i=i, n_events=n_events, base_dir=base_dir)
        for i, uid in enumerate(event_uids)
    ]

    n_workers = n_cores
    if len(events_to_parse) < n_cores:
        n_workers = len(events_to_parse)

    start_header = create_header(
        80, f"SCRAPING n={len(events_to_parse)} UFC EVENTS", True, "-"
    )
    print(start_header)
    start_time = time.time()
    if sequential or len(events_to_parse) < n_cores:
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

    report_stats(start_time, end_time, n_events, "events")

    successful_results = [i for i in results if i.success and i.message is None]
    if len(successful_results) > 0:
        print(create_header(80, "UPDATING UFC_EVENTS", True, "-"))
        write_parsing_timestamp(successful_results)

    print(footer)


if __name__ == "__main__":
    main()
