from __future__ import annotations

import datetime
import re

import bs4
from sqlmodel import Session, col, select

from panoctagon.common import (
    create_header,
    delete_existing_records,
    get_engine,
    handle_parsing_issues,
    write_data_to_db,
)
from panoctagon.models import BoxingFightParsingResult, FileContents
from panoctagon.tables import BoxingEvent, BoxingFight


def parse_event_page(event_page: FileContents) -> BoxingFightParsingResult:
    if event_page.file_num % 100 == 0:
        title = f"[{event_page.file_num + 1:05d} / {event_page.n_files:05d}]"
        print(create_header(80, title, False, "."))

    soup = bs4.BeautifulSoup(event_page.contents, "html.parser")
    event_uid = event_page.uid
    parsing_issues: list[str] = []

    event = parse_event_details(soup, event_uid, event_page.modified_ts.isoformat())
    bouts = parse_bouts(soup, event_uid)
    if len(bouts) == 0:
        parsing_issues.append("no bouts parsed")

    return BoxingFightParsingResult(uid=event_uid, result=bouts, event=event, issues=parsing_issues)


def parse_event_details(soup: bs4.BeautifulSoup, event_uid: str, downloaded_ts: str) -> BoxingEvent:
    date_raw = soup.find("span", class_="day")
    event_date = parse_date(date_raw) if date_raw is not None else ""

    image_url = None
    event_image = soup.select_one("div.unicard-img img")
    if event_image is not None:
        src = event_image.get("src")
        if isinstance(src, str):
            image_url = src

    event_location = ""
    broadcast = None
    bouts = None
    for desc in soup.find_all("p", class_="desc"):
        text = re.sub(r"\s+", " ", desc.get_text(" ", strip=True)).strip()
        if desc.find("i", class_="fa-map-marker") is not None:
            event_location = text
        elif text.startswith("Bouts"):
            bouts_match = re.search(r"Bouts\s+(\d+)", text)
            if bouts_match is not None:
                bouts = int(bouts_match.group(1))
        elif text:
            broadcast = text

    return BoxingEvent(
        event_uid=event_uid,
        title="",
        event_date=event_date,
        event_location=event_location,
        broadcast=broadcast,
        bouts=bouts,
        image_url=image_url,
        downloaded_ts=downloaded_ts,
    )


def parse_bouts(soup: bs4.BeautifulSoup, event_uid: str) -> list[BoxingFight]:
    panel = soup.find("div", class_="panel")
    if panel is None:
        return []

    fights: list[BoxingFight] = []
    for bout_order, li in enumerate(panel.find_all("li", class_="list-group-item"), start=1):
        boxer_links = [
            a
            for a in li.find_all("a", href=True)
            if isinstance(a["href"], str) and "boxer-" in a["href"]
        ]
        if len(boxer_links) != 2:
            continue

        fighter1_uid = str(boxer_links[0]["href"]).split("boxer-")[-1].strip()
        fighter2_uid = str(boxer_links[1]["href"]).split("boxer-")[-1].strip()

        main_event = li.find("i", class_="fa-star") is not None

        title_bout = None
        scheduled_rounds = None
        for div in li.find_all("div"):
            if "wrap" in (div.get("class") or []):
                continue
            text = div.get_text(" ", strip=True)
            if text == "Main Event":
                continue
            if "Scheduled" in text:
                rounds_match = re.search(r"Scheduled\s+(\d+)", text)
                if rounds_match is not None:
                    scheduled_rounds = int(rounds_match.group(1))
                continue
            title_bout = text

        match_uid = None
        match_link = li.find("a", href=lambda h: isinstance(h, str) and "match/" in h)
        if match_link is not None:
            match_uid = str(match_link["href"]).split("/")[-1].strip()

        fight_uid = match_uid if match_uid is not None else f"{event_uid}_{bout_order:02d}"

        fights.append(
            BoxingFight(
                event_uid=event_uid,
                fight_uid=fight_uid,
                fighter1_uid=fighter1_uid,
                fighter2_uid=fighter2_uid,
                title_bout=title_bout,
                scheduled_rounds=scheduled_rounds,
                main_event=main_event,
                bout_order=bout_order,
                match_uid=match_uid,
            )
        )

    return fights


def parse_date(date_tag: bs4.Tag) -> str:
    date_text = date_tag.get_text(" ", strip=True)
    return datetime.datetime.strptime(date_text, "%a, %b %d %Y").strftime("%Y-%m-%d")


def write_fight_results_to_db(results: list[BoxingFightParsingResult], force_run: bool) -> None:
    tbl_name = "boxing_fights"
    print(create_header(80, tbl_name, True, spacer="-"))

    clean_results = handle_parsing_issues(results, False)
    fights = [fight for r in clean_results for fight in r.result]
    if len(fights) == 0:
        print("no fights to write")
        return

    if force_run:
        uids = [fight.fight_uid for fight in fights]
        delete_existing_records(BoxingFight, col(BoxingFight.fight_uid), uids)

    write_data_to_db(fights)

    events_to_update = [r.event for r in clean_results if r.event is not None]
    if len(events_to_update) == 0:
        return

    engine = get_engine()
    with Session(engine) as session:
        existing_events = {
            event.event_uid: event for event in session.exec(select(BoxingEvent)).all()
        }

    for event in events_to_update:
        existing = existing_events.get(event.event_uid)
        if existing is not None and existing.title:
            event.title = existing.title

    print(create_header(80, "boxing_events", True, spacer="-"))
    write_data_to_db(events_to_update)
