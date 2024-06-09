import datetime
from dataclasses import dataclass

import requests
import bs4

from panoctagon.common import write_tuples_to_db, get_con


@dataclass(frozen=True)
class UFCEvent:
    event_uid: str
    title: str
    event_date: str
    event_location: str


def write_events(urls: list[UFCEvent]) -> None:
    con, cur = get_con()
    cur.execute(
        """
               CREATE TABLE IF NOT EXISTS
                ufc_events(
                event_uid TEXT PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_location TEXT NOT NULL
                );
 
        """
    )

    write_tuples_to_db(con, "ufc_events", urls)


def get_events() -> list[UFCEvent]:
    url = "http://www.ufcstats.com/statistics/events/completed?page=all"
    soup = bs4.BeautifulSoup(requests.get(url).content, "html.parser")

    data: list[UFCEvent] = []
    table = soup.find("table")
    if table is None:
        raise ValueError("No table found")

    table_body = table.find("tbody")
    if not isinstance(table_body, bs4.Tag):
        raise TypeError(f"expected bs4.Tag, got {type(table_body)}")

    rows = table_body.find_all("tr")
    if rows is None:
        raise ValueError()

    unparsed_events = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) != 2:
            continue

        url = row.a["href"]
        event_uid = url.split("/")[-1]
        title = row.a.text.strip()
        fight_location = cols[-1].text.strip()

        fight_date_txt: str = row.find("span", class_="b-statistics__date").text.strip()
        if fight_date_txt is None:
            unparsed_events.append(event_uid)
            continue

        fight_date = datetime.datetime.strptime(fight_date_txt, "%B %d, %Y")
        fight_date_formatted = datetime.datetime.strftime(fight_date, "%Y-%m-%d")
        if fight_date_formatted is None:
            unparsed_events.append(event_uid)
            continue

        results = (url, title, fight_date_formatted, fight_location)
        blank_strings = [i == "" for i in results]
        null_results = [i is None for i in results]

        if any(blank_strings) or any(null_results):
            print("parsing error")
            unparsed_events.append(event_uid)
            continue

        result = UFCEvent(event_uid, title, fight_date_formatted, fight_location)

        data.append(result)
    print(f"obtained {len(data)} fight urls")
    if len(unparsed_events) > 0:
        raise AssertionError(f"{len(unparsed_events)} unparsed events")

    return data


def main():
    print("getting stats")
    events = get_events()
    write_events(events)


if __name__ == "__main__":
    main()
