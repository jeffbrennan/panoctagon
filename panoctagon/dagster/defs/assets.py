from typing import Any

from dagster_dbt import DbtCliResource, dbt_assets

import panoctagon.ufc.parse.app as parse
import panoctagon.ufc.scrape.app as scrape
from dagster import AssetExecutionContext, AssetSpec, asset, multi_asset
from panoctagon.dagster.project import panoctagon_project
from panoctagon.divisions import setup_divisions
from panoctagon.promotions import setup_promotions

db_path = panoctagon_project.project_dir.joinpath("data/panoctagon_orm.duckdb")


@dbt_assets(manifest=panoctagon_project.manifest_path)
def panoctagon_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource) -> Any:
    yield from dbt.cli(["build"], context=context).stream()


@asset(compute_kind="python", key=["ufc_events"], deps=["divisions"])
def dagster_scrape_events(context: AssetExecutionContext) -> None:
    n_new_events = scrape.events()
    context.add_output_metadata({"n_records": n_new_events})


@asset(compute_kind="python", key=["scrape_fights"], deps=["ufc_events"])
def dagster_scrape_fights(context: AssetExecutionContext) -> None:
    n_new_fights = scrape.fights()
    context.add_output_metadata({"n_records": n_new_fights})


@multi_asset(
    compute_kind="python",
    specs=[
        AssetSpec("ufc_fights", deps=["scrape_fights"]),
        AssetSpec("ufc_fight_stats", deps=["scrape_fights"]),
    ],
)
def dagster_parse_fights(context: AssetExecutionContext) -> tuple[None, None]:
    n_records = parse.fights()
    context.add_output_metadata({"n_records": n_records}, output_name="ufc_fights")
    context.add_output_metadata({"n_records": n_records}, output_name="ufc_fight_stats")
    return None, None


@asset(compute_kind="python", key=["scrape_fighters"], deps=["ufc_fights"])
def dagster_scrape_fighters(context: AssetExecutionContext) -> None:
    n_new_fighters = scrape.fighters()
    context.add_output_metadata({"n_records": n_new_fighters})


@asset(compute_kind="python", key=["ufc_fighters_stg"], deps=["scrape_fighters"])
def dagster_parse_fighters(context: AssetExecutionContext) -> None:
    n_records = parse.fighters()
    context.add_output_metadata({"n_records": n_records})


@asset(compute_kind="python", key=["scrape_fighter_bio"], deps=["ufc_fighters_stg"])
def dagster_scrape_fighter_bio(context: AssetExecutionContext) -> None:
    n_bios = scrape.bios()
    context.add_output_metadata({"n_records": n_bios})


@asset(compute_kind="python", key=["ufc_fighters"], deps=["scrape_fighter_bio"])
def dagster_parse_fighter_bio(context: AssetExecutionContext) -> None:
    n_bios = parse.bios()
    context.add_output_metadata({"n_records": n_bios})


@asset(compute_kind="python", key=["scrape_bfo_events"], deps=["ufc_events"])
def dagster_scrape_bfo_events(context: AssetExecutionContext) -> None:
    n_downloaded = scrape.event_pages()
    context.add_output_metadata({"n_records": n_downloaded})


@asset(compute_kind="python", key=["scrape_bfo_fighters"], deps=["scrape_bfo_events"])
def dagster_scrape_bfo_fighters(context: AssetExecutionContext) -> None:
    n_downloaded = scrape.fighter_pages()
    context.add_output_metadata({"n_records": n_downloaded})


@asset(compute_kind="python", key=["bfo_raw_odds"], deps=["scrape_bfo_fighters"])
def dagster_scrape_bfo_odds(context: AssetExecutionContext) -> None:
    n_downloaded = scrape.fight_odds()
    context.add_output_metadata({"n_records": n_downloaded})


@asset(compute_kind="python", key=["bfo_fighter_odds"], deps=["scrape_bfo_fighters"])
def dagster_scrape_bfo_fighter_odds(context: AssetExecutionContext) -> None:
    n_downloaded = scrape.fighter_odds()
    context.add_output_metadata({"n_records": n_downloaded})


@asset(compute_kind="python", key=["bfo_parsed_odds"], deps=["bfo_raw_odds", "bfo_fighter_odds"])
def dagster_parse_bfo_odds(context: AssetExecutionContext) -> None:
    n_saved = parse.odds()
    context.add_output_metadata({"n_records": n_saved})


@asset(
    compute_kind="python",
    key=["bfo_ufc_link"],
    deps=["bfo_parsed_odds", "ufc_fights", "ufc_fighters"],
)
def dagster_link_bfo_odds(context: AssetExecutionContext) -> None:
    n_matched = parse.link_odds()
    context.add_output_metadata({"n_records": n_matched})


@asset(compute_kind="python", key=["divisions"], deps=["promotions"])
def dagster_divisions():
    setup_divisions()


@asset(compute_kind="python", key=["promotions"])
def dagster_promotions():
    setup_promotions()
