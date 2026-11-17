# =============================================================================
# ДЕМОНСТРАЦИОННЫЕ «неудачные выпуски» для защиты ЛР6 — НЕ для эксплуатации.
# Берут настоящий образ и вносят один дефект, который проявляется только на
# окружении (CI его не увидит, т.к. образ собирается вне pipeline):
#   --target broken-health    healthcheck контейнера всегда неуспешен
#   --target broken-scenario  приложение и /health работают, но отметка явки
#                             (основной сценарий) отвечает 500
# Сборка и публикация: make cd-demo-images BASE=<образ:тег>
# =============================================================================
ARG BASE=cityduma:local
ARG DEMO_COMMIT=de0000000000

FROM ${BASE} AS broken-health
ARG DEMO_COMMIT
ENV APP_COMMIT=${DEMO_COMMIT}
USER root
RUN printf 'import sys\nprint("demo: healthcheck сломан намеренно")\nsys.exit(1)\n' > /app/scripts/healthcheck.py
USER 10001:10001

FROM ${BASE} AS broken-scenario
ARG DEMO_COMMIT
ENV APP_COMMIT=${DEMO_COMMIT}
USER root
RUN python - <<'PY'
from pathlib import Path
p = Path("/app/app/routers/attendance.py")
s = p.read_text()
marker = "async def create_attendance("
head, tail = s.split(marker, 1)
sig, body = tail.split(":\n", 1)
p.write_text(head + marker + sig + ':\n    raise RuntimeError("demo: дефект основного сценария")\n' + body)
PY
USER 10001:10001
