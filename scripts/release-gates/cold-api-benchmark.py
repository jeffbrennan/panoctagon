"""Measure first requests against new API processes (OS file cache is not flushed)."""

import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

base = Path(__file__).resolve().parents[2]
python = base / ".venv/bin/python"
database = base / ".scratch/release-gates/data/panoctagon_orm.duckdb"
url = "http://127.0.0.1:18758"
routes = {
    "upcoming": "/api/upcoming",
    "roster": "/api/analytics/roster?division=MIDDLEWEIGHT",
    "network_all_years": "/api/analytics/network?division=HEAVYWEIGHT&start_year=1997&end_year=2026",
}
results = []
for sample in range(20):
    env = dict(os.environ, PANOCTAGON_API_DATABASE=str(database))
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "panoctagon.web.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18758",
            "--no-access-log",
        ],
        cwd=base,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(200):
            if process.poll() is not None:
                raise RuntimeError("API server exited before readiness")
            try:
                with urllib.request.urlopen(url + "/healthz", timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        else:
            raise RuntimeError("API server did not become live")
        row = {"sample": sample}
        for name, path in routes.items():
            start = time.perf_counter()
            with urllib.request.urlopen(url + path, timeout=120) as response:
                body = response.read()
            row[name] = {"ms": (time.perf_counter() - start) * 1000, "bytes": len(body)}
        results.append(row)
        print(json.dumps(row), flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
output = base / ".scratch/release-gates/api-process-cold.json"
output.write_text(json.dumps(results, indent=2))
