from dagster_dbt import DbtCliResource

from dagster import Definitions

from .assets import (
    dagster_divisions,
    dagster_parse_fighter_bio,
    dagster_parse_fighters,
    dagster_parse_fights,
    dagster_promotions,
    dagster_scrape_events,
    dagster_scrape_fighter_bio,
    dagster_scrape_fighters,
    dagster_scrape_fights,
    panoctagon_dbt_assets,
)
from .project import panoctagon_project
from .schedules import schedules

defs = Definitions(
    assets=[
        panoctagon_dbt_assets,
        dagster_scrape_events,
        dagster_scrape_fights,
        dagster_parse_fights,
        dagster_scrape_fighters,
        dagster_parse_fighters,
        dagster_scrape_fighter_bio,
        dagster_parse_fighter_bio,
        dagster_promotions,
        dagster_divisions,
    ],
    schedules=schedules,
    resources={
        "dbt": DbtCliResource(project_dir=panoctagon_project),
    },
)
