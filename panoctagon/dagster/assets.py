from typing import Any

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from .project import panoctagon_project

db_path = panoctagon_project.project_dir.joinpath("data/panoctagon_orm.db")


@dbt_assets(manifest=panoctagon_project.manifest_path)
def panoctagon_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource) -> Any:
    yield from dbt.cli(["build"], context=context).stream()
