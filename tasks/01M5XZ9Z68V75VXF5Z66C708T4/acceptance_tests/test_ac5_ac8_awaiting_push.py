"""Единая точка отправки `gitcmd`: отправка ветки задачи в `awaiting_human` отказана до вызова git в любой форме — обычной, явным refspec, `--delete`, `:<ветка>`.

Группа: разовый
Красен до реализации: точка отправки не смотрит на состояние `awaiting_human` — обычная отправка и явный refspec доходят до процесса git, а `--delete`/`:<ветка>` у проекта `operator` проходят, у `target-human` отказываются причиной белого списка, не называющей ожидание людей проекта.

Клон проекта — настоящий git-репозиторий по адресу
`repo_context.clone_path`; `subprocess.run`/`Popen` подменены шпионом:
отправка (`push`) записывается и не исполняется, прочие git-вызовы идут к
настоящему git (приём `tests/test_gitcmd_push_point.py`). Вход —
`gitcmd.in_repo` (клон проекта), он же ведёт в `gitcmd.git`. Проект —
с гейтом `operator` и `target-human` (отказ не зависит от гейта мержа);
имя проекта и ветки задачи порождаются модулем `random` при каждом
запуске, зерно печатается и входит в текст провала.

Группа разовая не по природе свойства, а по правилу долгоживущих файлов:
им запрещены импорт `orchestrator.gitcmd` и вызов git через `subprocess`
(`scripts/guard.py`, признак «git-история — факт задачи»), а предмет
критерия — сама точка отправки `gitcmd` и вызовы git.
"""
import random
import subprocess
from pathlib import Path

import pytest

from orchestrator import config, gitcmd, idgen, repo_context, store, targets

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
LETTERS = "abcdefghijkmnopqrstuvwxyz"
STATE = "awaiting_human"
GATES = ["operator", "target-human"]


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
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


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


def scenario(seed: int, gate: str) -> dict:
    """Проект с гейтом `gate`, его клон с веткой задачи и задача в
    `awaiting_human` на этой ветке."""
    rng = random.Random(seed)
    name = "p" + "".join(rng.choice(LETTERS) for _ in range(7))
    branch = f"task/{''.join(rng.choice(LETTERS) for _ in range(6))}-x"
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
        f"      mutation_claim_scope: [tests/test_*.py]\n"
        f"    machine:\n      forge: github\n"
        f"      url: https://localhost/team/{name}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")
    clone = repo_context.clone_path(name)
    clone.mkdir(parents=True)
    git_in(clone, "init", "-q", "-b", config.MAIN_BRANCH)
    git_in(clone, "config", "user.email", "artel@example.invalid")
    git_in(clone, "config", "user.name", "artel tests")
    git_in(clone, "commit", "-q", "--allow-empty", "-m", "init")
    git_in(clone, "remote", "add", "origin", f"https://localhost/team/{name}")
    git_in(clone, "branch", branch)
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача", "in_dev", branch, name,
                      config.DEFAULT_BUDGET_USD)
    set_state(task_id, STATE)
    return {"name": name, "branch": branch, "clone": clone, "task": task_id,
            "note": f"зерно: {seed}; проект {name} ({gate}); ветка {branch}"}


def set_state(task_id: str, state: str) -> None:
    conn = store.db()
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()


def assert_refused_for_awaiting(res, spy: Spy, note: str) -> None:
    """Отказ до процесса git с причиной, называющей ожидание людей проекта."""
    assert res.returncode != 0, f"{note}: отправка не отказана: {res}"
    reason = res.stderr if isinstance(res.stderr, str) else res.stderr.decode()
    assert STATE in reason or "ждёт людей проекта" in reason, (
        f"{note}: причина отказа не называет ожидание людей проекта: {reason!r}")
    assert spy.pushes == [], f"{note}: git увидел отправку: {spy.pushes}"


