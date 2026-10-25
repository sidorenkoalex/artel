"""Одна отправка ссылки документов на команду пульта (SPEC
01M5RWNJEZT6YA2VP7JK6F3RXS; ADR-0021 п.3, поправка 25.10.2026): область
отложенной отправки в `lease.run_locked`, досылка при выходе и в точках
досрочной досылки, прежнее поведение вне команды (AC-1 — AC-13 и критерии
ANSWER-1).

Песочница — настоящий git (`origin_real_git`, `tests/fixtures.py`): пульт —
`root`, его bare-origin — `add_origin()`. Шпион стоит на `subprocess.run`,
которым `gitcmd` запускает каждый git; подкоманда берётся сквозь пары
`-C <клон>`. Отправка ссылки документов — `git push …` с аргументом
`refs/artifacts/<id>…`.
"""
import contextlib
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (artifact_branch, checkpoint, ci, config, doctor,
                          fsm, fsm_merge_gate, github_adapter, gitcmd, lease,
                          repo_context, runner, snapshot, store)
from tests.sandbox import (FakeProc, capture, make_project_repo, patch_sleep,
                           strip_dash_c)

TASK = "01UNITONEPUSHCMDTSKA"
TASK_B = "01UNITONEPUSHCMDTSKB"
SID = "sess-unit-one-push"
EXTERNAL = "unitonepushext"
PUSH_OK = "push артефактной ветки"
PUSH_FAILED = "push артефактной ветки FAILED"
STATES = ("in_dev", "verifying", "review", "merge_gate")


@contextlib.contextmanager
def git_spy(answer=None):
    """Подкоманды git (без `-C <путь>`) всех процессов внутри блока;
    `answer(argv, sub)` — подменный исход вызова (или исключение), `None` —
    настоящий git."""
    calls = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            sub = strip_dash_c(cmd[1:])
            calls.append(sub)
            if answer is not None:
                res = answer(list(cmd), sub)
                if res is not None:
                    return res
        return real_run(cmd, *args, **kwargs)

    with mock.patch.object(gitcmd.subprocess, "run", side_effect=spy):
        yield calls


def is_ref_push(sub, task_id: str = "") -> bool:
    if not sub or sub[0] != "push":
        return False
    prefix = artifact_branch.branch_name(task_id) if task_id else "refs/artifacts/"
    return any(str(arg).startswith(prefix) for arg in sub[1:])


def ref_pushes(calls, task_id: str = "") -> list:
    return [c for c in calls if is_ref_push(c, task_id)]


def commit(task_id: str, name: str, target: str | None = None) -> str:
    return artifact_branch.commit_files(
        task_id, {f"tasks/{task_id}/{name}": f"{name} {task_id}\n"},
        f"{task_id}: {name}", target=target)


def commit_fixed(task_id: str, name: str) -> str:
    """Коммит и его фиксация: следующий переход не примет голову за
    сдвинутую мимо пульта."""
    sha = commit(task_id, name)
    store.record_fixation(store.db(), task_id)
    return sha


def area(body, task_id: str = TASK):
    """`body()` телом команды пульта."""
    return lease.run_locked(store.db(), task_id, SID, lambda sid: body())


def step(index: int) -> None:
    store.set_state(store.db(), TASK, STATES[index + 1], "fsm",
                    expected_state=STATES[index], detail="юнит-сценарий")


def origin_head(sb, ref: str, bare=None) -> str:
    out = sb.git("ls-remote", str(bare or sb.bare), ref).split()
    return out[0] if out else ""


def local_head(sb, ref: str, repo=None) -> str:
    args = ("-C", str(repo)) if repo is not None else ()
    return sb.git(*args, "for-each-ref", "--format=%(objectname)", ref).strip()


def journal(task_id: str, action: str) -> list:
    return [r["detail"] for r in store.task_steps(store.db(), task_id)
            if r["action"] == action]


