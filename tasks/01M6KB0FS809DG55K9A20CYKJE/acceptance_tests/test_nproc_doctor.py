"""Строка `doctor` предела процессов шага: статус, пометки, показанное ограничение.

Группа: разовый
Красен до реализации: точек подмены `runner._read_maxprocperuid`/`runner._user_process_count` нет — `mock.patch.object` падает AttributeError; строки с ограничением шага в `doctor.all_checks` нет.

Файл разовый по тому же доводу, что `test_nproc_step.py`: подменяются
закрытые точки, назначенные SPEC (решение Оператора Н-1).

Связка: «`doctor.all_checks` — `runner.role_nproc_limit`». Песочница —
фикстура `tmp_root` (`TmpRootTest`) со схемой БД; живой смок CLI роли
заменён заготовкой (`doctor._live_smoke_run`, как в
`tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`). Строка
находится по содержимому: в ней одновременно ограничение шага M и число
процессов N (или пометка «счёт недоступен»); N и V случайны, зерно
печатается и входит в текст провала.

Провалидировано временным стабом строки и `runner` (удалён, не
закоммичен): все методы зелёные; мутация границы `N > M` красит
вариант `equal`.
"""
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _step import (process_count, read_maxproc, seeded,  # noqa: E402
                   subprocess_answers)
from orchestrator import config, doctor, runner, store  # noqa: E402

UNAVAILABLE = "счёт недоступен"
DEFAULT = "значение по умолчанию"


@pytest.fixture
def pult(tmp_root):
    store.create_schema(store.db())
    smoke = doctor.Check("live-smoke", "ok", "живой смок заменён тестом")
    with mock.patch.object(doctor, "_live_smoke_run", lambda role: smoke):
        yield tmp_root


def limit_and_rows(patches, count_shown) -> tuple:
    """(M при подменах, строки doctor с M и `count_shown` в тексте)."""
    with ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        limit = runner.role_nproc_limit()
        checks = doctor.all_checks(store.db())
    rows = [c for c in checks
            if str(limit) in c.detail and str(count_shown) in c.detail]
    return limit, rows, checks


def show(checks) -> str:
    return "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)


def plain_limit(value) -> int:
    with read_maxproc(value):
        return runner.role_nproc_limit()


@pytest.mark.parametrize("delta", ["equal", "above", "below"])
def test_ac7_status_follows_count_against_step_limit(pult, delta):
    """N ≥ M — `warn` (в том числе N = M), N < M — `ok`; строка показывает M шага.

    Сценарий: `_read_maxprocperuid` → `(V, "ok")` со случайным V;
    `_user_process_count` → N = M ("equal"), M + k ("above") или M − k
    ("below"); строка находится по M и N в тексте.

    Ловит мутацию: граница строгая (`N > M`) — при N = M строка `ok`;
    либо строка сравнивает N с `kern.maxprocperuid`, а не с
    ограничением шага, — при N чуть выше M строка `ok`; либо строка
    считает ограничение своей формулой без вычета запаса — M в тексте
    не совпадает с `role_nproc_limit()`.
    """
    rng = seeded()
    value = (rng.randint(config.ROLE_NPROC_RESERVE + 50, 200000), "ok")
    limit = plain_limit(value)
    count = {"equal": limit, "above": limit + rng.randint(1, 300),
             "below": limit - rng.randint(1, max(1, limit - 1))}[delta]
    _, rows, checks = limit_and_rows(
        [read_maxproc(value), process_count(return_value=count)], count)
    note = f"зерно {rng.seed_value}, V={value}, N={count}, M={limit}\n{show(checks)}"
    assert len(rows) == 1, note
    assert rows[0].status == ("ok" if delta == "below" else "warn"), note


@pytest.mark.parametrize("outcome", ["failed", "absent"])
def test_ac7_default_value_marked_ok(pult, outcome):
    """`kern.maxprocperuid` недоступен — строка `ok` с пометкой «значение по умолчанию».

    Сценарий: `_read_maxprocperuid` → `(None, outcome)`, N < M.

    Ловит мутацию: недоступность параметра поднимает строку до `warn`
    либо пометка ставится только на исход "failed" — у "absent" её нет.
    """
    rng = seeded()
    limit = plain_limit((None, outcome))
    count = limit - rng.randint(1, max(1, limit - 1))
    _, rows, checks = limit_and_rows(
        [read_maxproc((None, outcome)), process_count(return_value=count)], count)
    note = f"зерно {rng.seed_value}, N={count}, M={limit}\n{show(checks)}"
    assert len(rows) == 1, note
    assert rows[0].status == "ok", note
    assert DEFAULT in rows[0].detail, note


