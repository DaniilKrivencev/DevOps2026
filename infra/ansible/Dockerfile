# Управляющий узел Ansible в контейнере (ЛР7): одинаковые версии инструментов
# у всех участников и в CI, не нужно ставить Ansible в Windows.
ARG PYTHON_IMAGE=python:3.12.16-slim-trixie
FROM ${PYTHON_IMAGE}
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client git make \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt
ENV ANSIBLE_FORCE_COLOR=1 PYTHONUNBUFFERED=1
WORKDIR /repo/infra/ansible
ENTRYPOINT ["/repo/infra/ansible/run.sh"]
