import uuid

from sqlmodel import Session, select

from panoctagon.common import get_engine, write_data_to_db
from panoctagon.tables import Promotions


def setup_promotions():
    ufc = Promotions(
        promotion_uid=str(uuid.uuid4()), name="UFC", founded_date="1993-11-12"
    )
    one = Promotions(
        promotion_uid=str(uuid.uuid4()), name="ONE", founded_date="2011-07-14"
    )

    promotions = [ufc, one]
    engine = get_engine()
    with Session(engine) as session:
        existing_promotions = list(session.exec(select(Promotions.name)).all())

    missing_promotions = [i for i in promotions if i.name not in existing_promotions]
    if len(missing_promotions) == 0:
        print("no new promotions to write")
        return

    write_data_to_db(promotions)


if __name__ == "__main__":
    setup_promotions()
