import uuid
from enum import Enum
from dataclasses import dataclass

from panoctagon.common import get_con, write_data_to_db


class UFCDivisionNames(str, Enum):
    STRAWWEIGHT = "Strawweight"
    WOMENS_STRAWWEIGHT = "Women's Strawweight"
    FLYWEIGHT = "Flyweight"
    WOMENS_FLYWEIGHT = "Women's Flyweight"
    BANTAMWEIGHT = "Bantamweight"
    WOMENS_BANTAMWEIGHT = "Women's Bantamweight"
    FEATHERWEIGHT = "Featherweight"
    WOMENS_FEATHERWEIGHT = "Women's Featherweight"
    LIGHTWEIGHT = "Lightweight"
    WELTERWEIGHT = "Welterweight"
    MIDDLEWEIGHT = "Middleweight"
    LIGHT_HEAVYWEIGHT = "Light Heavyweight"
    HEAVYWEIGHT = "Heavyweight"
    SUPER_HEAVYWEIGHT = "Super Heavyweight"
    CATCH_WEIGHT = "Catch Weight"
    OPEN_WEIGHT = "Open Weight"

class ONEDivisionNames(str, Enum):
    ATOMWEIGHT = "Atomweight"
    STRAWWEIGHT = "Strawweight"
    FLYWEIGHT = "Flyweight"
    BANTAMWEIGHT = "Bantamweight"
    FEATHERWEIGHT = "Featherweight"
    LIGHTWEIGHT = "Lightweight"
    WELTERWEIGHT = "Welterweight"
    MIDDLEWEIGHT = "Middleweight"
    LIGHT_HEAVYWEIGHT = "Light Heavyweight"
    HEAVYWEIGHT = "Heavyweight"


@dataclass(frozen=True)
class Division:
    promotion_uid: str
    division_uid: str
    name: str
    weight_lbs: int


def get_promotion_uid(promotion_name: str) -> str:
    con, cur = get_con()
    query = f"select promotion_uid from promotions where name = '{promotion_name}'"
    result = cur.execute(query)
    return result.fetchone()[0]


def write_divisions(divisions: list[Division]) -> None:
    con, _ = get_con()
    cur = con.cursor()
    cur.execute(
        f"""
              CREATE TABLE IF NOT EXISTS
               divisions(
               promotion_uid TEXT NOT NULL,
               division_uid TEXT NOT NULL,
               name TEXT NOT NULL,
               weight_lbs INTEGER NOT NULL,
               PRIMARY KEY (promotion_uid, division_uid),
               FOREIGN KEY (promotion_uid) references promotions(promotion_uid)
              );

           """
    )

    write_data_to_db(con, "divisions", divisions)


def get_ufc_divisions() -> list[Division]:
    ufc_uid = get_promotion_uid("UFC")
    ufc_division_weights: dict[UFCDivisionNames, int] = {
        UFCDivisionNames.STRAWWEIGHT: 115,
        UFCDivisionNames.FLYWEIGHT: 125,
        UFCDivisionNames.BANTAMWEIGHT: 135,
        UFCDivisionNames.FEATHERWEIGHT: 145,
        UFCDivisionNames.LIGHTWEIGHT: 155,
        UFCDivisionNames.WELTERWEIGHT: 170,
        UFCDivisionNames.MIDDLEWEIGHT: 185,
        UFCDivisionNames.LIGHT_HEAVYWEIGHT: 205,
        UFCDivisionNames.HEAVYWEIGHT: 265,
    }

    ufc_divisions: list[Division] = []
    for ufc_division_name, ufc_division_weight in ufc_division_weights.items():
        ufc_divisions.append(
            Division(
                promotion_uid=ufc_uid,
                division_uid=str(uuid.uuid4()),
                name=ufc_division_name,
                weight_lbs=ufc_division_weight,
            )
        )

    return ufc_divisions


def get_one_divisions() -> list[Division]:
    one_uid = get_promotion_uid("ONE")
    one_division_weights: dict[ONEDivisionNames, int] = {
        ONEDivisionNames.ATOMWEIGHT: 115,
        ONEDivisionNames.STRAWWEIGHT: 125,
        ONEDivisionNames.FLYWEIGHT: 135,
        ONEDivisionNames.BANTAMWEIGHT: 145,
        ONEDivisionNames.FEATHERWEIGHT: 155,
        ONEDivisionNames.LIGHTWEIGHT: 170,
        ONEDivisionNames.WELTERWEIGHT: 185,
        ONEDivisionNames.MIDDLEWEIGHT: 205,
        ONEDivisionNames.LIGHT_HEAVYWEIGHT: 225,
        ONEDivisionNames.HEAVYWEIGHT: 265,
    }

    one_divisions: list[Division] = []
    for one_division_name, one_division_weight in one_division_weights.items():
        one_divisions.append(
            Division(
                promotion_uid=one_uid,
                division_uid=str(uuid.uuid4()),
                name=one_division_name,
                weight_lbs=one_division_weight,
            )
        )
    return one_divisions

def setup_divisions():
    ufc_divisions = get_ufc_divisions()
    one_divisions = get_one_divisions()
    divisions = ufc_divisions + one_divisions
    write_divisions(divisions)


def main():
    setup_divisions()

if __name__ == "__main__":
    main()
