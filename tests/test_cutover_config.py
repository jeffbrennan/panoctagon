"""Check the rendered opt-in topology without starting the production network."""
import json
import subprocess
from pathlib import Path


def test_cutover_preserves_api_prefix_and_dagster_routing():
    root = Path(__file__).parents[1]

    def render(*files: str, profiles: tuple[str, ...] = ()):
        command = ['docker', 'compose']
        for profile in profiles:
            command += ['--profile', profile]
        for file in files:
            command += ['-f', file]
        return json.loads(subprocess.check_output([*command, 'config', '--format', 'json'], cwd=root))

    base = render('docker-compose.yaml')
    combined = render('docker-compose.yaml', 'docker-compose.svelte.yaml')
    services = combined['services']
    assert 'panoctagon_api' not in services

    frontend = services['panoctagon_frontend']
    assert frontend['labels']['traefik.http.routers.panoctagon_frontend.rule'] == base['services']['panoctagon_frontend']['labels']['traefik.http.routers.panoctagon_frontend.rule']
    assert 'middlewares' not in ' '.join(frontend['labels'])
    assert frontend['labels']['traefik.http.services.panoctagon_frontend.loadbalancer.server.port'] == '8050'
    assert int(frontend['deploy']['resources']['limits']['memory']) == 512 * 1024 * 1024
    assert any(v['target'] == '/panoctagon/data' and v['read_only'] for v in frontend['volumes'])
    assert services['panoctagon_backend']['labels'] == base['services']['panoctagon_backend']['labels']

    legacy = render('docker-compose.yaml', 'docker-compose.svelte.yaml', profiles=('legacy',))
    legacy_api = legacy['services']['panoctagon_api']
    assert legacy_api['labels']['traefik.enable'] == 'false'
    assert any(v['target'] == '/panoctagon/data' and v['read_only'] for v in legacy_api['volumes'])
