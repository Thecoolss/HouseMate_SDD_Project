"""openapi.yaml must describe exactly the routes the service registers."""

import re
from pathlib import Path

import yaml

SPEC = Path(__file__).resolve().parent.parent / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _documented():
    spec = yaml.safe_load(SPEC.read_text())
    return {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }


def _registered(app):
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            routes.add((method, path))
    return routes


def test_openapi_documents_every_registered_route_and_nothing_else(app):
    documented, registered = _documented(), _registered(app)

    assert registered - documented == set(), "routes missing from openapi.yaml"
    assert documented - registered == set(), "openapi.yaml documents routes that do not exist"


def test_every_protected_operation_declares_its_401(app):
    spec = yaml.safe_load(SPEC.read_text())
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in HTTP_METHODS and operation.get("security"):
                assert "401" in operation["responses"], f"{method.upper()} {path} has no 401"
