"""Проверка правил проекта (п. 14 ЛР3), входит в make verify.

Запрещено без обоснования:
  1. пропускать тесты: pytest.mark.skip / skipif / xfail / pytest.skip(...)
     — допускается только если reason содержит слово «обоснование»;
  2. снижать пороги: покрытие (fail_under) ниже базового;
  3. добавлять исключения анализаторов: `# noqa` / `# nosec` без кода правила
     и без пояснения (в той же строке после кода или комментарием строкой выше),
     новые ignore/per-file-ignores в ruff, отключение тестов bandit (skips).

Базовые значения зафиксированы здесь; их изменение — правка критического
файла приёмки и требует ревью (см. CONTRIBUTING.md).
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_DIRS = ["app", "scripts", "tests", "alembic"]

MIN_COVERAGE = 85
ALLOWED_RUFF_IGNORES: list[str] = []
ALLOWED_PER_FILE_IGNORES = {
    "tests/**": ["S101"],
    "tests/conftest.py": ["S101", "E402"],
    "app/routers/*.py": ["B008"],
    "app/main.py": ["B008"],
}
REQUIRED_VERIFY_STEPS = ["policy", "lint", "sast", "test", "migrate-check"]

SKIP_RE = re.compile(r"pytest\.(mark\.(skip|skipif|xfail)\b|skip\(|xfail\()")
SUPPRESS_RE = re.compile(r"#\s*(noqa|nosec)\b(?P<rest>.*)$", re.IGNORECASE)
CODE_RE = re.compile(r"^\s*:?\s*[A-Z]+\d+")


def check_skips(path: Path, lines: list[str]) -> list[str]:
    errors = []
    for i, line in enumerate(lines):
        if path.name == "check_policy.py" or not SKIP_RE.search(line):
            continue
        window = " ".join(lines[i : i + 4]).lower()
        if "обоснование" not in window:
            errors.append(f"{path}:{i + 1}: пропуск теста без обоснования: {line.strip()}")
    return errors


def check_suppressions(path: Path, lines: list[str]) -> list[str]:
    errors = []
    for i, line in enumerate(lines):
        match = SUPPRESS_RE.search(line)
        if not match or path.name == "check_policy.py":
            continue
        rest = match.group("rest")
        if not CODE_RE.match(rest):
            errors.append(f"{path}:{i + 1}: {match.group(1)} без кода правила")
            continue
        explained_inline = bool(re.search(r"[—\-]\s*\w", rest.split("#")[0]))
        prev = lines[i - 1].strip().lower() if i else ""
        explained_above = prev.startswith("#") and "обоснование" in prev
        if not (explained_inline or explained_above):
            errors.append(f"{path}:{i + 1}: {match.group(1)} без обоснования")
    return errors


def check_pyproject() -> list[str]:
    errors = []
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tool = data.get("tool", {})
    coverage = tool.get("coverage", {}).get("report", {}).get("fail_under", 0)
    if coverage < MIN_COVERAGE:
        errors.append(f"pyproject.toml: fail_under={coverage} ниже порога {MIN_COVERAGE}")
    lint = tool.get("ruff", {}).get("lint", {})
    if lint.get("ignore", []) != ALLOWED_RUFF_IGNORES:
        errors.append(f"pyproject.toml: новые ruff ignore без ревью: {lint.get('ignore')}")
    if lint.get("per-file-ignores", {}) != ALLOWED_PER_FILE_IGNORES:
        errors.append("pyproject.toml: per-file-ignores изменены без обновления политики")
    if tool.get("bandit", {}).get("skips"):
        errors.append("pyproject.toml: отключены проверки bandit (skips)")
    addopts = tool.get("pytest", {}).get("ini_options", {}).get("addopts", "")
    if "--strict-markers" not in addopts:
        errors.append("pyproject.toml: удалён --strict-markers")
    return errors


def check_makefile() -> list[str]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^verify:.*?(?=^\S)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return ["Makefile: нет цели verify"]
    body = match.group(0)
    errors = [
        f"Makefile: verify не запускает шаг '{step}'"
        for step in REQUIRED_VERIFY_STEPS
        if not re.search(rf"\b{re.escape(step)}\b", body)
    ]
    return errors


def main() -> int:
    errors: list[str] = []
    for directory in CHECK_DIRS:
        for path in sorted((ROOT / directory).rglob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            rel = path.relative_to(ROOT)
            if directory == "tests":
                errors += check_skips(rel, lines)
            errors += check_suppressions(rel, lines)
    errors += check_pyproject()
    errors += check_makefile()
    if errors:
        print("Нарушения правил проекта:")
        for err in errors:
            print(f"  ✗ {err}")
        return 1
    print("✔ Политика соблюдена: без пропусков тестов, снижения порогов и исключений")
    return 0


if __name__ == "__main__":
    sys.exit(main())
