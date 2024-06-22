import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import random
from typing import Optional

import bs4
import requests

from panoctagon.common import (
    get_con,
    get_table_rows,
    ScrapingConfig,
    dump_html,
    create_header,
    Symbols,
)


@dataclass
class EventToParse:
    uid: str
    i: int
    n_events: int
    base_dir: Path


@dataclass
class ScrapingWriteResult:
    config: Optional[ScrapingConfig]
    path: Optional[Path]
    success: bool
    attempts: int


@dataclass
class FightScrapingResult:
    event: EventToParse
    write: Optional[list[ScrapingWriteResult]]
    success: bool
    message: Optional[str]


def read_event_uids():
    con, cur = get_con()
    cur.execute("select event_uid from ufc_events")
    uids = [i[0] for i in cur.fetchall()]
    return uids


def get_list_of_fights(soup: bs4.BeautifulSoup) -> list[str]:
    rows = get_table_rows(soup)
    fight_uids = []

    for row in rows:
        if row.a is None:
            continue

        row_href = row.a["href"]

        if not isinstance(row_href, str):
            continue

        fight_uid = row_href.split("/")[-1]
        fight_uids.append(fight_uid)

    return fight_uids


def check_write_success(config: ScrapingConfig) -> bool:
    with config.path.open("r") as f:
        contents = "".join(f.readlines())

    issue_indicators = ["Internal Server Error", "Too Many Requests"]
    issues_exist = any(i in contents for i in issue_indicators)
    return not issues_exist


def get_fight_uids(event: EventToParse) -> Optional[list[str]]:
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
        return None

    soup = bs4.BeautifulSoup(response.content, "html.parser")

    try:
        fight_uids = get_list_of_fights(soup)
    except IndexError as e:
        print(e)
        return None

    return fight_uids


def get_fights_from_event(event: EventToParse) -> FightScrapingResult:
    header_title = f"[{event.i:03d}/{event.n_events:03d}] {event.uid}"
    fight_uids = get_fight_uids(event)
    write_results: list[ScrapingWriteResult] = []

    if fight_uids is None:
        return FightScrapingResult(
            event=event, write=None, success=False, message="no fight uids parsed"
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
        for fight_uid in fight_uids
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
            success=True,
            message="no files to download",
        )

    max_attempts = 5
    for config in configs:
        write_success = False
        attempts = 0
        sleep_multiplier = 0

        while not write_success and attempts < max_attempts:
            ms_to_sleep = random.randint(100 * sleep_multiplier, 200 * sleep_multiplier)
            time.sleep(ms_to_sleep / 1000)

            dump_html(config)

            write_success = check_write_success(config)
            sleep_multiplier += 10
            attempts += 1

        write_results.append(
            ScrapingWriteResult(
                config=config,
                path=config.path,
                success=write_success,
                attempts=attempts,
            )
        )

    bad_writes = [i for i in write_results if i.success]

    fights_deleted = len(bad_writes)
    fights_downloaded = len(write_results) - fights_deleted

    results = f"{Symbols.DOWN_ARROW.value} {fights_downloaded} | {Symbols.DELETED} {fights_deleted}"
    event_header = create_header(80, header_title + " | " + results, False, " ")
    message = None
    if len(bad_writes) > 0:
        message = f"{len(bad_writes)} fights failed to download"

        for bad_write in bad_writes:
            if bad_write.config is None or bad_write.path is None:
                continue
            print(f"deleting {bad_write.config.uid}")
            bad_write.path.unlink()

    return FightScrapingResult(
        event=event, write=write_results, success=len(bad_writes) == 0, message=message
    )


def main() -> None:
    n_cores = os.cpu_count()
    sequential = True

    if n_cores is None:
        n_cores = 4

    base_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fights"
    base_dir.mkdir(exist_ok=True, parents=True)

    event_uids = read_event_uids()
    n_events = len(event_uids)

    events_to_parse = [
        EventToParse(uid=uid, i=i, n_events=n_events, base_dir=base_dir)
        for i, uid in enumerate(event_uids)
    ]

    n_workers = n_cores
    if len(events_to_parse) < n_cores:
        n_workers = len(events_to_parse)

    print(create_header(80, "PANOCTAGON", True, "="))
    start_header = create_header(
        80, f"SCRAPING n={len(events_to_parse)} UFC EVENTS", True, "-"
    )
    print(start_header)
    start_time = time.time()
    if sequential:
        results = [get_fights_from_event(event) for event in events_to_parse]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            results = list(executor.map(get_fights_from_event, events_to_parse))
    end_time = time.time()

    fights_downloaded = len([i for i in results if i.success])
    fights_deleted = len(results) - fights_downloaded

    elapsed_time_seconds = end_time - start_time
    elapsed_time_seconds_per_event = elapsed_time_seconds / n_events

    stats_header = create_header(80, "RUN STATS", True, "-")

    print(stats_header)
    print(
        f"{Symbols.DOWN_ARROW.value} {fights_downloaded} | {Symbols.DELETED.value} {fights_deleted}"
    )
    print(f"elapsed time: {elapsed_time_seconds:.2f} seconds")
    print(f"elapsed time per event: {elapsed_time_seconds_per_event:.2f} seconds")
    print(create_header(80, "", center=True, spacer="="))


if __name__ == "__main__":
    main()
