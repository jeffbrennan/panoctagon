from __future__ import annotations

import datetime
import re
from typing import Optional, TypedDict

import bs4
from sqlmodel import Session, col, select

from panoctagon.boxing.parse.events import reconcile_fight_history
from panoctagon.common import (
    create_header,
    delete_existing_records,
    get_engine,
    handle_parsing_issues,
    write_data_to_db,
)
from panoctagon.enums import FightResult
from panoctagon.models import BoxingFighterParsingResult, FileContents
from panoctagon.tables import BoxingFight, BoxingFighter, BoxingFightHistory

RESULT_MAP = {
    "W": FightResult.WIN,
    "L": FightResult.LOSS,
    "D": FightResult.DRAW,
    "NC": FightResult.NO_CONTEST,
}

FRACTION_MAP = {"¼": 0.25, "½": 0.5, "¾": 0.75}


class FighterStats(TypedDict):
    total_bouts: Optional[int]
    nickname: Optional[str]
    weight_class: Optional[str]
    stance: Optional[str]
    height_inches: Optional[int]
    reach_inches: Optional[int]
    nationality: Optional[str]
    dob: Optional[str]


def parse_fighter(fighter_page: FileContents) -> BoxingFighterParsingResult:
    if fighter_page.file_num % 100 == 0:
        title = f"[{fighter_page.file_num + 1:05d} / {fighter_page.n_files:05d}]"
        print(create_header(80, title, False, "."))

    soup = bs4.BeautifulSoup(fighter_page.contents, "html.parser")
    parsing_issues: list[str] = []

    fighter = parse_fighter_details(soup, fighter_page.uid, fighter_page.modified_ts.isoformat())
    fight_history = parse_fight_history(soup, fighter_page.uid)

    return BoxingFighterParsingResult(
        uid=fighter_page.uid, result=fighter, fight_history=fight_history, issues=parsing_issues
    )


def parse_fighter_details(
    soup: bs4.BeautifulSoup, fighter_uid: str, downloaded_ts: str
) -> BoxingFighter:
    first_name, last_name = parse_name(soup)

    wins = losses = draws = kos = None
    ko_percent = None
    record_labels = [s.get_text(strip=True) for s in soup.find_all("span", class_="unilabel")]
    for label in record_labels:
        if label.endswith("W") and label[:-1].isdigit():
            wins = int(label[:-1])
        elif label.endswith("L") and label[:-1].isdigit():
            losses = int(label[:-1])
        elif label.endswith("D") and label[:-1].isdigit():
            draws = int(label[:-1])
        elif label.endswith("KO") and label[:-2].isdigit():
            kos = int(label[:-2])
        elif label.endswith("KO%") and label[:-3].isdigit():
            ko_percent = float(label[:-3])

    stats = parse_stats(soup)

    return BoxingFighter(
        fighter_uid=fighter_uid,
        first_name=first_name,
        last_name=last_name,
        nickname=stats.get("nickname"),
        weight_class=stats.get("weight_class"),
        stance=stats.get("stance"),
        height_inches=stats.get("height_inches"),
        reach_inches=stats.get("reach_inches"),
        nationality=stats.get("nationality"),
        dob=stats.get("dob"),
        wins=wins,
        losses=losses,
        draws=draws,
        kos=kos,
        ko_percent=ko_percent,
        total_bouts=stats.get("total_bouts"),
        downloaded_ts=downloaded_ts,
    )


def parse_name(soup: bs4.BeautifulSoup) -> tuple[str, str]:
    h1 = soup.select_one("h1.unicard-title")
    if h1 is None:
        return "", ""

    small = h1.find("small")
    if small is not None:
        small.decompose()

    name = h1.get_text(" ", strip=True).removesuffix("Boxing Record").strip()
    name_split = name.split(" ")
    if len(name_split) == 0:
        return "", ""
    return name_split[0], " ".join(name_split[1:])


