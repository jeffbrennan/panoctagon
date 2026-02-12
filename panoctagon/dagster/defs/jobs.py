from dagster import AssetSelection, define_asset_job

refresh = define_asset_job(
    name="refresh",
    selection=AssetSelection.all(),
    description="Refresh all UFC data assets",
)
