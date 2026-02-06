import datetime
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import bs4
import requests
from sqlmodel import Session, SQLModel, col, select

from panoctagon.common import create_header, get_engine
from panoctagon.tables import UFCBettingOdds, UFCEvent, UFCFight, UFCFighter

BASE_URL = "https://www.bestfightodds.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class EventOddsResult:
    event_uid: str
    event_title: str
    success: bool
    odds: list[UFCBettingOdds]
    error: Optional[str] = None


@dataclass
class FighterMatch:
    fighter_uid: str
    first_name: str
    last_name: str


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    return session


@dataclass
class BFOEvent:
    date: datetime.date
    name: str
    url: str


def parse_bfo_date(date_str: str) -> datetime.date:
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str.strip())
    return datetime.datetime.strptime(cleaned, "%b %d %Y").date()


def fetch_bfo_upcoming(session: requests.Session) -> dict[str, str]:
    """Fetch upcoming event URLs from BFO homepage. Returns {event_name: url}."""
    response = session.get(BASE_URL, timeout=30)
    if response.status_code != 200:
        return {}

    soup = bs4.BeautifulSoup(response.text, "html.parser")
    results: dict[str, str] = {}
    for link in soup.find_all("a", href=re.compile(r"/events/")):
        href = str(link.get("href", ""))
        name = link.get_text(strip=True)
        if name and href and "future-events" not in href:
            url = f"{BASE_URL}{href}" if href.startswith("/") else href
            results[name] = url
    return results


def fetch_bfo_archive(session: requests.Session, oldest_date: str) -> list[BFOEvent]:
    events: list[BFOEvent] = []
    page = 1

    while True:
        response = session.get(f"{BASE_URL}/archive", params={"page": page}, timeout=30)
        if response.status_code != 200:
            break

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tr")

        page_has_events = False
        for row in rows:
            date_cell = row.find("td", class_="content-list-date")
            title_cell = row.find("td", class_="content-list-title")
            if not date_cell or not title_cell:
                continue

            link = title_cell.find("a", href=re.compile(r"/events/"))
            if not link:
                continue

            page_has_events = True
            event_date = parse_bfo_date(date_cell.get_text(strip=True))
            event_name = link.get_text(strip=True)
            href = link.get("href", "")
            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            events.append(BFOEvent(date=event_date, name=event_name, url=url))

            if event_date < datetime.date.fromisoformat(oldest_date):
                return events

        if not page_has_events:
            break

        page += 1
        time.sleep(random.uniform(0.5, 1.5))

    return events


def find_bfo_event_url(
    event: UFCEvent, archive: list[BFOEvent], upcoming: dict[str, str]
) -> Optional[str]:
    numbered_match = re.search(r"UFC (\d+)", event.title)

    if numbered_match:
        number = numbered_match.group(1)
        for bfo in archive:
            if re.search(rf"UFC {number}\b", bfo.name):
                return bfo.url
        for name, url in upcoming.items():
            if re.search(rf"UFC {number}\b", name):
                return url
    else:
        for bfo in archive:
            if bfo.date == datetime.date.fromisoformat(event.event_date) and bfo.name == "UFC":
                return bfo.url
        if "UFC Fight Night" in upcoming:
            return upcoming["UFC Fight Night"]
        for name, url in upcoming.items():
            if name == "UFC" or (name.startswith("UFC ") and not re.search(r"UFC \d+", name)):
                return url

    return None


def parse_american_odds(odds_str: str) -> Optional[int]:
    if not odds_str or odds_str in ("-", "N/A", ""):
        return None

    cleaned = odds_str.strip().replace("\u2212", "-")
    cleaned = re.sub(r"[^\d\-+]", "", cleaned)

    if not cleaned:
        return None

    try:
        return int(cleaned)
    except ValueError:
        return None