def add_task(task_id: str) -> str:
    store.insert_task(store.db(), task_id, "Юнит-задача", STATES[0],
                      f"task/{task_id.lower()}-x", config.DEFAULT_TARGET, 25.0)
    return commit(task_id, "SPEC.md")


@pytest.fixture
def env(origin_real_git):
    """Пульт с bare-origin; ссылка `TASK` совпадает с origin."""
    sb = origin_real_git
    sb.add_origin()
    sb.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    head0 = add_task(TASK)
    e = SimpleNamespace(sb=sb, ref=artifact_branch.branch_name(TASK),
                        head0=head0, branch=f"task/{TASK.lower()}-x")
    e.lags = lambda ref=None: (origin_head(sb, ref or e.ref),
                               local_head(sb, ref or e.ref))
    return e


def unsent(e) -> bool:
    origin, local = e.lags()
    return origin != local


# --- Область и выход из неё -------------------------------------------------


def test_area_sends_once_on_exit(env):
    """Три перехода и коммит в теле команды — ни одной отправки до выхода,
    ровно одна после него; голова в origin равна локальной (AC-1).

    Ловит мутацию: `run_locked` не открывает `deferred_sends` вокруг тела —
    в конце тела уже четыре отправки.
    Ловит мутацию: выход из области не досылает набор — после команды 0
    отправок, origin отстаёт.
    """
    seen = {}
    with git_spy() as calls:
        def body():
            step(0)
            commit_fixed(TASK, "PLAN.md")
            step(1)
            step(2)
            seen["тело"] = len(ref_pushes(calls, TASK))
        area(body)
        after = len(ref_pushes(calls, TASK))
    assert seen["тело"] == 0
    assert after == 1
    assert not unsent(env)


def test_outside_area_sends_each_commit_right_after_update_ref(env):
    """Вне команды — прежнее поведение: отправка сразу после `update-ref`,
    по одной на коммит, в том числе после уже закрытой области (AC-1, AC-13).

    Ловит мутацию: глубина области не уменьшается при выходе — коммит после
    команды попадает в набор и не отправляется.
    Ловит мутацию: отложенная отправка включена всегда — вне команды
    отправок нет.
    """
    area(lambda: commit(TASK, "A.md"))
    with git_spy() as calls:
        commit(TASK, "B.md")
        commit(TASK, "C.md")
    marks = [i for i, c in enumerate(calls) if c[:2] == ("update-ref", env.ref)]
    assert len(marks) == 2
    assert calls[marks[0] + 1:marks[0] + 3] == [
        ("remote", "get-url", "origin"),
        ("push", "-q", "origin", f"{env.ref}:{env.ref}")]
    assert len(ref_pushes(calls, TASK)) == 2
    assert not unsent(env)


def test_nested_area_exit_sends_whole_set(env):
    """Выход из вложенной области досылает весь набор, внешний выход лишней
    отправки не даёт (AC-2).

    Ловит мутацию: досылка только при выходе из самой внешней области —
    после вложенной 0 отправок.
    Ловит мутацию: пара не убирается из набора при досылке — выход внешней
    отправляет повторно.
    """
    seen = {}
    with git_spy() as calls:
        def outer():
            commit(TASK, "A.md")
            area(lambda: commit(TASK, "B.md"))
            seen["после вложенной"] = (len(ref_pushes(calls, TASK)),
                                       unsent(env))
            area(lambda: commit(TASK, "C.md"))
            seen["после второй"] = len(ref_pushes(calls, TASK))
        area(outer)
        total = len(ref_pushes(calls, TASK))
    assert seen["после вложенной"] == (1, False)
    assert seen["после второй"] == 2
    assert total == 2


@pytest.mark.parametrize("exc", [RuntimeError("тело"), SystemExit("отказ"),
                                 KeyboardInterrupt()])
