"""Единая точка отправки `gitcmd` (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 3): белый список проекта не `operator`, журнал «ветка отправлена», опции `policy.push_options`.

Планка задачи — разовая; здесь — долгоживущий минимум свойств точки
отправки. Клон проекта — настоящий git-репозиторий по адресу
`repo_context.clone_path`; `subprocess.run`/`Popen` подменены шпионом:
отправка (`push`) записывается и не исполняется, прочие git-вызовы идут к
настоящему git.
"""
import subprocess
from pathlib import Path

import pytest

from orchestrator import alerts, config, gitcmd, idgen, repo_context, store, targets

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen


class Spy:
    def __init__(self):
        self.pushes = []

    @staticmethod
    def is_push(argv) -> bool:
        return isinstance(argv, list) and "push" in argv and argv[0] == "git"

    def run(self, argv, *args, **kwargs):
        if self.is_push(argv):
            self.pushes.append(list(argv))
            empty = "" if kwargs.get("text") else b""
            return subprocess.CompletedProcess(argv, 0, empty, empty)
        return REAL_RUN(argv, *args, **kwargs)

    def popen(self, argv, *args, **kwargs):
        if self.is_push(argv):
            self.pushes.append(list(argv))
            raise OSError("отправка процессом Popen не исполняется")
        return REAL_POPEN(argv, *args, **kwargs)


@pytest.fixture
def spy(initialized_tmp_root, monkeypatch):
    monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    s = Spy()
    monkeypatch.setattr(subprocess, "run", s.run)
    monkeypatch.setattr(subprocess, "Popen", s.popen)
    return s


def git_in(repo: Path, *args: str) -> str:
    return REAL_RUN(["git", *args], cwd=repo, check=True, capture_output=True,
                    text=True).stdout.strip()


def project(name: str, gate: str, policy: str = "") -> Path:
    """Запись проекта в локальном слое и его клон с веткой `feature/x`."""
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(
        f"targets:\n  {name}:\n"
        f"    description:\n      base: {config.MAIN_BRANCH}\n"
        f"      test_profile:\n        command: [python3, -m, pytest]\n"
        f"        long_lived_dir: tests\n"
        f"        long_lived_name: test_<id>_<name>.py\n"
        f"    policy:\n      no_paths: []\n      project_skills: []\n"
        f"      merge_gate: {gate}\n"
        f"      weakening_scope: [tests/**/*.py]\n"
        f"      mutation_claim_scope: [tests/test_*.py]\n{policy}"
        f"    machine:\n      forge: github\n"
        f"      url: https://localhost/team/{name}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")
    assert targets.target(name)["merge_gate"] == gate
    clone = repo_context.clone_path(name)
    clone.mkdir(parents=True)
    git_in(clone, "init", "-q", "-b", config.MAIN_BRANCH)
    git_in(clone, "config", "user.email", "artel@example.invalid")
    git_in(clone, "config", "user.name", "artel tests")
    git_in(clone, "commit", "-q", "--allow-empty", "-m", "init")
    git_in(clone, "remote", "add", "origin", f"https://localhost/team/{name}")
    git_in(clone, "branch", "feature/x")
    return clone


def task(name: str, branch: str = "feature/x", state: str = "in_dev") -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача", state, branch, name,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def sent(task_id: str) -> list:
    return [r["detail"] for r in store.task_steps(store.db(), task_id)
            if r["action"] == gitcmd.PUSH_SENT_ACTION]


def test_whitelist_refuses_base_push_with_alert(spy):
    """Проект `target-human`: отправка в `main` без своей задачи — отказ до процесса и алерт `incident`.

    Ловит мутацию: белый список не включается для `merge_gate`, отличного
    от `operator` (`targets.push_whitelisted` всегда False), — отправка в
    `main` дойдёт до процесса; отказ без контекста не заводит алерт с
    источником `branch_push_whitelist`.
    """
    clone = project("qhuman", "target-human")
    res = gitcmd.in_repo(clone, "push", "origin", config.MAIN_BRANCH)
    assert res.returncode != 0 and res.stderr, res
    assert spy.pushes == []
    sources = [r["source"] for r in alerts.open_alerts(store.db(), "incident")]
    assert gitcmd.PUSH_WHITELIST_SOURCE in sources


def test_whitelist_lease_checked_against_last_sent_sha(spy):
    """Проект `target-human`: перезапись `--force-with-lease=<ветка>:<sha>` проходит только с sha последней записи «ветка отправлена».

    Ловит мутацию: sha аренды не сверяется с журналом — чужой sha пройдёт;
    запись «ветка отправлена» не пишется после успешной отправки — верный
    sha будет отказан.
    """
    clone = project("qlease", "target-human")
    own = task("qlease")
    sha = git_in(clone, "rev-parse", "feature/x")
    assert gitcmd.in_repo(clone, "push", "origin", "feature/x").returncode == 0
    assert any(d.startswith(sha) for d in sent(own)), sent(own)
    wrong = gitcmd.in_repo(clone, "push", f"--force-with-lease=feature/x:{'0' * 40}",
                           "origin", "feature/x")
    assert wrong.returncode != 0
    pushes = len(spy.pushes)
    right = gitcmd.in_repo(clone, "push", f"--force-with-lease=feature/x:{sha}",
                           "origin", "feature/x")
    assert right.returncode == 0, right.stderr
    assert len(spy.pushes) == pushes + 1
    assert "push.pushOption=" in spy.pushes[-1]


def test_operator_push_gets_options_and_record(spy):
    """Проект `operator` с `push_options: [A=1]`: ветка задачи уходит с `-o A=1` и записью «ветка отправлена»; ссылка документов — без `-o`, белого списка нет.

    Ловит мутацию: опции добавляются и к `refs/artifacts/*`; запись пишется
    только под белым списком; к отправке проекта `operator` добавлен сброс
    `-c push.pushOption=`.
    """
    clone = project("qoper", "operator", "      push_options: [A=1]\n")
    own = task("qoper")
    assert gitcmd.in_repo(clone, "push", "origin", "feature/x").returncode == 0
    argv = spy.pushes[-1]
    assert argv[argv.index("-o") + 1] == "A=1"
    assert "push.pushOption=" not in argv
    assert sent(own)
    assert gitcmd.in_repo(clone, "push", "origin",
                          f"refs/artifacts/{own}").returncode == 0
    assert "-o" not in spy.pushes[-1]
    assert gitcmd.in_repo(clone, "push", "origin", config.MAIN_BRANCH).returncode == 0