def get_fighters_for_event(event_uid: str) -> dict[str, FighterMatch]:
    engine = get_engine()
    fighters_map: dict[str, FighterMatch] = {}

    with Session(engine) as session:
        fights = session.exec(select(UFCFight).where(col(UFCFight.event_uid) == event_uid)).all()

        fighter_uids = set()
        for fight in fights:
            fighter_uids.add(fight.fighter1_uid)
            fighter_uids.add(fight.fighter2_uid)

        for fighter_uid in fighter_uids:
            fighter = session.exec(
                select(UFCFighter).where(col(UFCFighter.fighter_uid) == fighter_uid)
            ).first()

            if fighter:
                fighters_map[fighter_uid] = FighterMatch(
                    fighter_uid=fighter_uid,
                    first_name=fighter.first_name.lower(),
                    last_name=fighter.last_name.lower(),
                )

    return fighters_map


def match_fighter_name(bfo_name: str, fighters: dict[str, FighterMatch]) -> Optional[str]:
    bfo_name_lower = bfo_name.lower().strip()

    for fighter_uid, fighter in fighters.items():
        full_name = f"{fighter.first_name} {fighter.last_name}"
        if bfo_name_lower == full_name:
            return fighter_uid

        if fighter.last_name in bfo_name_lower:
            first_initial = fighter.first_name[0] if fighter.first_name else ""
            if first_initial and bfo_name_lower.startswith(first_initial):
                return fighter_uid
            if bfo_name_lower == fighter.last_name:
                return fighter_uid
            if bfo_name_lower.endswith(fighter.last_name):
                return fighter_uid

    return None


def get_fight_uid_for_fighters(
    event_uid: str, fighter1_uid: str, fighter2_uid: str
) -> Optional[str]:
    engine = get_engine()
    with Session(engine) as session:
        fight = session.exec(
            select(UFCFight).where(
                col(UFCFight.event_uid) == event_uid,
                (
                    (
                        (col(UFCFight.fighter1_uid) == fighter1_uid)
                        & (col(UFCFight.fighter2_uid) == fighter2_uid)
                    )
                    | (
                        (col(UFCFight.fighter1_uid) == fighter2_uid)
                        & (col(UFCFight.fighter2_uid) == fighter1_uid)
                    )
                ),
            )
        ).first()

        if fight:
            return fight.fight_uid
    return None


def parse_event_odds(
    session: requests.Session,
    event_url: str,
    event_uid: str,
    fighters: dict[str, FighterMatch],
) -> list[UFCBettingOdds]:
    odds_list: list[UFCBettingOdds] = []
    current_ts = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")

    try:
        response = session.get(event_url, timeout=30)
        if response.status_code != 200:
            return odds_list

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table", class_="odds-table")

        if not tables:
            tables = soup.find_all("table")

        for table in tables:
            header_row = table.find("tr", class_="table-header")
            if not header_row:
                thead = table.find("thead")
                if thead:
                    header_row = thead.find("tr")

            bookmakers: list[str] = []
            if header_row:
                header_cells = header_row.find_all(["th", "td"])
                for cell in header_cells[1:]:
                    book_name = cell.get_text(strip=True)
                    if book_name:
                        bookmakers.append(book_name)

            if not bookmakers:
                bookmakers = ["BestFightOdds"]

            rows = table.find_all("tr")
            fight_rows: list[tuple[bs4.Tag, bs4.Tag]] = []
            i = 0
            while i < len(rows) - 1:
                row1 = rows[i]
                row2 = rows[i + 1]

                if "table-header" in row1.get("class", []):
                    i += 1
                    continue

                name_cell1 = row1.find("th", class_="oppcell")
                name_cell2 = row2.find("th", class_="oppcell")

                if name_cell1 and name_cell2:
                    fight_rows.append((row1, row2))
                    i += 2
                else:
                    i += 1

            for row1, row2 in fight_rows:
                name_cell1 = row1.find("th", class_="oppcell")
                name_cell2 = row2.find("th", class_="oppcell")

                if not name_cell1 or not name_cell2:
                    continue

                fighter1_name = name_cell1.get_text(strip=True)
                fighter2_name = name_cell2.get_text(strip=True)

                fighter1_uid = match_fighter_name(fighter1_name, fighters)
                fighter2_uid = match_fighter_name(fighter2_name, fighters)

                if not fighter1_uid or not fighter2_uid:
                    continue

                fight_uid = get_fight_uid_for_fighters(event_uid, fighter1_uid, fighter2_uid)
                if not fight_uid:
                    continue

                odds_cells1 = row1.find_all("td", class_="moneyline")
                odds_cells2 = row2.find_all("td", class_="moneyline")

                for idx, bookmaker in enumerate(bookmakers):
                    if idx < len(odds_cells1):
                        cell = odds_cells1[idx]
                        opening_span = cell.find("span", class_="opening")
                        closing_span = cell.find("span", class_="closing")

                        if opening_span:
                            opening = parse_american_odds(opening_span.get_text(strip=True))
                        else:
                            opening = None

                        if closing_span:
                            closing = parse_american_odds(closing_span.get_text(strip=True))
                        else:
                            closing = parse_american_odds(cell.get_text(strip=True))

                        if opening is not None or closing is not None:
                            odds_list.append(
                                UFCBettingOdds(
                                    fight_uid=fight_uid,
                                    fighter_uid=fighter1_uid,
                                    bookmaker=bookmaker,
                                    opening_odds=opening,
                                    closing_odds=closing,
                                    scraped_ts=current_ts,
                                )
                            )

                    if idx < len(odds_cells2):
                        cell = odds_cells2[idx]
                        opening_span = cell.find("span", class_="opening")
                        closing_span = cell.find("span", class_="closing")

                        if opening_span:
                            opening = parse_american_odds(opening_span.get_text(strip=True))
                        else:
                            opening = None

                        if closing_span:
                            closing = parse_american_odds(closing_span.get_text(strip=True))
                        else:
                            closing = parse_american_odds(cell.get_text(strip=True))

                        if opening is not None or closing is not None:
                            odds_list.append(
                                UFCBettingOdds(
                                    fight_uid=fight_uid,
                                    fighter_uid=fighter2_uid,
                                    bookmaker=bookmaker,
                                    opening_odds=opening,
                                    closing_odds=closing,
                                    scraped_ts=current_ts,
                                )
                            )

    except (requests.RequestException, Exception):
        pass

    return odds_list


