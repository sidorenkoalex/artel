"""Ограничение шага роли: вычисление, передача в `spawn_agent`, отказ при исчерпанном запасе, журнал.

Группа: разовый
Красен до реализации: точек подмены `runner._read_maxprocperuid`/`runner._user_process_count` и функции `runner.role_nproc_limit` ещё нет — `mock.patch.object` и вызов падают AttributeError, `cmd_run` не передаёт `nproc_limit`.

Файл разовый: его тесты подменяют закрытые точки, которые назначил SPEC
(решения Оператора Н-1, Н-4), а правила долгоживущих файлов `tests/`
закрытые имена запрещают. Свойства запуска настоящего процесса — в
долгоживущем файле задачи.

Связка: «`runner.cmd_run` — журнал задачи — `runner.spawn_agent`
(подменён `FakeProc`)», для AC-5 ещё «цикл `auto.cmd_auto` — алерты».
Песочница — `_step.step_sandbox` (`DeveloperBriefTmpRootTest`).
Входы (значения `kern.maxprocperuid`, ограничения пульта, счёт
процессов) порождаются `random`; зерно печатается и входит в текст
провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
все методы зелёные; мутация границы `N > M` красит оба варианта
`equal`.
"""
import io
import resource
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _step import (WARNING_COUNT, actions, journal, journal_text,  # noqa: E402
                   nproc_rlimit, one_attempt_agent, process_count,
                   read_maxproc, refusal_text, seeded, step_sandbox,
                   subprocess_answers, failing_agent)
from orchestrator import alerts, auto, config, runner, store, zone_lock  # noqa: E402

INF = resource.RLIM_INFINITY


def finite_min(*values):
    return min(v for v in values if v != INF)


# --- AC-1: шаг передаёт ограничение в spawn_agent --------------------------

def test_ac1_cmd_run_passes_role_limit_to_spawn_agent():
    """Шаг `runner.cmd_run` зовёт `spawn_agent` с `nproc_limit`, равным `role_nproc_limit()` того же шага.

    Сценарий: `kern.maxprocperuid` подменён случайным V (исход "ok"),
    счёт процессов — 1; шаг developer в `in_dev` запускается
    `runner.cmd_run`, агент — `FakeProc` подменённого `spawn_agent`.
    Аргумент `nproc_limit` вызова равен `runner.role_nproc_limit()`,
    вычисленному тестом при тех же подменах.

    Ловит мутацию: шаг вычисляет ограничение, но не передаёт его в
    `spawn_agent` (вызов без `nproc_limit`) — в kwargs вызова нет ключа;
    либо передаёт V без вычета запаса — число вызова на
    `ROLE_NPROC_RESERVE` больше `role_nproc_limit()`.
    """
    rng = seeded()
    value = rng.randint(config.ROLE_NPROC_RESERVE + 10, 200000)
    with step_sandbox() as (box, task), read_maxproc((value, "ok")), \
            process_count(return_value=1), one_attempt_agent() as spawn:
        box.capture(runner.cmd_run, task)
        expected = runner.role_nproc_limit()
        note = f"зерно {rng.seed_value}, V={value}\n{journal_text(journal(task))}"
    assert spawn.call_count == 1, note
    assert spawn.call_args.kwargs.get("nproc_limit") == expected, \
        (spawn.call_args, expected, note)


# --- AC-3: значение по умолчанию и запись-предупреждение --------------------

