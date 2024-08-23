from typing import Any

from dagster import AssetExecutionContext, asset, multi_asset, AssetSpec
from dagster_dbt import DbtCliResource, dbt_assets

from panoctagon.ufc.scrape_events import scrape_events
from panoctagon.ufc.scrape_fights import scrape_fights
from panoctagon.ufc.parse_fights import parse_fights
from panoctagon.ufc.parse_fighters import parse_fighters
from panoctagon.ufc.parse_fighter_bio import parse_fighter_bio
from panoctagon.ufc.scrape_fighter_bio import scrape_fighter_bio
from panoctagon.divisions import setup_divisions
from panoctagon.promotions import setup_promotions
from .project import panoctagon_project

db_path = panoctagon_project.project_dir.joinpath("data/panoctagon_orm.db")


@dbt_assets(manifest=panoctagon_project.manifest_path)
def panoctagon_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource) -> Any:
    yield from dbt.cli(["build"], context=context).stream()


@asset(compute_kind="python", key=["ufc_events"])
def dagster_scrape_events(context: AssetExecutionContext) -> None:
    n_new_events = scrape_events()
    context.add_output_metadata({"n_records": n_new_events})


@asset(compute_kind="python", key=["scrape_fights"], deps=["ufc_events"])
def dagster_scrape_fights(context: AssetExecutionContext) -> None:
    n_new_fights = scrape_fights()
    context.add_output_metadata({"n_records": n_new_fights})


@multi_asset(
    compute_kind="python",
    specs=[
        AssetSpec("ufc_fights", deps=["scrape_fights"]),
        AssetSpec("ufc_fight_stats", deps=["scrape_fights"]),
    ],
)
def dagster_parse_fights(context: AssetExecutionContext) -> tuple[None, None]:
    n_records = parse_fights()
    context.add_output_metadata({"n_records": n_records}, output_name="ufc_fights")
    context.add_output_metadata({"n_records": n_records}, output_name="ufc_fight_stats")
    return None, None


@asset(compute_kind="python", key=["scrape_fighters"], deps=["ufc_fights"])
def dagster_scrape_fighters(context: AssetExecutionContext) -> None:
    n_new_fighters = scrape_fights()
    context.add_output_metadata({"n_records": n_new_fighters})


@asset(compute_kind="python", key=["ufc_fighters_stg"], deps=["scrape_fighters"])
def dagster_parse_fighters(context: AssetExecutionContext) -> None:
    n_records = parse_fighters()
    context.add_output_metadata({"n_records": n_records})


@asset(compute_kind="python", key=["scrape_fighter_bio"], deps=["ufc_fighters_stg"])
def dagster_scrape_fighter_bio(context: AssetExecutionContext) -> None:
    n_bios = scrape_fighter_bio()
    context.add_output_metadata({"n_records": n_bios})


@asset(compute_kind="python", key=["ufc_fighters"], deps=["scrape_fighter_bio"])
def dagster_parse_fighter_bio(context: AssetExecutionContext) -> None:
    n_bios = parse_fighter_bio()
    context.add_output_metadata({"n_records": n_bios})


@asset(compute_kind="python", key=["divisions"])
def dagster_divisions():
    setup_divisions()


@asset(compute_kind="python", key=["promotions"])
def dagster_promotions():
    setup_promotions()