def test_body_exception_still_sends_and_propagates(env, exc):
    """Тело бросило (в том числе `SystemExit`, `KeyboardInterrupt`) —
    досылка сделана, наружу тот же объект, lease снят (AC-3).

    Ловит мутацию: досылка после `yield` вне `finally` — при исключении
    тела коммит остаётся недосланным.
    """
    def body():
        commit(TASK, "PLAN.md")
        raise exc
    with git_spy() as calls, pytest.raises(type(exc)) as info:
        area(body)
    assert info.value is exc
    assert len(ref_pushes(calls, TASK)) == 1
    assert not unsent(env)
    assert store.lease_row(store.db(), TASK) is None


def _push_of(task_id: str):
    def answer(argv, sub):
        if sub[:1] == ("push",) and any(
                str(a).startswith(artifact_branch.branch_name(task_id) + ":")
                for a in sub):
            raise RuntimeError("досылка упала")
        return None
    return answer


def test_failing_send_during_body_exception_one_stderr_line(env, capsys):
    """Досылка бросила при летящем исключении тела: наружу исключение тела,
    в stderr ровно одна строка на бросившую досылку, вторая пара дослана
    (AC-3; ANSWER-1, решение 6б).

    Ловит мутацию: исключение досылки не перехвачено при летящем исключении
    тела — наружу выходит `RuntimeError` досылки.
    Ловит мутацию: строка в stderr не печатается или печатается трассой.
    """
    add_task(TASK_B)
    raised = ValueError("тело упало")

    def body():
        commit(TASK, "PLAN.md")
        commit(TASK_B, "PLAN.md")
        raise raised
    capsys.readouterr()
    with git_spy(_push_of(TASK)), pytest.raises(ValueError) as info:
        area(body)
    err = capsys.readouterr().err.splitlines()
    assert info.value is raised
    assert len(err) == 1 and "досылка упала" in err[0], err
    ref_b = artifact_branch.branch_name(TASK_B)
    assert origin_head(env.sb, ref_b) == local_head(env.sb, ref_b)


def test_failing_send_on_normal_exit_raises_after_other_pairs(env):
    """Нормальный выход тела, досылка первой из двух пар бросила: вторая
    пара отправлена, затем наружу исключение досылки (ANSWER-1, решение 6а).

    Ловит мутацию: исключение досылки при нормальном выходе проглатывается.
    Ловит мутацию: исключение досылки обрывает цикл — вторая пара не дослана.
    """
    add_task(TASK_B)
    with git_spy(_push_of(TASK)), pytest.raises(RuntimeError, match="досылка"):
        area(lambda: (commit(TASK, "PLAN.md"), commit(TASK_B, "PLAN.md")))
    ref_b = artifact_branch.branch_name(TASK_B)
    assert origin_head(env.sb, ref_b) == local_head(env.sb, ref_b)
    assert store.lease_row(store.db(), TASK) is None


def test_empty_set_exit_no_git_no_db(env):
    """Пустой набор при выходе — ни вызова git, ни открытия соединения БД
    (AC-9; ANSWER-1, решение 6в: подменена `store.db`).

    Ловит мутацию: выход из области проверяет origin или журнал до
    проверки пустоты набора — в шпионе вызов git или `store.db` вызвана.
    """
    with git_spy() as calls, \
            mock.patch.object(store, "db", side_effect=AssertionError("БД")) as db:
        with artifact_branch.deferred_sends():
            pass
        assert artifact_branch.send_pending() == 0
    assert calls == []
    db.assert_not_called()
    with git_spy() as calls:
        assert area(lambda: "готово") == "готово"
    assert calls == []


def test_no_origin_area_silent(env):
    """Без origin коммиты в команде — ни отправки, ни записи журнала, ни
    исключения (AC-9).

    Ловит мутацию: досылка зовёт `artifact_branch.push` — пишется отказ
    «нет origin».
    """
    env.sb.git("remote", "remove", "origin")
    before = (journal(TASK, PUSH_OK), journal(TASK, PUSH_FAILED))
    def body():
        commit(TASK, "A.md")
        commit(TASK, "B.md")
        return "ок"
    with git_spy() as calls:
        result = area(body)
    assert result == "ок"
    assert ref_pushes(calls) == []
    assert (journal(TASK, PUSH_OK), journal(TASK, PUSH_FAILED)) == before


