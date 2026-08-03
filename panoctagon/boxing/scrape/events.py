from __future__ import annotations

import datetime
import random
import re
import time
from typing import Optional

import bs4
import requests
from sqlmodel import Session, select

from panoctagon.boxing.paths import events_dir, matches_dir, results_path, schedule_path
from panoctagon.common import (
    create_header,
    get_engine,
    scrape_page,
)
from panoctagon.models import ScrapingConfig
from panoctagon.tables import BoxingEvent, BoxingFight

FIGHTNIGHTS = "https://fightnights.com"
SCHEDULE_URL = f"{FIGHTNIGHTS}/upcoming-boxing-schedule"
EVENT_BASE_URL = f"{FIGHTNIGHTS}/event"
RESULTS_URL = f"{FIGHTNIGHTS}/boxing-results"


def parse_results(results_html: str) -> list[BoxingEvent]:
    soup = bs4.BeautifulSoup(results_html, "html.parser")
    events: list[BoxingEvent] = []
    for panel in soup.find_all("div", class_="panel"):
        event_link = panel.find("a", href=lambda h: isinstance(h, str) and "event-" in h)
        if event_link is None:
            continue
        href = event_link.get("href")
        if not isinstance(href, str):
            continue
        date_location = panel.select_one("div.well-content h5")
        if date_location is None:
            continue
        text = re.sub(r"\s+", " ", date_location.get_text(" ", strip=True))
        date_match = re.match(r"([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{2} \d{4})", text)
        if date_match is None:
            continue
        event_date = datetime.datetime.strptime(date_match.group(1), "%a, %b %d %Y").strftime(
            "%Y-%m-%d"
        )
        location = text[len(date_match.group(1)) :].strip()
        location = location.lstrip(" ")
        events.append(
            BoxingEvent(
                event_uid=href.split("event-")[-1].strip().strip("/"),
                title="",
                event_date=event_date,
                event_location=location,
                bouts=len(panel.select("li.list-group-item")),
            )
        )
    return events


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


def download_results(session: Optional[requests.Session] = None) -> list[BoxingEvent]:
    results_path().parent.mkdir(parents=True, exist_ok=True)
    config = ScrapingConfig(
        uid="results",
        description="boxing results",
        base_url=FIGHTNIGHTS,
        base_dir=results_path().parent,
        path=results_path(),
        url=RESULTS_URL,
    )
    result = scrape_page(config, session=session)
    if not result.success:
        raise RuntimeError(f"failed to download results: {result.error_type}")
    return parse_results(results_path().read_text())


def get_event_uids(force: bool = False) -> list[str]:
    """Return events that need an initial scrape or completed-fight refresh."""
    engine = get_engine()
    with Session(engine) as session:
        events = session.exec(select(BoxingEvent)).all()
        if force:
            return sorted(event.event_uid for event in events)

        fights = session.exec(select(BoxingFight.event_uid, BoxingFight.fighter1_result)).all()
    unresolved = {event_uid for event_uid, fighter1_result in fights if fighter1_result is None}
    today = datetime.date.today().isoformat()
    return sorted(
        event.event_uid
        for event in events
        if event.downloaded_ts is None
        or (event.event_date <= today and event.event_uid in unresolved)
    )


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
        if event_uid in downloaded and not force:
            event_path = events_dir() / f"{event_uid}.html"
            download_match_pages(event_path.read_text(), force=False, session=session)
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
            download_match_pages(config.path.read_text(), force=force, session=session)

    return n_downloaded


def get_match_uids(event_html: str) -> list[str]:
    soup = bs4.BeautifulSoup(event_html, "html.parser")
    panel = soup.find("div", class_="panel")
    if panel is None:
        return []
    match_uids: list[str] = []
    for link in panel.find_all("a", href=True):
        href = link.get("href")
        if not isinstance(href, str) or "match/" not in href:
            continue
        match_uid = href.split("match/")[-1].strip().strip("/")
        if match_uid and match_uid not in match_uids:
            match_uids.append(match_uid)
    return match_uids


def download_match_pages(
    event_html: str,
    force: bool = False,
    session: Optional[requests.Session] = None,
) -> int:
    matches_dir().mkdir(parents=True, exist_ok=True)
    downloaded = {path.stem for path in matches_dir().glob("*.html")}
    match_uids = get_match_uids(event_html)
    n_downloaded = 0
    for match_uid in match_uids:
        if match_uid in downloaded and not force:
            continue
        time.sleep(random.uniform(1.0, 2.5))
        config = ScrapingConfig(
            uid=match_uid,
            description="boxing match",
            base_url=f"{FIGHTNIGHTS}/match",
            base_dir=matches_dir(),
            path=matches_dir() / f"{match_uid}.html",
            url=f"{FIGHTNIGHTS}/match/{match_uid}",
        )
        result = scrape_page(config, session=session)
        if result.success:
            n_downloaded += 1
    return n_downloaded
