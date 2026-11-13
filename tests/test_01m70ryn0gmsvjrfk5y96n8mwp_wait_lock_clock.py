"""Тест ожидания замка полных прогонов ловит свои мутации и не зависит от
скорости машины (AC-2, AC-3).

Группа: долгоживущий
Красен до реализации: метод `WaitAcquireTest::test_wait_reports_holder_once_per_holder_and_gives_up_at_limit` ждёт по настоящим часам (подмена `POLL_SEC`), а не на подменённом `suite_lock.time` — мутации «без предела» крутятся до предохранителя 10 с, медленный опрос даёт одного держателя вместо двух, `suite_lock.time` во время теста — модуль `time`.

Мутации «`on_wait` на каждом опросе» и «замок поверх живого держателя»
нынешний метод уже ловит — эти два варианта AC-2 зелёные и до реализации.

Предмет — сам метод `tests/test_suite_lock.py`: он исполняется в этом же
процессе (`unittest`), мутации `orchestrator.suite_lock.wait_acquire`
подставляются в память на время прогона, файл кода на диске не меняется.
Мутанты повторяют `wait_acquire` и обращаются к часам через атрибут `time`
модуля `suite_lock` — те же часы, что видит настоящая функция. Каждый
мутант несёт предохранитель по настоящим часам (`ESCAPE_SEC`): тест,
который не ограничил ожидание сам, видит исключение `MutationEscaped`, а
не зависание. Песочница метода — его собственная (`TmpRootTest`) без
подмены `config.ROOT`: без клона-заглушки с `git init`, файл замка — во
временном каталоге `config.LOGS`.

Провалидировано временным стабом метода (подмена `suite_lock.time`
объектом с часами, продвигаемыми `sleep`, и счётчиком 1000 вызовов на
`monotonic` и `sleep`), подставленным в память, не на диск: все методы
файла зелёные.
"""
import random
import time
import unittest
from unittest import mock

import pytest

from orchestrator import suite_lock
from tests import test_suite_lock
from tests.sandbox import ALL_CONFIG_ATTRS

pytestmark = pytest.mark.size("small")

METHOD = "test_wait_reports_holder_once_per_holder_and_gives_up_at_limit"
# Предел AC-2: мутация краснеет не дольше чем за столько секунд.
ESCAPE_SEC = 10.0
# Настоящие часы — ссылки до любого прогона метода: подмена глобального
# `time.monotonic` методом видна сравнением с ними.
REAL_MONOTONIC = time.monotonic
REAL_SLEEP = time.sleep


class MutationEscaped(Exception):
    """Мутант крутился дольше `ESCAPE_SEC` по настоящим часам."""


def make_rng():
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def make_mutant(kind: str):
    """`wait_acquire` с одной мутацией из строки «Ловит мутацию» метода."""
    escape_at = REAL_MONOTONIC() + ESCAPE_SEC

    def wait_acquire(task_id, kind_=suite_lock.KIND_GATE, limit_sec=0.0,
                     on_wait=None):
        suite_lock.deliver_journal()
        deadline = suite_lock.time.monotonic() + limit_sec
        seen = None
        while True:
            if REAL_MONOTONIC() > escape_at:
                raise MutationEscaped(kind)
            holder = suite_lock.acquire(task_id, kind=kind_)
            if holder is None:
                return None
            key = (holder.get("task_id"), holder.get("pid"))
            if kind == "on_wait_every_poll" or key != seen:
                seen = key
                on_wait(holder)
            # Часы модуля — те, что подменяет метод: настоящая пауза здесь
            # только у метода, который часы не подменил.
            clock = suite_lock.time
            remaining = deadline - clock.monotonic()
            if kind == "no_limit":
                clock.sleep(suite_lock.POLL_SEC)
                continue
            if kind == "no_limit_no_pause":
                continue
            if remaining <= 0:
                if kind == "over_live_holder":
                    suite_lock.path().unlink()
                    return suite_lock.acquire(task_id, kind=kind_)
                return holder
            clock.sleep(min(suite_lock.POLL_SEC, remaining))

    return wait_acquire


def run_wait_test() -> unittest.TestResult:
    """Прогон метода в этом процессе; итог — `unittest.TestResult`."""

    class Case(test_suite_lock.WaitAcquireTest):
        PATCHED_ATTRS = tuple(a for a in ALL_CONFIG_ATTRS if a != "ROOT")

    result = unittest.TestResult()
    Case(METHOD).run(result)
    return result


def outcome_text(result: unittest.TestResult) -> str:
    return "\n".join(text for _case, text in result.errors + result.failures)


def green(result: unittest.TestResult) -> bool:
    return (result.testsRun == 1 and result.wasSuccessful()
            and not result.skipped)


@pytest.mark.parametrize("kind", ["on_wait_every_poll", "over_live_holder",
                                  "no_limit", "no_limit_no_pause"])