# --- Журнал досылки -----------------------------------------------------------


def _reject(sb, on: bool) -> None:
    hook = Path(sb.bare) / "hooks" / "pre-receive"
    if not on:
        hook.unlink()
        return
    hook.write_text("#!/bin/sh\nwhile read o n r; do case \"$r\" in "
                    "refs/artifacts/*) exit 1;; esac; done\nexit 0\n",
                    encoding="utf-8")
    hook.chmod(0o755)


def test_rejected_origin_one_failure_per_command_then_success(env):
    """origin отвергает запись: три коммита в команде — одна запись отказа
    прежнего текста; следующая команда — одна запись успеха (AC-8).

    Ловит мутацию: коммит в команде отправляется сразу — три записи отказа.
    Ловит мутацию: досылка без правила `_last_send_failed` — успеха после
    отказа в журнале нет.
    """
    _reject(env.sb, True)
    failed0 = len(journal(TASK, PUSH_FAILED))
    area(lambda: [commit(TASK, n) for n in ("A.md", "B.md", "C.md")])
    failed = journal(TASK, PUSH_FAILED)[failed0:]
    assert len(failed) == 1
    assert failed[0].startswith(artifact_branch.PUSH_REASON_NON_FAST_FORWARD)
    assert failed[0].endswith("— свести merge-коммитом")
    _reject(env.sb, False)
    ok0 = len(journal(TASK, PUSH_OK))
    area(lambda: commit(TASK, "D.md"))
    assert journal(TASK, PUSH_OK)[ok0:] == [
        f"push артефактной ветки {env.ref} — успех"]
    assert not unsent(env)


def test_server_5xx_on_send_retried_attempts_two(env):
    """5xx на первой попытке досылки — повтор и запись «(попыток 2)» (AC-8).

    Ловит мутацию: досылка не через `_send`/`_attempt_push` с повтором —
    одна попытка и запись отказа.
    """
    state = {"first": True}

    def answer(argv, sub):
        if is_ref_push(sub, TASK) and state["first"]:
            state["first"] = False
            return subprocess.CompletedProcess(
                argv, 1, "", "The requested URL returned error: 500")
        return None
    ok0 = len(journal(TASK, PUSH_OK))
    with git_spy(answer) as calls, patch_sleep(artifact_branch, mock.Mock()):
        area(lambda: (commit(TASK, "A.md"), commit(TASK, "B.md")))
    ok = journal(TASK, PUSH_OK)[ok0:]
    assert len(ref_pushes(calls, TASK)) == 2
    assert len(ok) == 1 and "(попыток 2)" in ok[0]
    assert not unsent(env)


# --- Задачи двух репозиториев ------------------------------------------------


@pytest.fixture
def two_repos(env):
    env.ext_repo = make_project_repo(EXTERNAL)
    env.ext_bare = config.PROJECTS / EXTERNAL / "origin.git"
    return env


def test_two_tasks_two_repos_first_write_order(two_repos):
    """Две задачи двух репозиториев: по одной отправке в порядке первой
    записи, каждая — в origin своего репозитория, запись с `target=` до
    строки в БД — тоже (AC-10).

    Ловит мутацию: пара хранит только задачу, репозиторий берётся при
    досылке по БД — запись с `target=` уходит в origin артели.
    Ловит мутацию: повтор пары добавляется в набор — у внешней две отправки.
    """
    e = two_repos
    ref_b = artifact_branch.branch_name(TASK_B)

    def body():
        commit(TASK_B, "SPEC.md", target=EXTERNAL)
        commit(TASK, "PLAN.md")
        store.insert_task(store.db(), TASK_B, "Внешняя", STATES[0],
                          f"task/{TASK_B.lower()}-x", EXTERNAL, 25.0)
        commit(TASK_B, "PLAN.md")
    with git_spy() as calls:
        area(body)
    order = [TASK_B if is_ref_push(c, TASK_B) else TASK
             for c in ref_pushes(calls)]
    assert order == [TASK_B, TASK]
    assert origin_head(e.sb, ref_b, e.ext_bare) == local_head(
        e.sb, ref_b, e.ext_repo) != ""
    assert origin_head(e.sb, ref_b) == ""
    assert not unsent(e)