@pytest.mark.parametrize("outcome", ["failed", "absent"])
def test_ac7_both_sources_unavailable_warn_with_both_marks(pult, outcome):
    """Нет ни `kern.maxprocperuid`, ни счёта — `warn` с пометками «счёт недоступен» и «значение по умолчанию».

    Сценарий: `_read_maxprocperuid` → `(None, outcome)`,
    `_user_process_count` бросает RuntimeError.

    Ловит мутацию: пометки взаимоисключающие (первая найденная
    недоступность прячет вторую) — в тексте одна из двух; либо сбой
    счёта роняет `doctor` исключением.
    """
    limit = plain_limit((None, outcome))
    _, rows, checks = limit_and_rows(
        [read_maxproc((None, outcome)),
         process_count(side_effect=RuntimeError("ps не ответил"))], UNAVAILABLE)
    note = f"M={limit}\n{show(checks)}"
    assert len(rows) == 1, note
    assert rows[0].status == "warn", note
    assert DEFAULT in rows[0].detail, note


def test_ac7_sysctl_missing_does_not_break_doctor(pult):
    """`subprocess.run` бросает FileNotFoundError на `sysctl` — строка `ok` с «значение по умолчанию», `doctor` цел.

    Сценарий: `_read_maxprocperuid` НЕ подменена; подменённый
    `subprocess.run` бросает FileNotFoundError на команду `sysctl`,
    прочие команды идут как прежде; `_user_process_count` → N < M.
    M считается `role_nproc_limit()` при тех же подменах.

    Ловит мутацию: `_read_maxprocperuid` ловит только
    `CalledProcessError`/`OSError` подкласса ниже — FileNotFoundError
    выходит наружу и роняет `all_checks`; либо строка при недоступном
    параметре пометку не ставит.
    """
    rng = seeded()
    missing = subprocess_answers({"sysctl": FileNotFoundError("sysctl")})
    with missing:
        limit = runner.role_nproc_limit()
    count = limit - rng.randint(1, max(1, limit - 1))
    shown, rows, checks = limit_and_rows(
        [subprocess_answers({"sysctl": FileNotFoundError("sysctl")}),
         process_count(return_value=count)], count)
    note = f"зерно {rng.seed_value}, N={count}, M={limit}\n{show(checks)}"
    assert shown == limit, note
    assert len(rows) == 1, note
    assert rows[0].status == "ok", note
    assert DEFAULT in rows[0].detail, note


def test_ac8_count_failure_marks_doctor_row(pult):
    """`_user_process_count` бросает — строка `doctor` `warn` с пометкой «счёт недоступен».

    Сценарий: `_read_maxprocperuid` → `(V, "ok")`, счёт бросает
    RuntimeError; строка находится по M и пометке.

    Ловит мутацию: сбой счёта показывается как ноль процессов — строка
    `ok` без пометки.
    """
    rng = seeded()
    value = (rng.randint(config.ROLE_NPROC_RESERVE + 50, 200000), "ok")
    limit, rows, checks = limit_and_rows(
        [read_maxproc(value),
         process_count(side_effect=RuntimeError("ps не ответил"))], UNAVAILABLE)
    note = f"зерно {rng.seed_value}, V={value}, M={limit}\n{show(checks)}"
    assert len(rows) == 1, note
    assert rows[0].status == "warn", note


@pytest.mark.parametrize("output", ["", "нет числа\n"])
def test_ac8_empty_ps_output_marks_doctor_row(pult, output):
    """Пустой вывод `ps` либо код 0 без числа — строка `warn` с пометкой «счёт недоступен».

    Сценарий: `_user_process_count` не подменена; подменённый
    `subprocess.run` отвечает на `ps` кодом 0 с выводом `output`.

    Ловит мутацию: пустой вывод засчитывается как ноль процессов —
    строка `ok` без пометки.
    """
    rng = seeded()
    value = (rng.randint(config.ROLE_NPROC_RESERVE + 50, 200000), "ok")
    limit, rows, checks = limit_and_rows(
        [read_maxproc(value), subprocess_answers({"ps": (0, output)})],
        UNAVAILABLE)
    note = f"зерно {rng.seed_value}, V={value}, M={limit}\n{show(checks)}"
    assert len(rows) == 1, note
    assert rows[0].status == "warn", note
