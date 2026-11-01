"""Create isolated data for production-server browser tests."""
import base64
import os
from datetime import datetime, timezone

import duckdb
from pathlib import Path

from tests.dashboard_seed import seed_dashboard

root = Path(os.environ.get('PANOCTAGON_TEST_DATA', '.scratch/integration')).resolve()
root.mkdir(parents=True, exist_ok=True)
database = root / 'dashboard.duckdb'
database.unlink(missing_ok=True)
seed_dashboard(database)
with duckdb.connect(str(database)) as db:
    future = f"{datetime.now(timezone.utc).year + 1}-12-01"
    db.execute("update ufc_events set event_date = ? where event_uid = 'future'", [future])
    db.execute("""
        insert into ufc_fights
        select 'extra' || cast(i as varchar), 'past', 'alpha', 'bravo', 'WIN', 'LOSS',
               'MIDDLEWEIGHT', 'REGULAR', 'Decision', 3, 10 + i from range(1, 21) t(i)
    """)
    db.execute("""
        insert into ufc_fights values ('draw', 'past', 'alpha', 'bravo', 'DRAW', 'DRAW',
               'MIDDLEWEIGHT', 'REGULAR', 'Decision', 3, 40)
    """)
headshots = root / 'headshots'
headshots.mkdir(exist_ok=True)
(headshots / 'alpha_headshot.png').write_bytes(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmZkAAAAASUVORK5CYII='
))
