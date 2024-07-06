import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import col

from panoctagon.common import (
    create_header,
    get_table_uids,
    report_stats,
    scrape_page,
)
from panoctagon.models import RunStats, ScrapingConfig
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
    title = f"[{fighter.i+ 1:04d}/{fighter.n_fighters:04d}] {fighter.uid}"
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


def main() -> None:
    start_time = time.time()

    print(create_header(80, "PANOCTAGON", True, "="))
    footer = create_header(80, "", True, "=")
    n_cores = os.cpu_count()
    if n_cores is None:
        n_cores = 4

    sequential = False

    all_fighter_uids = get_all_fighter_uids()
    base_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighters"

    base_dir.mkdir(exist_ok=True)
    scraped_fighters = [i.stem for i in base_dir.glob("*.html")]
    unscraped_fighters = [i for i in all_fighter_uids if i not in scraped_fighters]

    n_fighters = len(unscraped_fighters)

    if n_fighters == 0:
        print("no new fighters!")
        report_stats(
            RunStats(
                start=start_time,
                end=time.time(),
                successes=0,
                failures=0,
                n_ops=None,
                op_name="fighter",
            )
        )
        print(footer)
        return

    fighters_to_scrape = [
        FighterToScrape(uid=uid, i=i, n_fighters=n_fighters, base_dir=base_dir)
        for i, uid in enumerate(unscraped_fighters)
    ]

    print(create_header(80, f"SCRAPING n={n_fighters} fighters", True, "-"))
    if sequential or n_fighters < n_cores:
        results = [scrape_fighter(i) for i in fighters_to_scrape]
    else:
        with ProcessPoolExecutor(max_workers=n_cores) as executor:
            results = list(executor.map(scrape_fighter, fighters_to_scrape))

    successes = [i for i in results if i.success]
    n_successes = len(successes)
    failures = len(results) - n_successes

    report_stats(
        RunStats(
            start=start_time,
            end=time.time(),
            successes=n_successes,
            failures=failures,
            n_ops=n_fighters,
            op_name="fighter",
        )
    )
    print(footer)


if __name__ == "__main__":
    main()
