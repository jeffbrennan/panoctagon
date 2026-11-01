import json
import time
import urllib.request

results = {}
for key, path in [
    ("upcoming", "/api/upcoming"),
    ("roster", "/api/analytics/roster?division=MIDDLEWEIGHT"),
    (
        "network_all_years",
        "/api/analytics/network?division=HEAVYWEIGHT&start_year=1997&end_year=2026",
    ),
]:
    samples = []
    for _ in range(20):
        start = time.perf_counter()
        with urllib.request.urlopen("http://127.0.0.1:18751" + path, timeout=120) as response:
            body = response.read()
        samples.append({"ms": (time.perf_counter() - start) * 1000, "bytes": len(body)})
    results[key] = samples
    print(key, "first", round(samples[0]["ms"], 2), "last", round(samples[-1]["ms"], 2), flush=True)
with open(".scratch/release-gates/api-bench.json", "w") as f:
    json.dump(results, f, indent=2)
