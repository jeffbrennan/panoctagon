from dagster import AssetSelection, define_asset_job, multiprocess_executor

refresh = define_asset_job(
    name="refresh",
    selection=AssetSelection.all(),
    description="Refresh all UFC data assets",
    executor_def=multiprocess_executor.configured(
        {
            "tag_concurrency_limits": [
                {"key": "duckdb_write", "value": "true", "limit": 1}
            ]
        }
    ),
)
