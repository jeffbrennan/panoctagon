from panoctagon.divisions import setup_divisions
from panoctagon.promotions import setup_promotions


def main() -> None:
    setup_promotions()
    setup_divisions()


if __name__ == "__main__":
    main()
