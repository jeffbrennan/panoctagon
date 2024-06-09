import sqlite3
from dataclasses import dataclass, astuple, fields
from pathlib import Path
import bs4

@dataclass(frozen=True)
class Promotion:
    promotion_uid: str
    name: str


def write_tuples_to_db(con: sqlite3.Connection, tbl_name: str, data: list[dataclass]):
    cur = con.cursor()
    col_names = [f.name for f in fields(data[0])]
    n_cols = len(col_names)
    headers = ",".join(col_names)
    tuples = [astuple(i) for i in data]
    placeholders = ", ".join(["?"] * n_cols)

    query = f"INSERT INTO {tbl_name} ({headers}) VALUES ({placeholders})"
    cur.executemany(query, tuples)
    con.commit()


def get_con() -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    db_path = Path(__file__).parent.parent / "data" / "panoctagon.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    return con, cur


def get_table_rows(soup: bs4.BeautifulSoup) -> bs4.ResultSet:
    table = soup.find("table")
    if table is None:
        raise ValueError("No table found")

    table_body = table.find("tbody")
    if not isinstance(table_body, bs4.Tag):
        raise TypeError(f"expected bs4.Tag, got {type(table_body)}")

    rows = table_body.find_all("tr")
    if rows is None:
        raise ValueError()
    return rows