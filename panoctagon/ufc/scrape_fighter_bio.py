from itertools import repeat
import random

from pydantic import BaseModel

from panoctagon.common import setup_panoctagon
from panoctagon.tables import UFCFighter

import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Optional

from sqlmodel import Session, and_, col, select

from panoctagon.common import (
    create_header,
    get_engine,
    report_stats,
    scrape_page,
    Symbols,
)
from panoctagon.models import RunStats, ScrapingConfig, ScrapingWriteResult


class FighterBioScrapingResult(BaseModel):
    fighter: UFCFighter
    success: bool
    write: Optional[list[ScrapingWriteResult]]
    message: Optional[str]


def get_fighter_bio(fighter: UFCFighter, base_dir: Path) -> FighterBioScrapingResult:
    first_name = (
        "-".join(fighter.first_name.split(" "))
        .lower()
        .replace(".", "")
        .replace(" ", "")
    )

    last_name = (
        "-".join(fighter.last_name.split(" "))
        .lower()
        .replace("-jr.", "")
        .replace(".", "")
        .replace("'", "")
        .replace("machado-garry", "garry")
        .replace(" ", "")
    )

    url_uid = f"{first_name}-{last_name}"
    config = ScrapingConfig(
        base_dir=base_dir,
        uid=url_uid,
        description="fighter_bio",
        base_url="https://www.ufc.com/athlete/",
        path=base_dir / f"{fighter.fighter_uid}.html",
    )

    write_result = scrape_page(config)
    message = ""
    if not write_result.success:
        message = "failed to download"
        if write_result.config is not None and write_result.path is not None:
            write_result.path.unlink()

    if write_result.success:
        result_indicator = Symbols.CHECK.value
    else:
        result_indicator = Symbols.DELETED.value

    output_message = (
        f"[{result_indicator}] {fighter.first_name} {fighter.last_name} ({url_uid})"
    )
    print(
        create_header(title=output_message, center=False, spacer=" ", header_length=80)
    )

    return FighterBioScrapingResult(
        fighter=fighter,
        success=write_result.success,
        write=[write_result],
        message=message,
    )


def get_fighter(first_name: str, last_name: str) -> UFCFighter:
    engine = get_engine()

    with Session(engine) as session:
        cmd = select(UFCFighter).where(
            and_(UFCFighter.first_name == first_name, UFCFighter.last_name == last_name)
        )
        fighter = session.exec(cmd).one()
    return fighter


def get_unparsed_fighters(force_run: bool = False) -> list[UFCFighter]:
    cmd = select(UFCFighter)
    if not force_run:
        cmd = cmd.where(col(UFCFighter.bio_downloaded_ts).is_(None))

    cmd = cmd.order_by(col(UFCFighter.first_name))

    engine = get_engine()
    with Session(engine) as session:
        fighters = session.exec(cmd).all()
    return list(fighters)


def get_fighters_to_download(
    unparsed_fighters: list[UFCFighter], base_dir: Path, force_run: bool
) -> list[UFCFighter]:
    if force_run:
        return unparsed_fighters

    downloaded_fighter_uids = [i.stem for i in base_dir.glob("*.html")]
    return [
        i for i in unparsed_fighters if i.fighter_uid not in downloaded_fighter_uids
    ]


def main() -> None:
    setup = setup_panoctagon(title="Panoctagon Fighter Bio Scraper")
    output_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_bios"
    output_dir.mkdir(exist_ok=True, parents=True)

    fighters_to_download = get_unparsed_fighters()

    fighters_to_download = get_fighters_to_download(
        fighters_to_download, output_dir, setup.args.force
    )
    if setup.args.n:
        fighters_to_download = random.sample(fighters_to_download, setup.args.n)

    n_fighters_to_download = len(fighters_to_download)
    n_workers = setup.cpu_count
    if n_fighters_to_download < setup.cpu_count:
        n_workers = n_fighters_to_download

    start_header = create_header(
        80, f"SCRAPING n={n_fighters_to_download} Fighter Bios", True, "-"
    )
    print(start_header)
    start_time = time.time()
    if setup.args.sequential or n_fighters_to_download < setup.cpu_count:
        results = [
            get_fighter_bio(fighter, output_dir) for fighter in fighters_to_download
        ]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            results = list(
                executor.map(get_fighter_bio, fighters_to_download, repeat(output_dir))
            )
    end_time = time.time()

    bios_downloaded = 0
    bios_deleted = 0
    for result in results:
        if result.write is None:
            continue
        for write in result.write:
            if write.success:
                bios_downloaded += 1
            else:
                bios_deleted += 1

    report_stats(
        RunStats(
            start=start_time,
            end=end_time,
            n_ops=n_fighters_to_download,
            op_name="fighter bio",
            successes=bios_downloaded,
            failures=bios_deleted,
        )
    )

    print(setup.footer)


if __name__ == "__main__":
    main()
