"""system.yaml and the OpenAPI documents must match the code and the compose file."""

import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = yaml.safe_load((ROOT / "system.yaml").read_text())
SERVICES = list(SYSTEM["services"])
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _openapi(service):
    return yaml.safe_load((ROOT / SYSTEM["services"][service]["openapi"]).read_text())


def _config_source(service):
    return (ROOT / SYSTEM["services"][service]["path"] / "config.py").read_text()


def _operations(spec):
    return {
        f"{method.upper()} {path}"
        for path, item in spec["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }


def test_system_yaml_validates_against_the_schema():
    schema = json.loads((ROOT / "system.schema.json").read_text())

    jsonschema.validate(SYSTEM, schema)


@pytest.mark.parametrize("service", SERVICES)
def test_every_env_var_the_service_reads_is_listed_and_nothing_else(service):
    read = set(re.findall(r'os\.environ\.get\(\s*"([A-Z_]+)"', _config_source(service)))
    listed = set(SYSTEM["services"][service]["env"])

    assert read - listed == set(), "read by config.py but missing from system.yaml"
    assert listed - read == set(), "listed in system.yaml but never read by config.py"


@pytest.mark.parametrize("service", SERVICES)
def test_secrets_have_no_default_and_defaults_match_the_code(service):
    source = _config_source(service)
    for name, entry in SYSTEM["services"][service]["env"].items():
        if entry.get("secret"):
            assert "default" not in entry, f"{name} is a secret and must not have a default"
            continue
        match = re.search(rf'os\.environ\.get\(\s*"{name}",\s*("[^"]*"|[\d.]+)\s*\)', source)
        if match is None:  # default is an expression (e.g. 3 * 24 * 60 * 60); not compared
            continue
        in_code = match.group(1).strip('"')
        listed = str(entry["default"])
        try:
            assert float(in_code) == float(listed), f"{name}: code says {in_code}, yaml says {listed}"
        except ValueError:
            assert in_code == listed, f"{name}: code says {in_code}, yaml says {listed}"


@pytest.mark.parametrize("service", SERVICES)
def test_secret_settings_have_no_default_in_the_code(service):
    source = _config_source(service)
    for name, entry in SYSTEM["services"][service]["env"].items():
        if entry.get("secret") and name == "AUTH_SECRET":
            assert f'os.environ.get("{name}")' in source


@pytest.mark.parametrize("service", SERVICES)
def test_paths_and_health_endpoint_exist(service):
    entry = SYSTEM["services"][service]

    assert (ROOT / entry["path"]).is_dir()
    assert (ROOT / entry["openapi"]).is_file()
    assert (ROOT / entry["migrations"]).is_dir()
    assert f"GET {entry['health']}" in _operations(_openapi(service))
    port = re.search(r'"PORT",\s*(\d+)', _config_source(service)).group(1)
    assert entry["port_default"] == int(port)


@pytest.mark.parametrize("service", SERVICES)
def test_every_cross_seam_endpoint_exists_in_the_other_services_openapi(service):
    for call in SYSTEM["services"][service]["calls"]:
        assert call["service"] in SYSTEM["services"]
        assert call["url_env"] in SYSTEM["services"][service]["env"]
        missing = set(call["endpoints"]) - _operations(_openapi(call["service"]))
        assert missing == set(), f"{service} calls endpoints {call['service']} does not document"


def test_the_seam_in_the_code_calls_only_documented_endpoints():
    seam = (ROOT / "services/fairness/app/seam.py").read_text()
    called = set(re.findall(r'"(/internal/[a-z_]+)"', seam))
    documented = {call.split(" ", 1)[1] for call in SYSTEM["services"]["fairness"]["calls"][0]["endpoints"]}

    assert called == documented


def test_every_service_is_scaled_to_zero_with_one_replica_at_most():
    for service in SYSTEM["services"].values():
        assert service["azure"]["min_replicas"] == 0
        assert service["azure"]["max_replicas"] == 1


def test_azure_resources_carry_the_students_prefix():
    prefix = SYSTEM["prefix"]
    azure = SYSTEM["azure"]

    assert azure["sql_server"].startswith(prefix)
    assert azure["container_apps_environment"].startswith(prefix)
    for service in SYSTEM["services"].values():
        assert service["azure"]["container_app"].startswith(prefix)
        assert service["azure"]["sql_database"].startswith(prefix)
        assert service["azure"]["sql_database"].startswith(azure["sql_server"].removesuffix("-sql"))


def test_the_ui_calls_exactly_the_services_that_exist():
    assert set(SYSTEM["ui"]["calls"]) == set(SYSTEM["services"])
    assert (ROOT / SYSTEM["ui"]["path"] / "index.html").is_file()


@pytest.mark.parametrize("service", SERVICES)
def test_compose_only_sets_env_vars_the_service_documents(service):
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    set_in_compose = set(compose["services"][service]["environment"])

    assert set_in_compose - set(SYSTEM["services"][service]["env"]) == set()


def test_compose_runs_the_two_service_containers_and_a_stock_ui_image():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    built = {name for name, svc in compose["services"].items() if "build" in svc}

    assert built == set(SYSTEM["services"])
    assert "build" not in compose["services"]["ui"]
