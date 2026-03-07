from dagster import DefaultScheduleStatus, ScheduleDefinition

from .jobs import refresh

schedules = [
    ScheduleDefinition(
        job=refresh,
        cron_schedule="0 0 * * *",
        default_status=DefaultScheduleStatus.RUNNING,
    ),
]
