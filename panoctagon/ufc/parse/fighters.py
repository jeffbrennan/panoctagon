from datetime import datetime
from typing import Optional

import bs4
from pydantic import BaseModel
from sqlmodel import col

from panoctagon.common import (
    create_header,
    delete_existing_records,
    handle_parsing_issues,
    write_data_to_db,
)
from panoctagon.enums import Stance
from panoctagon.models import FighterParsingResult, FileContents
from panoctagon.tables import UFCFighter


class FighterStatsRaw(BaseModel):
    height: Optional[str] = None
    stance: Optional[str] = None
    reach: Optional[str] = None
    dob: Optional[str] = None


class FighterStats(BaseModel):
    height_inches: Optional[int] = None
    stance: Optional[Stance] = None
    reach_inches: Optional[int] = None
    dob: Optional[str] = None


def parse_fighter(fighter: FileContents) -> FighterParsingResult:
    if fighter.file_num % 100 == 0:
        print(f"{fighter.file_num + 1:04d} / {fighter.n_files:04d}")
    parsing_issues: list[str] = []
    fighter_html = bs4.BeautifulSoup(fighter.contents, parser="html.parser", features="lxml")

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
    stats = fighter_html.find_all("li", class_="b-list__box-list-item")
    stats_bio = stats[0:5]
    for stat in stats_bio:
        stat_split = stat.text.strip().split(":")
        col_name = stat_split[0].strip().lower()
        val = stat_split[1].strip().replace('"', "").replace("' ", "'")
        if val == "--":
            val = None
        all_stats_raw[col_name] = val

    fighter_stats_raw = FighterStatsRaw.model_validate(all_stats_raw)
    fighter_stats = FighterStats(height_inches=None, stance=None, reach_inches=None, dob=None)

    parsing_issues = []

    if fighter_stats_raw.height is not None:
        height_split: list[str] = fighter_stats_raw.height.split("'")
        fighter_stats.height_inches = (int(height_split[0]) * 12) + int(height_split[1])

    if fighter_stats_raw.stance is not None and fighter_stats_raw.stance != "":
        try:
            fighter_stats.stance = Stance(fighter_stats_raw.stance.replace("'", ""))
        except ValueError as e:
            parsing_issues.append(str(e))

    if fighter_stats_raw.reach is not None:
        fighter_stats.reach_inches = int(fighter_stats_raw.reach)

    if fighter_stats_raw.dob is not None:
        fighter_stats.dob = datetime.strptime(fighter_stats_raw.dob, "%b %d, %Y").strftime(
            "%Y-%m-%d"
        )

    fighter_parsed = UFCFighter(
        fighter_uid=fighter.uid,
        first_name=first_name,
        last_name=last_name,
        nickname=nickname,
        dob=fighter_stats.dob,
        place_of_birth=None,
        stance=fighter_stats.stance,
        style=None,
        height_inches=fighter_stats.height_inches,
        reach_inches=fighter_stats.reach_inches,
        leg_reach_inches=None,
        downloaded_ts=fighter.modified_ts.isoformat(),
    )

    return FighterParsingResult(uid=fighter.uid, result=fighter_parsed, issues=parsing_issues)


def write_fighter_results_to_db(results: list[FighterParsingResult], force_run: bool) -> None:
    tbl_name = "ufc_fighters"
    print(create_header(80, tbl_name, True, spacer="-"))

    clean_results = handle_parsing_issues(results, False)
    fighters = [i.result for i in clean_results]
    if force_run:
        uids = [i.fighter_uid for i in fighters]
        delete_existing_records(UFCFighter, col(UFCFighter.fighter_uid), uids)

    write_data_to_db(fighters)
