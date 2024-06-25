from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, astuple, fields, is_dataclass
from enum import Enum
from pathlib import Path
import random
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


@dataclass
class ScrapingWriteResult:
    config: Optional[ScrapingConfig]
    path: Optional[Path]
    success: bool
    attempts: int


class Symbols(Enum):
    DOWN_ARROW = "\u2193"
    DELETED = "\u2717"
    CHECK = "\u2714"


@dataclass
class RunStats:
    start: float
    end: float
    n_ops: Optional[int]
    op_name: str
    successes: Optional[int]
    failures: Optional[int]


@dataclass
class ParsingIssue:
    issue: str
    uids: list[str]


@dataclass(frozen=True, slots=True)
class ParsingResult:
    uid: str
    result: Optional[Any]
    issues: list[str]


def handle_parsing_issues(
    parsing_results: list[ParsingResult], raise_error: bool
) -> list[ParsingResult]:
    all_parsing_issues: list[ParsingIssue] = []
    for i, parsing_result in enumerate(parsing_results):
        if parsing_result.result is None:
            continue

        parsing_issues = parsing_result.issues
        if not parsing_issues:
            continue

        existing_issues = [i.issue for i in all_parsing_issues]
        for issue in parsing_issues:
            if issue in existing_issues:
                issue_index = existing_issues.index(issue)
                all_parsing_issues[issue_index].uids += [parsing_result.uid]
                continue

            all_parsing_issues.append(ParsingIssue(issue, [parsing_result.uid]))

    all_parsing_issues = sorted(
        all_parsing_issues, key=lambda x: len(x.uids), reverse=True
    )

    n_parsing_issues = len(all_parsing_issues)
    clean_results = parsing_results
    if n_parsing_issues > 0:
        issue_base_len = 12
        issue_prefix_len = issue_base_len - len("[n=]")
        issue_padded_len = 20
        n_uids_sample = 5
        header_len = 80
        print(create_header(header_len, "parsing issues", False, "."))

        for parsing_issue in all_parsing_issues:
            n_uids = len(parsing_issue.uids)
            uids = parsing_issue.uids

            if len(uids) > n_uids_sample:
                uids = random.sample(uids, n_uids_sample)
            if len(parsing_issue.issue) > header_len - issue_prefix_len:
                issue = parsing_issue.issue[0 : header_len - issue_padded_len] + "..."

            else:
                issue = parsing_issue.issue

            summary_title = f"[n={n_uids:12,d}] {issue}"
            print(create_header(header_len, summary_title, False, ""))
            for uid in uids:
                print(uid)

        if raise_error:
            assert n_parsing_issues == 0
        problem_uids = [
            item for sublist in [i.uids for i in all_parsing_issues] for item in sublist
        ]
        problem_uids_deduped = sorted(list(set(problem_uids)))

        print(create_header(80, "", True, "."))
        print(f"[n={len(problem_uids):5,d}] removing invalid records from insert")
        clean_results = [
            i for i in parsing_results if i.uid not in problem_uids_deduped
        ]
    return clean_results


def report_stats(stats: RunStats):
    print(create_header(80, "RUN STATS", True, "-"))

    if stats.successes is not None and stats.failures is not None:
        print(
            f"{Symbols.CHECK.value} {stats.successes} | {Symbols.DELETED.value} {stats.failures}"
        )

    elapsed_time_seconds = stats.end - stats.start
    print(f"elapsed time: {elapsed_time_seconds:.2f} seconds")

    if stats.n_ops is not None:
        elapsed_time_seconds_per_event = elapsed_time_seconds / stats.n_ops
        print(
            f"elapsed time per {stats.op_name}: {elapsed_time_seconds_per_event:.2f} seconds"
        )


def check_write_success(config: ScrapingConfig) -> bool:
    issue_indicators = ["Internal Server Error", "Too Many Requests"]
    with config.path.open() as f:
        contents = "".join(f.readlines())

    file_size_bytes = config.path.stat().st_size
    file_too_small = file_size_bytes < 1024
    issues_exist = any(i in contents for i in issue_indicators) or file_too_small
    return not issues_exist


def create_header(header_length: int, title: str, center: bool, spacer: str):
    if center:
        spacer_len = (header_length - len(title)) // 2
        output = f"{spacer * spacer_len}{title}{spacer * spacer_len}"
    else:
        output = f"{title}{spacer * (header_length - len(title))}"

    if len(output) < header_length:
        output += spacer * (header_length - len(output))
    if len(output) > header_length:
        output = spacer * header_length + "\n" + output

    return output


def get_parsed_uids(uid_col: str, tbl: str, force_run: bool) -> Optional[list[str]]:
    _, cur = get_con()
    if force_run:
        return None

    try:
        cur.execute(f"select {uid_col} from {tbl}")
        uids = [i[0] for i in cur.fetchall()]
    except sqlite3.OperationalError:
        return None
    return uids


def scrape_page(
    config: ScrapingConfig, max_attempts: int = 3, sleep_multiplier_increment: int = 10
) -> ScrapingWriteResult:
    write_success = False
    attempts = 0
    sleep_multiplier = 0

    while not write_success and attempts < max_attempts:
        ms_to_sleep = random.randint(100 * sleep_multiplier, 200 * sleep_multiplier)
        time.sleep(ms_to_sleep / 1000)

        dump_html(config)

        write_success = check_write_success(config)
        sleep_multiplier += sleep_multiplier_increment
        attempts += 1

    return ScrapingWriteResult(
        config=config,
        path=config.path,
        success=write_success,
        attempts=attempts,
    )


def get_html_files(
    path: Path, uid_col: str, tbl: str, force_run: bool, uid: Optional[str] = None
) -> list[FileContents]:
    all_files = list(path.glob("*.html"))
    if uid is not None:
        all_files = [f for f in all_files if uid in f.name]

    existing_uids = get_parsed_uids(uid_col, tbl, force_run)
    if existing_uids is None:
        files_to_parse = all_files
    else:
        files_to_parse = [i for i in all_files if i.stem not in existing_uids]

    fight_contents_to_parse: list[FileContents] = []
    for i, fpath in enumerate(files_to_parse):
        uid = fpath.stem
        with fpath.open() as f:
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
