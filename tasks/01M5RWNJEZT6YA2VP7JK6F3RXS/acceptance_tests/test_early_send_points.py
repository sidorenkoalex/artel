"""Досрочная досылка ссылки документов до выхода из команды пульта: сверка
и подтягивание с origin, отправка кодовой ветки, коммит закрытия, запуск
агента шага, долгие этапы гейта мержа (AC-4, AC-5, AC-6, AC-7, AC-11).

Группа: разовый
Почему разовый: проверяются `artifact_branch`, закрытые функции гейта мержа
и песочница `tests/test_review_package.py`; импорт этих имён — признак факта
задачи для долгоживущего слоя, после мержа свойство держит файл тестов
разработчика (требование 6 SPEC).

Красен до реализации: области нет — коммит внутри `run_locked` уходит в origin сразу, и предусловие каждого сценария «коммит в команде ещё не дослан» не выполняется; у коммита закрытия в команде с переходом отправок две, а не одна.

Каждый сценарий сначала проверяет предусловие «коммит в команде недослан»:
без него равенство origin и локальной головы в точке досылки держалось бы
и без досылки (немедленная отправка), и тест ничего бы не ловил.

Песочница и шпион — `_deferred.py`; AC-7 — песочница
`CmdRunReviewPackageTest` (`tests/test_review_package.py`).
"""
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tests.test_review_package as review_package_tests  # noqa: E402
from orchestrator import (artifact_branch, checkpoint, ci, config,  # noqa: E402
                          fsm_merge_gate, github_adapter, repo_context,
                          runner, snapshot, store)
from tests.sandbox import FakeProc, strip_dash_c  # noqa: E402
from _deferred import (TASK, area, commit, doc_rel, git_spy,  # noqa: E402
                       is_ref_push, lags, make_synced, ref_pushes, STATES)


@pytest.fixture
def synced(origin_real_git):
    """Пульт с bare-origin; ссылка `TASK` совпадает с origin."""
    return make_synced(origin_real_git)


@pytest.fixture
def cmd_run_sandbox():
    """Песочница `CmdRunReviewPackageTest` после `setUp()` (FakeGit вместо
    `gitcmd.git`, задача заведена `cmd_new`)."""
    case = review_package_tests.CmdRunReviewPackageTest(
        "test_developer_step_has_no_package")
    case.setUp()
    yield case
    case.doCleanups()


def test_ac4_sync_refusal_sends_once_in_area(synced):
    """Коммит в команде, затем сверка с origin — `None` и одна отправка.

    Сценарий: тело `run_locked` коммитит документ (ссылка в origin ещё
    отстаёт), затем зовёт `origin_sync_refusal`. Сверка даёт `None`, за
    всю команду ровно одна отправка, после неё origin равен локальной.

    Ловит мутацию: `origin_sync_refusal` не зовёт `send_pending(task_id)`
    первым действием — прежняя досылка при расхождении отправляет мимо
    набора, пара остаётся в нём, и выход из команды отправляет второй раз:
    отправок две.
    Ловит мутацию: досылка не убирает пару из набора — выход из команды
    отправляет ещё раз, отправок две.
    """
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["после коммита"] = lags(synced)
            seen["сверка"] = artifact_branch.origin_sync_refusal(TASK)
        area(TASK, body)
    origin, local = seen["после коммита"]
    assert origin != local, "предусловие: коммит в команде недослан"
    assert seen["сверка"] is None
    assert len(ref_pushes(calls, TASK)) == 1
    assert lags(synced)[0] == lags(synced)[1]


