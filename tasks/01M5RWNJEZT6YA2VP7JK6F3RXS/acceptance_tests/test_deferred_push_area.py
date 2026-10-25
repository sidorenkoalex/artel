"""Область отложенной отправки ссылки документов внутри команды пульта
(`lease.run_locked`): одна отправка при выходе, вложенность, исключения тела,
пустой набор и отсутствие `origin`, прежнее поведение вне команды
(AC-1, AC-2, AC-3, AC-9, AC-13).

Группа: разовый
Почему разовый: свойство живёт в `artifact_branch` и наблюдается через
`gitcmd`/`git push`, а их импорт — признак факта задачи для долгоживущего
слоя; после мержа его держит файл тестов разработчика (требование 6 SPEC).

Красен до реализации: области нет — каждый коммит внутри `run_locked` уходит в origin сразу, поэтому «0 отправок в конце тела» (AC-1, AC-2, AC-3) не держится, а досылка, бросившая исключение, вылетает из тела вместо исключения тела; AC-9 и AC-13 держат прежнее поведение и зелены с рождения.

Песочница и шпион — `_deferred.py`.
"""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, store  # noqa: E402
from _deferred import (PUSH_FAILED, PUSH_OK, TASK, TASK_B,  # noqa: E402
                       add_task, area, commit, commit_fixed, git_spy,
                       journal, lags,
                       make_synced, ref_pushes, step)


@pytest.fixture
def synced(origin_real_git):
    """Пульт с bare-origin; ссылка `TASK` совпадает с origin."""
    return make_synced(origin_real_git)


@pytest.fixture
def no_origin(origin_real_git):
    """Как `synced`, затем remote `origin` удалён."""
    env = make_synced(origin_real_git)
    origin_real_git.git("remote", "remove", "origin")
    return env


def scenario_order(rng: random.Random) -> list:
    """Три перехода по порядку и один коммит документов в случайном месте."""
    order = [0, 1, 2]
    order.insert(rng.randrange(len(order) + 1), "commit")
    return order


def play(order: list) -> None:
    for item in order:
        if item == "commit":
            commit_fixed(TASK, "PLAN.md")
        else:
            step(TASK, item)


def test_ac1_one_push_on_area_exit(synced):
    """Три перехода и коммит в теле одной команды — одна отправка после неё.

    Сценарий: тело `run_locked` делает три `store.set_state` (строки
    паспорта) и один `commit_files` в случайном порядке. В конце тела
    отправок `refs/artifacts/<id>` нет; после возврата `run_locked` —
    ровно одна, голова в origin равна локальной.

    Ловит мутацию: `run_locked` не открывает область вокруг `body(sid)` —
    в конце тела уже четыре отправки, после возврата тоже четыре.
    Ловит мутацию: досылка при выходе забыта — после возврата 0 отправок,
    origin отстаёт.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    order = scenario_order(random.Random(seed))
    seen = {}
    with git_spy() as calls:
        def body():
            play(order)
            seen["в конце тела"] = len(ref_pushes(calls, TASK))
        area(TASK, body)
        after = len(ref_pushes(calls, TASK))
    origin, local = lags(synced)
    why = f"зерно {seed}, порядок {order}"
    assert seen["в конце тела"] == 0, why
    assert after == 1, why
    assert origin == local, why


def test_ac1_same_scenario_outside_area_pushes_each_commit(synced):
    """Тот же сценарий вне команды пульта — четыре отправки, как прежде.

    Ловит мутацию: отложенная отправка включена всегда, а не только внутри
    области — вне `run_locked` отправок 0 и origin отстаёт.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    order = scenario_order(random.Random(seed))
    with git_spy() as calls:
        play(order)
    origin, local = lags(synced)
    why = f"зерно {seed}, порядок {order}"
    assert len(ref_pushes(calls, TASK)) == 4, why
    assert origin == local, why


def test_ac2_nested_area_exit_sends_whole_set(synced):
    """Внешняя команда и две вложенные подряд, в каждой коммит.

    Сценарий: внешнее тело коммитит, затем вложенный `run_locked` с
    коммитом, затем второй вложенный с коммитом. После выхода из первого
    вложенного (до входа во второй) отправка уже сделана и origin равен
    локальной голове; всего две отправки, выход внешнего лишней не даёт.

    Ловит мутацию: досылка только при выходе из самой внешней области —
    после первого вложенного 0 отправок, origin отстаёт.
    Ловит мутацию: пара не удаляется из набора после досылки — выход
    внешнего досылает ещё раз, отправок три и больше.
    """
    seen = {}
    with git_spy() as calls:
        def nested(name, key):
            area(TASK, lambda: commit(TASK, name))
            seen[key] = (len(ref_pushes(calls, TASK)), *lags(synced))

        def outer():
            commit(TASK, "A.md")
            nested("B.md", "первый")
            nested("C.md", "второй")
        area(TASK, outer)
        total = len(ref_pushes(calls, TASK))
    pushes, origin, local = seen["первый"]
    assert pushes == 1, seen
    assert origin == local, seen
    assert seen["второй"][0] == 2, seen
    assert total == 2, seen
    assert lags(synced)[0] == lags(synced)[1]


