import uuid

from panoctagon.common import write_data_to_db
from panoctagon.models import Promotions


def write_promotions(promotions: list[Promotions]) -> None:
    cur.execute(
        """
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
    ufc = Promotions(
        promotion_uid=str(uuid.uuid4()), name="UFC", founded_date="1993-11-12"
    )
    one = Promotions(
        promotion_uid=str(uuid.uuid4()), name="ONE", founded_date="2011-07-14"
    )

    promotions = [ufc, one]
    write_promotions(promotions)


def main():
    setup_promotions()


if __name__ == "__main__":
    main()