def parse_stats(soup: bs4.BeautifulSoup) -> FighterStats:
    stats: FighterStats = {
        "total_bouts": None,
        "nickname": None,
        "weight_class": None,
        "stance": None,
        "height_inches": None,
        "reach_inches": None,
        "nationality": None,
        "dob": None,
    }

    stats_heading = next(
        (h for h in soup.find_all("h4") if h.get_text(strip=True) == "Stats"), None
    )
    if stats_heading is None:
        return stats

    card = stats_heading.find_parent("div", class_="unicard")
    if card is None:
        return stats

    for li in card.find_all("li"):
        text = li.get_text(" ", strip=True)
        if ":" not in text:
            continue
        label, value = [i.strip() for i in text.split(":", 1)]
        if value == "":
            value = None

        if label == "Total Bouts" and value is not None:
            stats["total_bouts"] = int(value)
        elif label == "Alias":
            stats["nickname"] = value
        elif label == "Weightclass":
            stats["weight_class"] = value
        elif label == "Stance":
            stats["stance"] = value
        elif label == "Height" and value is not None:
            stats["height_inches"] = parse_height(value)
        elif label == "Reach" and value is not None:
            stats["reach_inches"] = parse_reach(value)
        elif label == "Nationality":
            stats["nationality"] = value
        elif label == "Date Of Birth":
            stats["dob"] = value

    return stats


def parse_height(height_text: str) -> Optional[int]:
    match = re.search(r"(\d+)'\s*(\d+)\"?", height_text)
    if match is None:
        return None
    return (int(match.group(1)) * 12) + int(match.group(2))


def parse_reach(reach_text: str) -> Optional[int]:
    match = re.search(r"(\d+)\"?", reach_text)
    if match is None:
        return None
    return int(match.group(1))


def parse_fight_history(soup: bs4.BeautifulSoup, boxer_uid: str) -> list[BoxingFightHistory]:
    history: list[BoxingFightHistory] = []
    for div in soup.find_all(
        "div", class_=lambda c: bool(c and "unicard-framed" in c and "mgb-5" in c)
    ):
        ul = div.find("ul")
        if ul is None:
            continue

        fight_item = ul.find("li", class_="fs-120")
        if fight_item is None:
            continue

        boxer_links = [
            a
            for a in fight_item.find_all("a", href=True)
            if isinstance(a["href"], str) and "boxer-" in a["href"]
        ]
        if len(boxer_links) != 2:
            continue

        result = parse_fight_history_item(ul, boxer_uid, boxer_links)
        if result is not None:
            history.append(result)

    return history


