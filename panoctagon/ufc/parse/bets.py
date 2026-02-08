import base64
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import bs4
from dateutil import parser as dateparser
from sqlmodel import Session, SQLModel, col, select

from panoctagon.common import create_header, get_engine
from panoctagon.tables import BFOParsedOdds, BFORawOdds, BFOUFCLink, UFCEvent, UFCFight, UFCFighter

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


def parse_and_store_odds(force: bool = False) -> dict[str, int]:
    print(create_header(80, "PARSING BFO ODDS", True, "="))

    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[BFOParsedOdds.__table__])  # pyright: ignore[reportAttributeAccessIssue]

    slug_to_date = _load_event_dates()

    with Session(engine) as session:
        raw_odds_rows = session.exec(select(BFORawOdds)).all()
        existing_slugs: set[str] = set()
        if not force:
            rows = session.exec(
                select(col(BFOParsedOdds.slug)).distinct()
            ).all()
            existing_slugs = set(rows)

    raw_odds_index: dict[tuple[int, str], str] = {}
    for row in raw_odds_rows:
        raw_odds_index[(row.match_id, row.fighter)] = row.value

    event_htmls = sorted(RAW_ODDS_DIR.glob("*.html"))
    if not force:
        event_htmls = [p for p in event_htmls if p.stem not in existing_slugs]
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


MATCH_THRESHOLD = 0.8


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"\s+odds$", "", t)
    t = re.sub(r"\bvs\.\b", "vs", t)
    return t


