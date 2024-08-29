from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import typer
from sqlalchemy.sql.operators import is_not
from sqlmodel import col

from panoctagon.common import create_header, get_html_files, setup_panoctagon
from panoctagon.tables import UFCFight, UFCFighter
from panoctagon.ufc.parse.bios import (
    parse_headshot,
    write_headshot_results_to_db,
)
from panoctagon.ufc.parse.fighters import parse_fighter, write_fighter_results_to_db
from panoctagon.ufc.parse.fights import (
    parse_fight,
    write_fight_results_to_db,
    write_stats_to_db,
)

app = typer.Typer()


@app.command(name="bios")
def bios(force: bool = False) -> int:
    setup = setup_panoctagon(title="Fighter Bio Parser")
    bio_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_bios"
    headshot_dir = (
        Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_headshots"
    )

    fighter_bios = get_html_files(
        path=bio_dir,
        uid_col=col(UFCFighter.fighter_uid),
        where_clause=is_not(UFCFighter.bio_downloaded_ts, None),  # type: ignore
        force_run=force,
    )

    if len(fighter_bios) == 0:
        print("no fighter bios to parse. exiting early")
        print(setup.footer)
        return 0

    print(create_header(80, f"PARSING n={len(fighter_bios)} fighter bios", True, "-"))
    with ProcessPoolExecutor(max_workers=setup.cpu_count - 1) as executor:
        headshot_results = list(executor.map(parse_headshot, fighter_bios))

    headshots_on_disk = list(headshot_dir.glob("*.png"))
    headshot_uids_on_disk = [i.stem.split("_")[0] for i in headshots_on_disk]

    headshots_validated = [
        i for i in headshot_results if i.uid in headshot_uids_on_disk
    ]
    write_headshot_results_to_db(headshots_validated)
    return len(headshots_validated)


@app.command(name="fighters")
def fighters(force: bool = False) -> int:
    setup = setup_panoctagon(title="Panoctagon UFC Fighter Parser")
    script_dir = Path(__file__).parents[2] / "data/raw/ufc/fighters"
    if not script_dir.exists():
        raise ValueError("expecting a directory containing at least one fighter")

    fighters_to_parse = get_html_files(
        path=script_dir,
        uid_col=col(UFCFighter.fighter_uid),
        where_clause=None,
        force_run=force,
    )

    if len(fighters_to_parse) == 0:
        print("no fighters to parse. exiting early")
        print(setup.footer)
        return 0

    with ProcessPoolExecutor(max_workers=setup.cpu_count - 1) as executor:
        results = list(executor.map(parse_fighter, fighters_to_parse))
    print(len(results))

    write_fighter_results_to_db(results, force)
    print(setup.footer)
    return len(results)


@app.command(name="fights")
def fights(force: bool = False) -> int:
    setup = setup_panoctagon(title="Panoctagon UFC Fight Parser")
    fight_dir = Path(__file__).parents[2] / "data/raw/ufc/fights"
    fights_to_parse = get_html_files(
        path=fight_dir,
        uid_col=col(UFCFight.fight_uid),
        where_clause=None,
        force_run=force,
    )

    for fight in fights_to_parse:
        fight.uid = fight.uid.split("_")[-1]

    if len(fights_to_parse) == 0:
        print("no fights to parse. exiting early")
        print(setup.footer)
        return 0

    print(create_header(80, f"PARSING n={len(fights_to_parse)} fights", True, "-"))
    with ProcessPoolExecutor(max_workers=setup.cpu_count - 1) as executor:
        results = list(executor.map(parse_fight, fights_to_parse))

    write_fight_results_to_db(results, force)
    write_stats_to_db(results)
    print(setup.footer)
    return len(results)