def test_ac4_fetch_from_origin_same_not_diverged(synced):
    """Коммит в команде, затем подтягивание из origin — `FETCH_SAME`.

    Сценарий: тело `run_locked` коммитит документ (origin отстаёт), затем
    зовёт `fetch_from_origin`. Исход — `FETCH_SAME`, не `FETCH_DIVERGED`:
    своя недосланная голова дослана до `git fetch`.

    Ловит мутацию: `fetch_from_origin` не досылает задачу до `git fetch` —
    локальная голова впереди origin, исход `FETCH_DIVERGED`.
    """
    seen = {}

    def body():
        commit(TASK, "PLAN.md")
        seen["после коммита"] = lags(synced)
        seen["исход"] = artifact_branch.fetch_from_origin(TASK)
    area(TASK, body)
    origin, local = seen["после коммита"]
    assert origin != local, "предусловие: коммит в команде недослан"
    assert seen["исход"][0] == artifact_branch.FETCH_SAME, seen["исход"]


def test_ac5_docs_sent_before_code_branch_push(synced):
    """Отправка кодовой ветки — ссылка документов уходит раньше неё.

    Сценарий: кодовой ветки задачи нет в origin; тело `run_locked`
    коммитит документ (origin отстаёт), затем зовёт
    `github_adapter.ensure_head_in_origin`. В записанных argv отправка
    `refs/artifacts/<id>` стоит раньше `push -u origin <ветка>`.

    Ловит мутацию: досылка перед отправкой ветки в `ensure_head_in_origin`
    пропущена — отправка документов случается только при выходе из
    команды, после `push -u origin <ветка>`.
    """
    synced.sb.git("branch", synced.branch)
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["после коммита"] = lags(synced)
            seen["исход"] = github_adapter.ensure_head_in_origin(
                store.db(), TASK, synced.branch)
        area(TASK, body)
    origin, local = seen["после коммита"]
    assert origin != local, "предусловие: коммит в команде недослан"
    assert seen["исход"] == (True, "")
    docs = [i for i, c in enumerate(calls) if is_ref_push(c, TASK)]
    code = [i for i, c in enumerate(calls)
            if c == ("push", "-u", "origin", synced.branch)]
    assert docs and code, calls
    assert docs[0] < code[0], calls


def test_ac5_head_already_in_origin_no_send(synced):
    """Голова кодовой ветки уже в origin — досылки в этом вызове нет.

    Сценарий: кодовая ветка задачи отправлена в origin заранее; тело
    `run_locked` коммитит документ, затем зовёт `ensure_head_in_origin`.
    За время вызова ни одной отправки `refs/artifacts/<id>`.

    Ловит мутацию: досылка стоит до сверки «голова уже в origin» — при
    совпадении голов документы всё равно отправляются в этом вызове.
    """
    synced.sb.git("branch", synced.branch)
    synced.sb.git("push", "-q", "origin", synced.branch)
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["после коммита"] = lags(synced)
            mark = len(calls)
            seen["исход"] = github_adapter.ensure_head_in_origin(
                store.db(), TASK, synced.branch)
            seen["в вызове"] = ref_pushes(calls[mark:], TASK)
        area(TASK, body)
    origin, local = seen["после коммита"]
    assert origin != local, "предусловие: коммит в команде недослан"
    assert seen["исход"] == (True, "")
    assert seen["в вызове"] == []


def test_ac6_closing_commit_sent_before_return(synced):
    """Переход и коммит закрытия в одной команде — одна отправка до возврата.

    Сценарий: тело `run_locked` делает `store.set_state` в `killed` и
    `snapshot.commit_closing`. После перехода отправок нет; к возврату из
    `commit_closing` — ровно одна, origin равен локальной голове и несёт
    RETRO; выход из команды лишней отправки не даёт.

    Ловит мутацию: `commit_closing` не досылает задачу после записанного
    коммита — к его возврату отправок 0, RETRO в origin нет до выхода из
    команды.
    """
    rel = doc_rel(TASK, "RETRO.md")
    seen = {}
    with git_spy() as calls:
        def body():
            store.set_state(store.db(), TASK, "killed", "operator",
                            expected_state=STATES[0], detail="сценарий планки")
            seen["после перехода"] = len(ref_pushes(calls, TASK))
            seen["итог"] = snapshot.commit_closing(store.db(), TASK, "killed")
            seen["к возврату"] = len(ref_pushes(calls, TASK))
            origin, local = lags(synced)
            seen["головы"] = (origin, local)
            seen["RETRO"] = rel in synced.sb.git(
                "--git-dir", synced.sb.bare, "ls-tree", "-r", "--name-only",
                origin).split() if origin else False
        area(TASK, body)
        total = len(ref_pushes(calls, TASK))
    origin, local = seen["головы"]
    assert seen["после перехода"] == 0, "предусловие: переход в команде недослан"
    assert seen["итог"].startswith(f"коммит закрытия {TASK}"), seen["итог"]
    assert seen["к возврату"] == 1
    assert origin == local == snapshot.closing_sha(store.db(), TASK)
    assert seen["RETRO"] is True
    assert total == 1


