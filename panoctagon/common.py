import sqlite3
from dataclasses import dataclass, astuple, fields, is_dataclass
from pathlib import Path
from typing import Optional, Any

import bs4
import requests


@dataclass(frozen=True)
class Promotion:
    promotion_uid: str
    name: str


@dataclass
class ScrapingConfig:
    uid: str
    description: str
    base_url: str
    base_dir: Path
    fname: str


def dump_html(config: ScrapingConfig, log_uid: bool) -> None:
    if log_uid:
        print(f"saving {config.description}: {config.uid}")
    url = f"{config.base_url}/{config.uid}"
    output_path = config.base_dir / f"{config.uid}.html"
    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")

    with output_path.open("w") as f:
        f.write(str(soup))


def write_data_to_db(
    con: sqlite3.Connection,
    tbl_name: str,
    data: list[tuple] | list[Any],
    col_names: Optional[list[str]],
) -> None:
    cur = con.cursor()

    if is_dataclass(data[0]):
        col_names = [f.name for f in fields(data[0])]
        tuples = [astuple(i) for i in data]  # pyright: ignore [reportArgumentType]
    elif isinstance(data[0], tuple):
        if col_names is None:
            raise ValueError(
                "expecting headers to be specified when data is a list of tuples"
            )
        tuples = data
    else:
        raise NotImplementedError(f"unsupported data type: {type(data[0])}")

    if col_names is None:
        raise ValueError("expecting headers")

    if not isinstance(tuples[0], tuple):
        raise TypeError("expecting tuples")

    n_cols = len(col_names)
    headers = ",".join(col_names)
    placeholders = ", ".join(["?"] * n_cols)

    query = f"INSERT INTO {tbl_name} ({headers}) VALUES ({placeholders})"
    cur.executemany(query, tuples)  # pyright: ignore [reportArgumentType]
    con.commit()


def get_con() -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    db_path = Path(__file__).parent.parent / "data" / "panoctagon.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    return con, cur


def get_table_rows(
    soup: bs4.BeautifulSoup, table_num: int = 0
) -> bs4.ResultSet[bs4.Tag]:
    tables = soup.findAll("table")
    table = tables[table_num]
    if table is None:
        raise ValueError("No table found")

    table_body = table.find("tbody")
    if not isinstance(table_body, bs4.Tag):
        raise TypeError(f"expected bs4.Tag, got {type(table_body)}")

    rows = table_body.find_all("tr")
    if rows is None:
        raise ValueError()
    return rows
