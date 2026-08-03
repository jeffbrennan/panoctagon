from __future__ import annotations

import datetime
import random
import time
from typing import Optional

import bs4
import requests

from panoctagon.boxing.paths import events_dir, schedule_path
from panoctagon.common import (
    create_header,
    get_engine,
    get_table_uids,
    scrape_page,
)
from panoctagon.models import ScrapingConfig
from panoctagon.tables import BoxingEvent
from sqlmodel import Session, col, select

FIGHTNIGHTS = "https://fightnights.com"
SCHEDULE_URL = f"{FIGHTNIGHTS}/upcoming-boxing-schedule"
EVENT_BASE_URL = f"{FIGHTNIGHTS}/event"


def parse_schedule(schedule_html: str) -> list[BoxingEvent]:
    soup = bs4.BeautifulSoup(schedule_html, "html.parser")
    events: list[BoxingEvent] = []

    for ul in soup.find_all("ul", class_="event-list"):
        for li in ul.find_all("li"):
            date_raw = li.find("time", class_="visible-xs")
            title_a = li.find("h2", class_="title")
            if date_raw is None or title_a is None or title_a.a is None:
                continue

            href = title_a.a.get("href")
            if not isinstance(href, str) or "event-" not in href:
                continue
            event_uid = href.split("event-")[-1].strip()

            descs = [p.get_text(" ", strip=True) for p in li.find_all("p", class_="desc")]
            event_location = descs[0] if len(descs) > 0 else ""
            broadcast = descs[1] if len(descs) > 1 else None

            date_text = date_raw.get_text(" ", strip=True)
            event_date = datetime.datetime.strptime(date_text, "%a, %b %d %Y").strftime("%Y-%m-%d")

            events.append(
                BoxingEvent(
                    event_uid=event_uid,
                    title=title_a.a.get_text(" ", strip=True),
                    event_date=event_date,
                    event_location=event_location,
                    broadcast=broadcast,
                )
            )

    return events


def download_schedule(session: Optional[requests.Session] = None) -> list[BoxingEvent]:
    schedule_path().parent.mkdir(parents=True, exist_ok=True)

    config = ScrapingConfig(
        uid="schedule",
        description="boxing schedule",
        base_url=FIGHTNIGHTS,
        base_dir=schedule_path().parent,
        path=schedule_path(),
        url=SCHEDULE_URL,
    )
    result = scrape_page(config, session=session)
    if not result.success:
        raise RuntimeError(f"failed to download schedule: {result.error_type}")

    return parse_schedule(schedule_path().read_text())


def get_event_uids(force: bool = False) -> list[str]:
    """Upcoming event uids from the boxing_events table."""
    existing = get_table_uids(col(BoxingEvent.event_uid))
    if existing is None:
        return []

    if not force:
        engine = get_engine()
        with Session(engine) as session:
            uids = session.exec(
                select(BoxingEvent.event_uid).where(col(BoxingEvent.downloaded_ts).is_(None))
            ).all()
        return list(uids)
    return sorted(set(existing))


def get_event_pages(
    force: bool = False,
    max_downloads: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> int:
    """Download the fightnights event page for every upcoming event."""
    events_dir().mkdir(parents=True, exist_ok=True)
    downloaded = [i.stem for i in events_dir().glob("*.html")]

    event_uids = get_event_uids(force)

    n_downloaded = 0
    for i, event_uid in enumerate(event_uids):
        if max_downloads is not None and n_downloaded >= max_downloads:
            break
        if event_uid in downloaded:
            continue

        title = f"[{i + 1:03d}/{len(event_uids):03d}] {event_uid}"
        print(create_header(80, title, False, "."))
        time.sleep(random.uniform(1.0, 2.5))

        config = ScrapingConfig(
            uid=event_uid,
            description="boxing event",
            base_url=EVENT_BASE_URL,
            base_dir=events_dir(),
            path=events_dir() / f"{event_uid}.html",
            url=f"{FIGHTNIGHTS}/event-{event_uid}",
        )
        result = scrape_page(config, session=session)
        if result.success:
            n_downloaded += 1

    return n_downloaded
