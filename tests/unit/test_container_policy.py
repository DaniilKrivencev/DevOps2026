"""Запреты контейнерного окружения (ЛР4, п. 13): make container-lint."""

import json

import pytest

from scripts import container_policy as cp

pytestmark = pytest.mark.unit

GOOD_DOCKERFILE = """
ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm
FROM ${PYTHON_IMAGE} AS builder
RUN pip install x
FROM ${PYTHON_IMAGE} AS runtime
ARG APP_VERSION=1.0
ENV PATH=/opt/venv/bin:$PATH \\
    APP_ENV=production
USER 10001:10001
HEALTHCHECK --interval=10s CMD ["python", "-m", "scripts.healthcheck"]
CMD ["uvicorn"]
"""


def good_service(**extra):
    svc = {"image": "cityduma:0.4.0-abc", "healthcheck": {"test": ["CMD", "true"]}}
    svc.update(extra)
    return svc


@pytest.mark.parametrize(
    ("image", "error"),
    [
        ("postgres:16.6-alpine", None),
        ("ghcr.io/org/app:sha-1a2b3c", None),
        ("localhost:5000/app:1.0", None),
        ("app@sha256:abcd", None),
        ("app:latest", "тег latest запрещён: app:latest"),
        ("app", "образ без тега: app"),
        ("localhost:5000/app", "образ без тега: localhost:5000/app"),
    ],
)
def test_image_ref(image, error):
    assert cp.image_ref_error(image) == error


def test_real_project_files_pass(tmp_path):
    compose = tmp_path / "compose.json"
    compose.write_text(json.dumps({"services": {"nginx": good_service(ports=[{"target": 8080}])}}))
    assert cp.run(compose) == []


def test_good_dockerfile():
    assert cp.check_dockerfile(GOOD_DOCKERFILE) == []


@pytest.mark.parametrize(
    ("replace", "by", "error"),
    [
        ("python:3.12.8-slim-bookworm", "python:latest", "тег latest"),
        ("python:3.12.8-slim-bookworm", "python", "образ без тега"),
        ("USER 10001:10001", "USER root", "от root"),
        ("USER 10001:10001", "USER 0", "от root"),
        ("USER 10001:10001", "", "от root"),
        (
            'HEALTHCHECK --interval=10s CMD ["python", "-m", "scripts.healthcheck"]',
            "HEALTHCHECK NONE",
            "HEALTHCHECK",
        ),
        (
            'HEALTHCHECK --interval=10s CMD ["python", "-m", "scripts.healthcheck"]',
            "",
            "HEALTHCHECK",
        ),
        ("APP_ENV=production", "DB_PASSWORD=qwerty", "секрет в ENV DB_PASSWORD"),
        ("ARG APP_VERSION=1.0", "ARG API_TOKEN=abc", "секрет в ARG API_TOKEN"),
    ],
)
def test_bad_dockerfile(replace, by, error):
    errors = cp.check_dockerfile(GOOD_DOCKERFILE.replace(replace, by))
    assert any(error in e for e in errors), errors


def test_user_reset_in_new_stage():
    text = "FROM a:1 AS b\nUSER app\nFROM a:1\nHEALTHCHECK CMD true\n"
    assert any("от root" in e for e in cp.check_dockerfile(text))


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("*\n!app/\n", True),
        ("# comment\n.env\nfoo\n", True),
        ("*\n!app/\n!.env\n", False),
        ("app/tmp\n", False),
        ("", False),
    ],
)
def test_dockerignore(text, ok):
    assert (cp.check_dockerignore(text) == []) is ok


def test_compose_ok():
    config = {
        "services": {
            "app1": good_service(),
            "migrate": {"image": "cityduma:1.0"},
            "nginx": good_service(ports=[{"target": 8080, "published": "8080"}]),
        }
    }
    assert cp.check_compose(config) == []


@pytest.mark.parametrize(
    ("name", "svc", "error"),
    [
        ("app1", good_service(image="cityduma:latest"), "тег latest"),
        ("app1", {"healthcheck": {"test": ["CMD", "x"]}}, "не задан image"),
        ("app1", good_service(user="root"), "от root"),
        ("app1", good_service(user="0:0"), "от root"),
        ("app1", good_service(privileged=True), "privileged"),
        ("app1", good_service(network_mode="host"), "network_mode"),
        ("app1", good_service(healthcheck={"disable": True}), "healthcheck отключён"),
        ("app1", good_service(healthcheck={"test": ["NONE"]}), "healthcheck отключён"),
        ("app1", {"image": "x:1"}, "нет healthcheck"),
        ("db", good_service(ports=[{"target": 5432}]), "порта 5432"),
        ("nginx", good_service(ports=[{"target": 8080}, {"target": 22}]), "порта 22"),
        ("app1", good_service(ports=["8000"]), "порта 8000"),
        ("app1", good_service(build={"args": {"DB_PASSWORD": "x"}}), "build-аргументе"),
    ],
)
def test_compose_violations(name, svc, error):
    errors = cp.check_compose({"services": {name: svc}})
    assert any(error in e for e in errors), errors


def test_main(tmp_path, capsys):
    assert cp.main(["x"]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"services": {"db": {"image": "postgres:latest"}}}))
    assert cp.main(["x", str(bad)]) == 1
    assert "тег latest" in capsys.readouterr().out
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"services": {}}))
    assert cp.main(["x", str(good)]) == 0
