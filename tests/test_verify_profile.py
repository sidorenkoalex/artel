"""Профиль проверок `verify` на `verifying`: свойства из ответа Оператора
ANSWER-1 SPEC 01M6F3DKM3KB2JYMD0J50YRBPE, не покрытые долгоживущими файлами
задачи.

Стенд — `Stand` долгоживущего файла задачи (настоящий git песочницы,
проекты `gitlab` в локальном слое, CI — подделка хостинга по sha).
"""
from unittest import mock

from orchestrator import config, forge, store, targets, verify
from tests.test_01m6f3dkm3kb2jymd0j50yrbpe_verify_flow import (  # noqa: F401
    NOT_EXPECTED, OTHER_HEAD, TO_ESCALATED, TO_REVIEW, Stand, stand)


def test_new_head_inside_visit_needs_new_wait_and_marks(stand):
    """Смена головы внутри визита `verifying` (подтяжка `pull-main`):
    отметки прежней головы не действуют, ожидание — заново по новому sha
    после его зелёного CI; `waiting_on` — `ci`, пока CI новой головы идёт.

    Сценарий: профиль из двух проверок `a`, `b`; ожидание по голове X,
    `verify-ok a X`. Новый коммит без нового входа в `verifying` (голова
    Y), CI Y идёт — опрос: ожидания нет, `waiting_on` — `ci`, `verify-ok b
    X` — «отметка для другой головы», `verify-ok b Y` — «проверка не
    ожидается для этой головы». CI Y зелёный — опрос: «ждёт проверки a по
    sha Y» (отметка `a` по X не в счёт), `waiting_on` — `operator`;
    `verify-ok b Y` — задача в `verifying`; `verify-ok a Y` — `review`.

    Ловит мутацию: ожидание держится по визиту без сверки головы — опрос с
    головой Y не опрашивает CI и `verify-ok b Y` проходит до зелёного CI;
    отметки ищутся по визиту без sha — после `verify-ok b Y` задача уходит
    в `review` по отметке `a` головы X.
    """
    first, second = stand.check_name(), stand.check_name()
    while second == first:
        second = stand.check_name()
    stand.record([first, second])
    task, old, _rows, _out = stand.waiting_task()
    code, out, _r = stand.verify_ok(task, first, old, stand.text())
    assert code is None and stand.state(task) == "verifying", stand.why(task, out)
    new = stand.commit_code(task)
    stand.ci(task, forge.RUNNING)
    _rows, out = stand.poll(task)
    assert stand.state(task) == "verifying", stand.why(task, out)
    assert stand.waiting_on(task) == "ci", stand.why(task, out)
    code, out, rows = stand.verify_ok(task, second, old, stand.text())
    assert code is not None and OTHER_HEAD in out, stand.why(task, out)
    code, out, rows = stand.verify_ok(task, second, new, stand.text())
    assert code is not None and NOT_EXPECTED in out, stand.why(task, out)
    stand.ci(task, forge.GREEN)
    _rows, out = stand.poll(task)
    assert stand.visit_waits(task, first, new), stand.why(task, out)
    assert stand.waiting_on(task) == "operator", stand.why(task, out)
    code, out, _r = stand.verify_ok(task, second, new, stand.text())
    assert code is None and stand.state(task) == "verifying", stand.why(task, out)
    assert stand.status_waits(task, first, new), stand.why(task, out)
    code, out, _r = stand.verify_ok(task, first, new, stand.text())
    assert code is None and stand.state(task) == "review", stand.why(task, out)


def test_ceiling_still_applies_while_waiting_for_ci(stand):
    """У проекта с `verify` потолок `VERIFYING_CEILING_SEC` при ожидании
    CI (до записи «ждёт проверки») действует как прежде: эскалация.

    Сценарий: задача проекта `ext` в `verifying`, CI головы идёт, потолок
    подменён нулём — опрос: задача в `escalated`, текст перехода называет
    потолок ожидания CI; записи ожидания нет.

    Ловит мутацию: потолок снят для всего `verifying` проекта с профилем
    (а не только для ожидания отметки) — задача остаётся в `verifying`.
    """
    task = stand.new_task()
    stand.ci(task, forge.RUNNING)
    with mock.patch.object(config, "VERIFYING_CEILING_SEC", 0):
        rows, out = stand.poll(task)
    escalations = [r for r in rows if r["action"] == TO_ESCALATED]
    assert stand.state(task) == "escalated", stand.why(task, out)
    assert escalations and "потолок ожидания CI" in escalations[-1]["detail"], \
        stand.why(task, out)
    assert not stand.visit_waits(task, stand.checks[0], stand.head(task)), \
        stand.why(task, out)


def test_empty_verify_is_same_as_absent_field(stand):
    """`verify: []` — то же, что отсутствие поля: запись загружается, и
    задача по зелёному CI уходит из `verifying` в `review` без ожидания.

    Сценарий: запись `ext` с `verify: []`; `targets.verify_checks` —
    пусто; задача в `verifying`, CI зелёный, опрос — `review`, записи
    ожидания нет, `waiting_on` — не `operator`.

    Ловит мутацию: пустой список читается как непустой профиль (ожидание
    без проверок) или как недопустимое значение — задача остаётся в
    `verifying`.
    """
    stand.record([])
    assert targets.verify_checks(targets.target(stand.ext)) == []
    task = stand.new_task()
    stand.ci(task, forge.GREEN)
    rows, out = stand.poll(task)
    assert stand.state(task) == "review", stand.why(task, out)
    assert TO_REVIEW in [r["action"] for r in rows], stand.why(task, out)
    assert not [r for r in rows if r["action"] == verify.WAIT_ACTION], \
        stand.why(task, out)
    assert stand.waiting_on(task) != "operator", stand.why(task, out)


def test_operator_is_actor_of_verify_transitions(stand):
    """Переходы `verify-ok`/`verify-fail` и их записи — автора `operator`.

    Сценарий: две задачи в ожидании отметки; `verify-ok` первой — запись
    `state -> review` и запись отметки автора `operator`; `verify-fail`
    второй — запись `state -> in_dev` и запись возврата автора `operator`.

    Ловит мутацию: переход пишется автором `fsm` — надзор эпика не видит
    в нём действия Оператора и не подхватывает задачу после отметки.
    """
    task, sha, _rows, _out = stand.waiting_task()
    code, out, rows = stand.verify_ok(task, stand.checks[0], sha, stand.text())
    assert code is None, stand.why(task, out)
    actors = {r["action"]: r["actor"] for r in rows}
    assert actors.get(TO_REVIEW) == "operator", stand.why(task, out)
    assert actors.get(verify.OK_ACTION) == "operator", stand.why(task, out)
    other, _sha, _rows, _out = stand.waiting_task()
    code, out, rows = stand.verify_fail(other, stand.checks[0], stand.text())
    assert code is None, stand.why(other, out)
    actors = {r["action"]: r["actor"] for r in rows}
    assert actors.get("state -> in_dev") == "operator", stand.why(other, out)
    assert actors.get(verify.FAIL_ACTION) == "operator", stand.why(other, out)
    assert store.get_task(stand.conn, other)["verify_fails"] == 1
