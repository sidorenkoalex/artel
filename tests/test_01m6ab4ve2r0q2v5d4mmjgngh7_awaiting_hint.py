"""Подсказка состояния `awaiting_human` после появления `mr-sync`: без «(шаг Б2.2)», с именем команды.

Группа: долгоживущий
Красен до реализации: `fsm.AWAITING_HUMAN_HINT` и подсказка `awaiting_human` в `config.AUTO_STOP` несут «(шаг Б2.2)» — отказ `approve`/`reject`/`answer`/`amend-tests` и совет остановки `auto` для задачи в `awaiting_human` его содержат.

Песочница — `light_transition` (`LightTransitionSandbox`: задача артели,
заведённая `cmd_new`, `gitcmd.git` — подделка, `gitcmd.in_repo` —
подмена с хуками). Состояние `awaiting_human` ставится прямой установкой в
БД. Свойство держит связку «команда — FSM — база»: команда читает
состояние строки задачи и печатает подсказку. Основания и тексты ответа —
из `random`, зерно печатается и входит в текст провала.

Подсказка `config.AUTO_STOP["awaiting_human"]` (SPEC: «подсказка
`awaiting_human` в `config.py:941-943`») строкой `status` не печатается —
её показывает совет остановки `auto` (`auto.auto_stop_advice`); `status`
проверяется на отсутствие «(шаг Б2.2)».

Провалидировано временным стабом (удалён, не закоммичен): «(шаг Б2.2)»
убран из `fsm.AWAITING_HUMAN_HINT` и `config.AUTO_STOP` — все методы
зелёные.
"""
import contextlib
import io
import random

import pytest

from orchestrator import amend, answer, auto, catalog, config, fsm, store

STATE = "awaiting_human"
OLD_STEP = "(шаг Б2.2)"
COMMAND = "mr-sync"
WORDS = ("ветка", "ревью", "проект", "люди", "слияние", "основание", "правка")


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def sandbox(light_transition, monkeypatch):
    """Лёгкая песочница без роли в окружении: команды идут от Оператора."""
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    return light_transition


def words(rng: random.Random) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(rng.randrange(2, 6)))


def run(fn, *args) -> str:
    """Вывод команды (stdout, stderr и текст `SystemExit`) одной строкой."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


@pytest.mark.parametrize("command", ["approve", "reject", "answer", "amend-tests"])
def test_ac19_refusals_name_mr_sync_without_step(sandbox, seed, command):
    """Отказ `approve`/`reject`/`answer`/`amend-tests` по задаче в `awaiting_human` называет `mr-sync` и не несёт «(шаг Б2.2)».

    Сценарий: задача песочницы в `awaiting_human` (для `amend-tests` — со
    случайным `tests_locked_sha`, иначе команда отказала бы раньше своей
    причиной); команда Оператора со случайным основанием или файлом
    ответа. Вывод команды содержит «mr-sync» и не содержит «(шаг Б2.2)»;
    задача в `awaiting_human`.

    Ловит мутацию: «(шаг Б2.2)» убран только из одной точки (константа
    `fsm` правлена, а одна из команд печатает свой текст) — вывод этой
    команды его несёт; либо подсказка переписана без имени `mr-sync`.
    """
    rng = random.Random(seed)
    sandbox.set_state(STATE)
    if command == "approve":
        out = run(fsm.cmd_approve, sandbox.TASK)
    elif command == "reject":
        out = run(fsm.cmd_reject, sandbox.TASK, words(rng))
    elif command == "answer":
        path = sandbox.root / f"answer-{rng.randrange(10 ** 6)}.md"
        path.write_text(f"Ответ Оператора: {words(rng)}\n", encoding="utf-8")
        out = run(answer.cmd_answer, sandbox.TASK, str(path))
    else:
        locked = "".join(rng.choice("0123456789abcdef") for _ in range(40))
        store.update_task(store.db(), sandbox.TASK, tests_locked_sha=locked)
        out = run(amend.cmd_amend_tests, sandbox.TASK, words(rng))
    note = f"зерно: {seed}; команда {command}:\n{out}"
    assert COMMAND in out, note
    assert OLD_STEP not in out, note
    assert sandbox.state() == STATE, note


def test_ac19_state_hint_names_mr_sync_without_step(sandbox, seed):
    """Подсказка состояния `awaiting_human` (`config.AUTO_STOP`, её печатает остановка `auto`) называет `mr-sync` и не несёт «(шаг Б2.2)»; `status` её прежнего текста не несёт.

    Сценарий: задача песочницы в `awaiting_human`; совет остановки
    `auto.auto_stop_advice` для этого состояния (причина и подсказка —
    текст `config.AUTO_STOP["awaiting_human"]`, SPEC: `config.py:941-943`)
    содержит «mr-sync» и не содержит «(шаг Б2.2)»; вывод
    `catalog.cmd_status` не содержит «(шаг Б2.2)».

    Ловит мутацию: правлена только `fsm.AWAITING_HUMAN_HINT`, а подсказка
    состояния `awaiting_human` в `config` осталась прежней — совет
    остановки несёт «(шаг Б2.2)»; либо подсказка переписана без имени
    `mr-sync`.
    """
    sandbox.set_state(STATE)
    reason, hint = auto.auto_stop_advice(store.db(), sandbox.TASK, STATE)
    out = run(catalog.cmd_status)
    note = f"зерно: {seed}:\nсовет: {reason} | {hint}\nstatus:\n{out}"
    assert COMMAND in hint, note
    assert OLD_STEP not in f"{reason} {hint}", note
    assert OLD_STEP not in out, note
