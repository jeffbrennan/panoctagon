from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
import time
import random
import requests
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
    fighter: UFCFighter,
    base_dir: Path,
    index: int,
    total_fighters: int,
    session: Optional[requests.Session] = None,
) -> FighterBioScrapingResult:
    first_name = (
        "-".join(fighter.first_name.split(" "))
        .lower()
        .replace(".", "")
        .replace("'", "")
        .replace(" ", "")
    )

    uid_map = {
        "machado-garry": "garry",
        "alberta-cerra-leon": "alberto-cerro-leon",
        "alex-ricci": "alessandro-ricci",
        "alvaro-herrera-mendoza": "alvaro-herrera",
        "anying-wang": "wang-anying",
        "antonio-rodrigo-nogueira": "minotauro-nogueira",
        "asu-almabayev": "assu-almabayev",
        "bibulatov-magomed": "magomed-bibulatov",
        "chan-mi-jeon": "chanmi-jeon",
        "constantinos-philippou": "costas-philippou",
        "cristiane-justino": "cris-cyborg",
        "damon-blackshear": "damon-blackshear",
        "guangyou-ning": "ning-guangyou",
        "jeff-molina": "jeffrey-molina",
        "jon-olav-einemo": "john-olav-einemo",
        "kevin-ferguson": "kimbo-slice",
        "manvel-gamburyan": "manny-gamburyan",
        "michelle-waterson-gomez": "michelle-waterson",
        "mirko-filipovic": "mirko-cro-cop",
        "montserrat-conejo-ruiz": "montserrat-conejo",
        "philip-de-fries": "phil-de-fries",
        "quinton-jackson": "rampage-jackson",
        "rameau-thierry-sokoudjou": "rameau-sokoudjou",
        "rogerio-nogueira": "antonio-rogerio-nogueira",
        "roldan-sangchaan": "roldan-sangcha",
        "ronaldo-rodriguez": "luis-rodriguez",
        "rostem-akman": "rostam-akman",
        "sai-wang": "wang-sai",
        "seo-hee-ham": "seohee-ham",
        "silvana-gomez-juarez": "silvana-juarez",
        "tiago-dos-santos-e-silva": "tiago-trator",
        "war-machine": "jon-koppenhaver",
        "wulijiburen": "wuliji-buren",
        "yizha": "yi-zha",
        "yuta-sasaki": "ulka-sasaki",
        "arjan-bhullar": "arjan-singh-bhullar",
        "brad-scott": "bradley-scott",
        "brianna-fortino": "brianna-van-buren",
        "ben-alloway": "benny-alloway",
        "azunna-anyanwu": "zu-anyanwu",
        "billy-ray-goff": "billy-goff",
        "dan-bobish": "daniel-bobish",
        "chris-liguori": None,
        "alex-stiebling": "alex-steibling",
        "christophe-leninger": "christophe-leininger",
        "dan-argueta": "daniel-argueta",
        "carlos-barreto": None,
        "danny-downes": "dan-downes",
        "david-abbott": "tank-abbott",
        "david-kaplan": "dave-kaplan",
        "dmitri-stepanov": "dmitrei-stepanov",
        "dwayne-cason": "duane-cason",
        "ebenezer-fontes-braga": "ebenezer-braga",
        "edilberto-de-oliveira": "edilberto-crocota",
        "edimilson-souza": "kevin-souza",
        "emily-kagan": "emily-peters-kagan",
        "emmanuel-yarborough": "emmanuel-yarbrough",
        "fernando-bruno": None,
        "flavio-luiz-moura": "flavio-moura",
        "geraldo-de-freitas": "gerlado-de-freitas-jr",
        "glaico-franca-moreira": "glaico-franca",
        "godofredo-pepey": None,
        "humberto-brown-morrison": "humberto-brown",
        "jim-wallhead": "jimmy-wallhead",
        "ike-villanueva": "isaac-villanueva",
        "jack-nilson": "jack-nilsson",
        "joe-moreira": None,
        "heather-clark": "heather-jo-clark",
        "josh-shockman": "josh-schockman",
        "joseph-gigliotti": "joe-gigliotti",
        "josh-rafferty": None,
        "joshua-weems": "josh-weems",
        "katsuhisa-fujii": "katsuhisa-fuji",
        "juan-manuel-puig": "juan-puig",
        "josh-stansbury": "joshua-stansbury",
        "geza-kalman": "saiid-khosseyni-3",
        "kristof-midoux": "christophe-midoux",
        "keiichiro-yamamiya": "keichiro-yamamiya",
        "leonardo-guimaraes": None,
        "marcelo-mello": "marcello-mello",
        "marcelo-aguiar": "marcello-aguiar",
        "marcus-silveira": "marcus-da-silviera",
        "mark-robinson": "mark-david-robinson",
        "marcos-mariano": None,
        "miguel-torres": "miguel-angel-torres",
        "richard-crunkilton": "richard-crunkilton-jr",
        "reza-nasri": "reza-nazri",
        "orlando-wiet": None,
        "nicholas-musoke": "nico-musoke",
        "raphael-pessoa": "raphael-pessoa-nunes",
        "ramiro-hernandez": "junior-hernandez",
        "renee-forte": None,
        "richard-walsh": "rich-walsh",
        "scott-fiedler": "scott-fielder",
        "sanae-kikuta": "sinae-kikuta",
        "robert-whiteford": "rob-whiteford",
        "robert-mcdaniel": "bubba-mcdaniel",
        "ryan-mcgillivray": None,
        "robert-sanchez": "roberto-sanchez",
        "robert-peralta": "robbie-peralta",
        "rodolfo-rubio-perez": "rodolfo-rubio",
        "tsuyoshi-kohsaka": "tsuyoshi-kosaka",
        "timmy-cuamba": "timothy-cuamba",
        "tony-fryklund": "anthony-fryklund",
        "wendell-oliveira-marques": "wendell-oliveira",
        "vernon-ramos-ho": "vernon-ramos",
        "tony-petarra": None,
        "steve-kennedy": "steven-kennedy",
        "sean-daugherty": "sean-daughtery",
        "zhang-tiequan": "tiequan-zhang",
        "khalil-rountree": "khalil-rountree-jr",
    }

    last_name = (
        "-".join(fighter.last_name.split(" "))
        .lower()
        .replace("-jr.", "")
        .replace(".", "")
        .replace("'", "")
        .replace(" ", "")
    )

    url_uid = f"{first_name}-{last_name}"
    url_uid = url_uid.removesuffix("-")

    for orig, replacement in uid_map.items():
        if replacement == "" or replacement is None:
            continue
        url_uid = url_uid.replace(orig, replacement)

    config = ScrapingConfig(
        base_dir=base_dir,
        uid=url_uid,
        description="fighter_bio",
        base_url="https://www.ufc.com/athlete",
        path=base_dir / f"{fighter.fighter_uid}.html",
    )

    write_result = scrape_page(config, max_attempts=1, session=session)
    message = ""

    if not write_result.success:
        if write_result.error_type == "page_not_found":
            message = "page not found (404)"
            result_indicator = "-"
        else:
            message = f"failed ({write_result.error_type or 'unknown error'})"
            result_indicator = Symbols.DELETED.value

        if (
            write_result.config is not None
            and write_result.path is not None
            and write_result.path.exists()
        ):
            write_result.path.unlink()
    else:
        result_indicator = Symbols.CHECK.value

    prefix = f"{index:03d} / {total_fighters:03d}"
    if write_result.error_type == "page_not_found":
        output_message = (
            f"[{prefix}] {result_indicator} {fighter.first_name} {fighter.last_name} (no UFC page)"
        )
    else:
        output_message = f"[{prefix}] {result_indicator} {fighter.first_name} {fighter.last_name} ({config.base_url}/{url_uid})"

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


def scrape_fighter_bios_parallel(
    fighters: list[UFCFighter],
    base_dir: Path,
    max_workers: int = 3,
) -> list[FighterBioScrapingResult]:
    total_fighters = len(fighters)
    results = []
    completed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_fighter = {}

        for i, fighter in enumerate(fighters, 1):
            time.sleep(random.uniform(0.5, 1.5))
            future = executor.submit(
                get_fighter_bio,
                fighter,
                base_dir,
                i,
                total_fighters,
                None,
            )
            future_to_fighter[future] = fighter

        for future in as_completed(future_to_fighter):
            completed_count += 1
            result = future.result()
            results.append(result)

    return results
