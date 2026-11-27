import json
import time
import os
from panoctagon.dashboard.pages.network import update_network_graph

samples = []
for i in range(20):
    start = time.perf_counter()
    figure = update_network_graph("network", "HEAVYWEIGHT", [1997, 2026])
    payload = figure.to_json().encode()
    samples.append({"ms": (time.perf_counter() - start) * 1000, "bytes": len(payload)})
    print("dash", i, round(samples[-1]["ms"], 1), flush=True)
with open(
    os.environ.get("GATE_NETWORK_OUTPUT", ".scratch/release-gates/network-dash.json"), "w"
) as f:
    json.dump(samples, f)
