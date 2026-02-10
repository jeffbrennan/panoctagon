"""
To add a daily schedule that materializes your dbt assets, uncomment the following lines.
"""

from dagster import DefaultScheduleStatus
from dagster_dbt import build_schedule_from_dbt_selection

from .assets import panoctagon_dbt_assets

# TODO: define daily job on all assets except for things like divisions, promotions
schedules = [
    build_schedule_from_dbt_selection(
        [panoctagon_dbt_assets],
        job_name="materialize_dbt_models",
        cron_schedule="0 0 * * *",
        dbt_select="fqn:*",
        default_status=DefaultScheduleStatus.RUNNING,
    ),
]