def test_ac7_spawn_sees_unsent_docs_sent(cmd_run_sandbox):
    """Шаг роли: недосланный коммит до запуска дослан к вызову `spawn_agent`.

    Сценарий — песочница `CmdRunReviewPackageTest` (FakeGit пишет вызовы
    git): шаг разработчика `runner.cmd_run`; подмена
    `checkpoint.main_copy_watch_start` (между подготовкой шага и запуском
    агента, внутри команды) коммитит документ задачи `commit_files`. В
    вызовах самого коммита отправки нет (коммит недослан); к моменту
    вызова `runner.spawn_agent` отправка `refs/artifacts/<id>` уже
    записана — набор недосланных пуст.

    Ловит мутацию: досылка перед `spawn_agent` в `_spawn_and_wait`
    пропущена — до запуска агента отправки нет, она случится только при
    выходе из команды после шага.
    """
    case = cmd_run_sandbox
    case.set_state("in_dev")
    docs = artifact_branch.docs_dir(case.TASK, config.DEFAULT_TARGET)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "PLAN.md").write_text("маркер\n", encoding="utf-8")
    ref = artifact_branch.branch_name(case.TASK)
    marks = {}
    real_watch = checkpoint.main_copy_watch_start

    def watch_with_commit(conn, task_id):
        marks["до коммита"] = len(case.git.raw_calls)
        marks["sha"] = commit(task_id, "NOTE-developer.md")
        marks["после коммита"] = len(case.git.raw_calls)
        return real_watch(conn, task_id)

    def spawn(cmd, **kwargs):
        marks.setdefault("запуск", len(case.git.raw_calls))
        return FakeProc(["готово\n"])

    with mock.patch.object(checkpoint, "main_copy_watch_start",
                           side_effect=watch_with_commit), \
            mock.patch.object(runner, "spawn_agent", side_effect=spawn):
        case.capture(runner.cmd_run, case.TASK)
    calls = [strip_dash_c(c) for c in case.git.raw_calls]
    assert "запуск" in marks and "после коммита" in marks, marks
    own = calls[marks["до коммита"]:marks["после коммита"]]
    assert marks["sha"], own
    assert any(c[:2] == ("update-ref", ref) for c in own), own
    assert ref_pushes(own, case.TASK) == [], "предусловие: коммит недослан"
    before_spawn = calls[marks["после коммита"]:marks["запуск"]]
    assert ref_pushes(before_spawn, case.TASK), before_spawn


def _branch_ci(env, probe):
    with mock.patch.object(fsm_merge_gate.ci, "branch_status",
                           side_effect=lambda *a, **k: (probe(), (True, "CI зелёный"))[1]):
        start = time.monotonic()
        fsm_merge_gate._wait_for_branch_ci_green(store.db(), TASK, env.branch,
                                                 start, start + 600)


