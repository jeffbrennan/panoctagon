import base64
import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path

import bs4
from sqlmodel import Session, SQLModel

from panoctagon.common import create_header, get_engine
from panoctagon.tables import UFCBettingOdds

RAW_ODDS_DIR = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "betting_odds"
RAW_API_DIR = RAW_ODDS_DIR / "api"


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


def _parse_mean_odds_from_file(path: Path) -> tuple[int | None, int | None]:
    encoded = path.read_text(encoding="utf-8").strip()
    if not encoded:
        return None, None

    try:
        decoded = decode_bfo_response(encoded)
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


def _api_response_path(match_id: int, player: int) -> Path:
    return RAW_API_DIR / f"m{match_id}_p{player}.txt"


def parse_and_store_odds() -> dict[str, int]:
    print(create_header(80, "PARSING ODDS FROM LOCAL FILES", True, "="))

    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[UFCBettingOdds.__table__])  # pyright: ignore[reportAttributeAccessIssue]

    event_htmls = sorted(RAW_ODDS_DIR.glob("*.html"))
    print(f"  {len(event_htmls)} event pages to parse")

    current_ts = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    total_saved = 0
    events_with_odds = 0
    events_without_odds = 0

    for html_path in event_htmls:
        html = html_path.read_text(encoding="utf-8")
        matchups = parse_matchups_from_html(html)
        event_odds: list[UFCBettingOdds] = []

        for matchup in matchups:
            for player in (1, 2):
                api_path = _api_response_path(matchup.match_id, player)
                if not api_path.exists():
                    continue

                opening, closing = _parse_mean_odds_from_file(api_path)
                if opening is None and closing is None:
                    continue

                fighter_name = matchup.fighter1_name if player == 1 else matchup.fighter2_name
                event_odds.append(
                    UFCBettingOdds(
                        fight_uid=f"bfo-{matchup.match_id}",
                        fighter_uid=fighter_name,
                        bookmaker="BFO Mean",
                        opening_odds=opening,
                        closing_odds=closing,
                        scraped_ts=current_ts,
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
