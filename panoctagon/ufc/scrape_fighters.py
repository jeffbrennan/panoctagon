import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from panoctagon.common import (
    create_header,
    get_con,
    report_stats,
    scrape_page,
)
from panoctagon.models import RunStats, ScrapingConfig


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
    _, cur = get_con()
    cur.execute("select fighter1_uid from ufc_fights")
    f1_uids = [i[0] for i in cur.fetchall()]
    cur.execute("select fighter2_uid from ufc_fights")
    f2_uids = [i[0] for i in cur.fetchall()]

    all_uids = sorted(set(f1_uids + f2_uids))

    return all_uids


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


def main():
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

    successes = len([i for i in results if i.success])
    failures = len(results) - successes

    report_stats(
        RunStats(
            start=start_time,
            end=time.time(),
            successes=successes,
            failures=failures,
            n_ops=n_fighters,
            op_name="fighter",
        )
    )
    print(footer)


if __name__ == "__main__":
    main()
