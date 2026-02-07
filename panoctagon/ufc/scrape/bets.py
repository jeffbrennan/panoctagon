import datetime
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import bs4
import requests
from sqlmodel import Session, select

from panoctagon.common import create_header, get_engine
from panoctagon.tables import UFCBettingOdds, UFCEvent

BASE_URL = "https://www.bestfightodds.com"
RAW_ODDS_DIR = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "betting_odds"
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
    event_date = datetime.date.fromisoformat(event.event_date)

    for bfo in archive:
        if bfo.date == event_date and "UFC" in bfo.name:
            return bfo.url

    if "UFC Fight Night" in upcoming:
        return upcoming["UFC Fight Night"]
    for name, url in upcoming.items():
        if name == "UFC" or (name.startswith("UFC ") and not re.search(r"UFC \d+", name)):
            return url

    return None


SEARCH_STATE_PATH = RAW_ODDS_DIR / "search_state.json"


def _load_search_state() -> dict[str, list[str]]:
    if not SEARCH_STATE_PATH.exists():
        return {"completed_terms": [], "discovered_events": []}
    return json.loads(SEARCH_STATE_PATH.read_text(encoding="utf-8"))


def _save_search_state(state: dict[str, list[str]]) -> None:
    SEARCH_STATE_PATH.parent.mkdir(exist_ok=True, parents=True)
    SEARCH_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _get_max_ufc_event_number() -> int:
    engine = get_engine()
    with Session(engine) as session:
        titles = session.exec(select(UFCEvent.title)).all()
    numbers = []
    for title in titles:
        match = re.match(r"UFC (\d+)", title)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers) if numbers else 325


def search_bfo_events(
    session: requests.Session,
    delay_range: tuple[float, float] = (1.0, 3.0),
    max_searches: int | None = None,
) -> list[BFOEvent]:
    max_event_num = _get_max_ufc_event_number()
    search_terms = [f"UFC {i}" for i in range(1, max_event_num + 1)] + ["UFC Fight Night"]

    state = _load_search_state()
    completed_terms = set(state["completed_terms"])
    all_events: dict[str, dict[str, str]] = {
        e["slug"]: e
        for e in state.get("discovered_events", [])  # type: ignore[union-attr]
    }

    pending_terms = [t for t in search_terms if t not in completed_terms]
    if max_searches is not None:
        pending_terms = pending_terms[:max_searches]
    if not pending_terms:
        print(f"  all {len(search_terms)} search terms already completed")
    else:
        print(
            f"  {len(pending_terms)} search terms remaining ({len(completed_terms)} already done)"
        )

    for term in pending_terms:
        time.sleep(random.uniform(*delay_range))
        try:
            response = session.get(f"{BASE_URL}/search", params={"query": term}, timeout=30)
            if response.status_code != 200:
                print(f"  search failed for '{term}': HTTP {response.status_code}")
                continue
        except requests.RequestException as e:
            print(f"  search error for '{term}': {e}")
            continue

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=re.compile(r"/events/")):
            href = str(link.get("href", ""))
            name = link.get_text(strip=True)
            if not name or not href or "future-events" in href:
                continue

            slug = href.rstrip("/").split("/")[-1]
            if slug in all_events:
                continue

            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            date_str = ""
            date_cell = link.find_parent("tr")
            if date_cell:
                date_td = date_cell.find("td", class_="content-list-date")
                if date_td:
                    date_str = date_td.get_text(strip=True)

            all_events[slug] = {"slug": slug, "name": name, "url": url, "date_str": date_str}

        completed_terms.add(term)
        state["completed_terms"] = sorted(completed_terms)
        state["discovered_events"] = list(all_events.values())  # type: ignore[assignment]
        _save_search_state(state)

        print(f"  searched '{term}': {len(all_events)} total events found")

    results: list[BFOEvent] = []
    for e in all_events.values():
        event_date = datetime.date.today()
        if e["date_str"]:
            try:
                event_date = parse_bfo_date(e["date_str"])
            except ValueError:
                pass
        results.append(BFOEvent(date=event_date, name=e["name"], url=e["url"]))

    return results


def download_bfo_event_pages(
    events: list[BFOEvent],
    session: requests.Session,
    delay_range: tuple[float, float] = (1.0, 3.0),
) -> int:
    RAW_ODDS_DIR.mkdir(exist_ok=True, parents=True)
    downloaded = 0

    for event in events:
        slug = event.url.rstrip("/").split("/")[-1]
        filepath = RAW_ODDS_DIR / f"{slug}.html"

        if filepath.exists():
            continue

        time.sleep(random.uniform(*delay_range))
        try:
            response = session.get(event.url, timeout=30)
            if response.status_code != 200:
                print(f"  download failed for {event.name}: HTTP {response.status_code}")
                continue
        except requests.RequestException as e:
            print(f"  download error for {event.name}: {e}")
            continue

        filepath.write_text(response.text, encoding="utf-8")
        downloaded += 1
        print(f"  [{downloaded}] downloaded {slug}")

    return downloaded


def download_bfo_pages(
    delay_range: tuple[float, float] = (1.0, 3.0),
    max_searches: int | None = None,
) -> dict[str, int]:
    print(create_header(80, "SEARCHING BFO EVENTS", True, "="))
    session = get_session()

    events = search_bfo_events(session, delay_range, max_searches=max_searches)
    print(f"\n[n={len(events):5,d}] total events discovered")

    print(create_header(80, "DOWNLOADING EVENT PAGES", True, "="))
    downloaded = download_bfo_event_pages(events, session, delay_range)

    existing = len(list(RAW_ODDS_DIR.glob("*.html")))
    print(f"\n[n={downloaded:5,d}] newly downloaded")
    print(f"[n={existing:5,d}] total on disk")

    return {"discovered": len(events), "downloaded": downloaded, "total_on_disk": existing}
