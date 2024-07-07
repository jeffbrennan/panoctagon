from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import bs4
from sqlmodel import col

from panoctagon.common import (
    create_header,
    delete_existing_records,
    get_html_files,
    handle_parsing_issues,
    write_data_to_db,
    setup_panoctagon,
)
from panoctagon.enums import Stance
from panoctagon.models import FighterParsingResult, FileContents
from panoctagon.tables import UFCFighter


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

    fighter_parsed = UFCFighter(
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
        downloaded_ts=fighter.modified_ts.isoformat(),
    )

    return FighterParsingResult(
        uid=fighter.uid, result=fighter_parsed, issues=parsing_issues
    )


def write_fighter_results_to_db(
    results: list[FighterParsingResult], force_run: bool
) -> None:
    tbl_name = "ufc_fighters"
    print(create_header(80, tbl_name, True, spacer="-"))

    clean_results = handle_parsing_issues(results, False)
    fighters = [i.result for i in clean_results]
    if force_run:
        uids = [i.fighter_uid for i in fighters]
        delete_existing_records(UFCFighter, col(UFCFighter.fighter_uid), uids)

    write_data_to_db(fighters)


def main() -> None:
    setup = setup_panoctagon(title="Panoctagon UFC Fighter Parser")
    script_dir = Path(__file__).parents[2] / "data/raw/ufc/fighters"
    if not script_dir.exists():
        raise ValueError("expecting a directory containing at least one fighter")

    fighters = get_html_files(
        script_dir, col(UFCFighter.fighter_uid), force_run=setup.args.force
    )

    if len(fighters) == 0:
        print("no fighters to parse. exiting early")
        print(setup.footer)
        return

    with ProcessPoolExecutor(max_workers=setup.cpu_count - 1) as executor:
        results = list(executor.map(parse_fighter, fighters))
    print(len(results))

    write_fighter_results_to_db(results, setup.args.force)
    print(setup.footer)


if __name__ == "__main__":
    main()