@pytest.mark.parametrize("outcome", ["failed", "absent"])
def test_ac3_fallback_limit_keeps_min_over_pult_limits(outcome):
    """Без `kern.maxprocperuid` ограничение считается от `ROLE_NPROC_FALLBACK_MAXPROC` с тем же min.

    Сценарий: `_read_maxprocperuid` → `(None, outcome)`;
    `resource.getrlimit(RLIMIT_NPROC)` подменён случайными парами
    (конечные выше и ниже `FALLBACK − RESERVE`, бесконечные). Ожидание —
    min(FALLBACK − RESERVE, конечные из мягкого и жёсткого пульта).

    Ловит мутацию: при исходе не "ok" функция отдаёт
    `FALLBACK − RESERVE`, не сверяясь с пределами пульта (min потерян) —
    на паре с мягким пределом ниже этого числа результат больше
    мягкого предела; либо подставляет FALLBACK без вычета запаса.
    """
    rng = seeded()
    base = config.ROLE_NPROC_FALLBACK_MAXPROC - config.ROLE_NPROC_RESERVE
    pairs = [(INF, INF)]
    for _ in range(6):
        hard = rng.choice([INF, rng.randint(2, base * 3)])
        top = base * 3 if hard == INF else hard
        soft = rng.choice([INF if hard == INF else hard, rng.randint(1, top)])
        pairs.append((soft, hard))
    pairs.append((max(1, base // 2), INF))
    for soft, hard in pairs:
        with read_maxproc((None, outcome)), nproc_rlimit(soft, hard):
            got = runner.role_nproc_limit()
        assert got == finite_min(base, soft, hard), \
            (f"зерно {rng.seed_value}", outcome, soft, hard, got)


def step_actions(maxproc) -> tuple:
    """Записи шага из всех попыток при подменённом чтении `kern.maxprocperuid`."""
    with step_sandbox() as (box, task), read_maxproc(maxproc), \
            process_count(return_value=1), failing_agent() as spawn:
        box.capture(runner.cmd_run, task)
        rows = journal(task)
    return spawn.call_count, rows


def test_ac3_failed_read_journals_one_warning_absent_none():
    """Сбой чтения даёт ровно одну лишнюю запись на шаг из нескольких попыток, отсутствие параметра — ни одной.

    Сценарий: три одинаковых шага developer (каждая попытка rc=1, все
    `AGENT_ATTEMPTS` попыток) в свежих песочницах: эталон с `(V, "ok")`, затем
    `(None, "failed")` и `(None, "absent")`. Записи журнала (актор,
    действие) сравниваются с эталоном: у "failed" ровно одна лишняя
    запись, ни одной пропавшей; у "absent" набор совпадает с эталоном.

    Ловит мутацию: предупреждение пишется на каждую попытку — у
    "failed" две лишние записи; либо выбор записи идёт не по исходу, а
    по одному «значение не прочитано» — у "absent" тоже появляется
    лишняя запись; либо предупреждения нет вовсе — лишних записей ноль.
    """
    rng = seeded()
    value = rng.randint(config.ROLE_NPROC_RESERVE + 10, 200000)
    calls_ok, base_rows = step_actions((value, "ok"))
    calls_failed, failed_rows = step_actions((None, "failed"))
    calls_absent, absent_rows = step_actions((None, "absent"))
    note = (f"зерно {rng.seed_value}\nэталон:\n{journal_text(base_rows)}\n"
            f"failed:\n{journal_text(failed_rows)}\n"
            f"absent:\n{journal_text(absent_rows)}")
    assert calls_ok == calls_failed == calls_absent == config.AGENT_ATTEMPTS > 1, note
    base = actions(base_rows)
    extra = actions(failed_rows) - base
    assert sum(extra.values()) == 1, (extra, note)
    assert not (base - actions(failed_rows)), note
    assert actions(absent_rows) == base, note


@pytest.mark.skipif(sys.platform != "darwin",
                    reason="kern.maxprocperuid есть только на macOS")
@pytest.mark.parametrize("output", ["", "kern.maxprocperuid: нет\n"])
def test_ac3_empty_or_numberless_sysctl_is_failed_on_macos(output):
    """Пустой вывод `sysctl` или код 0 без числа — исход `(None, "failed")` на macOS.

    Сценарий: `subprocess.run` подменён — команда `sysctl` отвечает
    кодом 0 с выводом `output`; `runner._read_maxprocperuid()`.

    Ловит мутацию: разбор вывода падает ValueError наружу либо
    принимает пустой вывод за «параметра нет» — исход "absent" вместо
    "failed" (тогда предупреждение в журнал не пишется).
    """
    with subprocess_answers({"sysctl": (0, output)}):
        assert runner._read_maxprocperuid() == (None, "failed")


# --- AC-4: оба предела пульта бесконечны ------------------------------------

def test_ac4_infinite_pult_limits_give_first_term():
    """При бесконечных пределах пульта ограничение — V − RESERVE либо FALLBACK − RESERVE.

    Сценарий: `resource.getrlimit(RLIMIT_NPROC)` →
    `(RLIM_INFINITY, RLIM_INFINITY)`; `_read_maxprocperuid` → `(V, "ok")`
    для нескольких случайных V, затем `(None, "failed")` и
    `(None, "absent")`.

    Ловит мутацию: `RLIM_INFINITY` участвует в min как число — на
    Linux (−1) результат −1, на macOS результат не меняется, но тест с
    подменой видит отрицательное либо огромное значение; либо при
    исходе "ok" подставляется FALLBACK — результат не равен V − RESERVE.
    """
    rng = seeded()
    with nproc_rlimit(INF, INF):
        for _ in range(5):
            value = rng.randint(config.ROLE_NPROC_RESERVE + 1, 500000)
            with read_maxproc((value, "ok")):
                got = runner.role_nproc_limit()
            assert got == value - config.ROLE_NPROC_RESERVE, \
                (f"зерно {rng.seed_value}", value, got)
        for outcome in ("failed", "absent"):
            with read_maxproc((None, outcome)):
                got = runner.role_nproc_limit()
            assert got == (config.ROLE_NPROC_FALLBACK_MAXPROC
                           - config.ROLE_NPROC_RESERVE), (outcome, got)


# --- AC-5: исчерпанный запас процессов --------------------------------------

def refused_step(state: str, rng, above: int):
    """Шаг в `state` при счёте N = M + above: (SystemExit, N, M, spawn, записи, захват зоны)."""
    with step_sandbox(state) as (box, task), \
            read_maxproc((rng.randint(config.ROLE_NPROC_RESERVE + 10, 200000), "ok")):
        limit = runner.role_nproc_limit()
        count = limit + above
        with process_count(return_value=count), one_attempt_agent() as spawn:
            with pytest.raises(SystemExit) as exc:
                box.capture(runner.cmd_run, task)
            rows = journal(task)
            occupied = zone_lock._occupies(store.db(), task)
    return exc.value, count, limit, spawn, rows, occupied


@pytest.mark.parametrize("delta", ["equal", "above"])
def test_ac5_cmd_run_refuses_with_named_reason(delta):
    """`runner.cmd_run` при N ≥ M выходит SystemExit «запас процессов пользователя исчерпан: N из M», агент не порождён.

    Сценарий: шаг test_author (`tests_writing`); счёт процессов подменён
    числом N = M (вариант "equal") либо N = M + k (k случайное > 0).

    Ловит мутацию: граница сравнения строгая (`N > M`) — при N = M шаг
    стартует и агент порождается; либо отказ — исход "skipped" из
    попытки вместо SystemExit, и `cmd_run` возвращается без исключения.
    """
    rng = seeded()
    above = 0 if delta == "equal" else rng.randint(1, 500)
    exc, count, limit, spawn, rows, _ = refused_step("tests_writing", rng, above)
    note = f"зерно {rng.seed_value}, N={count}, M={limit}\n{journal_text(rows)}"
    assert refusal_text(count, limit) in str(exc), (str(exc), note)
    assert spawn.call_count == 0, note
    assert "agent run started" not in [r["action"] for r in rows], note


def test_ac5_developer_refusal_leaves_no_zone_claim():
    """Отказ developer-шага по исчерпанному запасу — SystemExit с причиной, захвата зоны у задачи нет.

    Сценарий: шаг developer (`in_dev`), N ≥ M; после `SystemExit` задача
    зону не занимает (`zone_lock._occupies` ложно — последний маркер
    захвата снят).

    Ловит мутацию: проверка запаса стоит в `_cmd_run` до `try/finally`
    снятия захвата (или вне `_run_developer_step`) — «zone claimed»
    записан, а снятие не сделано, задача держит зону.
    """
    rng = seeded()
    exc, count, limit, spawn, rows, occupied = refused_step(
        "in_dev", rng, rng.randint(0, 300))
    note = f"зерно {rng.seed_value}, N={count}, M={limit}\n{journal_text(rows)}"
    assert refusal_text(count, limit) in str(exc), (str(exc), note)
    assert spawn.call_count == 0, note
    assert occupied is False, note


def test_ac5_auto_stops_with_alert_and_no_retry():
    """Цикл `auto` при N ≥ M: агент не порождён, цикл остановлен «run отказался стартовать», тревога открыта.

    Сценарий: задача в `in_dev` (PLAN без статуса — предварительный
    advance её не двигает), счёт N = M + k; `auto.cmd_auto(<id>)`.
    Ожидание: `spawn_agent` не вызван ни разу; вывод несёт причину и
    «run отказался стартовать»; запись «auto остановлен» одна; открыт
    алерт `attention`.

    Ловит мутацию: отказ сделан исходом попытки ("skipped") вместо
    SystemExit — `auto` не видит отказа стартовать, крутит шаги до
    предела, алерт «run отказался стартовать» не открывается; либо отказ
    попадает в ветку без тревоги (как пауза).
    """
    rng = seeded()
    with step_sandbox("in_dev") as (box, task), \
            read_maxproc((rng.randint(config.ROLE_NPROC_RESERVE + 10, 200000), "ok")):
        limit = runner.role_nproc_limit()
        count = limit + rng.randint(0, 300)
        before = len(journal(task))
        buf = io.StringIO()
        with process_count(return_value=count), one_attempt_agent() as spawn, \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                auto.cmd_auto(task)
            except SystemExit as exc:
                buf.write(f"\n{exc}")
        rows = journal(task)[before:]
        attention = alerts.open_alerts(store.db(), "attention")
    out = buf.getvalue()
    note = (f"зерно {rng.seed_value}, N={count}, M={limit}\nвывод:\n{out}\n"
            f"журнал:\n{journal_text(rows)}")
    assert spawn.call_count == 0, note
    assert refusal_text(count, limit) in out, note
    assert "run отказался стартовать" in out, note
    assert [r["action"] for r in rows].count("auto остановлен") == 1, note
    assert attention, note


# --- AC-8: счёт процессов недоступен ----------------------------------------

def count_unavailable_step(rng, count_patch) -> tuple:
    value = rng.randint(config.ROLE_NPROC_RESERVE + 10, 200000)
    with step_sandbox() as (box, task), read_maxproc((value, "ok")), \
            count_patch, failing_agent() as spawn:
        box.capture(runner.cmd_run, task)
        rows = journal(task)
    return spawn.call_count, rows


def test_ac8_count_failure_starts_step_with_one_warning():
    """`_user_process_count` бросает — шаг из нескольких попыток запущен, предупреждение о счёте одно, с причиной.

    Сценарий: `runner._user_process_count` бросает RuntimeError со
    случайной меткой; шаг developer, каждая попытка rc=1 (все
    `AGENT_ATTEMPTS`). Ожидание: агент порождён на каждой попытке;
    ровно одна запись с «счёт процессов пользователя недоступен: », и
    она несёт текст причины.

    Ловит мутацию: исключение счёта не ловится — шаг падает
    RuntimeError, агент не порождён; либо счёт и предупреждение — в
    каждой попытке — записей несколько; либо причина не попадает в запись.
    """
    rng = seeded()
    token = f"ps-сбой-{rng.randrange(1 << 20)}"
    calls, rows = count_unavailable_step(
        rng, process_count(side_effect=RuntimeError(token)))
    note = f"зерно {rng.seed_value}\n{journal_text(rows)}"
    warnings = [r for r in rows
                if WARNING_COUNT in f"{r['action']} {r['detail']}"]
    assert calls == config.AGENT_ATTEMPTS > 1, note
    assert len(warnings) == 1, note
    assert token in f"{warnings[0]['action']} {warnings[0]['detail']}", note


@pytest.mark.parametrize("output", ["", "нет числа\n"])
def test_ac8_empty_ps_output_is_count_unavailable(output):
    """Пустой вывод `ps` либо код 0 без числа — тот же исход «счёт недоступен»: шаг запущен, предупреждение одно.

    Сценарий: `_user_process_count` не подменена; подменённый
    `subprocess.run` на команду `ps` отвечает кодом 0 с выводом
    `output`; шаг из нескольких попыток.

    Ловит мутацию: пустой вывод засчитывается как ноль процессов —
    предупреждения нет; либо `int("")` падает ValueError мимо
    обработки — шаг не стартует.
    """
    rng = seeded()
    calls, rows = count_unavailable_step(
        rng, subprocess_answers({"ps": (0, output)}))
    note = f"зерно {rng.seed_value}\n{journal_text(rows)}"
    warnings = [r for r in rows
                if WARNING_COUNT in f"{r['action']} {r['detail']}"]
    assert calls == config.AGENT_ATTEMPTS > 1, note
    assert len(warnings) == 1, note