def test_send_pending_by_repo_and_by_task(two_repos):
    """`send_pending(repo=R)` досылает только задачи репозитория R,
    `send_pending(task_id)` — только эту задачу; остальное ждёт выхода
    (ANSWER-1, решение 3б).

    Ловит мутацию: фильтр по репозиторию или задаче не применяется —
    досылается весь набор.
    """
    e = two_repos
    ref_b = artifact_branch.branch_name(TASK_B)
    seen = {}

    def body():
        commit(TASK, "PLAN.md")
        commit(TASK_B, "SPEC.md", target=EXTERNAL)
        seen["repo"] = artifact_branch.send_pending(repo=e.ext_repo)
        seen["после repo"] = (unsent(e), origin_head(e.sb, ref_b, e.ext_bare))
        commit(TASK_B, "PLAN.md", target=EXTERNAL)
        seen["task"] = artifact_branch.send_pending(TASK)
        seen["после task"] = (unsent(e), origin_head(e.sb, ref_b, e.ext_bare),
                              local_head(e.sb, ref_b, e.ext_repo))
    area(body)
    assert seen["repo"] == 1
    assert seen["после repo"][0] is True and seen["после repo"][1]
    assert seen["task"] == 1
    unsent_a, origin_b, local_b = seen["после task"]
    assert unsent_a is False
    assert origin_b != local_b
    assert origin_head(e.sb, ref_b, e.ext_bare) == local_head(
        e.sb, ref_b, e.ext_repo)


def test_dead_send_recovered_outside_area_and_by_sync(env):
    """Досылка «умерла» — переход вне команды отправляет ссылку целиком,
    `origin_sync_refusal` досылает и даёт `None` (AC-12).

    Ловит мутацию: признак области не снимается при выходе — переход вне
    команды тоже откладывает отправку.
    """
    def dead(argv, sub):
        return subprocess.CompletedProcess(argv, 0, "", "") \
            if is_ref_push(sub) else None
    with git_spy(dead):
        area(lambda: commit_fixed(TASK, "PLAN.md"))
    assert unsent(env)
    step(0)
    assert not unsent(env)
    with git_spy(dead):
        area(lambda: commit(TASK, "NOTE.md"))
    assert unsent(env)
    assert artifact_branch.origin_sync_refusal(TASK) is None
    assert not unsent(env)


def test_doctor_fix_sends_unsent_closing_commit(env):
    """Коммит закрытия, не дошедший до origin, досылает `doctor --fix`
    (AC-12).

    Ловит мутацию: коммит закрытия в команде не записывается или не
    становится головой — починке нечего досылать, origin не равен ему.
    """
    def dead(argv, sub):
        return subprocess.CompletedProcess(argv, 0, "", "") \
            if is_ref_push(sub) else None

    def body():
        store.set_state(store.db(), TASK, "killed", "operator",
                        expected_state=STATES[0], detail="юнит")
        snapshot.commit_closing(store.db(), TASK, "killed")
    with git_spy(dead):
        area(body)
    closing = snapshot.closing_sha(store.db(), TASK)
    assert closing and origin_head(env.sb, env.ref) != closing
    capture(doctor._fix_unsent_closed_refs, store.db())
    assert origin_head(env.sb, env.ref) == closing


# --- Точки досрочной досылки -------------------------------------------------


