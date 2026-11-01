"""Create isolated data for production-server browser tests."""
import base64
import os
from pathlib import Path

from tests.dashboard_seed import seed_dashboard

root = Path(os.environ.get('PANOCTAGON_TEST_DATA', '.scratch/integration')).resolve()
root.mkdir(parents=True, exist_ok=True)
database = root / 'dashboard.duckdb'
database.unlink(missing_ok=True)
seed_dashboard(database)
headshots = root / 'headshots'
headshots.mkdir(exist_ok=True)
(headshots / 'alpha_headshot.png').write_bytes(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmZkAAAAASUVORK5CYII='
))
