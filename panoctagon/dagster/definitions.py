from dagster import Definitions
from dagster_dbt import DbtCliResource

from .assets import panoctagon_dbt_assets
from .project import panoctagon_project
from .schedules import schedules

defs = Definitions(
    assets=[panoctagon_dbt_assets],
    schedules=schedules,
    resources={
        "dbt": DbtCliResource(project_dir=panoctagon_project),
    },
)
