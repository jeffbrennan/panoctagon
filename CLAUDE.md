# Purpose
panoctagon is a project designed to aggregate, analyze, and visualize the outcomes of UFC fights.

# Code style
- Never add comments that simply describe what the code beneath is doing
- Only add comments when an implementation is non-obvious, and cannot be done simpler
- Always prioritize writing simple, readable code unless specifically asked otherwise
- Do not over-abstract implementations unless specifically asked otherwise
- Do not use emojis anywhere

# Tool use
- Always use `uv run python` instead of `python` and `uv run dbt` instead of `dbt`
- To run Dagster with persistent storage: `DAGSTER_HOME="/Users/jeffb/Desktop/Life/personal-projects/panoctagon/data/dagster" uv run dagster dev`
