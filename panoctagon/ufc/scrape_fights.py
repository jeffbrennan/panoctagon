import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bs4
import requests

from panoctagon.common import get_table_rows


def read_event_uids():
    con = sqlite3.connect("../../data/panoctagon.db")
    cur = con.cursor()
    cur.execute("select event_uid from ufc_events")
    uids = [i[0] for i in cur.fetchall()]
    return uids


def dump_fight_html(fight_uid: str) -> None:
    print(f"saving fight: {fight_uid}")
    url = f"http://www.ufcstats.com/fight-details/{fight_uid}"
    output_path = Path(__file__).parents[2] / f"data/raw/ufc/fights/{fight_uid}.html"

    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")

    with output_path.open("w") as f:
        f.write(str(soup))


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


def get_fights_from_event(uid):
    url = f"http://www.ufcstats.com/event-details/{uid}"
    response = requests.get(url).content
    soup = bs4.BeautifulSoup(response, "html.parser")
    fight_uids = get_list_of_fights(soup)
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(dump_fight_html, fight_uids)


def main() -> None:
    event_uids = read_event_uids()
    n_events = len(event_uids)
    for i, uid in enumerate(event_uids, 1):
        print(f"[{i:03d}/{n_events:03d}] processing event : {uid}")
        get_fights_from_event(uid)


if __name__ == "__main__":
    main()