def _main_ci(env, probe):
    ctx = repo_context.resolve(config.DEFAULT_TARGET)
    head = env.sb.git("rev-parse", config.MAIN_BRANCH).strip()
    status = SimpleNamespace(kind=ci.MAIN_GREEN, note="зелёный")
    with mock.patch.object(fsm_merge_gate.ci, "main_line_status",
                           side_effect=lambda *a, **k: (probe(), status)[1]):
        fsm_merge_gate._await_main_ci(store.db(), TASK, head, ctx)


def _full_suite(paths):
    def run(env, probe):
        ctx = repo_context.resolve(config.DEFAULT_TARGET)
        green = SimpleNamespace(green=True, detail="полный прогон зелёный",
                                outcome="green")
        with tempfile.TemporaryDirectory() as scratch, \
                mock.patch.object(fsm_merge_gate.acceptance, "full_suite",
                                  side_effect=lambda *a, **k: (probe(), green)[1]):
            fsm_merge_gate._full_suite_or_refuse(store.db(), TASK, paths,
                                                 Path(scratch), ctx)
    return run


POINTS = {
    "ожидание CI ветки": _branch_ci,
    "ожидание CI main": _main_ci,
    "полный прогон нужен": _full_suite(["tests/test_appendix.py"]),
}


@pytest.mark.parametrize("point", [
    "ожидание CI ветки",
    "ожидание CI main",
    "полный прогон нужен",
])
def test_ac11_long_merge_stage_sees_origin_synced(synced, point):
    """Долгий этап гейта мержа: в момент опроса CI / запуска прогона origin
    равен локальной голове.

    Сценарий: тело `run_locked` коммитит документ (origin отстаёт), затем
    зовёт точку гейта: `_wait_for_branch_ci_green` (опрос
    `ci.branch_status` подменён), `_await_main_ci` (опрос
    `ci.main_line_status` подменён) либо `_full_suite_or_refuse` с путём
    `tests/…`, которому прогон нужен (`acceptance.full_suite` подменён). В
    момент первого опроса CI или запуска прогона голова
    `refs/artifacts/<id>` в origin равна локальной. Свой недосланный коммит
    перед каждой точкой (ANSWER-1, решение гейта 5); `_ci_ready_or_wait`
    CI не опрашивает и досылки не получает.

    Ловит мутацию: досылка первым действием `_wait_for_branch_ci_green`
    (или `_await_main_ci`, или перед прогоном в `_full_suite_or_refuse`)
    пропущена — в момент опроса/прогона origin отстаёт от локальной.
    """
    seen = []

    def probe():
        if not seen:
            seen.append(lags(synced))

    def body():
        commit(TASK, "PLAN.md")
        seen_before = lags(synced)
        POINTS[point](synced, probe)
        return seen_before
    origin0, local0 = area(TASK, body)
    assert origin0 != local0, "предусловие: коммит в команде недослан"
    assert seen, f"{point}: опрос CI/прогон не вызван"
    origin, local = seen[0]
    assert origin == local, point


def test_ac11_full_suite_not_needed_no_send(synced):
    """Прогон после приложений не нужен — `_full_suite_or_refuse` не досылает.

    Сценарий: тело `run_locked` коммитит документ (origin отстаёт), затем
    зовёт `_full_suite_or_refuse` с путём вне классов полного прогона
    (`docs/…`). Прогон не запускается; сразу после вызова, ещё внутри
    команды, ссылка в origin по-прежнему отстаёт и отправок не было.

    Ловит мутацию: досылка в `_full_suite_or_refuse` стоит до проверки
    «прогон нужен» — документы отправляются и при ненужном прогоне.
    """
    ran = []
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["после коммита"] = lags(synced)
            _full_suite(["docs/appendix.md"])(synced, lambda: ran.append(1))
            seen["после вызова"] = lags(synced)
            seen["отправок"] = len(ref_pushes(calls, TASK))
        area(TASK, body)
    origin, local = seen["после коммита"]
    assert origin != local, "предусловие: коммит в команде недослан"
    assert ran == []
    assert seen["отправок"] == 0
    assert seen["после вызова"][0] != seen["после вызова"][1]
