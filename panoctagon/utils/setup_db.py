from sqlmodel import SQLModel

from panoctagon.common import get_engine


def main() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    print("✓ Database schema created successfully")


if __name__ == "__main__":
    main()
