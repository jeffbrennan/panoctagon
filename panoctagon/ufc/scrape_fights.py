import sqlite3
import requests
from dataclasses import dataclass
from common import write_tuples_to_db, get_con, get_table_rows
import bs4
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


class FightStyle(str, Enum):
    MMA = "MMA"
    MUAY_THAI = "Muay Thai"
    BJJ = "Brazilian Jiu-Jitsu"


class FightType(str, Enum):
    BOUT = "bout"
    TITLE = "title"


@dataclass(frozen=True)
class Decision:
    fight_uid: str
    decision: str
    method: str
    decision_round: int
    decision_time_seconds: int
    referee: str
    judge1_uid: str
    judge2_uid: str
    judge3_uid: str
    judge1_score1: int
    judge1_score2: int
    judge2_score1: int
    judge2_score2: int
    judge3_score1: int
    judge3_score2: int


@dataclass(frozen=True)
class Fight:
    event_uid: str
    fight_uid: str
    fight_style: FightStyle
    fight_type: FightType
    fighter_uid: str
    round_num: int
    knockdowns: int
    sig_strikes_landed: int
    sig_strikes_attempted: int
    total_strikes_landed: int
    total_strikes_attempted: int
    takedowns_landed: int
    takedowns_attempted: int
    submissions_attempted: int
    reversals: int
    control_time_seconds: int
    sig_strikes_head_landed: int
    sig_strikes_head_attempted: int
    sig_strikes_body_landed: int
    sig_strikes_body_attempted: int
    sig_strikes_leg_landed: int
    sig_strikes_leg_attempted: int
    sig_strikes_distance_landed: int
    sig_strikes_distance_attempted: int
    sig_strikes_clinch_landed: int
    sig_strikes_clinch_attempted: int
    sig_strikes_grounded_landed: int
    sig_strikes_grounded_attempted: int


def write_fight_stats(fight: Fight) -> None:
    con, _ = get_con()
    write_tuples_to_db(con, "raw_fights", [fight])


def read_event_uids():
    con = sqlite3.connect("../../data/panoctagon.db")
    cur = con.cursor()
    cur.execute("select event_uid from ufc_events")
    uids = [i[0] for i in cur.fetchall()]
    return uids


def parse_fight(fight_html: bs4.BeautifulSoup) -> Fight:
    raise NotImplementedError()

def parse_decision() -> Decision:
    raise NotImplementedError()


def get_fight_html_files() -> list[str]:
    base_dir = Path(__file__).parents[2] / "data/raw/ufc/fights"
    all_files = base_dir.glob("*.html")

    all_html = []
    for fight_file in all_files:
        with fight_file.open("r") as f:
            all_html.append(f.read())

    return all_html


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
        fight_uid = row.a["href"].split("/")[-1]
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
    # event_uids = read_event_uids()
    # n_events = len(event_uids)
    # for i, uid in enumerate(event_uids, 1):
    #     print(f"[{i:03d}/{n_events:03d}] processing event : {uid}")
    #     get_fights_from_event(uid)

    fights = get_fight_html_files()
    print(len(fights))
    for i, fight in enumerate(fights):
        fight_soup = bs4.BeautifulSoup(fight)
        print("processing fight", i)
        parse_fight(fight_soup)


if __name__ == "__main__":
    main()
