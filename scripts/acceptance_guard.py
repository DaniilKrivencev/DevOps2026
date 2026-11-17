"""Защита критических файлов приёмки (ЛР5, п. 14–16) — этап CI guard.

Сравнивает текущий коммит с базой (целевая ветка запроса на слияние или
предыдущее состояние ветки) и:
  1. перечисляет изменённые критические файлы приёмки — они попадают в отчёт
     job'а и требуют одобрения владельца кода (CODEOWNERS + защита ветки);
  2. ОСТАНАВЛИВАЕТ pipeline, если количество тестов уменьшилось: удалить тест
     незаметно нельзя. Исключение — явное согласование: метка запроса на слияние
     `allow-test-removal` (переменная GUARD_ALLOW_TEST_REMOVAL=1), поставить
     которую может только сопровождающий.

Ослабление порогов и исключения анализаторов ловят check_policy.py и
container_policy.py, удаление шагов CI — ревью владельца .github/.

    python -m scripts.acceptance_guard <база> [<коммит>]
"""

from __future__ import annotations

import os
import re

# Обоснование nosec: вызывается только git со списком аргументов, без shell
import subprocess  # nosec B404
import sys

CRITICAL_PATTERNS = (
    "Makefile",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    ".gitleaks.toml",
    ".gitleaksignore",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.lock",
    "scripts/check_policy.py",
    "scripts/check_mutation.py",
    "scripts/container_policy.py",
    "scripts/container_check.sh",
    "scripts/acceptance_guard.py",
    "scripts/ci.sh",
    ".github/",
    "tests/",
    "alembic/versions/",
    "infra/ansible/roles/",
    "infra/ansible/inventories/",
    "infra/ansible/group_vars/",
    "infra/ansible/site.yml",
    "scripts/infra_policy.py",
)
TEST_DEF_RE = re.compile(r"^\s*(async\s+)?def\s+test_\w+", re.MULTILINE)
EMPTY_SHA = "0" * 40


def is_critical(path: str) -> bool:
    return any(
        path == pattern or (pattern.endswith("/") and path.startswith(pattern))
        for pattern in CRITICAL_PATTERNS
    )


def count_tests(sources: dict[str, str]) -> int:
    """Количество тестовых функций в файлах tests/**/test_*.py."""
    return sum(
        len(TEST_DEF_RE.findall(text))
        for path, text in sources.items()
        if path.startswith("tests/") and path.rsplit("/", 1)[-1].startswith("test_")
    )


def _git(*args: str) -> str:
    # Обоснование noqa/nosec: фиксированная команда git, список аргументов, без shell
    return subprocess.run(  # noqa: S603  # nosec B603 B607
        ["git", *args],  # noqa: S607 — git из PATH контейнера инструментов
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def collect_test_sources(rev: str) -> dict[str, str]:
    files = _git("ls-tree", "-r", "--name-only", rev, "--", "tests").split()
    return {f: _git("show", f"{rev}:{f}") for f in files if f.endswith(".py")}


def evaluate(
    changed: list[str], tests_before: int, tests_after: int, allow_removal: bool
) -> tuple[list[str], list[str]]:
    """→ (критические изменённые файлы, ошибки)."""
    critical = sorted(p for p in changed if is_critical(p))
    errors = []
    if tests_after < tests_before and not allow_removal:
        errors.append(
            f"количество тестов уменьшилось: было {tests_before}, стало {tests_after}. "
            "Удаление тестов требует явного согласования (метка allow-test-removal)."
        )
    return critical, errors


def write_summary(lines: list[str]) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else ""
    head = argv[2] if len(argv) > 2 else "HEAD"
    if not base or base == EMPTY_SHA:
        print("guard: нет базы для сравнения (новая ветка) — проверка пропущена")
        return 0
    base = _git("merge-base", base, head).strip() or base
    changed = _git("diff", "--name-only", base, head).split()
    before, after = count_tests(collect_test_sources(base)), count_tests(collect_test_sources(head))
    allow = os.getenv("GUARD_ALLOW_TEST_REMOVAL") == "1"
    critical, errors = evaluate(changed, before, after, allow)

    report = [f"### Критические файлы приёмки ({base[:12]}..{head})", ""]
    report += [f"- `{p}` — требуется одобрение CODEOWNERS" for p in critical] or ["- не изменялись"]
    report += ["", f"Тестов: было {before}, стало {after}"]
    print("\n".join(report))
    write_summary(report)
    for err in errors:
        print(f"✗ {err}")
    if errors:
        return 1
    print("✔ guard: тесты не удалены, изменения критических файлов перечислены")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