def test_sync_refusal_sends_once_in_area(env):
    """Коммит в команде, затем `origin_sync_refusal` — `None`, одна отправка
    за команду (AC-4).

    Ловит мутацию: `origin_sync_refusal` не досылает набор первым действием —
    пара остаётся, выход отправляет второй раз.
    """
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["до"] = unsent(env)
            seen["сверка"] = artifact_branch.origin_sync_refusal(TASK)
        area(body)
    assert seen == {"до": True, "сверка": None}
    assert len(ref_pushes(calls, TASK)) == 1


def test_sync_refusal_no_second_push_when_pending_send_failed(env):
    """Досылка в `origin_sync_refusal` отказала — повторной отправки в том же
    вызове нет, отказ называет расхождение (отправок за вызов не больше
    прежнего, требование 3а).

    Ловит мутацию: после досылки прежняя ветка «расходится — `_send`»
    отправляет ещё раз — две отправки за вызов.
    """
    seen = {}

    def body():
        commit(TASK, "PLAN.md")
        _reject(env.sb, True)
        with git_spy() as calls:
            seen["сверка"] = artifact_branch.origin_sync_refusal(TASK)
        seen["отправок"] = len(ref_pushes(calls, TASK))
    area(body)
    assert seen["отправок"] == 1
    assert "расходится с origin" in seen["сверка"]


def test_fetch_from_origin_and_fetch_all_not_diverged(env):
    """Своя недосланная голова досылается до `git fetch`: `fetch_from_origin`
    — `FETCH_SAME`, `fetch_all_from_origin` — не `FETCH_DIVERGED` (AC-4;
    ANSWER-1, решение 3а).

    Ловит мутацию: подтягивание не досылает задачу (репозиторий) до
    `git fetch` — исход `FETCH_DIVERGED`.
    """
    seen = {}
    repo = artifact_branch.task_repo(TASK)

    def body():
        commit(TASK, "A.md")
        seen["до 1"] = unsent(env)
        seen["one"] = artifact_branch.fetch_from_origin(TASK)[0]
        commit(TASK, "B.md")
        seen["до 2"] = unsent(env)
        outcomes, _ = artifact_branch.fetch_all_from_origin(repo)
        seen["all"] = outcomes[TASK][0]
    area(body)
    assert seen["до 1"] and seen["до 2"]
    assert seen["one"] == artifact_branch.FETCH_SAME
    assert seen["all"] == artifact_branch.FETCH_SAME


def _order(calls, branch) -> tuple:
    docs = [i for i, c in enumerate(calls) if is_ref_push(c, TASK)]
    code = [i for i, c in enumerate(calls)
            if c == ("push", "-u", "origin", branch)]
    return docs, code


def test_ensure_head_in_origin_docs_before_code(env):
    """Ветки нет в origin — документы отправлены раньше `push -u`; голова уже
    в origin — досылки нет (AC-5).

    Ловит мутацию: досылка перед отправкой ветки пропущена — документы уходят
    только при выходе, после кода.
    Ловит мутацию: досылка до сверки «голова уже в origin» — при совпадении
    документы отправляются.
    """
    env.sb.git("branch", env.branch)
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["первый"] = github_adapter.ensure_head_in_origin(
                store.db(), TASK, env.branch)
            commit(TASK, "NOTE.md")
            mark = len(calls)
            seen["второй"] = github_adapter.ensure_head_in_origin(
                store.db(), TASK, env.branch)
            seen["в втором"] = ref_pushes(calls[mark:], TASK)
        area(body)
    docs, code = _order(calls, env.branch)
    assert seen["первый"] == (True, "") == seen["второй"]
    assert docs and code and docs[0] < code[0]
    assert seen["в втором"] == []


