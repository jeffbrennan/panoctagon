"""Check the rendered opt-in topology without starting the production network."""
import json
import os
import subprocess
from pathlib import Path


def _render(*files: str, profiles: tuple[str, ...] = (), env: dict[str, str] | None = None):
    root = Path(__file__).parents[1]
    command = ['docker', 'compose']
    for profile in profiles:
        command += ['--profile', profile]
    for file in files:
        command += ['-f', file]
    merged_env = {**os.environ, **(env or {})}
    return json.loads(subprocess.check_output([*command, 'config', '--format', 'json'], cwd=root, env=merged_env))


def test_cutover_preserves_api_prefix_and_dagster_routing():
    base = _render('docker-compose.yaml')
    combined = _render('docker-compose.yaml', 'docker-compose.svelte.yaml')
    services = combined['services']
    assert 'panoctagon_api' not in services

    frontend = services['panoctagon_frontend']
    assert frontend['labels']['traefik.http.routers.panoctagon_frontend.rule'] == base['services']['panoctagon_frontend']['labels']['traefik.http.routers.panoctagon_frontend.rule']
    assert 'middlewares' not in ' '.join(frontend['labels'])
    assert frontend['labels']['traefik.http.services.panoctagon_frontend.loadbalancer.server.port'] == '8050'
    assert int(frontend['deploy']['resources']['limits']['memory']) == 512 * 1024 * 1024
    assert any(v['target'] == '/panoctagon/data' and v['read_only'] for v in frontend['volumes'])
    assert services['panoctagon_backend']['labels'] == base['services']['panoctagon_backend']['labels']

    legacy = _render('docker-compose.yaml', 'docker-compose.svelte.yaml', profiles=('legacy',))
    legacy_api = legacy['services']['panoctagon_api']
    assert legacy_api['labels']['traefik.enable'] == 'false'
    assert any(v['target'] == '/panoctagon/data' and v['read_only'] for v in legacy_api['volumes'])


def test_prod_overlay_uses_prebuilt_ghcr_images():
    prod = _render(
        'docker-compose.yaml',
        'docker-compose.svelte.yaml',
        'docker-compose.prod.yaml',
        env={'IMAGE_TAG': 'sha-abc1234'},
    )
    services = prod['services']
    assert 'panoctagon_api' not in services
    assert services['panoctagon_frontend']['image'] == 'ghcr.io/jeffbrennan/panoctagon-frontend:sha-abc1234'
    for backend_service in ('panoctagon_backend', 'panoctagon_daemon', 'panoctagon_code_server'):
        assert services[backend_service]['image'] == 'ghcr.io/jeffbrennan/panoctagon-backend:sha-abc1234'
    assert int(services['panoctagon_frontend']['deploy']['resources']['limits']['memory']) == 512 * 1024 * 1024
