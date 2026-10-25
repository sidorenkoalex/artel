"""Журнал досылки, задачи двух репозиториев в одной команде и восстановление
после «умершей» досылки (AC-8, AC-10, AC-12).

Группа: разовый
Почему разовый: проверяются `artifact_branch` и закрытая починка `doctor`
(`_fix_unsent_closed_refs`); импорт этих имён — признак факта задачи для
долгоживущего слоя, после мержа свойство держит файл тестов разработчика
(требование 6 SPEC).

Красен до реализации: области нет — каждый из трёх коммитов в команде отправляется сам и пишет свой отказ (три записи вместо одной), коммит задачи с повтором отправляется дважды, а «отправок в конце тела 0» не держится; AC-12 держит прежнее восстановление и зелен с рождения.

Песочница и шпион — `_deferred.py`.
"""
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, config, doctor, snapshot, store  # noqa: E402
from tests.sandbox import capture, make_project_repo, patch_sleep  # noqa: E402
from _deferred import (PUSH_FAILED, PUSH_OK, STATES, TASK, TASK_B,  # noqa: E402
                       area, commit, fake_ok, git_spy, is_ref_push, journal,
                       lags, local_head, make_synced, origin_head, ref_pushes,
                       step)

EXTERNAL = "plankext"


@pytest.fixture
def synced(origin_real_git):
    """Пульт с bare-origin; ссылка `TASK` совпадает с origin."""
    return make_synced(origin_real_git)


@pytest.fixture
def two_repos(origin_real_git):
    """`synced` плюс клон внешнего проекта со своим bare-origin."""
    env = make_synced(origin_real_git)
    env.ext_repo = make_project_repo(EXTERNAL)
    env.ext_bare = config.PROJECTS / EXTERNAL / "origin.git"
    return env


def reject_ref_pushes(sb) -> None:
    """origin отвергает запись в `refs/artifacts/*` (`pre-receive`)."""
    hook = Path(sb.bare) / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        "  case \"$ref\" in refs/artifacts/*) exit 1;; esac\n"
        "done\n"
        "exit 0\n", encoding="utf-8")
    hook.chmod(0o755)


def accept_ref_pushes(sb) -> None:
    (Path(sb.bare) / "hooks" / "pre-receive").unlink()


def test_ac8_rejected_three_commits_one_failure_then_one_success(synced):
    """origin отвергает запись — одна запись отказа на команду, затем успех.

    Сценарий: `pre-receive` origin отвергает `refs/artifacts/*`; тело
    `run_locked` делает три коммита. В журнале ровно одна новая запись
    «push артефактной ветки FAILED» прежнего текста (non-fast-forward с
    обоими sha и советом свести merge-коммитом). Хук убран, следующая
    команда коммитит документ — одна запись об успехе после отказа, новых
    отказов нет, origin равен локальной.

    Ловит мутацию: коммит внутри команды по-прежнему отправляется сразу —
    три записи отказа вместо одной.
    Ловит мутацию: досылка пишет журнал своим текстом либо без правила
    `_last_send_failed` — запись об успехе после отказа не появляется или
    текст отказа не прежний.
    """
    reject_ref_pushes(synced.sb)
    failed0 = len(journal(TASK, PUSH_FAILED))

    def body():
        for name in ("A.md", "B.md", "C.md"):
            commit(TASK, name)
    area(TASK, body)
    failed = journal(TASK, PUSH_FAILED)[failed0:]
    local = local_head(synced.sb, synced.ref)
    assert len(failed) == 1, failed
    assert failed[0].startswith(artifact_branch.PUSH_REASON_NON_FAST_FORWARD + ": "), failed
    assert failed[0].endswith(f"; локальный sha {local}, origin sha "
                              f"{synced.head0} — свести merge-коммитом"), failed

    accept_ref_pushes(synced.sb)
    ok0 = len(journal(TASK, PUSH_OK))
    area(TASK, lambda: commit(TASK, "D.md"))
    ok = journal(TASK, PUSH_OK)[ok0:]
    assert ok == [f"push артефактной ветки {synced.ref} — успех"], ok
    assert len(journal(TASK, PUSH_FAILED)) == failed0 + 1
    origin, local = lags(synced)
    assert origin == local


def test_ac8_server_5xx_retried_once_journaled_attempts_two(synced):
    """Ответ сервера 5xx на первой попытке досылки — повтор и «попыток 2».

    Сценарий: первая отправка `refs/artifacts/<id>` отвечает
    `HTTP 500` (подмена процесса git), дальше — настоящий git; пауза
    повтора подменена. Тело `run_locked` делает два коммита: в конце тела
    отправок нет; после команды — две попытки, одна запись успеха с
    «(попыток 2)», отказов нет, origin равен локальной.

    Ловит мутацию: досылка зовёт `_attempt_push` без повтора ответа
    сервера — одна попытка и запись «push артефактной ветки FAILED».
    Ловит мутацию: коммит в команде отправляется сразу — в конце тела уже
    есть отправки.
    """
    state = {"first": True}

    def answer(argv, sub):
        if is_ref_push(sub, TASK) and state["first"]:
            state["first"] = False
            return subprocess.CompletedProcess(
                argv, 1, "", "error: RPC failed; HTTP 500 curl 22 The "
                             "requested URL returned error: 500")
        return None

    failed0 = len(journal(TASK, PUSH_FAILED))
    ok0 = len(journal(TASK, PUSH_OK))
    seen = {}
    sleep = mock.Mock()
    with git_spy(answer) as calls, patch_sleep(artifact_branch, sleep):
        def body():
            commit(TASK, "A.md")
            commit(TASK, "B.md")
            seen["в конце тела"] = len(ref_pushes(calls, TASK))
        area(TASK, body)
    ok = journal(TASK, PUSH_OK)[ok0:]
    assert seen["в конце тела"] == 0
    assert len(ref_pushes(calls, TASK)) == 2
    assert len(ok) == 1 and "(попыток 2)" in ok[0], ok
    assert len(journal(TASK, PUSH_FAILED)) == failed0
    assert sleep.call_count == 1
    origin, local = lags(synced)
    assert origin == local