@pytest.mark.parametrize("gate", GATES)
def test_ac5_plain_push_of_awaiting_branch_refused(spy, seed, gate):
    """Обычная отправка ветки задачи в `awaiting_human` отказана до вызова git; та же отправка в `in_dev` проходит.

    Сценарий: клон проекта, задача на случайной ветке в `awaiting_human`;
    `gitcmd.in_repo(клон, "push", "origin", <ветка>)` и тот же вызов с
    `-u` возвращают отказ, причина называет `awaiting_human` (или «ждёт
    людей проекта»), шпион не видит ни одного `git push`. Контроль: та же
    задача в `in_dev` — `push origin <ветка>` доходит до шпиона.

    Ловит мутацию: отказа по состоянию нет — отправка доходит до git;
    проверка состояния стоит после запуска процесса или только в
    `gitcmd.git` без входа `-C` клона проекта; состояние сверяется с
    перечнем, где `awaiting_human` нет.
    """
    sc = scenario(seed, gate)
    for args in (("push", "origin", sc["branch"]),
                 ("push", "-u", "origin", sc["branch"])):
        res = gitcmd.in_repo(sc["clone"], *args)
        assert_refused_for_awaiting(res, spy, f"{sc['note']}; {args}")
    set_state(sc["task"], "in_dev")
    res = gitcmd.in_repo(sc["clone"], "push", "origin", sc["branch"])
    assert res.returncode == 0, f"{sc['note']}: контроль в in_dev отказан: {res}"
    assert spy.pushes, f"{sc['note']}: контроль в in_dev не дошёл до git"


@pytest.mark.parametrize("gate", GATES)
def test_ac6_explicit_refspec_push_of_awaiting_branch_refused(spy, seed, gate):
    """Отправка ветки задачи в `awaiting_human` явным refspec отказана до вызова git.

    Сценарий: задача на случайной ветке в `awaiting_human`; отправки
    `HEAD:<ветка>`, `<ветка>:refs/heads/<ветка>`, `refs/heads/<ветка>` и
    `<sha>:<ветка>` через `gitcmd.in_repo` клона возвращают отказ с
    причиной, называющей ожидание людей проекта; шпион не видит `git push`.

    Ловит мутацию: состояние проверяется только у refspec вида `<ветка>`
    (имя без `:`) — форма `src:dst` или полное `refs/heads/<ветка>` уйдёт
    в git.
    """
    sc = scenario(seed, gate)
    sha = git_in(sc["clone"], "rev-parse", sc["branch"])
    branch = sc["branch"]
    for spec in (f"HEAD:{branch}", f"{branch}:refs/heads/{branch}",
                 f"refs/heads/{branch}", f"{sha}:{branch}"):
        res = gitcmd.in_repo(sc["clone"], "push", "origin", spec)
        assert_refused_for_awaiting(res, spy, f"{sc['note']}; refspec {spec}")


@pytest.mark.parametrize("gate", GATES)
def test_ac7_delete_push_of_awaiting_branch_refused(spy, seed, gate):
    """`push --delete` ветки задачи в `awaiting_human` отказан до вызова git с причиной об ожидании людей проекта.

    Сценарий: задача на случайной ветке в `awaiting_human`;
    `gitcmd.in_repo(клон, "push", "origin", "--delete", <ветка>)` и та же
    отправка с `--delete` перед `origin` возвращают отказ, причина
    называет `awaiting_human` (или «ждёт людей проекта»); шпион не видит
    `git push`.

    Ловит мутацию: проверка состояния стоит рядом с записью «ветка
    отправлена» (`plan.sent`), за условием «не удаление» — `--delete`
    у проекта `operator` дойдёт до git, у `target-human` отказ даст белый
    список с иной причиной.
    """
    sc = scenario(seed, gate)
    for args in (("push", "origin", "--delete", sc["branch"]),
                 ("push", "--delete", "origin", sc["branch"])):
        res = gitcmd.in_repo(sc["clone"], *args)
        assert_refused_for_awaiting(res, spy, f"{sc['note']}; {args}")


@pytest.mark.parametrize("gate", GATES)
def test_ac8_colon_delete_push_of_awaiting_branch_refused(spy, seed, gate):
    """Удаление `:<ветка>` ветки задачи в `awaiting_human` отказано до вызова git с причиной об ожидании людей проекта.

    Сценарий: задача на случайной ветке в `awaiting_human`;
    `gitcmd.in_repo(клон, "push", "origin", ":<ветка>")` и форма
    `:refs/heads/<ветка>` возвращают отказ с причиной, называющей
    ожидание людей проекта; шпион не видит `git push`.

    Ловит мутацию: состояние проверяется только у отправляемых веток
    (`branches` без `colon`) — удаление пустым источником не сверяется и
    у проекта `operator` уходит в git, у `target-human` отказ даёт белый
    список с иной причиной.
    """
    sc = scenario(seed, gate)
    for spec in (f":{sc['branch']}", f":refs/heads/{sc['branch']}"):
        res = gitcmd.in_repo(sc["clone"], "push", "origin", spec)
        assert_refused_for_awaiting(res, spy, f"{sc['note']}; refspec {spec}")
