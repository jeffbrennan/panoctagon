import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bs4
import requests

from panoctagon.common import get_table_rows, ScrapingConfig, dump_html


def read_event_uids():
    con = sqlite3.connect("../../data/panoctagon.db")
    cur = con.cursor()
    cur.execute("select event_uid from ufc_events")
    uids = [i[0] for i in cur.fetchall()]
    return uids



def get_list_of_fights(soup: bs4.BeautifulSoup) -> list[str]:
    rows = get_table_rows(soup)
    fight_uids = []

    for row in rows:
        if row.a is None:
            continue

        row_href = row.a["href"]

        if not isinstance(row_href, str):
            continue

        fight_uid = row_href.split("/")[-1]
        fight_uids.append(fight_uid)

    return fight_uids


def get_fights_from_event(uid: str, base_dir: Path) -> None:
    url = f"http://www.ufcstats.com/event-details/{uid}"
    response = requests.get(url).content
    soup = bs4.BeautifulSoup(response, "html.parser")
    fight_uids = get_list_of_fights(soup)

    configs = [
        ScrapingConfig(
            uid=i,
            description="fight",
            base_url="http://www.ufcstats.com/fight-details",
            base_dir=base_dir,
            fname=i,
        )
        for i in fight_uids
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(dump_html, configs)


def main() -> None:
    event_uids = read_event_uids()
    n_events = len(event_uids)
    base_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fights"
    base_dir.mkdir(exist_ok=True)

    for i, uid in enumerate(event_uids, 1):
        print(f"[{i:03d}/{n_events:03d}] processing event : {uid}")
        get_fights_from_event(uid, base_dir)


if __name__ == "__main__":
    main()
