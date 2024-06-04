import datetime
import sqlite3
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from panoctagon.common import write_tuples_to_db


@dataclass(frozen=True)
class UFCEvent:
    url: str
    title: str
    event_date: str
    event_location: str


def write_events(urls: list[UFCEvent]) -> None:
    con = sqlite3.connect("../../data/panoctagon.db")
    cur = con.cursor()
    cur.execute(
        f"""
               CREATE TABLE IF NOT EXISTS
                ufc_events(
                url TEXT PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_location TEXT NOT NULL
                );
 
    """
    )

    write_tuples_to_db(con, "ufc_events", urls)


def get_events() -> list[UFCEvent]:
    url = "http://www.ufcstats.com/statistics/events/completed?page=all"
    soup = BeautifulSoup(requests.get(url).content, "html.parser")

    data: list[UFCEvent] = []
    table = soup.find("table")
    table_body = table.find("tbody")

    rows = table_body.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) != 2:
            continue

        url = row.a["href"]
        title = row.a.text.strip()
        fight_date_txt: str = row.find("span", class_="b-statistics__date").text.strip()
        fight_date_formatted = None
        if fight_date_txt is not None:
            fight_date = datetime.datetime.strptime(fight_date_txt, "%B %d, %Y")
            fight_date_formatted = datetime.datetime.strftime(fight_date, "%Y-%m-%d")
        fight_location = cols[-1].text.strip()

        results = (url, title, fight_date_formatted, fight_location)
        blank_strings = [i == "" for i in results]
        null_results = [i is None for i in results]

        if any(blank_strings) or any(null_results):
            print("parsing error")
            continue

        result = UFCEvent(url, title, fight_date_formatted, fight_location)

        data.append(result)
    print(f"obtained {len(data)} fight urls")
    return data


def main():
    print("getting stats")
    events = get_events()
    write_events(events)


if __name__ == "__main__":
    main()
