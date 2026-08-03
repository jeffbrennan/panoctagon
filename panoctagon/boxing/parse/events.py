from __future__ import annotations

import datetime
import re
from collections.abc import Sequence

import bs4
from sqlmodel import Session, col, select

from panoctagon.common import (
    create_header,
    get_engine,
    handle_parsing_issues,
)
from panoctagon.enums import FightResult
from panoctagon.models import (
    BoxingFightParsingResult,
    BoxingMatchParsingResult,
    BoxingMatchResult,
    FileContents,
)
from panoctagon.tables import BoxingEvent, BoxingFight, BoxingFightHistory


RESULT_MAP = {
    "W": FightResult.WIN,
    "L": FightResult.LOSS,
    "D": FightResult.DRAW,
    "NC": FightResult.NO_CONTEST,
    "DQ": FightResult.DQ,
}


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

    title = ""
    title_tag = soup.select_one("ul.eventp-list h2.title")
    if title_tag is not None:
        title = re.sub(r"\s+", " ", title_tag.get_text(" ", strip=True))

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
        title=title,
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

        fight_uid = (
            match_uid
            if match_uid is not None
            else f"{event_uid}_{min(fighter1_uid, fighter2_uid)}_{max(fighter1_uid, fighter2_uid)}"
        )

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


def parse_match_page(match_page: FileContents) -> BoxingMatchParsingResult:
    soup = bs4.BeautifulSoup(match_page.contents, "html.parser")
    boxer_links = [
        a
        for a in soup.find_all("a", href=True)
        if isinstance(a["href"], str) and "boxer-" in a["href"]
    ]
    if len(boxer_links) < 2:
        return BoxingMatchParsingResult(
            uid=match_page.uid,
            result=BoxingMatchResult(
                match_uid=match_page.uid,
                fighter1_uid="",
                fighter2_uid="",
            ),
            issues=["missing fighters"],
        )

    fighter1_uid = str(boxer_links[0]["href"]).split("boxer-")[-1].strip()
    fighter2_uid = str(boxer_links[1]["href"]).split("boxer-")[-1].strip()
    result_spans = [
        span
        for span in soup.find_all("span")
        if span.get_text(strip=True) in RESULT_MAP and "color" in str(span.get("style", "")).lower()
    ]
    issues: list[str] = []
    if len(result_spans) < 2:
        issues.append("missing fight outcomes")

    method_span = next(
        (span for span in soup.find_all("span") if "#3366CC" in str(span.get("style", "")).upper()),
        None,
    )
    decision = None
    decision_round = None
    if method_span is not None:
        method_text = re.sub(r"\s+", " ", method_span.get_text(" ", strip=True)).strip()
        method_match = re.match(r"^(.*?)\s+(\d+)$", method_text)
        if method_match is None:
            decision = method_text or None
        else:
            decision = method_match.group(1).strip() or None
            decision_round = int(method_match.group(2))

    fighter1_result = (
        RESULT_MAP.get(result_spans[0].get_text(strip=True)) if len(result_spans) > 0 else None
    )
    fighter2_result = (
        RESULT_MAP.get(result_spans[1].get_text(strip=True)) if len(result_spans) > 1 else None
    )
    return BoxingMatchParsingResult(
        uid=match_page.uid,
        result=BoxingMatchResult(
            match_uid=match_page.uid,
            fighter1_uid=fighter1_uid,
            fighter2_uid=fighter2_uid,
            fighter1_result=fighter1_result,
            fighter2_result=fighter2_result,
            decision=decision,
            decision_round=decision_round,
        ),
        issues=issues,
    )


def apply_match_results(
    fights: list[BoxingFight], match_results: list[BoxingMatchParsingResult]
) -> None:
    results_by_uid = {result.result.match_uid: result.result for result in match_results}
    for fight in fights:
        if fight.match_uid is None:
            continue
        match = results_by_uid.get(fight.match_uid)
        if match is None:
            continue

        if (fight.fighter1_uid, fight.fighter2_uid) == (match.fighter1_uid, match.fighter2_uid):
            fight.fighter1_result = match.fighter1_result
            fight.fighter2_result = match.fighter2_result
        elif (fight.fighter1_uid, fight.fighter2_uid) == (match.fighter2_uid, match.fighter1_uid):
            fight.fighter1_result = match.fighter2_result
            fight.fighter2_result = match.fighter1_result
        else:
            continue
        fight.decision = match.decision
        fight.decision_round = match.decision_round


def parse_date(date_tag: bs4.Tag) -> str:
    date_text = date_tag.get_text(" ", strip=True)
    return datetime.datetime.strptime(date_text, "%a, %b %d %Y").strftime("%Y-%m-%d")


def reconcile_fight_history(fight: BoxingFight, history: Sequence[BoxingFightHistory]) -> None:
    matching_history = [
        item
        for item in history
        if {item.boxer_uid, item.opponent_uid} == {fight.fighter1_uid, fight.fighter2_uid}
    ]
    for item in matching_history:
        if item.boxer_uid == fight.fighter1_uid:
            if fight.fighter1_result is None:
                fight.fighter1_result = item.boxer_result
            if fight.fighter2_result is None:
                fight.fighter2_result = item.opponent_result
        else:
            if fight.fighter1_result is None:
                fight.fighter1_result = item.opponent_result
            if fight.fighter2_result is None:
                fight.fighter2_result = item.boxer_result
        if fight.decision is None:
            fight.decision = item.decision
        if fight.decision_round is None:
            fight.decision_round = item.decision_round

        if item.boxer_uid == fight.fighter1_uid:
            item.boxer_result = fight.fighter1_result
            item.opponent_result = fight.fighter2_result
        else:
            item.boxer_result = fight.fighter2_result
            item.opponent_result = fight.fighter1_result
        item.decision = fight.decision
        item.decision_round = fight.decision_round


def write_fight_results_to_db(results: list[BoxingFightParsingResult], force_run: bool) -> None:
    del force_run
    tbl_name = "boxing_fights"
    print(create_header(80, tbl_name, True, spacer="-"))

    clean_results = handle_parsing_issues(results, False)
    events_to_update = [r.event for r in clean_results if r.event is not None]
    if len(events_to_update) == 0:
        print("no events to write")
        return

    event_uids = [event.event_uid for event in events_to_update]
    fights_by_event = {
        result.uid: result.result for result in clean_results if result.event is not None
    }
    engine = get_engine()
    with Session(engine) as session:
        existing_events = {
            event.event_uid: event
            for event in session.exec(
                select(BoxingEvent).where(col(BoxingEvent.event_uid).in_(event_uids))
            ).all()
        }
        history = session.exec(
            select(BoxingFightHistory).where(col(BoxingFightHistory.event_uid).in_(event_uids))
        ).all()
        existing_fights = session.exec(
            select(BoxingFight).where(col(BoxingFight.event_uid).in_(event_uids))
        ).all()
        for fight in existing_fights:
            session.delete(fight)

        for event in events_to_update:
            existing = existing_events.get(event.event_uid)
            if existing is not None and not event.title:
                event.title = existing.title
            session.merge(event)

            for fight in fights_by_event.get(event.event_uid, []):
                reconcile_fight_history(fight, history)
                session.add(fight)
        session.commit()
