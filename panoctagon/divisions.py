import uuid
from typing import Optional

from sqlmodel import Session, col, select

from panoctagon.common import (
    get_engine,
)
from panoctagon.enums import ONEDivisionNames, UFCDivisionNames
from panoctagon.tables import Divisions, Promotions


def get_promotion_uid(promotion_name: str) -> str:
    engine = get_engine()

    with Session(engine) as session:
        statement = select(Promotions).where(col(Promotions.name) == promotion_name)
        results = session.exec(statement)
        return next(results).promotion_uid


def write_divisions(divisions: list[Divisions]) -> None:
    engine = get_engine()

    with Session(engine) as session:
        for division in divisions:
            session.add(Divisions(name=division.name))

        session.commit()


def get_ufc_divisions() -> list[Divisions]:
    ufc_uid = get_promotion_uid("UFC")
    ufc_division_weights: dict[UFCDivisionNames, Optional[int]] = {
        UFCDivisionNames.OPEN_WEIGHT: None,
        UFCDivisionNames.CATCH_WEIGHT: None,
        UFCDivisionNames.STRAWWEIGHT: 115,
        UFCDivisionNames.WOMENS_STRAWWEIGHT: 115,
        UFCDivisionNames.FLYWEIGHT: 125,
        UFCDivisionNames.WOMENS_FLYWEIGHT: 125,
        UFCDivisionNames.BANTAMWEIGHT: 135,
        UFCDivisionNames.WOMENS_BANTAMWEIGHT: 135,
        UFCDivisionNames.FEATHERWEIGHT: 145,
        UFCDivisionNames.WOMENS_FEATHERWEIGHT: 145,
        UFCDivisionNames.LIGHTWEIGHT: 155,
        UFCDivisionNames.WELTERWEIGHT: 170,
        UFCDivisionNames.MIDDLEWEIGHT: 185,
        UFCDivisionNames.LIGHT_HEAVYWEIGHT: 205,
        UFCDivisionNames.HEAVYWEIGHT: 265,
        UFCDivisionNames.SUPER_HEAVYWEIGHT: 999,
    }

    ufc_divisions: list[Divisions] = []
    for ufc_division_name, ufc_division_weight in ufc_division_weights.items():
        ufc_divisions.append(
            Divisions(
                promotion_uid=ufc_uid,
                division_uid=str(uuid.uuid4()),
                name=ufc_division_name,
                weight_lbs=ufc_division_weight,
            )
        )

    return ufc_divisions


def get_one_divisions() -> list[Divisions]:
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

    one_divisions: list[Divisions] = []
    for one_division_name, one_division_weight in one_division_weights.items():
        one_divisions.append(
            Divisions(
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

    engine = get_engine()
    with Session(engine) as session:
        existing_divisions = list(session.exec(select(Divisions.name)).all())

    missing_divisions = [i for i in divisions if i.name not in existing_divisions]
    if len(missing_divisions) == 0:
        print("no new divisions to write")
        return
    write_divisions(divisions)


if __name__ == "__main__":
    setup_divisions()
