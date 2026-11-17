"""Защита критических файлов приёмки (ЛР5): удаление тестов не проходит незаметно."""

import pytest

from scripts import acceptance_guard as ag

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("path", "critical"),
    [
        ("Makefile", True),
        ("tests/unit/test_x.py", True),
        (".github/workflows/ci.yml", True),
        ("alembic/versions/0005_x.py", True),
        ("scripts/check_policy.py", True),
        ("requirements.lock", True),
        ("infra/ansible/roles/ssh/templates/sshd-cityduma.conf.j2", True),
        ("infra/ansible/inventories/production/group_vars/cityduma/vault.yml", True),
        ("app/main.py", False),
        ("docs/README.md", False),
        ("scripts/seed.py", False),
        ("Makefile.bak", False),
    ],
)
def test_is_critical(path, critical):
    assert ag.is_critical(path) is critical


def test_count_tests():
    sources = {
        "tests/unit/test_a.py": "def test_one():\n    pass\n\nasync def test_two():\n    pass\n",
        "tests/unit/test_b.py": "class T:\n    def test_m(self): ...\ndef helper(): ...\n",
        "tests/conftest.py": "def test_not_counted(): ...\n",
        "app/test_x.py": "def test_outside(): ...\n",
    }
    assert ag.count_tests(sources) == 3


@pytest.mark.parametrize(
    ("before", "after", "allow", "errors"),
    [(10, 10, False, 0), (10, 12, False, 0), (10, 9, False, 1), (10, 9, True, 0)],
)
def test_evaluate(before, after, allow, errors):
    critical, errs = ag.evaluate(["app/x.py", "tests/t.py", "Makefile"], before, after, allow)
    assert critical == ["Makefile", "tests/t.py"]
    assert len(errs) == errors


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GUARD_ALLOW_TEST_REMOVAL", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    ag._git("init", "-q", "-b", "main")
    ag._git("config", "user.email", "t@t")
    ag._git("config", "user.name", "t")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_1(): ...\ndef test_2(): ...\n")
    ag._git("add", ".")
    ag._git("commit", "-q", "-m", "base")
    return tmp_path


def _commit(repo, content, msg):
    (repo / "tests" / "test_a.py").write_text(content)
    ag._git("commit", "-q", "-am", msg)


def test_main_detects_removed_test(repo, capsys, monkeypatch):
    summary = repo / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    _commit(repo, "def test_1(): ...\n", "remove test")
    assert ag.main(["guard", "HEAD~1"]) == 1
    out = capsys.readouterr().out
    assert "было 2, стало 1" in out
    assert "`tests/test_a.py`" in summary.read_text()


def test_main_allows_with_approval(repo, monkeypatch):
    monkeypatch.setenv("GUARD_ALLOW_TEST_REMOVAL", "1")
    _commit(repo, "def test_1(): ...\n", "remove test")
    assert ag.main(["guard", "HEAD~1"]) == 0


def test_main_ok_when_tests_added(repo, capsys):
    _commit(repo, "def test_1(): ...\ndef test_2(): ...\ndef test_3(): ...\n", "add")
    assert ag.main(["guard", "HEAD~1", "HEAD"]) == 0
    assert "✔ guard" in capsys.readouterr().out


@pytest.mark.parametrize("base", ["", "0" * 40])
def test_main_without_base(base, capsys):
    assert ag.main(["guard", base]) == 0
    assert "пропущена" in capsys.readouterr().out


def test_main_base_missing_after_history_rewrite(repo, capsys):
    assert ag.main(["guard", "1" * 40]) == 0
    assert "история переписана" in capsys.readouterr().out