def scrape_event_odds(
    event: UFCEvent,
    event_num: int,
    total_events: int,
    session: requests.Session,
    event_url: Optional[str],
    delay_range: tuple[float, float] = (1.0, 3.0),
) -> EventOddsResult:
    title = f"[{event_num + 1:04d}/{total_events:04d}] {event.title}"
    print(create_header(80, title, False, "."))

    delay = random.uniform(delay_range[0], delay_range[1])
    time.sleep(delay)

    if not event_url:
        return EventOddsResult(
            event_uid=event.event_uid,
            event_title=event.title,
            success=False,
            odds=[],
            error="event_not_found",
        )

    fighters = get_fighters_for_event(event.event_uid)
    if not fighters:
        return EventOddsResult(
            event_uid=event.event_uid,
            event_title=event.title,
            success=False,
            odds=[],
            error="no_fighters_found",
        )

    odds = parse_event_odds(session, event_url, event.event_uid, fighters)

    return EventOddsResult(
        event_uid=event.event_uid,
        event_title=event.title,
        success=len(odds) > 0,
        odds=odds,
        error=None if odds else "no_odds_parsed",
    )


def get_events_to_scrape(force: bool = False) -> list[UFCEvent]:
    engine = get_engine()

    with Session(engine) as session:
        if force:
            events = session.exec(select(UFCEvent).order_by(col(UFCEvent.event_date).desc())).all()
            return list(events)

        scraped_fight_uids = session.exec(select(UFCBettingOdds.fight_uid).distinct()).all()
        scraped_fight_uids_set = set(scraped_fight_uids)

        all_events = session.exec(select(UFCEvent).order_by(col(UFCEvent.event_date).desc())).all()

        events_to_scrape = []
        for event in all_events:
            fights = session.exec(
                select(UFCFight).where(col(UFCFight.event_uid) == event.event_uid)
            ).all()

            fight_uids = {f.fight_uid for f in fights}
            if not fight_uids.issubset(scraped_fight_uids_set):
                events_to_scrape.append(event)

        return events_to_scrape


