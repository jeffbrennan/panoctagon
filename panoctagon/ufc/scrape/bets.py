import datetime
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

import bs4
import requests
from sqlmodel import Session, select

from panoctagon.common import create_header, get_engine
from panoctagon.tables import UFCEvent

BASE_URL = "https://www.bestfightodds.com"
RAW_ODDS_DIR = Path(__file__).parents[3] / "data" / "raw" / "ufc" / "betting_odds"
RAW_API_DIR = RAW_ODDS_DIR / "api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


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


@dataclass
class BFOMatchup:
    match_id: int
    fighter1_name: str
    fighter2_name: str


def parse_bfo_date(date_str: str) -> datetime.date:
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str.strip())
    return datetime.datetime.strptime(cleaned, "%b %d %Y").date()


# ---------------------------------------------------------------------------
# Step 1: Search for events + download event HTML pages
# ---------------------------------------------------------------------------

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


def _api_response_path(match_id: int, player: int) -> Path:
    return RAW_API_DIR / f"m{match_id}_p{player}.txt"


def download_fight_odds(
    delay_range: tuple[float, float] = (0.2, 0.5),
    max_downloads: int | None = None,
) -> dict[str, int]:
    print(create_header(80, "DOWNLOADING FIGHT ODDS API RESPONSES", True, "="))
    RAW_API_DIR.mkdir(exist_ok=True, parents=True)
    session = get_session()

    event_htmls = sorted(RAW_ODDS_DIR.glob("*.html"))
    print(f"  {len(event_htmls)} event pages on disk")

    pending: list[tuple[int, int, str]] = []
    for html_path in event_htmls:
        html = html_path.read_text(encoding="utf-8")
        matchups = parse_matchups_from_html(html)
        for matchup in matchups:
            for player in (1, 2):
                if not _api_response_path(matchup.match_id, player).exists():
                    name = matchup.fighter1_name if player == 1 else matchup.fighter2_name
                    pending.append((matchup.match_id, player, name))

    print(f"  {len(pending)} API responses to download")

    if max_downloads is not None:
        pending = pending[:max_downloads]

    downloaded = 0
    failed = 0
    total = len(pending)
    for i, (match_id, player, name) in enumerate(pending, 1):
        time.sleep(random.uniform(*delay_range))
        try:
            response = session.get(
                f"{BASE_URL}/api/ggd",
                params={"m": match_id, "p": player},
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=30,
            )
            if response.status_code != 200:
                print(f"  failed m={match_id} p={player} ({name}): HTTP {response.status_code}")
                failed += 1
                continue
        except requests.RequestException as e:
            print(f"  error m={match_id} p={player} ({name}): {e}")
            failed += 1
            continue

        _api_response_path(match_id, player).write_text(response.text, encoding="utf-8")
        downloaded += 1
        print(f"  [{i}/{total}] m={match_id} p={player} {name}")

    existing = len(list(RAW_API_DIR.glob("*.txt")))
    print(f"\n[n={downloaded:5,d}] newly downloaded")
    print(f"[n={failed:5,d}] failed")
    print(f"[n={existing:5,d}] total on disk")

    return {"downloaded": downloaded, "failed": failed, "total_on_disk": existing}
