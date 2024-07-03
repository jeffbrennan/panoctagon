import uuid

from panoctagon.common import write_data_to_db
from panoctagon.tables import Promotions


def setup_promotions():
    ufc = Promotions(
        promotion_uid=str(uuid.uuid4()), name="UFC", founded_date="1993-11-12"
    )
    one = Promotions(
        promotion_uid=str(uuid.uuid4()), name="ONE", founded_date="2011-07-14"
    )

    promotions = [ufc, one]
    write_data_to_db(promotions)


def main():
    setup_promotions()


if __name__ == "__main__":
    main()
