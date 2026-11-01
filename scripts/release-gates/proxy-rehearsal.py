import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

root = Path(".scratch/release-gates/traefik")


def get(path):
    req = urllib.request.Request(
        "http://127.0.0.1:18754" + path, headers={"Host": "panoctagon.test"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def switch(name):
    temporary = root / "active.tmp"
    temporary.write_bytes((root / f"{name}.yml").read_bytes())
    os.replace(temporary, root / "active.yml")
    for _ in range(100):
        status, body = get("/api/metadata")
        if status == 200 and ("current_year" in json.loads(body)) == (name == "cutover"):
            return
        time.sleep(0.1)
    raise RuntimeError(f"proxy failed to switch to {name}")


results = []
for phase in ("legacy", "cutover", "legacy"):
    switch(phase)
    index, html = get("/")
    status, metadata = get("/api/metadata")
    health, _ = get("/api/health")
    invalid, _ = get("/api/api/health")
    dagster, dagster_path = get("/dagster/server_info")
    assert index == status == health == dagster == 200
    assert invalid == 404
    assert dagster_path == "/dagster/server_info"
    assert ("_dash" in html) == (phase == "legacy")
    results.append(
        {
            "phase": phase,
            "root": index,
            "api_metadata": status,
            "api_health": health,
            "double_api": invalid,
            "dagster_path": dagster_path,
        }
    )
print(json.dumps(results, indent=2))
Path(".scratch/release-gates/proxy-result.json").write_text(json.dumps(results, indent=2))
