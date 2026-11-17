"""Тесты самой политики (п. 14): нарушения действительно обнаруживаются."""

import sqlite3
from pathlib import Path

import pytest

from scripts import check_mutation, check_policy

pytestmark = pytest.mark.unit

SKIP_MARK = "@pytest.mark." + "skip"  # строка собрана, чтобы политика не сработала на этот файл


def test_skip_without_reason_detected():
    errors = check_policy.check_skips(Path("t.py"), [SKIP_MARK, "def test_x(): ..."])
    assert len(errors) == 1
    assert "без обоснования" in errors[0]


def test_skip_with_justification_allowed():
    lines = [SKIP_MARK + '(reason="обоснование: нет PostgreSQL")', "def test_x(): ..."]
    assert check_policy.check_skips(Path("t.py"), lines) == []


@pytest.mark.parametrize(
    "line",
    ["x = 1  # " + "noqa", "x = 1  # " + "noqa: F401", "import subprocess  # " + "nosec"],
)
def test_suppression_without_justification_detected(line):
    assert check_policy.check_suppressions(Path("m.py"), [line])


@pytest.mark.parametrize(
    "lines",
    [
        ["import app.models  # " + "noqa: F401 — регистрирует модели"],
        ["# Обоснование: без shell", "subprocess.run(cmd)  # " + "nosec B603"],
    ],
)
def test_suppression_with_justification_allowed(lines):
    assert check_policy.check_suppressions(Path("m.py"), lines) == []


def test_current_project_passes_policy(capsys):
    assert check_policy.main() == 0
    assert "Политика соблюдена" in capsys.readouterr().out


def test_lowered_coverage_threshold_detected(monkeypatch):
    monkeypatch.setattr(check_policy, "MIN_COVERAGE", 101)
    assert any("fail_under" in e for e in check_policy.check_pyproject())


def test_lowered_mutation_threshold_detected(monkeypatch):
    monkeypatch.setattr(check_policy, "MIN_MUTATION_SCORE", 1000)
    assert any("MUTATION_MIN" in e for e in check_policy.check_makefile())


def test_new_ruff_ignore_detected(monkeypatch):
    monkeypatch.setattr(check_policy, "ALLOWED_PER_FILE_IGNORES", {})
    monkeypatch.setattr(check_policy, "ALLOWED_RUFF_IGNORES", ["E501"])
    errors = check_policy.check_pyproject()
    assert any("ruff ignore" in e for e in errors)
    assert any("per-file-ignores" in e for e in errors)


def test_missing_verify_step_detected(monkeypatch):
    monkeypatch.setattr(check_policy, "REQUIRED_VERIFY_STEPS", ["nonexistent-step"])
    assert check_policy.check_makefile() == ["Makefile: verify не запускает шаг 'nonexistent-step'"]


def test_main_reports_violations(monkeypatch, capsys):
    monkeypatch.setattr(check_policy, "MIN_COVERAGE", 101)
    assert check_policy.main() == 1
    assert "Нарушения правил проекта" in capsys.readouterr().out


# ─── Порог мутационного тестирования ──────────────────────────────────────────


def _mutmut_cache(path: Path, killed: int, survived: int) -> None:
    with sqlite3.connect(path / ".mutmut-cache") as conn:
        conn.execute("CREATE TABLE Mutant (id INTEGER, status TEXT)")
        conn.executemany(
            "INSERT INTO Mutant VALUES (?, ?)",
            [(i, "ok_killed") for i in range(killed)]
            + [(i, "bad_survived") for i in range(survived)],
        )


def test_mutation_score_above_threshold(tmp_path, monkeypatch):
    _mutmut_cache(tmp_path, killed=9, survived=1)
    monkeypatch.chdir(tmp_path)
    assert check_mutation.main(["x", "90"]) == 0


def test_mutation_score_below_threshold(tmp_path, monkeypatch):
    _mutmut_cache(tmp_path, killed=8, survived=2)
    monkeypatch.chdir(tmp_path)
    assert check_mutation.main(["x", "90"]) == 1


def test_mutation_cache_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert check_mutation.main(["x"]) == 1
