import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

import bs4
from dateutil import parser as dateparser
from sqlmodel import Session, SQLModel, select

from panoctagon.common import create_header, get_engine
from panoctagon.tables import BFOParsedOdds, BFORawOdds

RAW_ODDS_DIR = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "betting_odds"
SEARCH_STATE_PATH = RAW_ODDS_DIR / "search_state.json"


@dataclass
class BFOMatchup:
    match_id: int
    fighter1_name: str
    fighter2_name: str


def parse_matchups_from_html(html: str) -> list[BFOMatchup]:
    soup = bs4.BeautifulSoup(html, "html.parser")
    matchups: list[BFOMatchup] = []

    rows = soup.find_all("tr", id=re.compile(r"^mu-\d+$"))
    for row in rows:
        match_id = int(row["id"].replace("mu-", ""))  # type: ignore[arg-type]
        name1_tag = row.find("span", class_="t-b-fcc")
        if not name1_tag:
            continue
        fighter1 = name1_tag.get_text(strip=True)

        next_row = row.find_next_sibling("tr")
        if not next_row:
            continue
        name2_tag = next_row.find("span", class_="t-b-fcc")
        if not name2_tag:
            continue
        fighter2 = name2_tag.get_text(strip=True)

        matchups.append(
            BFOMatchup(match_id=match_id, fighter1_name=fighter1, fighter2_name=fighter2)
        )

    return matchups


def decode_bfo_response(encoded: str) -> str:
    raw = base64.b64decode(encoded)
    text = raw.decode("utf-8")
    charset = "".join(chr(i) for i in range(33, 127))
    half = len(charset) // 2
    result = []
    for ch in text:
        idx = charset.find(ch)
        if idx >= 0:
            ch = charset[(idx + half) % len(charset)]
        result.append(ch)
    return "".join(result)


def decimal_to_american(dec: float) -> int:
    if dec >= 2.0:
        return round((dec - 1) * 100)
    return round(-100 / (dec - 1))


def _load_event_dates() -> dict[str, str]:
    data = json.loads(SEARCH_STATE_PATH.read_text(encoding="utf-8"))
    slug_to_date: dict[str, str] = {}
    for event in data.get("discovered_events", []):
        slug = event["slug"]
        date_str = event["date_str"]
        try:
            dt = dateparser.parse(date_str)
            if dt:
                slug_to_date[slug] = dt.date().isoformat()
        except (ValueError, TypeError):
            pass
    return slug_to_date


def _parse_event_title(soup: bs4.BeautifulSoup) -> str | None:
    header = soup.find("div", class_="table-header")
    if not header:
        return None
    link = header.find("a")  # type: ignore[union-attr]
    if not link:
        return None
    return link.get_text(strip=True)


def _extract_mean_odds(value: str) -> tuple[int | None, int | None]:
    if not value.strip():
        return None, None

    try:
        decoded = decode_bfo_response(value)
        data = json.loads(decoded)
    except Exception:
        return None, None

    for series in data:
        if series.get("name") != "Mean":
            continue
        points = series.get("data", [])
        if not points:
            return None, None
        opening_dec = points[0].get("y")
        closing_dec = points[-1].get("y")
        opening = decimal_to_american(opening_dec) if opening_dec else None
        closing = decimal_to_american(closing_dec) if closing_dec else None
        return opening, closing

    return None, None


def parse_and_store_odds() -> dict[str, int]:
    print(create_header(80, "PARSING BFO ODDS", True, "="))

    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[BFOParsedOdds.__table__])  # pyright: ignore[reportAttributeAccessIssue]

    slug_to_date = _load_event_dates()

    with Session(engine) as session:
        raw_odds_rows = session.exec(select(BFORawOdds)).all()

    raw_odds_index: dict[tuple[int, str], str] = {}
    for row in raw_odds_rows:
        raw_odds_index[(row.match_id, row.fighter)] = row.value

    event_htmls = sorted(RAW_ODDS_DIR.glob("*.html"))
    print(f"  {len(event_htmls)} event pages to parse")

    total_saved = 0
    events_with_odds = 0
    events_without_odds = 0

    for html_path in event_htmls:
        slug = html_path.stem
        event_date = slug_to_date.get(slug, "")

        html = html_path.read_text(encoding="utf-8")
        soup = bs4.BeautifulSoup(html, "html.parser")
        event_title = _parse_event_title(soup) or slug

        matchups = parse_matchups_from_html(html)
        event_odds: list[BFOParsedOdds] = []

        for matchup in matchups:
            for fighter_key, fighter_name in [("f1", matchup.fighter1_name), ("f2", matchup.fighter2_name)]:
                value = raw_odds_index.get((matchup.match_id, fighter_key))
                if value is None:
                    continue

                opening, closing = _extract_mean_odds(value)
                if opening is None and closing is None:
                    continue

                event_odds.append(
                    BFOParsedOdds(
                        match_id=matchup.match_id,
                        fighter=fighter_key,
                        slug=slug,
                        event_title=event_title,
                        event_date=event_date,
                        fighter_name=fighter_name,
                        opening_odds=opening,
                        closing_odds=closing,
                    )
                )

        if event_odds:
            with Session(engine) as session:
                for odd in event_odds:
                    session.merge(odd)
                session.commit()
            total_saved += len(event_odds)
            events_with_odds += 1
        else:
            events_without_odds += 1

    print(f"\n[n={events_with_odds:5,d}] events with odds")
    print(f"[n={events_without_odds:5,d}] events without odds")
    print(f"[n={total_saved:5,d}] odds records saved")

    return {
        "events_with_odds": events_with_odds,
        "events_without_odds": events_without_odds,
        "total_saved": total_saved,
    }
