from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from sqlmodel import Session, and_, col, select

from panoctagon.common import (
    Symbols,
    create_header,
    get_engine,
    scrape_page,
)
from panoctagon.models import ScrapingConfig, ScrapingWriteResult
from panoctagon.tables import UFCFighter


class FighterBioScrapingResult(BaseModel):
    fighter: UFCFighter
    success: bool
    write: Optional[list[ScrapingWriteResult]]
    message: Optional[str]


def get_fighter_bio(
    fighter: UFCFighter, base_dir: Path, index: int, total_fighters: int
) -> FighterBioScrapingResult:
    first_name = "-".join(fighter.first_name.split(" ")).lower().replace(".", "").replace(" ", "")

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

    prefix = f"[{index:03d} / {total_fighters:03d}]"
    output_message = (
        f"[{prefix}] {result_indicator} {fighter.first_name} {fighter.last_name} ({url_uid})"
    )
    print(create_header(title=output_message, center=False, spacer=" ", header_length=80))

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
            and_(
                UFCFighter.first_name == first_name,
                UFCFighter.last_name == last_name,
            )
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
    return [i for i in unparsed_fighters if i.fighter_uid not in downloaded_fighter_uids]