def test_ensure_draft_mr_docs_before_code(env):
    """`ensure_draft_mr` с отправкой ветки — документы раньше `push -u`
    (ANSWER-1, решение 2).

    Ловит мутацию: досылка перед отправкой ветки в `ensure_draft_mr`
    пропущена.
    """
    env.sb.git("branch", env.branch)
    gh = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "url", ""))
    with git_spy() as calls, \
            mock.patch.object(github_adapter, "_is_github_target",
                              return_value=True), \
            mock.patch.object(github_adapter, "_commits_over_base",
                              return_value=1), \
            mock.patch.object(github_adapter, "_touched_protected_paths",
                              return_value=[]), \
            mock.patch.object(github_adapter.ci, "gh", gh):
        def body():
            commit(TASK, "PLAN.md")
            github_adapter.ensure_draft_mr(store.db(), TASK,
                                           store.get_task(store.db(), TASK))
        area(body)
    docs, code = _order(calls, env.branch)
    assert docs and code and docs[0] < code[0], calls


def test_sync_main_or_wait_docs_before_code(env):
    """Подтяжка на гейте мержа с отправкой ветки — документы раньше
    `push -u` (ANSWER-1, решение 2).

    Ловит мутацию: досылка перед отправкой подтяжки в `_sync_main_or_wait`
    пропущена.
    """
    env.sb.git("branch", env.branch)
    ctx = repo_context.resolve(config.DEFAULT_TARGET)
    with git_spy() as calls, \
            mock.patch.object(fsm, "_pull_main_or_escalate",
                              return_value="pulled"):
        def body():
            commit(TASK, "PLAN.md")
            return fsm_merge_gate._sync_main_or_wait(
                store.db(), TASK, store.get_task(store.db(), TASK),
                "merge_gate", env.branch, ctx)
        outcome = capture(area, body)
    docs, code = _order(calls, env.branch)
    assert docs and code and docs[0] < code[0], (outcome, calls)


def test_commit_closing_sends_before_return(env):
    """Переход и коммит закрытия в одной команде — одна отправка, сделанная
    до возврата `commit_closing`; RETRO в origin (AC-6).

    Ловит мутацию: `commit_closing` не досылает задачу — к возврату 0
    отправок.
    """
    rel = f"tasks/{TASK}/RETRO.md"
    seen = {}
    with git_spy() as calls:
        def body():
            store.set_state(store.db(), TASK, "killed", "operator",
                            expected_state=STATES[0], detail="юнит")
            seen["после перехода"] = len(ref_pushes(calls, TASK))
            snapshot.commit_closing(store.db(), TASK, "killed")
            seen["к возврату"] = len(ref_pushes(calls, TASK))
            origin = origin_head(env.sb, env.ref)
            seen["RETRO"] = rel in env.sb.git(
                "--git-dir", env.sb.bare, "ls-tree", "-r", "--name-only",
                origin).split()
        area(body)
        total = len(ref_pushes(calls, TASK))
    assert seen == {"после перехода": 0, "к возврату": 1, "RETRO": True}
    assert total == 1
    assert origin_head(env.sb, env.ref) == snapshot.closing_sha(store.db(), TASK)


@pytest.fixture
def cmd_run_sandbox():
    import tests.test_review_package as review_package_tests
    case = review_package_tests.CmdRunReviewPackageTest(
        "test_developer_step_has_no_package")
    case.setUp()
    yield case
    case.doCleanups()


