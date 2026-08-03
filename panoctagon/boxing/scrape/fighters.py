from __future__ import annotations

import random
import time
from typing import Optional

import requests
from sqlmodel import col

from panoctagon.boxing.paths import fighters_dir
from panoctagon.common import create_header, get_table_uids, scrape_page
from panoctagon.models import ScrapingConfig
from panoctagon.tables import BoxingFight

FIGHTNIGHTS = "https://fightnights.com"
BOXER_BASE_URL = f"{FIGHTNIGHTS}/boxer"


def get_all_fighter_uids() -> list[str]:
    f1_uids = get_table_uids(col(BoxingFight.fighter1_uid)) or []
    f2_uids = get_table_uids(col(BoxingFight.fighter2_uid)) or []
    return sorted(set(f1_uids + f2_uids))


def download_boxer_pages(
    force: bool = False,
    max_downloads: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> int:
    """Download the fightnights boxer page for every fighter on the main card."""
    fighters_dir().mkdir(parents=True, exist_ok=True)
    downloaded = [i.stem for i in fighters_dir().glob("*.html")]

    fighter_uids = get_all_fighter_uids()

    n_downloaded = 0
    for i, fighter_uid in enumerate(fighter_uids):
        if max_downloads is not None and n_downloaded >= max_downloads:
            break
        if fighter_uid in downloaded and not force:
            continue

        title = f"[{i + 1:03d}/{len(fighter_uids):03d}] {fighter_uid}"
        print(create_header(80, title, False, "."))
        time.sleep(random.uniform(1.0, 2.5))

        config = ScrapingConfig(
            uid=fighter_uid,
            description="boxer",
            base_url=BOXER_BASE_URL,
            base_dir=fighters_dir(),
            path=fighters_dir() / f"{fighter_uid}.html",
            url=f"{FIGHTNIGHTS}/boxer-{fighter_uid}",
        )
        result = scrape_page(config, session=session)
        if result.success:
            n_downloaded += 1

    return n_downloaded