@pytest.mark.parametrize("exc_type, text", [
    (RuntimeError, "тело упало"),
    (SystemExit, "отказ"),
])
def test_ac3_body_exception_still_sends(synced, exc_type, text):
    """Тело коммитит и бросает исключение — отправка сделана, исключение то же.

    Сценарий: тело `run_locked` коммитит документ, затем бросает
    `RuntimeError` либо `SystemExit("отказ")`. В конце тела отправок нет;
    наружу выходит тот же объект исключения; ссылка в origin равна
    локальной; lease задачи снят.

    Ловит мутацию: досылка стоит после `body(sid)` вне `try`/`finally` —
    при исключении тела коммит остаётся недосланным, origin отстаёт.
    Ловит мутацию: досылка ловит `Exception`, но не `BaseException`, и
    подменяет `SystemExit` — наружу выходит другое исключение либо ничего.
    """
    raised = exc_type(text)
    seen = {}
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            seen["в конце тела"] = len(ref_pushes(calls, TASK))
            raise raised
        with pytest.raises(exc_type) as info:
            area(TASK, body)
    origin, local = lags(synced)
    assert info.value is raised
    assert seen["в конце тела"] == 0
    assert len(ref_pushes(calls, TASK)) == 1
    assert origin == local
    assert store.lease_row(store.db(), TASK) is None


def test_ac3_failing_send_does_not_replace_body_exception(synced):
    """Досылка бросила при летящем исключении тела — наружу исключение тела.

    Сценарий: две задачи; тело коммитит документы первой, затем второй и
    бросает `ValueError`. Отправка первой бросает `RuntimeError` (подмена
    процесса git). Наружу выходит тот же `ValueError`; вторая задача
    дослана — её ссылка в origin равна локальной.

    Ловит мутацию: досылка без защиты при летящем исключении — наружу
    выходит `RuntimeError` досылки вместо исключения тела.
    Ловит мутацию: исключение досылки обрывает цикл набора — вторая задача
    остаётся недосланной.
    """
    add_task(TASK_B)
    ref_b = artifact_branch.branch_name(TASK_B)

    def answer(argv, sub):
        if sub[:1] == ("push",) and any(
                str(a).startswith(artifact_branch.branch_name(TASK) + ":")
                for a in sub):
            raise RuntimeError("досылка упала")
        return None

    raised = ValueError("тело упало")
    with git_spy(answer):
        def body():
            commit(TASK, "PLAN.md")
            commit(TASK_B, "PLAN.md")
            raise raised
        with pytest.raises(ValueError) as info:
            area(TASK, body)
    origin_b, local_b = lags(synced, ref_b)
    assert info.value is raised
    assert origin_b == local_b
    assert store.lease_row(store.db(), TASK) is None


def test_ac9_no_origin_no_push_no_journal(no_origin):
    """Без origin коммиты внутри команды — ни отправки, ни записи журнала.

    Сценарий: remote `origin` удалён; тело `run_locked` коммитит два
    документа и возвращает значение. Отправок `refs/artifacts/<id>` нет,
    записей журнала об исходе отправки не прибавилось, `run_locked` вернул
    значение тела без исключения.

    Ловит мутацию: досылка зовёт `artifact_branch.push` вместо `_send` —
    без origin пишется «push артефактной ветки FAILED: нет origin».
    """
    before = (len(journal(TASK, PUSH_OK)), len(journal(TASK, PUSH_FAILED)))
    with git_spy() as calls:
        def body():
            commit(TASK, "PLAN.md")
            commit(TASK, "NOTE.md")
            return "готово"
        result = area(TASK, body)
    assert result == "готово"
    assert ref_pushes(calls) == []
    assert (len(journal(TASK, PUSH_OK)),
            len(journal(TASK, PUSH_FAILED))) == before


def test_ac9_empty_set_no_git_on_exit(synced):
    """Тело без коммитов — выход из команды не зовёт git вовсе.

    Сценарий: тело `run_locked` ничего не пишет и возвращает значение;
    шпион процессов стоит на всё время команды. Ни одного вызова git, в
    том числе `remote get-url origin`.

    Ловит мутацию: выход из области проверяет origin (`remote get-url`) или
    перебирает задачи через git до проверки пустоты набора — в шпионе
    появляется вызов git.
    """
    with git_spy() as calls:
        result = area(TASK, lambda: "готово")
    assert result == "готово"
    assert calls == []


def test_ac13_outside_area_send_right_after_update_ref(synced):
    """Вне команды коммит документов отправляется сразу после `update-ref`.

    Сценарий: `commit_files` без открытой области. Хвост вызовов git после
    `update-ref` ссылки — ровно `remote get-url origin` и
    `push -q origin <ref>:<ref>`, как до задачи; к возврату `commit_files`
    ссылка в origin равна локальной.

    Ловит мутацию: признак «область открыта» не сбрасывается после выхода
    из `run_locked` (счётчик вложенности не уменьшается) — вне команды
    коммит после первой команды попадает в набор, отправки после
    `update-ref` нет.
    """
    area(TASK, lambda: commit(TASK, "A.md"))
    with git_spy() as calls:
        head = commit(TASK, "PLAN.md")
    origin, local = lags(synced)
    ref = synced.ref
    marks = [i for i, c in enumerate(calls) if c[:2] == ("update-ref", ref)]
    assert head
    assert len(marks) == 1, calls
    assert calls[marks[0] + 1:] == [("remote", "get-url", "origin"),
                                    ("push", "-q", "origin", f"{ref}:{ref}")], calls
    assert origin == local == head