def test_spawn_agent_sees_docs_sent(cmd_run_sandbox):
    """Коммит документов внутри `cmd_run` до запуска агента — к вызову
    `spawn_agent` его отправка уже сделана (AC-7). Коммит до запуска —
    подмена `checkpoint.main_copy_watch_start`, которую `cmd_run` зовёт
    между подготовкой шага и `_spawn_and_wait`.

    Ловит мутацию: досылка перед `spawn_agent` в `_spawn_and_wait`
    пропущена — до запуска отправки нет.
    """
    case = cmd_run_sandbox
    case.set_state("in_dev")
    docs = artifact_branch.docs_dir(case.TASK, config.DEFAULT_TARGET)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "PLAN.md").write_text("маркер\n", encoding="utf-8")
    marks = {}
    real_watch = checkpoint.main_copy_watch_start

    def watch_with_commit(conn, task_id):
        marks["до"] = len(case.git.raw_calls)
        commit(task_id, "NOTE-developer.md")
        marks["после"] = len(case.git.raw_calls)
        return real_watch(conn, task_id)

    def spawn(cmd, **kwargs):
        marks.setdefault("запуск", len(case.git.raw_calls))
        return FakeProc(["готово\n"])

    with mock.patch.object(checkpoint, "main_copy_watch_start",
                           side_effect=watch_with_commit), \
            mock.patch.object(runner, "spawn_agent", side_effect=spawn):
        case.capture(runner.cmd_run, case.TASK)
    calls = [strip_dash_c(c) for c in case.git.raw_calls]
    assert ref_pushes(calls[marks["до"]:marks["после"]], case.TASK) == []
    assert ref_pushes(calls[marks["после"]:marks["запуск"]], case.TASK)


def _branch_ci(e, probe):
    with mock.patch.object(fsm_merge_gate.ci, "branch_status",
                           side_effect=lambda *a, **k: (probe(),
                                                        (True, "зелёный"))[1]):
        start = time.monotonic()
        fsm_merge_gate._wait_for_branch_ci_green(store.db(), TASK, e.branch,
                                                 start, start + 600)


def _main_ci(e, probe):
    ctx = repo_context.resolve(config.DEFAULT_TARGET)
    head = e.sb.git("rev-parse", config.MAIN_BRANCH).strip()
    status = SimpleNamespace(kind=ci.MAIN_GREEN, note="зелёный")
    with mock.patch.object(fsm_merge_gate.ci, "main_line_status",
                           side_effect=lambda *a, **k: (probe(), status)[1]):
        fsm_merge_gate._await_main_ci(store.db(), TASK, head, ctx)


def _full_suite(paths):
    def run(e, probe):
        ctx = repo_context.resolve(config.DEFAULT_TARGET)
        green = SimpleNamespace(green=True, detail="зелёный", outcome="green")
        with tempfile.TemporaryDirectory() as scratch, \
                mock.patch.object(fsm_merge_gate.acceptance, "full_suite",
                                  side_effect=lambda *a, **k: (probe(),
                                                               green)[1]):
            fsm_merge_gate._full_suite_or_refuse(store.db(), TASK, paths,
                                                 Path(scratch), ctx)
    return run


@pytest.mark.parametrize("point", [_branch_ci, _main_ci,
                                   _full_suite(["tests/test_x.py"])],
                         ids=["ci-ветки", "ci-main", "прогон-нужен"])
def test_long_merge_stage_sees_origin_synced(env, point):
    """Долгий этап гейта мержа: в момент первого опроса CI / запуска прогона
    ссылка в origin равна локальной (AC-11).

    Ловит мутацию: досылка первым действием `_wait_for_branch_ci_green`,
    `_await_main_ci` или перед прогоном `_full_suite_or_refuse` пропущена —
    в момент опроса origin отстаёт.
    """
    seen = []

    def probe():
        if not seen:
            seen.append(unsent(env))

    def body():
        commit(TASK, "PLAN.md")
        before = unsent(env)
        capture(point, env, probe)
        return before
    assert area(body) is True
    assert seen == [False]


def test_full_suite_not_needed_no_send(env):
    """Прогон не нужен — `_full_suite_or_refuse` не досылает (AC-11).

    Ловит мутацию: досылка до проверки «прогон нужен».
    """
    seen = {}

    def body():
        commit(TASK, "PLAN.md")
        _full_suite(["docs/x.md"])(env, lambda: seen.setdefault("прогон", 1))
        seen["отстаёт"] = unsent(env)
    area(body)
    assert seen == {"отстаёт": True}