def parse_fight_history_item(
    ul: bs4.Tag, boxer_uid: str, boxer_links: list[bs4.Tag]
) -> Optional[BoxingFightHistory]:
    date_item = ul.find("li", class_="fs-110")
    if date_item is None:
        return None

    event_link = date_item.find("a", href=lambda h: isinstance(h, str) and "/event-" in h)
    if event_link is None:
        return None

    event_uid = str(event_link["href"]).split("event-")[-1].strip()
    fight_date = datetime.datetime.strptime(
        event_link.get_text(" ", strip=True), "%a, %b %d %Y"
    ).strftime("%Y-%m-%d")
    venue_text = date_item.get_text(" ", strip=True)
    venue = venue_text.split("@ ", 1)[-1].strip() if "@ " in venue_text else None

    fight_item = ul.find("li", class_="fs-120")
    if fight_item is None:
        return None

    fight_text = fight_item.get_text(" ", strip=True)

    weights = [parse_weight(w) for w in re.findall(r"([0-9]+[¼½¾]?)\s*lbs", fight_text)]
    weights += [None] * (2 - len(weights))

    result_spans = [
        s
        for s in fight_item.find_all("span")
        if s.get("style") is not None
        and "color" in str(s.get("style"))
        and s.get_text(strip=True) in RESULT_MAP
    ]
    if len(result_spans) == 0:
        return None

    method_span = next(
        (
            s
            for s in fight_item.find_all("span")
            if s.get("style") is not None and "#3366CC" in str(s.get("style"))
        ),
        None,
    )

    decision = None
    decision_round = None
    title_bout = None
    if method_span is not None:
        method_text = method_span.get_text(" ", strip=True)
        if method_text:
            method_split = method_text.rsplit(" ", 1)
            if len(method_split) == 2 and method_split[1].isdigit():
                decision, decision_round = method_split[0], int(method_split[1])
            else:
                decision = method_text
            title_bout = fight_text.split(method_text, 1)[-1].strip() or None

    f1_uid, f2_uid = [str(a["href"]).split("boxer-")[-1].strip() for a in boxer_links[:2]]
    boxer_is_f1 = boxer_uid == f1_uid
    boxer_result_raw = (
        result_spans[0].get_text(strip=True)
        if boxer_is_f1 and len(result_spans) > 0
        else result_spans[1].get_text(strip=True)
        if not boxer_is_f1 and len(result_spans) > 1
        else None
    )
    opponent_result_raw = (
        result_spans[1].get_text(strip=True)
        if boxer_is_f1 and len(result_spans) > 1
        else result_spans[0].get_text(strip=True)
        if not boxer_is_f1 and len(result_spans) > 0
        else None
    )

    boxer_result = RESULT_MAP.get(boxer_result_raw) if boxer_result_raw is not None else None
    opponent_result = (
        RESULT_MAP.get(opponent_result_raw) if opponent_result_raw is not None else None
    )

    judge_cards = None
    for li in ul.find_all("li", recursive=False):
        if li.get("class") in (["fs-110"], ["fs-120"]):
            continue
        judge_text = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
        if judge_text:
            judge_cards = judge_text
            break

    return BoxingFightHistory(
        boxer_uid=boxer_uid,
        event_uid=event_uid,
        opponent_uid=f2_uid if boxer_is_f1 else f1_uid,
        fight_date=fight_date,
        venue=venue,
        boxer_weight_lbs=weights[0] if boxer_is_f1 else weights[1],
        opponent_weight_lbs=weights[1] if boxer_is_f1 else weights[0],
        boxer_result=boxer_result,
        opponent_result=opponent_result,
        decision=decision,
        decision_round=decision_round,
        title_bout=title_bout,
        judge_cards=judge_cards,
    )


def parse_weight(weight_text: str) -> float:
    for char, fraction in FRACTION_MAP.items():
        if char in weight_text:
            return int(weight_text[:-1]) + fraction
    return float(weight_text)


def write_fighter_results_to_db(results: list[BoxingFighterParsingResult], force_run: bool) -> None:
    clean_results = handle_parsing_issues(results, False)
    fighters = [i.result for i in clean_results]
    boxer_uids = [i.uid for i in clean_results]

    if len(fighters) == 0:
        print("no fighters to write")
        return

    if force_run:
        delete_existing_records(BoxingFighter, col(BoxingFighter.fighter_uid), boxer_uids)

    print(create_header(80, "boxing_fighters", True, spacer="-"))
    write_data_to_db(fighters)

    if len(boxer_uids) > 0:
        delete_existing_records(BoxingFightHistory, col(BoxingFightHistory.boxer_uid), boxer_uids)
    history = [fight for r in clean_results for fight in r.fight_history]
    print(create_header(80, "boxing_fight_history", True, spacer="-"))
    write_data_to_db(history)
    engine = get_engine()
    with Session(engine) as session:
        fights = session.exec(
            select(BoxingFight).where(
                col(BoxingFight.fighter1_uid).in_(boxer_uids)
                | col(BoxingFight.fighter2_uid).in_(boxer_uids)
            )
        ).all()
        stored_history = session.exec(
            select(BoxingFightHistory).where(col(BoxingFightHistory.boxer_uid).in_(boxer_uids))
        ).all()
        for fight in fights:
            reconcile_fight_history(fight, stored_history)
        session.commit()
