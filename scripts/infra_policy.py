"""Требования к инфраструктурному коду (ЛР7, п. 9 и 12) — шаг make infra-lint.

Проверяет каталог infra/ansible:
  1. секреты не хранятся открыто: каждый vault.yml зашифрован ansible-vault,
     а параметры с паролями/токенами в остальных файлах — только ссылки {{ vault_... }};
  2. нет лишних открытых портов: firewall открывает только разрешённые порты;
  3. минимальные права: нет прав 0777/0666 и т.п., нет ignore_errors;
  4. нет необъяснимых shell-команд: модуль shell запрещён, у каждой задачи
     command — комментарий «Обоснование:» и явный changed_when;
  5. повторяемость: задачи command без changed_when помечали бы «изменено» каждый
     запуск — это и проверяет п. 4 (фактическую повторяемость проверяет make infra-test).

    python -m scripts.infra_policy [каталог]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra" / "ansible"

ALLOWED_FIREWALL_PORTS = {"{{ ssh_port }}", "{{ http_port }}"}
SECRET_KEY_RE = re.compile(
    r"^\s*(\w*?(?:^|_)?(?:password|passwd|secret|token|private_key))\s*:\s*(.+)$", re.I
)
VAULT_REF_RE = re.compile(r"""^["']?\{\{\s*vault_\w+\s*\}\}["']?$""")
EMPTY_VALUES = {'""', "''", "[]", "{}"}
WIDE_MODE_RE = re.compile(r"""mode:\s*["']?0?([0-7]{3})["']?""")
TASK_START_RE = re.compile(r"^(\s*)- name:")


def check_vault_files(base: Path) -> list[str]:
    errors = []
    for path in sorted(base.rglob("vault.yml")):
        if not path.read_text(encoding="utf-8").startswith("$ANSIBLE_VAULT;"):
            errors.append(f"{path.relative_to(base)}: файл секретов не зашифрован ansible-vault")
    return errors


def check_plain_secrets(path: Path, lines: list[str], base: Path) -> list[str]:
    errors = []
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        match = SECRET_KEY_RE.match(line)
        if not match:
            continue
        value = match.group(2).split(" #")[0].strip()
        if value in EMPTY_VALUES or VAULT_REF_RE.match(value) or "{{" in value:
            continue
        errors.append(f"{path.relative_to(base)}:{i}: открытое значение секрета {match.group(1)}")
    return errors


def split_tasks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Делит YAML-файл задач на блоки «- name: …» (номер первой строки, строки блока)."""
    tasks: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 0
    indent = None
    for i, line in enumerate(lines, 1):
        m = TASK_START_RE.match(line)
        if m and (indent is None or len(m.group(1)) <= indent):
            if current:
                tasks.append((start, current))
            current, start, indent = [line], i, len(m.group(1))
        elif current:
            current.append(line)
    if current:
        tasks.append((start, current))
    return tasks


def module_used(block: list[str], module: str) -> bool:
    """Модуль задачи — ключ на уровне задачи (отступ «- name» + 2), не аргумент модуля."""
    indent = len(block[0]) - len(block[0].lstrip()) + 2
    pattern = re.compile(rf"^ {{{indent}}}(ansible\.builtin\.)?{module}:")
    return any(pattern.match(line) for line in block)


def check_tasks(path: Path, lines: list[str], base: Path) -> list[str]:
    errors = []
    rel = path.relative_to(base)
    for start, block in split_tasks(lines):
        text = "\n".join(block)
        if module_used(block, "shell"):
            errors.append(f"{rel}:{start}: модуль shell запрещён — используйте модули или command")
        if module_used(block, "command"):
            if "обоснование" not in text.lower():
                errors.append(f"{rel}:{start}: command без комментария «Обоснование:»")
            if "changed_when:" not in text:
                errors.append(f"{rel}:{start}: command без changed_when (ломает повторяемость)")
        if re.search(r"^\s*ignore_errors:\s*(true|yes)", text, re.M | re.I):
            errors.append(f"{rel}:{start}: ignore_errors скрывает сбои")
    return errors


def check_modes(path: Path, lines: list[str], base: Path) -> list[str]:
    errors = []
    for i, line in enumerate(lines, 1):
        m = WIDE_MODE_RE.search(line)
        if m and int(m.group(1)[-1]) & 2:
            errors.append(f"{path.relative_to(base)}:{i}: права {m.group(1)} — запись для всех")
    return errors


def check_firewall(base: Path) -> list[str]:
    path = base / "roles" / "firewall" / "defaults" / "main.yml"
    if not path.exists():
        return ["roles/firewall/defaults/main.yml: нет списка разрешённых портов"]
    ports = re.findall(r'port:\s*("[^"]*"|[^,}\s]+)', path.read_text(encoding="utf-8"))
    extra = {p.strip('"') for p in ports} - ALLOWED_FIREWALL_PORTS
    return [f"firewall: лишний открытый порт {p}" for p in sorted(extra)]


def run(base: Path = INFRA) -> list[str]:
    errors = check_vault_files(base) + check_firewall(base)
    for path in sorted(base.rglob("*.yml")):
        if path.name == "vault.yml" or "test" in path.relative_to(base).parts[:1]:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        errors += check_plain_secrets(path, lines, base)
        errors += check_modes(path, lines, base)
        if "tasks" in path.parts or "handlers" in path.parts:
            errors += check_tasks(path, lines, base)
    return errors


def main(argv: list[str]) -> int:
    base = Path(argv[1]) if len(argv) > 1 else INFRA
    errors = run(base)
    if errors:
        print("Нарушения требований к инфраструктурному коду:")
        for err in errors:
            print(f"  ✗ {err}")
        return 1
    print("✔ Инфраструктурный код: секреты зашифрованы, лишних портов нет, права минимальны,")
    print("  shell не используется, у каждой command есть обоснование и changed_when")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
