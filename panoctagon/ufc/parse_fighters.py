import argparse
import os
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import bs4
from panoctagon.common import (
    Fighter,
    FighterParsingResult,
    FileContents,
    Stance,
    create_header,
    delete_existing_records,
    get_con,
    get_html_files,
    handle_parsing_issues,
    write_data_to_db,
)


def create_fighters_table(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS
        ufc_fighters(
            fighter_uid TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            nickname TEXT,
            dob TEXT NOT NULL,
            place_of_birth TEXT,
            stance TEXT,
            style TEXT,
            height_inches INTEGER,
            reach_inches INTEGER,
            leg_reach_inches INTEGER,
            PRIMARY KEY (fighter_uid)
            ) STRICT;

    """
    )


def parse_fighter(fighter: FileContents) -> FighterParsingResult:
    if fighter.file_num % 100 == 0:
        print(f"{fighter.file_num:04d} / {fighter.n_files:04d}")
    parsing_issues = []
    fighter_html = bs4.BeautifulSoup(
        fighter.contents, parser="html.parser", features="lxml"
    )

    fighter_name_raw = fighter_html.find("span", class_="b-content__title-highlight")
    if fighter_name_raw is None:
        parsing_issues.append("name not found")
        first_name = ""
        last_name = ""
    else:
        fighter_name_split = fighter_name_raw.text.strip().split(" ")
        first_name = fighter_name_split[0]
        last_name = " ".join(fighter_name_split[1:])

    nickname_raw = fighter_html.find("p", class_="b-content__Nickname")
    if nickname_raw is None:
        nickname = None
    else:
        nickname = nickname_raw.text.strip().replace("'", "")
        if nickname == "":
            nickname = None
    all_stats_raw = {}
    stats = fighter_html.findAll("li", class_="b-list__box-list-item")
    stats_bio = stats[0:5]
    for stat in stats_bio:
        stat_split = stat.text.strip().split(":")
        col_name = stat_split[0].strip().lower()
        val = stat_split[1].strip().replace('"', "").replace("' ", "'")
        if val == "--":
            val = None
        all_stats_raw[col_name] = val
    parsing_issues = []
    height_inches = None
    if all_stats_raw["height"] is not None:
        height_split = all_stats_raw["height"].split("'")
        height_inches = (int(height_split[0]) * 12) + int(height_split[1])

    stance = None
    if all_stats_raw["stance"] is not None:
        stance_clean = all_stats_raw["stance"].replace("'", "")
        if stance_clean != "":
            try:
                stance = Stance(all_stats_raw["stance"])
            except ValueError as e:
                parsing_issues.append(str(e))
                stance = None
        else:
            stance = None

    reach_inches = None
    if all_stats_raw["reach"] is not None:
        reach_inches = int(all_stats_raw["reach"])
    dob = None
    if all_stats_raw["dob"] is not None:
        dob_raw = all_stats_raw["dob"]
        dob = datetime.strptime(dob_raw, "%b %d, %Y").strftime("%Y-%m-%d")

    fighter_parsed = Fighter(
        fighter_uid=fighter.uid,
        first_name=first_name,
        last_name=last_name,
        nickname=nickname,
        dob=dob,
        place_of_birth=None,
        stance=stance,
        style=None,
        height_inches=height_inches,
        reach_inches=reach_inches,
        leg_reach_inches=None,
    )

    return FighterParsingResult(
        uid=fighter.uid, result=fighter_parsed, issues=parsing_issues
    )


def write_fighter_results_to_db(
    results: list[FighterParsingResult], force_run: bool
) -> None:
    tbl_name = "ufc_fights"
    print(create_header(80, tbl_name, True, spacer="-"))
    con, cur = get_con()
    create_fighters_table(cur)

    clean_results = handle_parsing_issues(results, False)
    fighters = [i.result for i in clean_results]
    if force_run:
        uids: tuple[str, ...] = tuple(
            (str(i.fighter_uid) for i in fighters if i is not None)
        )
        delete_existing_records(tbl_name, "fighter_uid", uids)

    print(f"[n={len(fighters):5,d}] writing records")
    write_data_to_db(con, tbl_name, fighters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Panoctagon UFC Fighter Parser")
    parser.add_argument(
        "-f",
        "--force",
        help="force existing parsed fighters to be reprocessed",
        action="store_true",
        required=False,
        default=False,
    )
    args = parser.parse_args()
    print(create_header(80, "PANOCTAGON", True, "="))
    footer = create_header(80, "", True, "=")
    cpu_count = os.cpu_count()
    if cpu_count is None:
        cpu_count = 4

    fighters_dir = Path(__file__).parents[2] / "data/raw/ufc/fighters"
    fighters = get_html_files(
        fighters_dir, "fighter_uid", "ufc_fighters", force_run=True
    )

    if len(fighters) == 0:
        print("no fights to parse. exiting early")
        print(footer)
        return

    with ProcessPoolExecutor(max_workers=cpu_count - 1) as executor:
        results = list(executor.map(parse_fighter, fighters))
    print(len(results))

    write_fighter_results_to_db(results, args.force)
    print(footer)


if __name__ == "__main__":
    main()