def test_ac10_two_tasks_two_repos_one_push_each_in_first_write_order(two_repos):
    """Две задачи двух репозиториев в одной команде — по одной отправке.

    Сценарий: в теле `run_locked` задача внешнего проекта пишет первый
    коммит с `target=` ДО своей строки в БД, задача артели коммитит, затем
    строка внешней задачи заводится и она коммитит ещё раз (уже по БД);
    порядок первых записей двух задач случаен. После команды — ровно по
    одной отправке на задачу, в порядке первой записи; ссылка каждой в
    origin своего репозитория равна локальной, в origin артели ссылки
    внешней задачи нет.

    Ловит мутацию: пара набора хранит только задачу, а репозиторий берётся
    при досылке по БД/проекту по умолчанию — первая запись с `target=`
    уходит в origin артели или не уходит вовсе.
    Ловит мутацию: повтор пары добавляется в набор — у внешней задачи две
    отправки.
    """
    env = two_repos
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    external_first = random.Random(seed).random() < 0.5
    ref_b = artifact_branch.branch_name(TASK_B)
    why = f"зерно {seed}, внешняя первой: {external_first}"

    def body():
        if external_first:
            commit(TASK_B, "SPEC.md", target=EXTERNAL)
            commit(TASK, "PLAN.md")
        else:
            commit(TASK, "PLAN.md")
            commit(TASK_B, "SPEC.md", target=EXTERNAL)
        store.insert_task(store.db(), TASK_B, "Задача проекта", STATES[0],
                          f"task/{TASK_B.lower()}-x", EXTERNAL, 25.0)
        commit(TASK_B, "PLAN.md")
    with git_spy() as calls:
        area(TASK, body)
    pushes = ref_pushes(calls)
    order = [TASK_B if is_ref_push(c, TASK_B) else TASK for c in pushes]
    expected = [TASK_B, TASK] if external_first else [TASK, TASK_B]
    assert order == expected, why
    assert origin_head(env.sb, ref_b, env.ext_bare) == local_head(
        env.sb, ref_b, env.ext_repo) != "", why
    assert origin_head(env.sb, env.ref) == local_head(env.sb, env.ref), why
    assert origin_head(env.sb, ref_b) == "", why


def _dead_send(argv, sub):
    """Отправка ссылки документов «умерла»: процесс не дошёл до origin."""
    return fake_ok(argv) if is_ref_push(sub) else None


def test_ac12_dead_send_recovered_by_transition_and_sync(synced):
    """Досылка «умерла» — переход вне команды и сверка с origin догоняют.

    Сценарий: в команде коммит, отправка ссылки подменена ничего не
    делающей (процесс «умер» до отправки) — origin отстаёт. Затем
    `store.set_state` вне команды отправляет ссылку целиком: голова в
    origin равна локальной. Снова «умершая» досылка коммита — затем
    `origin_sync_refusal` досылает и даёт `None`.

    Ловит мутацию: признак открытой области не снимается при выходе из
    `run_locked` — переход вне команды тоже откладывает отправку, origin
    остаётся позади.
    """
    with git_spy(_dead_send):
        area(TASK, lambda: commit(TASK, "PLAN.md"))
    origin, local = lags(synced)
    assert origin != local, "предусловие: досылка не дошла до origin"

    step(TASK, 0)
    origin, local = lags(synced)
    assert origin == local

    with git_spy(_dead_send):
        area(TASK, lambda: commit(TASK, "NOTE.md"))
    origin, local = lags(synced)
    assert origin != local, "предусловие: досылка не дошла до origin"

    assert artifact_branch.origin_sync_refusal(TASK) is None
    origin, local = lags(synced)
    assert origin == local


def test_ac12_doctor_fix_sends_unsent_closing_commit(synced):
    """Закрытая задача с недосланным коммитом закрытия — `doctor --fix` досылает.

    Сценарий: в команде переход в `killed` и `snapshot.commit_closing`,
    отправки подменены ничего не делающими — коммит закрытия только
    локально. `doctor._fix_unsent_closed_refs` (починка `doctor --fix`)
    отправляет его: голова в origin равна коммиту закрытия.

    Зелёный с рождения: досылку коммита закрытия делает прежняя починка `doctor --fix`; тест держит, что отложенная отправка её не ломает — коммит закрытия записан, равен локальной голове и доходит до origin.
    """
    def body():
        store.set_state(store.db(), TASK, "killed", "operator",
                        expected_state=STATES[0], detail="сценарий планки")
        snapshot.commit_closing(store.db(), TASK, "killed")
    with git_spy(_dead_send):
        area(TASK, body)
    closing = snapshot.closing_sha(store.db(), TASK)
    origin, local = lags(synced)
    assert closing and local == closing
    assert origin != closing, "предусловие: коммит закрытия не дослан"

    capture(doctor._fix_unsent_closed_refs, store.db())

    assert origin_head(synced.sb, synced.ref) == closing
