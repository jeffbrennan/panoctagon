from dataclasses import dataclass
import time
import random
from pathlib import Path

from panoctagon.common import get_con, dump_html, ScrapingConfig



def get_all_fighter_uids() -> list[str]:
    _, cur = get_con()
    cur.execute("select fighter1_uid from ufc_fights")
    f1_uids = [i[0] for i in cur.fetchall()]
    cur.execute("select fighter2_uid from ufc_fights")
    f2_uids = [i[0] for i in cur.fetchall()]

    all_uids = sorted(set(f1_uids + f2_uids))

    return all_uids


def main():
    all_fighter_uids = get_all_fighter_uids()
    base_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighters"
    base_url = "http://ufcstats.com/fighter-details"

    base_dir.mkdir(exist_ok=True)
    scraped_fighters = [i.stem for i in base_dir.glob("*.html")]
    unscraped_fighters = [i for i in all_fighter_uids if i not in scraped_fighters]

    for i, fighter_uid in enumerate(unscraped_fighters):
        print(f"[{i + 1:04d}/{len(unscraped_fighters):04d}] scraping fighter {fighter_uid}")
        sleep_ms = random.randint(200, 500)
        time.sleep(sleep_ms / 1000)

        config = ScrapingConfig(
            uid=fighter_uid,
            description="fighter",
            base_url=base_url,
            base_dir=base_dir,
            fname=fighter_uid,
        )
        dump_html(config, False)


if __name__ == "__main__":
    main()
