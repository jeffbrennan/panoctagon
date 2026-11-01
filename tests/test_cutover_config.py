"""Check the rendered opt-in topology without starting the production network."""
import json
import subprocess
from pathlib import Path


def test_cutover_preserves_api_prefix_and_dagster_routing():
    root = Path(__file__).parents[1]
    def render(*files):
        command = ['docker', 'compose']
        for file in files:
            command += ['-f', file]
        return json.loads(subprocess.check_output([*command, 'config', '--format', 'json'], cwd=root))
    base = render('docker-compose.yaml')
    combined = render('docker-compose.yaml', 'docker-compose.svelte.yaml')
    services = combined['services']
    assert services['panoctagon_api']['labels']['traefik.enable'] == 'false'
    frontend = services['panoctagon_frontend']
    assert frontend['labels']['traefik.http.routers.panoctagon_frontend.rule'] == base['services']['panoctagon_frontend']['labels']['traefik.http.routers.panoctagon_frontend.rule']
    assert 'middlewares' not in ' '.join(frontend['labels'])
    assert frontend['labels']['traefik.http.services.panoctagon_frontend.loadbalancer.server.port'] == '8050'
    assert services['panoctagon_backend']['labels'] == base['services']['panoctagon_backend']['labels']
    for service in ('panoctagon_frontend', 'panoctagon_api'):
        assert any(v['target'] == '/panoctagon/data' and v['read_only'] for v in services[service]['volumes'])