def scrape_odds_sequential(
    events: list[UFCEvent],
    archive: list[BFOEvent],
    upcoming: dict[str, str],
    delay_range: tuple[float, float] = (1.0, 3.0),
) -> list[EventOddsResult]:
    results: list[EventOddsResult] = []
    session = get_session()

    for i, event in enumerate(events):
        event_url = find_bfo_event_url(event, archive, upcoming)
        result = scrape_event_odds(event, i, len(events), session, event_url, delay_range)
        results.append(result)

    return results


def scrape_odds_parallel(
    events: list[UFCEvent],
    archive: list[BFOEvent],
    upcoming: dict[str, str],
    max_workers: int = 2,
    delay_range: tuple[float, float] = (2.0, 5.0),
) -> list[EventOddsResult]:
    results: list[EventOddsResult] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_event = {}
        for i, event in enumerate(events):
            session = get_session()
            event_url = find_bfo_event_url(event, archive, upcoming)
            future = executor.submit(
                scrape_event_odds, event, i, len(events), session, event_url, delay_range
            )
            future_to_event[future] = event

        for future in as_completed(future_to_event):
            result = future.result()
            results.append(result)

    return results


def save_odds_to_db(odds: list[UFCBettingOdds]) -> int:
    if not odds:
        return 0

    engine = get_engine()
    with Session(engine) as session:
        for odd in odds:
            session.merge(odd)
        session.commit()

    return len(odds)


def scrape_betting_odds(
    force: bool = False,
    sequential: bool = True,
    n: int = 0,
    max_workers: int = 2,
    delay_range: tuple[float, float] = (1.0, 3.0),
) -> dict[str, int]:
    print(create_header(80, "SCRAPING BETTING ODDS", True, "="))

    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[UFCBettingOdds.__table__])  # pyright: ignore[reportAttributeAccessIssue]

    events = get_events_to_scrape(force)
    # if n > 0:
    #     events = events[:n]

    events = events[0:3]

    print(f"[n={len(events):5,d}] events to scrape")

    if not events:
        print("No events to scrape")
        return {"success": 0, "failed": 0, "odds_saved": 0}

    oldest_date = min(e.event_date for e in events)
    http_session = get_session()
    print("Fetching BFO event listings...")
    upcoming = fetch_bfo_upcoming(http_session)
    archive = fetch_bfo_archive(http_session, oldest_date)
    print(f"[n={len(archive):5,d}] archive events, [{len(upcoming):5,d}] upcoming events")

    if sequential:
        results = scrape_odds_sequential(events, archive, upcoming, delay_range)
    else:
        results = scrape_odds_parallel(events, archive, upcoming, max_workers, delay_range)

    total_odds: list[UFCBettingOdds] = []
    success_count = 0
    fail_count = 0

    for result in results:
        if result.success:
            success_count += 1
            total_odds.extend(result.odds)
        else:
            fail_count += 1
            print(f"  Failed: {result.event_title} - {result.error}")

    odds_saved = save_odds_to_db(total_odds)

    print(create_header(80, "RESULTS", True, "-"))
    print(f"Events succeeded: {success_count}")
    print(f"Events failed: {fail_count}")
    print(f"Odds records saved: {odds_saved}")

    return {"success": success_count, "failed": fail_count, "odds_saved": odds_saved}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape UFC betting odds")
    parser.add_argument("--force", action="store_true", help="Re-scrape all events")
    parser.add_argument("--sequential", action="store_true", default=True, help="Run sequentially")
    parser.add_argument("--parallel", action="store_true", help="Run with limited parallelism")
    parser.add_argument("-n", type=int, default=0, help="Limit number of events")
    parser.add_argument("--max-workers", type=int, default=2, help="Max parallel workers")
    parser.add_argument(
        "--min-delay", type=float, default=1.0, help="Min delay between requests (s)"
    )
    parser.add_argument(
        "--max-delay", type=float, default=3.0, help="Max delay between requests (s)"
    )

    args = parser.parse_args()

    scrape_betting_odds(
        force=args.force,
        sequential=not args.parallel,
        n=args.n,
        max_workers=args.max_workers,
        delay_range=(args.min_delay, args.max_delay),
    )