def _fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def link_bfo_to_ufc(force: bool = False) -> dict[str, int]:
    print(create_header(80, "LINKING BFO ODDS TO UFC FIGHTS", True, "="))

    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[BFOUFCLink.__table__])  # pyright: ignore[reportAttributeAccessIssue]

    with Session(engine) as session:
        ufc_events = {e.event_uid: e for e in session.exec(select(UFCEvent)).all()}
        ufc_fighters = {f.fighter_uid: f for f in session.exec(select(UFCFighter)).all()}
        ufc_fights = session.exec(select(UFCFight)).all()

        bfo_events = session.exec(
            select(
                col(BFOParsedOdds.slug),
                col(BFOParsedOdds.event_title),
                col(BFOParsedOdds.event_date),
            ).distinct()
        ).all()

        bfo_rows = session.exec(select(BFOParsedOdds)).all()

        existing_keys: set[tuple[int, str]] = set()
        if not force:
            for row in session.exec(select(BFOUFCLink)).all():
                existing_keys.add((row.match_id, row.fighter))

    ufc_events_by_date: dict[str, list[UFCEvent]] = {}
    for e in ufc_events.values():
        ufc_events_by_date.setdefault(e.event_date, []).append(e)

    fights_by_event: dict[str, list[UFCFight]] = {}
    for f in ufc_fights:
        fights_by_event.setdefault(f.event_uid, []).append(f)

    def fighter_full_name(fighter_uid: str) -> str:
        f = ufc_fighters.get(fighter_uid)
        if not f:
            return ""
        return f"{f.first_name} {f.last_name}".strip()

    bfo_event_to_ufc: dict[str, str] = {}
    for slug, bfo_title, bfo_date in bfo_events:
        if not bfo_date:
            continue
        candidates = ufc_events_by_date.get(bfo_date, [])
        if not candidates:
            continue
        norm_bfo = _normalize_title(bfo_title)
        best_event = None
        best_ratio = 0.0
        for candidate in candidates:
            ratio = _fuzzy_ratio(norm_bfo, _normalize_title(candidate.title))
            if ratio > best_ratio:
                best_ratio = ratio
                best_event = candidate
        if best_event and best_ratio >= MATCH_THRESHOLD:
            bfo_event_to_ufc[slug] = best_event.event_uid

    ufc_fighter_name_index: dict[str, str] = {}
    for fuid, fighter in ufc_fighters.items():
        full = f"{fighter.first_name} {fighter.last_name}".strip().lower()
        ufc_fighter_name_index[full] = fuid

    fights_by_fighter: dict[str, list[UFCFight]] = {}
    for fight in ufc_fights:
        fights_by_fighter.setdefault(fight.fighter1_uid, []).append(fight)
        fights_by_fighter.setdefault(fight.fighter2_uid, []).append(fight)

    bfo_rows_by_match: dict[int, list[BFOParsedOdds]] = {}
    for row in bfo_rows:
        bfo_rows_by_match.setdefault(row.match_id, []).append(row)

    fighter_match_cache: dict[str, tuple[str | None, float]] = {}

    def _find_best_fighter(name: str) -> tuple[str | None, float]:
        if name in fighter_match_cache:
            return fighter_match_cache[name]
        best_uid = None
        best_ratio = 0.0
        name_lower = name.lower()
        for full_name, fuid in ufc_fighter_name_index.items():
            ratio = SequenceMatcher(None, name_lower, full_name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_uid = fuid
        fighter_match_cache[name] = (best_uid, best_ratio)
        return best_uid, best_ratio

    matched = 0
    matched_fallback = 0
    skipped_existing = 0
    unmatched_event = 0
    unmatched_fighter = 0
    links: list[BFOUFCLink] = []

    for row in bfo_rows:
        if (row.match_id, row.fighter) in existing_keys:
            skipped_existing += 1
            continue

        event_uid = bfo_event_to_ufc.get(row.slug)
        if event_uid:
            card = fights_by_event.get(event_uid, [])
            best_fight = None
            best_fighter_uid = None
            best_ratio = 0.0
            for fight in card:
                for fuid in [fight.fighter1_uid, fight.fighter2_uid]:
                    name = fighter_full_name(fuid)
                    ratio = _fuzzy_ratio(row.fighter_name, name)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_fight = fight
                        best_fighter_uid = fuid

            if best_fight and best_fighter_uid and best_ratio >= MATCH_THRESHOLD:
                links.append(
                    BFOUFCLink(
                        match_id=row.match_id,
                        fighter=row.fighter,
                        fight_uid=best_fight.fight_uid,
                        fighter_uid=best_fighter_uid,
                        event_uid=event_uid,
                    )
                )
                matched += 1
                continue
            else:
                unmatched_fighter += 1
                continue

        partner_rows = bfo_rows_by_match.get(row.match_id, [])
        partner = next((r for r in partner_rows if r.fighter != row.fighter), None)
        if not partner:
            unmatched_event += 1
            continue

        fighter_uid, f_ratio = _find_best_fighter(row.fighter_name)
        if not fighter_uid or f_ratio < MATCH_THRESHOLD:
            unmatched_event += 1
            continue

        partner_uid, p_ratio = _find_best_fighter(partner.fighter_name)
        if not partner_uid or p_ratio < MATCH_THRESHOLD:
            unmatched_event += 1
            continue

        shared_fight = None
        for fight in fights_by_fighter.get(fighter_uid, []):
            other = fight.fighter2_uid if fight.fighter1_uid == fighter_uid else fight.fighter1_uid
            if other == partner_uid:
                shared_fight = fight
                break

        if not shared_fight:
            unmatched_event += 1
            continue

        links.append(
            BFOUFCLink(
                match_id=row.match_id,
                fighter=row.fighter,
                fight_uid=shared_fight.fight_uid,
                fighter_uid=fighter_uid,
                event_uid=shared_fight.event_uid,
            )
        )
        matched_fallback += 1

    if links:
        with Session(engine) as session:
            for link in links:
                session.merge(link)
            session.commit()

    print(f"\n[n={matched:5,d}] matched (event+fighter)")
    print(f"[n={matched_fallback:5,d}] matched (fighter fallback)")
    print(f"[n={skipped_existing:5,d}] skipped (already linked)")
    print(f"[n={unmatched_event:5,d}] unmatched (no event/fighter match)")
    print(f"[n={unmatched_fighter:5,d}] unmatched (event matched, fighter not)")

    return {
        "matched": matched,
        "matched_fallback": matched_fallback,
        "skipped_existing": skipped_existing,
        "unmatched_event": unmatched_event,
        "unmatched_fighter": unmatched_fighter,
    }
