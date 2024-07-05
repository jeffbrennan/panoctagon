from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Optional, Type

import bs4
import requests
from sqlalchemy import Engine
from sqlalchemy.orm import Mapped
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


def get_engine() -> Engine:
    db_path = Path(__file__).parent.parent / "data" / "panoctagon_orm.db"
    engine_path = "sqlite:///" + str(db_path.resolve())
    engine = create_engine(engine_path, echo=True)
    return engine


def delete_existing_records(
    tbl_model: Type[SQLModel], uid_col: Mapped[Any], uids: list[str]
) -> None:
    print(f"[n={len(uids):5,d}] deleting records")
    engine = get_engine()

    with Session(engine) as session:
        statement = select(tbl_model).where(uid_col.in_(uids))
        results = session.exec(statement).all()

        assert len(results) == len(uids)
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

            all_parsing_issues.append(
                ParsingIssue(issue=issue, uids=[parsing_result.uid])
            )

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


def get_table_uids(
    uid_col: Mapped[Any], force_run: bool = False
) -> Optional[list[Any]]:
    if force_run:
        return None

    engine = get_engine()
    with Session(engine) as session:
        results = session.exec(select(uid_col)).all()

    if len(results) == 0:
        return None

    return list(results)


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
    path: Path, uid_col: Mapped[Any], force_run: bool, uid: Optional[str] = None
) -> list[FileContents]:
    all_files = list(path.glob("*.html"))
    if uid is not None:
        all_files = [f for f in all_files if uid in f.name]

    existing_uids = get_table_uids(uid_col, force_run)
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


def write_data_to_db(data: list[SQLModelType]) -> None:
    engine = get_engine()

    with Session(engine) as session:
        session.bulk_save_objects(data)
        session.commit()


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
