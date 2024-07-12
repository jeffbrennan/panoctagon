from pathlib import Path

import bs4
import requests
from sqlmodel import col, Session, select

from panoctagon.common import get_html_files, get_engine
from panoctagon.models import FileContents
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


def parse_headshot(bio: FileContents):
    print(bio.uid)
    headshot_dir = (
        Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_headshots"
    )

    bio_html = bs4.BeautifulSoup(bio.contents, features="lxml")
    fighter = get_fighter(bio.uid)
    fighter_name = fighter.first_name + " " + fighter.last_name

    images = [
        i
        for i in bio_html.find_all("img")
        if all(x in i.attrs for x in ["alt", "src", "class"])
    ]

    fighter_image_urls = set(
        [
            i["src"]
            for i in images
            if fighter_name.lower() in i["alt"].lower()
            and (
                "headshot" in "".join(i["class"]).lower()
                or "profile" in "".join(i["class"]).lower()
            )
        ]
    )

    if len(fighter_image_urls) == 0:
        print("no urls found!")
        return

    for url in fighter_image_urls:
        url_clean = url.split("?")[0]
        if "full_body" in url:
            image_type = "full"
        else:
            image_type = "headshot"

        ext = url_clean.split(".")[-1]
        fpath = headshot_dir / f"{bio.uid}_{image_type}.{ext}"
        save_image_from_url(url_clean, fpath)


def main() -> None:
    bio_dir = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_bios"
    fighter_bios = get_html_files(bio_dir, col(UFCFighter.fighter_uid), True)
    for bio in fighter_bios[0:5]:
        parse_headshot(bio)


if __name__ == "__main__":
    main()
