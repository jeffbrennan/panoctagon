from panoctagon.common import get_engine
from panoctagon.models import Divisions, Promotions
from sqlmodel import SQLModel


def main() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    main()
