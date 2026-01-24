from pathlib import Path

import bs4
import requests
from sqlmodel import col, Session, select

from panoctagon.common import (
    create_header,
    get_engine,
)
from panoctagon.models import FileContents, ParsingResult
from panoctagon.tables import UFCFighter


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
        title = f"[{bio.file_num:05d} / {bio.n_files - 1:05d}]"
        print(create_header(80, title, False, "."))

    headshot_dir = (
        Path(__file__).parents[3] / "data" / "raw" / "ufc" / "fighter_headshots"
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
