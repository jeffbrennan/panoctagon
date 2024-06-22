import uuid
from dataclasses import dataclass

from panoctagon.common import get_con, write_data_to_db


@dataclass(frozen=True)
class Promotion:
    promotion_uid: str
    name: str
    founded_date: str


def write_promotions(promotions: list[Promotion]) -> None:
    con, _ = get_con()
    cur = con.cursor()
    cur.execute(
        f"""
           CREATE TABLE IF NOT EXISTS
            promotions(
            promotion_uid TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            founded_date TEXT NOT NULL
           );

        """
    )

    write_data_to_db(con, "promotions", promotions)


def setup_promotions():
    ufc = Promotion(
        promotion_uid=str(uuid.uuid4()), name="UFC", founded_date="1993-11-12"
    )
    one = Promotion(
        promotion_uid=str(uuid.uuid4()), name="ONE", founded_date="2011-07-14"
    )

    promotions = [ufc, one]
    write_promotions(promotions)


def main():
    setup_promotions()


if __name__ == "__main__":
    main()
