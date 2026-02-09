from __future__ import annotations

import datetime
import os
import random
import time
from functools import wraps
from pathlib import Path
from typing import Any, Optional, Type

import bs4
import requests
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.orm import Mapped
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine, select

from panoctagon.enums import Symbols
from panoctagon.models import (
    FileContents,
    ParsingIssue,
    ParsingResultType,
    RunStats,
    ScrapingConfig,
    ScrapingWriteResult,
    SQLModelType,
)


class ScrapingArgs(BaseModel):
    force: bool
    sequential: bool
    n: int


class PanoctagonSetup(BaseModel):
    footer: str
    cpu_count: int
    start_time: float


def get_current_time() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        print(create_header(100, f"[START] {func.__name__}", center=False, spacer="-"))
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(
            create_header(
                100,
                f"[ END ] {func.__name__} - took {total_time:.4f} s",
                center=False,
                spacer="=",
            )
        )
        return result

    return timeit_wrapper


def get_engine() -> Engine:
    db_path = Path(__file__).parent.parent / "data" / "panoctagon_orm.duckdb"
    engine_path = "duckdb:///" + str(db_path.resolve())
    engine = create_engine(
        engine_path,
        echo=False,
        poolclass=NullPool,
        connect_args={"read_only": False},
    )
    return engine


def delete_existing_records(
    tbl_model: Type[SQLModel], uid_col: Mapped[Any], uids: list[str]
) -> None:
    print(f"[n={len(uids):5,d}] deleting records")
    engine = get_engine()

    with Session(engine) as session:
        statement = select(tbl_model).where(uid_col.in_(uids))
        results = session.exec(statement).all()

        for result in results:
            session.delete(result)
        session.commit()


def handle_parsing_issues(
    parsing_results: list[ParsingResultType], raise_error: bool
) -> list[ParsingResultType]:
    all_parsing_issues: list[ParsingIssue] = []
    for _, parsing_result in enumerate(parsing_results):
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

            all_parsing_issues.append(ParsingIssue(issue=issue, uids=[parsing_result.uid]))

    all_parsing_issues = sorted(all_parsing_issues, key=lambda x: len(x.uids), reverse=True)

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
        clean_results = [i for i in parsing_results if i.uid not in problem_uids_deduped]
    return clean_results


def report_stats(stats: RunStats):
    print(create_header(80, "RUN STATS", True, "-"))

    if stats.successes is not None and stats.failures is not None:
        print(f"{Symbols.CHECK.value} {stats.successes} | {Symbols.DELETED.value} {stats.failures}")

    elapsed_time_seconds = stats.end - stats.start
    print(f"elapsed time: {elapsed_time_seconds:.2f} seconds")

    if stats.n_ops is not None and stats.n_ops > 0:
        elapsed_time_seconds_per_event = elapsed_time_seconds / stats.n_ops
        print(f"elapsed time per {stats.op_name}: {elapsed_time_seconds_per_event:.2f} seconds")


def check_write_success(config: ScrapingConfig) -> tuple[bool, Optional[str]]:
    with config.path.open() as f:
        contents = "".join(f.readlines())

    file_size_bytes = config.path.stat().st_size
    file_too_small = file_size_bytes < 1024

    if "Search results" in contents:
        return False, "page_not_found"
    if "Internal Server Error" in contents:
        return False, "server_error"
    if "Too Many Requests" in contents:
        return False, "rate_limited"
    if file_too_small:
        return False, "file_too_small"

    return True, None


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


def get_table_uids(
    uid_col: Mapped[Any],
    force_run: bool = False,
    where_clause: Optional[Any] = None,
) -> Optional[list[Any]]:
    if force_run:
        return None

    engine = get_engine()
    with Session(engine) as session:
        cmd = select(uid_col)
        if where_clause is not None:
            cmd = cmd.where(where_clause)
            print(cmd)
        results = session.exec(cmd).all()

    if len(results) == 0:
        return None

    return list(results)


