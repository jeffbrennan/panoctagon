import datetime

import bs4
import requests
from sqlmodel import col

from panoctagon.common import (
    get_table_rows,
    write_data_to_db,
    get_table_uids,
    delete_existing_records,
    setup_panoctagon,
)
from panoctagon.tables import UFCEvent


def get_events(all_events: bool, page_num: int = 1) -> list[UFCEvent]:
    url = f"http://www.ufcstats.com/statistics/events/completed?page={page_num}"
    if all_events:
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

    if len(unparsed_events) > 0:
        raise AssertionError(f"{len(unparsed_events)} unparsed events")

    return data


def main():
    setup = setup_panoctagon(title="Panoctagon UFC Event Scraper")
    existing_events = get_table_uids(col(UFCEvent.event_uid))

    if setup.args.force and existing_events is not None:
        delete_existing_records(UFCEvent, col(UFCEvent.event_uid), uids=existing_events)
        existing_events = None

    all_events = existing_events is None or setup.args.force
    events = get_events(all_events)

    if existing_events is None:
        new_events = events
    else:
        new_events = [i for i in events if i.event_uid not in existing_events]

    if len(new_events) == 0:
        print("no new events. exiting early")
        print(setup.footer)
        return

    write_data_to_db(new_events)
    print(setup.footer)


if __name__ == "__main__":
    main()
