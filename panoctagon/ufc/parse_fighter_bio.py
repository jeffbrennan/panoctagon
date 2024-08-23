from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import bs4
import requests
from sqlmodel import col, Session, select

from panoctagon.common import (
    create_header,
    get_html_files,
    get_engine,
    setup_panoctagon,
)
from panoctagon.models import FileContents, ParsingResult
from panoctagon.tables import UFCFighter
from sqlalchemy.sql.operators import is_not

def get_fighter(uid: str) -> UFCFighter:
    engine = get_engine()
    with Session(engine) as session:
        cmd = select(UFCFighter).where(UFCFighter.fighter_uid == uid)
        results = session.exec(cmd).one()
    return results


def save_image_from_url(url: str, fpath: Path):
    page = requests.get(url)

    with fpath.open(mode="wb") as f:
        f.write(page.content)


class HeadshotParsingResult(ParsingResult):
    bio_downloaded_ts: str


def parse_headshot(bio: FileContents) -> HeadshotParsingResult:
    if bio.file_num % 100 == 0:
        title = f"[{bio.file_num:05d} / {bio.n_files-1:05d}]"
        print(create_header(80, title, False, "."))

    headshot_dir = (
        Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_headshots"
    )

    bio_downloaded_ts = bio.modified_ts.isoformat()

    bio_html = bs4.BeautifulSoup(bio.contents, features="lxml")
    fighter = get_fighter(bio.uid)

    fighter_name = fighter.first_name + "_" + fighter.last_name
    fighter_name_last_first = fighter.last_name + "_" + fighter.first_name

    images = [
        i
        for i in bio_html.find_all("img")
        if all(x in i.attrs for x in ["src", "class"])
    ]

    fighter_image_urls = set(
        [
            i["src"]
            for i in images
            if fighter_name.lower() in i["src"].lower()
            or fighter_name.upper() in i["src"].upper()
            or fighter_name_last_first.lower() in i["src"].lower()
            or fighter_name_last_first.upper() in i["src"].upper()
            and (
                "headshot" in "".join(i["class"]).lower()
                or "profile" in "".join(i["class"]).lower()
            )
        ]
    )

    if len(fighter_image_urls) == 0:
        return HeadshotParsingResult(
            uid=bio.uid,
            result=bio,
            bio_downloaded_ts=bio_downloaded_ts,
            issues=["no urls found"],
        )

    for url in fighter_image_urls:
        url_clean = url.split("?")[0]
        if "full_body" in url:
            image_type = "full"
        else:
            image_type = "headshot"

        ext = url_clean.split(".")[-1]
        fpath = headshot_dir / f"{bio.uid}_{image_type}.{ext}"
        save_image_from_url(url_clean, fpath)

    return HeadshotParsingResult(
        uid=bio.uid, result=True, bio_downloaded_ts=bio_downloaded_ts, issues=[]
    )


def write_headshot_results_to_db(headshots: list[HeadshotParsingResult]) -> None:
    engine = get_engine()

    print(f"[n={len(headshots):5,d}] updating records in `UFCFighter`")
    with Session(engine) as session:
        for headshot in headshots:
            record = session.exec(
                select(UFCFighter).where(col(UFCFighter.fighter_uid) == headshot.uid)
            ).one()
            record.has_headshot = True
            record.bio_downloaded_ts = headshot.bio_downloaded_ts
            session.add(record)
        session.commit()


def parse_fighter_bio() -> int:
    setup = setup_panoctagon(title="Fighter Bio Parser")
    bio_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_bios"
    headshot_dir = (
        Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_headshots"
    )

    fighter_bios = get_html_files(
        path=bio_dir,
        uid_col=col(UFCFighter.fighter_uid),
        where_clause=is_not(UFCFighter.bio_downloaded_ts, None),
        force_run=setup.args.force,
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

if __name__ == "__main__":
    parse_fighter_bio()
