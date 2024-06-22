import sqlite3
from dataclasses import dataclass, astuple, fields, is_dataclass
from enum import Enum
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
    path: Path


@dataclass
class FileContents:
    uid: str
    path: Path
    contents: str
    file_num: int
    n_files: int


class Symbols(Enum):
    DOWN_ARROW = "\u2193"
    DELETED = "\u2717"


def create_header(header_length: int, title: str, center: bool, spacer: str):
    if center:
        spacer_len = (header_length - len(title)) // 2
        output = f"{spacer * spacer_len}{title}{spacer * spacer_len}"
    else:
        output = f"{title}{spacer * (header_length - len(title))}"

    if len(output) < header_length:
        output = output + spacer * (header_length - len(output))

    return output


def get_parsed_uids(uid_col: str, tbl: str) -> list[str]:
    _, cur = get_con()
    cur.execute(f"select {uid_col} from {tbl}")
    uids = [i[0] for i in cur.fetchall()]
    return uids


def get_html_files(
    dir: Path, uid_col: str, tbl: str, uid: Optional[str] = None
) -> list[FileContents]:
    all_files = list(dir.glob("*.html"))
    if uid is not None:
        all_files = [f for f in all_files if uid in f.name]

    existing_uids = get_parsed_uids(uid_col, tbl)
    files_to_parse = [i for i in all_files if i.stem not in existing_uids]

    fight_contents_to_parse = []
    for i, fpath in enumerate(files_to_parse):
        uid = fpath.stem
        with fpath.open("r") as f:
            fight_contents_to_parse.append(
                FileContents(
                    uid=uid,
                    path=fpath,
                    contents=f.read(),
                    file_num=i,
                    n_files=len(files_to_parse),
                )
            )

    return fight_contents_to_parse


def dump_html(config: ScrapingConfig, log_uid: bool = False) -> None:
    if log_uid:
        print(f"saving {config.description}: {config.uid}")
    url = f"{config.base_url}/{config.uid}"
    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")

    with config.path.open("w") as f:
        f.write(str(soup))


def write_data_to_db(
    con: sqlite3.Connection,
    tbl_name: str,
    data: list[tuple] | list[Any],
    col_names: Optional[list[str]] = None,
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
