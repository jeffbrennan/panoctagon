import random
import time
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import col

from panoctagon.common import (
    create_header,
    get_table_uids,
    scrape_page,
)
from panoctagon.models import ScrapingConfig
from panoctagon.tables import UFCFight


@dataclass
class FighterToScrape:
    uid: str
    i: int
    n_fighters: int
    base_dir: Path


@dataclass
class FighterScrapingResult:
    fighter: FighterToScrape
    success: bool
    message = ""


def get_all_fighter_uids() -> list[str]:
    f1_uids = get_table_uids(col(UFCFight.fighter1_uid))
    f2_uids = get_table_uids(col(UFCFight.fighter2_uid))

    assert f1_uids is not None
    assert f2_uids is not None
    return sorted(set(f1_uids + f2_uids))


def scrape_fighter(fighter: FighterToScrape) -> FighterScrapingResult:
    title = f"[{fighter.i + 1:04d}/{fighter.n_fighters:04d}] {fighter.uid}"
    print(create_header(80, title, False, "."))
    base_url = "http://ufcstats.com/fighter-details"

    sleep_ms = random.randint(200, 500)
    time.sleep(sleep_ms / 1000)

    config = ScrapingConfig(
        uid=fighter.uid,
        description="fighter",
        base_url=base_url,
        base_dir=fighter.base_dir,
        path=fighter.base_dir / f"{fighter.uid}.html",
    )

    result = scrape_page(config)
    if not result.success:
        if result.path:
            print(f"deleting {config.uid}")
            result.path.unlink()

    return FighterScrapingResult(fighter, success=result.success)
