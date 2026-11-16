"""Validate the rendered runtime contract without Azure access or real credentials."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render_app', ROOT / 'scripts/azure/render_app.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture()
def env():
    return {
        'GITHUB_SHA': 'a' * 40,
        'GITHUB_REPOSITORY_OWNER': 'Thecoolss', 'PREFIX': 'sdroubi-ieu2024',
        'LOCATION': 'germanywestcentral', 'ENVIRONMENT_ID': '/environment',
        'UI_ORIGIN': 'https://ui.example', 'HOUSEHOLD_URL': 'https://household.example',
        'HOUSEHOLD_DATABASE_URL': 'household-private', 'FAIRNESS_DATABASE_URL': 'fairness-private',
        'AUTH_SECRET': 'private-auth',
    }


@pytest.mark.parametrize('service,port', [('household', 5000), ('fairness', 5001)])
def test_deployment_preserves_service_isolation_and_scale_to_zero(env, service, port):
    app = module.render(service, env)['properties']
    assert app['configuration']['activeRevisionsMode'] == 'Single'
    ingress = app['configuration']['ingress']
    assert ingress['external'] and not ingress['allowInsecure'] and ingress['targetPort'] == port
    template = app['template']
    assert template['scale']['minReplicas'] == 0 and template['scale']['maxReplicas'] == 1
    assert len(template['containers']) == 1
    container = template['containers'][0]
    assert container['image'] == f'ghcr.io/thecoolss/housemate-{service}:' + 'a' * 40
    variables = {v['name']: v for v in container['env']}
    assert variables['GIT_SHA']['value'] == env['GITHUB_SHA']
    assert variables['DATABASE_URL'] == {'name': 'DATABASE_URL', 'secretRef': 'database-url'}
    assert variables['AUTH_SECRET'] == {'name': 'AUTH_SECRET', 'secretRef': 'auth-secret'}
    assert variables['CORS_ORIGIN']['value'] == env['UI_ORIGIN']
    secrets = {s['name']: s['value'] for s in app['configuration']['secrets']}
    assert secrets['database-url'] == env[service.upper() + '_DATABASE_URL']
    if service == 'fairness':
        assert variables['HOUSEHOLD_URL']['value'] == env['HOUSEHOLD_URL']
    probes = {p['type']: p for p in container['probes']}
    assert probes['Startup']['failureThreshold'] * probes['Startup']['periodSeconds'] > 90
    assert 'tcpSocket' in probes['Liveness']


@pytest.mark.parametrize('service', ['household', 'fairness'])
def test_deployment_omits_unsupported_express_revision_controls(env, service):
    app = module.render(service, env)['properties']
    assert 'revisionSuffix' not in app['template']
    assert 'traffic' not in app['configuration']['ingress']
    assert 'workloadProfileName' not in app


def test_latest_tag_cannot_be_deployed(env):
    env['GITHUB_SHA'] = 'latest'
    with pytest.raises(ValueError, match='SHA'):
        module.render('household', env)


def test_unknown_service_cannot_be_deployed(env):
    with pytest.raises(ValueError, match='service'):
        module.render('other-project', env)


def test_health_check_rejects_old_revision_and_accepts_expected_sha(monkeypatch):
    import io
    import json
    spec = importlib.util.spec_from_file_location('check_health', ROOT / 'scripts/azure/check_health.py')
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)
    versions = iter(['old', 'new'])
    sleeps = []
    class Response(io.BytesIO):
        status = 200
    def response(*args, **kwargs):
        return Response(json.dumps({'status': 'ok', 'db': 'ok', 'version': next(versions)}).encode())
    monkeypatch.setattr(health.urllib.request, 'urlopen', response)
    monkeypatch.setattr(health.time, 'sleep', sleeps.append)
    health.wait_for_health('https://service.example', 'new')
    assert len(sleeps) == 1


def test_health_check_stops_after_budget(monkeypatch):
    spec = importlib.util.spec_from_file_location('check_health', ROOT / 'scripts/azure/check_health.py')
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)
    now = [0]
    def sleep(seconds):
        now[0] += seconds
    def unavailable(*args, **kwargs):
        raise OSError('not ready')
    monkeypatch.setattr(health.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(health.time, 'sleep', sleep)
    monkeypatch.setattr(health.urllib.request, 'urlopen', unavailable)
    with pytest.raises(SystemExit, match='not ready within 12s'):
        health.wait_for_health('https://service.example', 'new', budget=12)
    assert now[0] == 12
