"""Запреты контейнерного окружения (ЛР4, п. 13) — шаг make container-lint.

Проверяет Dockerfile, .dockerignore и итоговую конфигурацию Compose
(`docker compose config --format json`) на запрещённое:

  1. тег latest или образ без тега (FROM и image:);
  2. запуск от root (USER в Dockerfile, user: в Compose, privileged, network_mode: host);
  3. секреты в образе (ENV/ARG с паролями и токенами в Dockerfile, build-args,
     .env не исключён из контекста сборки);
  4. отключённый healthcheck (HEALTHCHECK NONE, disable: true, test: NONE)
     и долгоживущие сервисы без healthcheck;
  5. публикация лишних портов (разрешено только ALLOWED_PORTS).

Изменение разрешённых значений ниже — правка критического файла приёмки.

    python -m scripts.container_policy reports/compose.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# сервис → разрешённые опубликованные порты (target внутри контейнера)
ALLOWED_PORTS: dict[str, set[int]] = {"nginx": {8080}}
# разовые задачи: завершаются сами, healthcheck для них не обязателен
ONE_SHOT_SERVICES = {"migrate"}
SECRET_NAME_RE = re.compile(r"PASSW|SECRET|TOKEN|PRIVATE|API_?KEY|AUTH_USERS|CREDENTIAL", re.I)
ROOT_USERS = {"", "root", "0"}


def image_ref_error(image: str) -> str | None:
    """Ошибка, если образ без тега, с тегом latest. Digest (@sha256:) допускается."""
    if "@sha256:" in image:
        return None
    name, _, tag = image.rpartition(":")
    if not name or "/" in tag:
        return f"образ без тега: {image}"
    if tag == "latest":
        return f"тег latest запрещён: {image}"
    return None


def _user_is_root(user: str) -> bool:
    return user.split(":", 1)[0].strip() in ROOT_USERS


def check_dockerfile(text: str) -> list[str]:
    errors: list[str] = []
    args: dict[str, str] = {}
    stages: set[str] = set()
    last_user = ""
    healthcheck = None
    for raw in text.replace("\\\n", " ").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        instr, _, rest = line.partition(" ")
        instr, rest = instr.upper(), rest.strip()
        if instr == "ARG":
            name, _, value = rest.partition("=")
            args[name.strip()] = value.strip()
            if value and SECRET_NAME_RE.search(name):
                errors.append(f"Dockerfile: секрет в ARG {name}")
        elif instr == "FROM":
            parts = rest.split()
            image = re.sub(r"\$\{?(\w+)\}?", lambda m: args.get(m.group(1), ""), parts[0])
            if len(parts) >= 3 and parts[1].upper() == "AS":
                stages.add(parts[2])
            if image not in stages and (err := image_ref_error(image)):
                errors.append(f"Dockerfile: {err}")
            last_user = ""
        elif instr == "USER":
            last_user = rest
        elif instr == "HEALTHCHECK":
            healthcheck = rest
        elif instr == "ENV":
            for name in re.findall(r"(\w+)=", rest) or rest.split()[:1]:
                if SECRET_NAME_RE.search(name):
                    errors.append(f"Dockerfile: секрет в ENV {name}")
    if _user_is_root(last_user):
        errors.append("Dockerfile: итоговый образ запускается от root (нет USER или USER root)")
    if healthcheck is None or healthcheck.upper().startswith("NONE"):
        errors.append("Dockerfile: нет HEALTHCHECK или он отключён")
    return errors


def check_dockerignore(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    deny_all = bool(lines) and lines[0] == "*"
    excludes_env = deny_all or any(ln in (".env", "**/.env", "*.env") for ln in lines)
    reincluded = any(ln.startswith("!") and ".env" in ln for ln in lines)
    if not excludes_env or reincluded:
        return [".dockerignore: файл .env может попасть в контекст сборки"]
    return []


def _healthcheck_disabled(hc: dict) -> bool:
    test = hc.get("test") or []
    return bool(hc.get("disable")) or (bool(test) and str(test[0]).upper() == "NONE")


def check_service(name: str, svc: dict) -> list[str]:
    errors: list[str] = []
    image = svc.get("image")
    if not image:
        errors.append(f"{name}: не задан image с явным тегом")
    elif err := image_ref_error(image):
        errors.append(f"{name}: {err}")
    if "user" in svc and _user_is_root(str(svc["user"])):
        errors.append(f"{name}: запуск от root (user: {svc['user']})")
    if svc.get("privileged"):
        errors.append(f"{name}: privileged запрещён")
    if svc.get("network_mode") == "host":
        errors.append(f"{name}: network_mode host запрещён")
    hc = svc.get("healthcheck")
    if hc and _healthcheck_disabled(hc):
        errors.append(f"{name}: healthcheck отключён")
    elif not hc and name not in ONE_SHOT_SERVICES:
        errors.append(f"{name}: нет healthcheck")
    allowed = ALLOWED_PORTS.get(name, set())
    for port in svc.get("ports") or []:
        target = int(port.get("target", 0)) if isinstance(port, dict) else int(str(port))
        if target not in allowed:
            errors.append(f"{name}: публикация порта {target} запрещена")
    for arg in (svc.get("build") or {}).get("args") or {}:
        if SECRET_NAME_RE.search(arg):
            errors.append(f"{name}: секрет в build-аргументе {arg}")
    return errors


def check_compose(config: dict) -> list[str]:
    errors: list[str] = []
    for name, svc in sorted((config.get("services") or {}).items()):
        errors += check_service(name, svc)
    return errors


def run(compose_json: Path, root: Path = ROOT) -> list[str]:
    errors = check_dockerfile((root / "Dockerfile").read_text(encoding="utf-8"))
    errors += check_dockerignore((root / ".dockerignore").read_text(encoding="utf-8"))
    errors += check_compose(json.loads(compose_json.read_text(encoding="utf-8")))
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("использование: python -m scripts.container_policy <compose.json>")
        return 2
    errors = run(Path(argv[1]))
    if errors:
        print("Нарушения запретов контейнерного окружения:")
        for err in errors:
            print(f"  ✗ {err}")
        return 1
    print("✔ Контейнерное окружение: без latest, root, секретов в образе, отключённых healthcheck")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