def test_ac2_mutation_turns_wait_test_red_within_limit(kind):
    """Каждая мутация `wait_acquire` даёт красный метод быстрее 10 с.

    Сценарий: `suite_lock.wait_acquire` на время прогона метода заменён
    мутантом — `on_wait` на каждом опросе; на пределе замок снят и взят
    поверх живого держателя; ожидание без предела с паузой опроса; без
    предела и без паузы (опрос по-прежнему читает `monotonic`). Метод
    обязан упасть своим утверждением или исключением своего счётчика
    опросов, а не предохранителем мутанта, и уложиться в 10 с.

    Ловит мутацию: счётчик опросов стоит только на подменённом `sleep`
    (мутант без паузы крутится до предохранителя — `MutationEscaped` в
    итоге); метод по-прежнему ждёт по настоящим часам с `POLL_SEC` 0,01
    (мутант без предела крутится 10 с до предохранителя); утверждение на
    `seen` ослаблено до «держатель среди записей» (мутант «на каждом
    опросе» зелёный).
    """
    started = REAL_MONOTONIC()
    with mock.patch.object(suite_lock, "wait_acquire", make_mutant(kind)):
        result = run_wait_test()
    elapsed = REAL_MONOTONIC() - started

    text = outcome_text(result)
    assert result.testsRun == 1, text
    assert not green(result), f"мутация {kind}: метод зелёный"
    assert "MutationEscaped" not in text, (
        f"мутация {kind}: метод не ограничил ожидание сам\n{text}")
    assert elapsed < ESCAPE_SEC, f"мутация {kind}: {elapsed:.1f} с"


def test_ac3_wait_test_runs_on_module_clock_and_survives_slow_polls():
    """Метод зелёный, когда каждый опрос дольше предела по настоящим часам.

    Сценарий: каждый вызов `suite_lock.acquire` во время прогона метода
    предварён настоящей паузой случайной длины 0,25–0,45 с (больше предела
    ожидания 0,2 с) и записывает, что видит: атрибут `time` модуля
    `suite_lock` и глобальный `time.monotonic`. Метод зелёный; на каждом
    опросе `suite_lock.time` — не модуль `time`, у него есть `monotonic`,
    `sleep` и `time`; глобальный `time.monotonic` — настоящий; после
    прогона `suite_lock.time` снова модуль `time`.

    Ловит мутацию: метод оставлен на подмене `POLL_SEC` и настоящих часах
    (второе ожидание сдаётся после первого же опроса — `calls` с одним
    держателем, метод красный, `suite_lock.time` — модуль `time`); подменён
    глобальный `time.monotonic` вместо атрибута модуля (запись опроса
    видит не настоящие часы); подмена не снята после метода.
    """
    seed, rng = make_rng()
    pause = rng.uniform(0.25, 0.45)
    original_acquire = suite_lock.acquire
    seen_clocks = []

    def slow_acquire(*args, **kwargs):
        REAL_SLEEP(pause)
        seen_clocks.append((suite_lock.time, time.monotonic is REAL_MONOTONIC))
        return original_acquire(*args, **kwargs)

    with mock.patch.object(suite_lock, "acquire", slow_acquire):
        result = run_wait_test()

    tag = f"зерно {seed}, пауза {pause:.2f} с"
    assert green(result), f"{tag}\n{outcome_text(result)}"
    assert seen_clocks, tag
    for clock, global_real in seen_clocks:
        assert clock is not time, f"{tag}: suite_lock.time — модуль time"
        for name in ("monotonic", "sleep", "time"):
            assert callable(getattr(clock, name, None)), f"{tag}: нет {name}"
        assert global_real, f"{tag}: глобальный time.monotonic подменён"
    assert suite_lock.time is time, f"{tag}: подмена не снята"


@pytest.mark.parametrize("kind", ["no_limit", "no_limit_no_pause"])
def test_ac3_poll_counter_stops_unbounded_wait_near_thousand_polls(kind):
    """Ожидание без предела обрывает счётчик метода около 1000 опросов.

    Сценарий: `wait_acquire` заменён мутантом без предела (с паузой опроса
    и без неё); вызовы `suite_lock.acquire` считаются. Метод красный не
    предохранителем мутанта, а своим исключением, и число опросов за весь
    метод — от 950 до 1050: счётчик бросает после 1000 опросов, а не
    раньше и не позже.

    Ловит мутацию: счётчика нет вовсе (опросы идут до предохранителя
    мутанта — десятки тысяч и `MutationEscaped`); предел счётчика
    100 или 10000 вместо 1000 (число опросов вне диапазона); счётчик на
    сумме вызовов `monotonic` и `sleep` (обрыв около 500 опросов).
    """
    original_acquire = suite_lock.acquire
    polls = []

    def counted_acquire(*args, **kwargs):
        polls.append(1)
        return original_acquire(*args, **kwargs)

    with mock.patch.object(suite_lock, "wait_acquire", make_mutant(kind)), \
            mock.patch.object(suite_lock, "acquire", counted_acquire):
        result = run_wait_test()

    text = outcome_text(result)
    assert not green(result), f"мутация {kind}: метод зелёный"
    assert "MutationEscaped" not in text, (
        f"мутация {kind}: {len(polls)} опросов до предохранителя\n{text}")
    assert 950 <= len(polls) <= 1050, f"мутация {kind}: {len(polls)} опросов"
