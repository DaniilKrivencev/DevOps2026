"""Требования к инфраструктурному коду (ЛР7): секреты, порты, права, shell-команды."""

import pytest

from scripts import infra_policy as ip

pytestmark = pytest.mark.unit

GOOD_TASKS = """---
- name: Пакеты
  ansible.builtin.apt:
    name: curl
- name: Пользователь
  ansible.builtin.user:
    name: app
    shell: /bin/bash
- name: Чтение правил
  # Обоснование: модуля нет, только чтение
  ansible.builtin.command: iptables -S INPUT
  changed_when: false
"""


def make_tree(
    tmp_path, tasks=GOOD_TASKS, vault="$ANSIBLE_VAULT;1.1;AES256\n3133\n", fw=None, extra=None
):
    (tmp_path / "roles/r/tasks").mkdir(parents=True)
    (tmp_path / "roles/r/tasks/main.yml").write_text(tasks)
    (tmp_path / "roles/firewall/defaults").mkdir(parents=True)
    (tmp_path / "roles/firewall/defaults/main.yml").write_text(
        fw
        or '---\nfirewall_tcp_services:\n  - {name: ssh, port: "{{ ssh_port }}", source: x}\n'
        '  - {name: http, port: "{{ http_port }}", source: 0.0.0.0/0}\n'
    )
    (tmp_path / "inv/group_vars").mkdir(parents=True)
    (tmp_path / "inv/group_vars/vault.yml").write_text(vault)
    (tmp_path / "inv/group_vars/main.yml").write_text(
        extra or '---\npostgres_password: "{{ vault_postgres_password }}"\npassword_lock: true\n'
    )
    return tmp_path


def test_good_tree(tmp_path):
    assert ip.run(make_tree(tmp_path)) == []


def test_real_project_passes():
    assert ip.run() == []


def test_unencrypted_vault(tmp_path):
    errors = ip.run(make_tree(tmp_path, vault="vault_postgres_password: qwerty\n"))
    assert any("не зашифрован" in e for e in errors)


@pytest.mark.parametrize(
    ("line", "bad"),
    [
        ("postgres_password: qwerty", True),
        ("api_token: abc", True),
        ('registry_password: ""', False),
        ('postgres_password: "{{ vault_postgres_password }}"', False),
        ("# postgres_password: qwerty", False),
        ("app_secretary_login: secretary", False),
        ("ansible_ssh_private_key_file: ~/.ssh/k", False),
    ],
)
def test_plain_secrets(tmp_path, line, bad):
    errors = ip.run(make_tree(tmp_path, extra=f"---\n{line}\n"))
    assert any("открытое значение" in e for e in errors) is bad


def test_extra_firewall_port(tmp_path):
    fw = "---\nfirewall_tcp_services:\n  - {name: db, port: 5432, source: 0.0.0.0/0}\n"
    errors = ip.run(make_tree(tmp_path, fw=fw))
    assert errors == ["firewall: лишний открытый порт 5432"]


def test_missing_firewall_defaults(tmp_path):
    tree = make_tree(tmp_path)
    (tree / "roles/firewall/defaults/main.yml").unlink()
    assert any("нет списка" in e for e in ip.run(tree))


@pytest.mark.parametrize(
    ("task", "error"),
    [
        ("- name: X\n  ansible.builtin.shell: rm -rf /tmp/x\n", "shell запрещён"),
        ("- name: X\n  shell: echo\n", "shell запрещён"),
        ("- name: X\n  ansible.builtin.command: ls\n  changed_when: false\n", "Обоснование"),
        ("- name: X\n  # Обоснование: нужно\n  ansible.builtin.command: ls\n", "changed_when"),
        (
            "- name: X\n  ansible.builtin.apt:\n    name: x\n  ignore_errors: true\n",
            "ignore_errors",
        ),
        ("- name: X\n  ansible.builtin.file:\n    path: /x\n    mode: '0777'\n", "запись для всех"),
        ('- name: X\n  ansible.builtin.copy:\n    dest: /x\n    mode: "0666"\n', "запись для всех"),
    ],
)
def test_bad_tasks(tmp_path, task, error):
    errors = ip.run(make_tree(tmp_path, tasks="---\n" + task))
    assert any(error in e for e in errors), errors


def test_main(tmp_path, capsys):
    assert ip.main(["x", str(make_tree(tmp_path))]) == 0
    bad = make_tree(tmp_path / "bad", vault="plain\n")
    assert ip.main(["x", str(bad)]) == 1
    assert "не зашифрован" in capsys.readouterr().out