def scrape_page(
    config: ScrapingConfig,
    max_attempts: int = 3,
    sleep_multiplier_increment: int = 10,
    session: Optional[requests.Session] = None,
) -> ScrapingWriteResult:
    write_success = False
    attempts = 0
    sleep_multiplier = 1
    last_status_code = None
    error_type = None

    while not write_success and attempts < max_attempts:
        attempts += 1
        dump_success, status_code = dump_html(config, session=session)
        last_status_code = status_code

        if status_code == 404:
            error_type = "page_not_found"
            break

        if dump_success:
            write_success, content_error = check_write_success(config)
            if not write_success:
                error_type = content_error or "invalid_content"
                if error_type == "page_not_found":
                    break

        if attempts == max_attempts:
            if not write_success and status_code != 200 and error_type is None:
                if status_code == 0:
                    error_type = "connection_error"
                else:
                    error_type = "http_error"
            break

        if not write_success:
            ms_to_sleep = random.randint(500 * sleep_multiplier, 1000 * sleep_multiplier)
            time.sleep(ms_to_sleep / 1000)
            sleep_multiplier += sleep_multiplier_increment

    return ScrapingWriteResult(
        config=config,
        path=config.path,
        success=write_success,
        attempts=attempts,
        status_code=last_status_code,
        error_type=error_type,
    )


def get_html_files(
    path: Path,
    uid_col: Mapped[Any],
    where_clause: Optional[Any] = None,
    force_run: bool = False,
) -> list[FileContents]:
    all_files = list(path.glob("*.html"))

    existing_uids = get_table_uids(uid_col, force_run, where_clause)
    if existing_uids is None:
        files_to_parse = all_files
    else:
        files_to_parse = []
        for f in all_files:
            uid_parts = f.stem.split("_")
            if not any(part in existing_uids for part in uid_parts):
                files_to_parse.append(f)

    fight_contents_to_parse: list[FileContents] = []
    for i, fpath in enumerate(files_to_parse):
        uid = fpath.stem

        modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
        with fpath.open() as f:
            fight_contents_to_parse.append(
                FileContents(
                    uid=uid,
                    path=fpath,
                    modified_ts=modification_time,
                    contents=f.read(),
                    file_num=i,
                    n_files=len(files_to_parse),
                )
            )

    return fight_contents_to_parse


def dump_html(
    config: ScrapingConfig, log_uid: bool = False, session: Optional[requests.Session] = None
) -> tuple[bool, int]:
    if log_uid:
        print(f"saving {config.description}: {config.uid}")
    url = f"{config.base_url}/{config.uid}"

    try:
        if session is None:
            response = requests.get(url, timeout=30)
        else:
            response = session.get(url, timeout=30)

        status_code = response.status_code

        if status_code != 200:
            return False, status_code

        soup = bs4.BeautifulSoup(response.text, "html.parser")

        with config.path.open("w") as f:
            f.write(str(soup))

        return True, status_code
    except (
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ):
        return False, 0


def write_data_to_db(data: list[SQLModelType]) -> None:
    if not data:
        return

    engine = get_engine()
    print(f"[n={len(data):5,d}] writing records")

    with Session(engine) as session:
        for item in data:
            session.merge(item)
        session.commit()


def get_table_rows(soup: bs4.BeautifulSoup) -> list[bs4.ResultSet[bs4.Tag]]:
    tables = soup.find_all("table")
    all_results = []
    for table in tables:
        if table is None:
            raise ValueError("No table found")

        table_body = table.find("tbody")
        if not isinstance(table_body, bs4.Tag):
            raise TypeError(f"expected bs4.Tag, got {type(table_body)}")

        rows = table_body.find_all("tr")
        if rows is None:
            raise ValueError()

        all_results.append(rows)

    return all_results


def setup_panoctagon(title: str) -> PanoctagonSetup:
    start_time = time.time()
    print(create_header(80, "PANOCTAGON", True, "="))
    footer = create_header(80, "", True, "=")
    cpu_count = os.cpu_count()
    if cpu_count is None:
        cpu_count = 4

    return PanoctagonSetup(
        footer=footer,
        cpu_count=cpu_count,
        start_time=start_time,
    )


def write_parsing_timestamp(
    tbl: Type[SQLModel],
    update_col_name: str,
    uid_col: Mapped[Any],
    result_uids: list[str],
) -> None:
    current_timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"updating {len(result_uids)} rows")
    start = time.time()
    engine = get_engine()
    with Session(engine) as session:
        for uid in result_uids:
            record = session.exec(select(tbl).where(uid_col == uid)).one()
            record.__setattr__(update_col_name, current_timestamp)
            session.add(record)
            session.commit()
    end = time.time()
    print(f"elapsed time: {end - start:.2f} seconds")
