import json
import os
import time
import urllib.request
from pathlib import Path

base = Path(".scratch/release-gates")
directory = base / "snapshots"
config = base / "traefik"
revisions = json.loads((base / "snapshot-revisions.json").read_text())


def write_atomic(path, content):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content)
    os.replace(temporary, path)


write_atomic(config / "active.yml", (config / "cutover-snapshot.yml").read_text())
results = []
for revision, expected in [(revisions[0], 2637), (revisions[1], 2638), (revisions[0], 2637)]:
    write_atomic(directory / "manifest.json", json.dumps(revision))
    for _ in range(50):
        request = urllib.request.Request(
            "http://127.0.0.1:18754/api/metadata", headers={"Host": "panoctagon.test"}
        )
        with urllib.request.urlopen(request) as response:
            metadata = json.load(response)
        if metadata.get("revision") == revision["revision"]:
            break
        time.sleep(0.1)
    assert metadata["revision"] == revision["revision"]
    assert metadata["fighters"] == expected
    results.append(
        {"revision": revision["revision"], "fighters": metadata["fighters"], "status": 200}
    )
print(json.dumps(results, indent=2))
(base / "snapshot-result.json").write_text(json.dumps(results, indent=2))
