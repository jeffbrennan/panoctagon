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


class Decision(str, Enum):
    KO = "Knockout"
    TKO = "Technical Knockout"
    UNANIMOUS_DECISION = "Unanimous Decision"
    SPLIT_DECISION = "Split Decision"
    DRAW = "Draw"
    NO_CONTEST = "No Contest"
    DQ = "Disqualificaton"


@dataclass(frozen=True)
class Fight:
    event_uid: str
    fight_uid: str
    fight_style: FightStyle
    fight_type: FightType
    decision: str
    method: str
    decision_round: int
    decision_time_seconds: int
    referee: str


@dataclass(frozen=True)
class RoundSigStats:
    fight_uid: str
    fighter_uid: str
    round_num: int
    sig_strikes_landed: int
    sig_strikes_attempted: int
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


@dataclass(frozen=True)
class RoundTotalStats:
    fight_uid: str
    fighter_uid: str
    round_num: int
    knockdowns: int
    total_strikes_landed: int
    total_strikes_attempted: int
    takedowns_landed: int
    takedowns_attempted: int
    submissions_attempted: int
    reversals: int
    control_time_seconds: int


@dataclass(frozen=True)
class RoundStats:
    fight_uid: str
    fighter_uid: str
    round_num: int
    total_stats: RoundTotalStats
    sig_stats: RoundSigStats


@dataclass(frozen=True)
class FightContents:
    fight_uid: str
    contents: str


def write_fight_stats(fight: Fight) -> None:
    con, _ = get_con()
    write_tuples_to_db(con, "raw_fights", [fight])


def read_event_uids():
    con = sqlite3.connect("../../data/panoctagon.db")
    cur = con.cursor()
    cur.execute("select event_uid from ufc_events")
    uids = [i[0] for i in cur.fetchall()]
    return uids


def parse_sig_totals(
    fight_html: bs4.BeautifulSoup, fight_uid: str
) -> list[RoundSigStats]:
    tbl = get_table_rows(fight_html, 3)
    if len(tbl) != 1:
        raise ValueError()

    tbl = tbl[0]
    totals_cols = [i.text.strip() for i in tbl.findAll("th")][:-3]
    expected_cols = [
        "Fighter",
        "KD" "Sig. str.",
        "Sig. str. %",
        "Total str.",
        "Td %",
        "Td %",
        "Sub. att",
        "Rev.",
        "Ctrl",
    ]
    if totals_cols != expected_cols:
        raise ValueError()

    totals_per_round = get_table_rows(fight_html, 1)
    totals = []
    for round_num, round in enumerate(totals_per_round, 1):
        vals = [
            i.text.strip()
            for i in round.findAll("p", class_="b-fight-details__table-text")
        ]
        totals_raw = dict(zip(totals_cols, vals))

    return totals


def get_split_stat(stat: str, sep: str) -> tuple[int, int]:
    "parses stat like `1 of 2` to a tuple containing `1` and `2`"
    val1, val2 = stat.split(f" {sep} ")
    return (int(val1), int(val2))


def parse_round_totals(
    fight_html: bs4.BeautifulSoup, fight_uid: str
) -> list[RoundTotalStats]:
    totals_cols = [i.text.strip() for i in fight_html.findAll("table")[0].findAll("th")]
    expected_cols = [
        "Fighter",
        "KD",
        "Sig. str.",
        "Sig. str. %",
        "Total str.",
        "Td",
        "Td %",
        "Sub. att",
        "Rev.",
        "Ctrl",
    ]
    if totals_cols != expected_cols:
        raise ValueError()

    totals_per_round = get_table_rows(fight_html, 1)
    totals = []
    for round_num, round in enumerate(totals_per_round, 1):
        vals = [
            val.text.strip()
            for val in round.findAll("p", class_="b-fight-details__table-text")
        ]
        f1_vals = [val for i, val in enumerate(vals) if i % 2 == 0]
        f2_vals = [val for i, val in enumerate(vals) if i % 2 == 1]

        f1_uid, f2_uid = [i["href"].split("/")[-1] for i in round.findAll("a")]
        if len(f1_vals) != len(totals_cols) or len(f2_vals) != len(totals_cols):
            raise ValueError(
                f"Round {round_num} has {len(totals_cols)} cols. Got {len(vals)} values"
            )

        f1_totals_raw = dict(zip(totals_cols, f1_vals))
        f2_totals_raw = dict(zip(totals_cols, f2_vals))

        f1_totals_raw["Fighter"] = f1_uid
        f2_totals_raw["Fighter"] = f2_uid
        all_totals_raw = [f1_totals_raw, f2_totals_raw]

        for totals_raw in all_totals_raw:
            total_strikes_landed, total_strikes_attempted = get_split_stat(
                totals_raw["Total str."], "of"
            )
            takedowns_landed, takedowns_attempted = get_split_stat(
                totals_raw["Td"], "of"
            )
            control_time = totals_raw["Ctrl"].split(":")
            control_time_seconds = (int(control_time[0]) * 60) + (int(control_time[1]))
            totals.append(
                RoundTotalStats(
                    fight_uid=fight_uid,
                    fighter_uid=totals_raw["Fighter"],
                    round_num=round_num,
                    knockdowns=int(totals_raw["KD"]),
                    total_strikes_landed=total_strikes_landed,
                    total_strikes_attempted=total_strikes_attempted,
                    takedowns_landed=takedowns_landed,
                    takedowns_attempted=takedowns_attempted,
                    submissions_attempted=int(totals_raw["Sub. att"]),
                    reversals=int(totals_raw["Rev."]),
                    control_time_seconds=control_time_seconds,
                )
            )

    return totals


def get_event_uid(fight_html: bs4.BeautifulSoup) -> str:
    event_uid_results = [
        i for i in fight_html.findAll("a") if "event-details" in str(i)
    ]
    if len(event_uid_results) != 1:
        raise ValueError(f"Expected exactly one event, got {len(event_uid_results)}")

    event_uid = event_uid_results[0]["href"].split("/")[-1]
    return event_uid


def parse_fight(fight_contents: FightContents) -> tuple[Fight, list[RoundStats]]:
    fight_html = bs4.BeautifulSoup(fight_contents.contents)
    fight_tables = fight_html.findAll("table")
    if len(fight_tables) != 4:
        raise ValueError(f"Expected 4 tables, got {len(fight_tables)}")

    event_uid = get_event_uid(fight_html)
    total_stats = parse_round_totals(fight_html, fight_contents.fight_uid)
    sig_stats = parse_sig_totals(fight_html, fight_contents.fight_uid)

    # merge total stats and sig strikes


def get_fight_html_files() -> list[FightContents]:
    base_dir = Path(__file__).parents[2] / "data/raw/ufc/fights"
    all_files = base_dir.glob("*.html")

    all_fight_contents = []
    for fight_file in all_files:
        fight_uid = fight_file.stem
        with fight_file.open("r") as f:
            all_fight_contents.append(
                FightContents(fight_uid=fight_uid, contents=f.read())
            )

    return all_fight_contents


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
    # event_uids = read_event_uids()
    # n_events = len(event_uids)
    # for i, uid in enumerate(event_uids, 1):
    #     print(f"[{i:03d}/{n_events:03d}] processing event : {uid}")
    #     get_fights_from_event(uid)

    fights = get_fight_html_files()[0:1]
    print(len(fights))
    for i, fight in enumerate(fights):
        print("processing fight", i)
        parse_fight(fight)


if __name__ == "__main__":
    main()
