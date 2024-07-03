import datetime

import bs4
import requests
from panoctagon.common import get_con, get_table_rows, write_data_to_db
from panoctagon.models import UFCEvent


def write_events(urls: list[UFCEvent]) -> None:
    con, cur = get_con()
    cur.execute(
        """
               CREATE TABLE IF NOT EXISTS
                ufc_events(
                event_uid TEXT PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_location TEXT NOT NULL,
                downloaded_ts TEXT
                );
 
        """
    )

    write_data_to_db(con, "ufc_events", urls)


def get_events() -> list[UFCEvent]:
    url = "http://www.ufcstats.com/statistics/events/completed?page=all"
    soup = bs4.BeautifulSoup(requests.get(url).content, "html.parser")

    data: list[UFCEvent] = []
    rows = get_table_rows(soup)
    unparsed_events: list[str] = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) != 2:
            continue

        if row.a is None:
            continue

        url = row.a["href"]
        if not isinstance(url, str):
            raise TypeError()

        event_uid = url.split("/")[-1]
        title = row.a.text.strip()
        event_location = cols[-1].text.strip()

        fight_date_txt_raw = row.find("span", class_="b-statistics__date")
        if fight_date_txt_raw is None:
            unparsed_events.append(event_uid)
            continue

        fight_date_txt = fight_date_txt_raw.text.strip()
        if fight_date_txt == "":
            unparsed_events.append(event_uid)
            continue

        fight_date = datetime.datetime.strptime(fight_date_txt, "%B %d, %Y")
        event_date_formatted = datetime.datetime.strftime(fight_date, "%Y-%m-%d")
        if event_date_formatted == "":
            unparsed_events.append(event_uid)
            continue

        results = (url, title, event_date_formatted, event_location)
        blank_strings = [i == "" for i in results]
        null_results = [i is None for i in results]

        if any(blank_strings) or any(null_results):
            print("parsing error")
            unparsed_events.append(event_uid)
            continue

        result = UFCEvent(
            event_uid=event_uid,
            title=title,
            event_date=event_date_formatted,
            event_location=event_location,
        )

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
