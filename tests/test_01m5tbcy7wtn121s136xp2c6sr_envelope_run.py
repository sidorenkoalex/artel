"""Проверка старта первого шага роли: конверт бюджета эпика и зависимость запуска `start_after`.

Группа: долгоживущий
Красен до реализации: команд `epic new`/`epic envelope`/`epic start-after` и таблицы `epics` нет — заведение эпика сценария падает отказом «Неизвестная команда epic», проверки конверта и `start_after` в `runner` нет.

Публичная поверхность: команды пульта — диспетчер `artel.main()` с argv
(`epic new <проект> "<название>" --goal … --envelope N` из SPEC шага Э1,
`epic envelope`, `epic start-after`, `status`, `epic show`); шаг роли —
`runner.cmd_run(<id>)`; привязка задачи к эпику — колонка `tasks.epic_id`
(SPEC Э1, требование 1); потрачено задачи — колонка `tasks.spent_usd`
(слагаемое `budget.spent_with_estimate`).

Связка, которую держит файл: «команда `run` — проверка перед стартом —
журнал — БД». Отказ перед стартом наблюдается так: агент
(`runner.spawn_agent`), подготовка рабочего каталога (`workspace.ensure`)
и предполётная проверка (`doctor.preflight_checks`) подменены; дошедший до
предполёта `run` останавливается исключением-меткой `ReachedPreflight` —
значит, проверки конверта и `start_after` его пропустили (требование 7
SPEC: обе стоят до pre-flight).

Суммы, состояния и id задач порождаются модулем `random` при каждом
запуске; зерно печатается и входит в текст провала.

Провалидировано временным стабом реализации Э1+Э2а (таблица `epics`, команды
`epic …`, проверки `runner`, алерт `budget`, строки `watch`, остановка
`auto`, граф `merge_after`; удалён, не закоммичен): все методы файла
зелёные; правдоподобные мутации стаба, названные в заявках, их красят.
"""
import io
import os
import random
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import pytest

from orchestrator import artel, budget, catalog, config, runner, store, workspace

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
STEP_STATES = ("tests_writing", "review")


class ReachedPreflight(Exception):
    """`run` прошёл проверки до предполёта — дальше сценарию идти незачем."""


class Pult:
    """Сценарий над лёгкой песочницей переходов: эпики, задачи, `run`."""

    def __init__(self, sandbox, seed: int):
        self.sandbox = sandbox
        self.seed = seed
        self.rng = random.Random(seed)
        self.counter = 0
        self.spawn = mock.Mock(side_effect=AssertionError("агент запущен"))
        self.ensure = mock.Mock(side_effect=AssertionError("рабочий каталог готовится"))
        self.preflight = mock.Mock(side_effect=ReachedPreflight())

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cli(self, *argv: str) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            artel.main()
        return buf.getvalue()

    def cli_refusal(self, *argv: str) -> str:
        """Текст отказа команды; команда, не отказавшая, — провал сценария."""
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                return f"{buf.getvalue()}\n{exc}"
        raise AssertionError(self.msg(f"{argv} не отказала:\n{buf.getvalue()}"))

    def new_epic(self, envelope=None) -> str:
        self.counter += 1
        title = f"Эпик сценария {self.seed:x}-{self.counter}"
        argv = ["epic", "new", config.DEFAULT_TARGET, title, "--goal",
                "Цель сценария"]
        if envelope is not None:
            argv += ["--envelope", f"{envelope}"]
        self.cli(*argv)
        row = store.db().execute("SELECT id FROM epics WHERE title=?",
                                 (title,)).fetchone()
        assert row is not None, self.msg(f"эпик «{title}» не заведён")
        return row["id"]

    def envelope(self, epic_id: str):
        return store.db().execute("SELECT envelope_usd FROM epics WHERE id=?",
                                  (epic_id,)).fetchone()["envelope_usd"]

    def new_task(self, state: str, epic_id: str | None = None,
                 spent: float = 0.0) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-konvert",
                          config.DEFAULT_TARGET, 1000.0)
        store.update_task(conn, task_id, spent_usd=spent)
        if epic_id is not None:
            store.update_task(conn, task_id, epic_id=epic_id)
        if state == "spec_writing":
            tdir = config.TASKS / task_id
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "TZ.md").write_text("# ТЗ сценария\n\nЦель.\n",
                                        encoding="utf-8")
        return task_id

    def set_state(self, task_id: str, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        conn.commit()

    def mark_started(self, task_id: str) -> None:
        role = runner.step_role(store.get_task(store.db(), task_id)) or "analyst"
        store.journal(store.db(), task_id, role, "agent run started",
                      "попытка 1/3, шаг сценария")

    def run(self, task_id: str) -> dict:
        """`run` задачи: исход (`preflight` | `exit` | `return`), текст и
        записи журнала задачи, добавленные этим вызовом (без записей lease)."""
        conn = store.db()
        before = len(store.task_steps(conn, task_id))
        buf = io.StringIO()
        outcome, text = "return", ""
        with mock.patch.object(runner, "spawn_agent", self.spawn), \
                mock.patch.object(workspace, "ensure", self.ensure), \
                mock.patch("orchestrator.doctor.preflight_checks", self.preflight), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                runner.cmd_run(task_id)
            except ReachedPreflight:
                outcome = "preflight"
            except SystemExit as exc:
                outcome, text = "exit", str(exc)
        rows = [r for r in store.task_steps(store.db(), task_id)[before:]
                if r["actor"] != "lease"]
        return {"outcome": outcome, "text": f"{buf.getvalue()}\n{text}",
                "rows": rows}

    def started(self, task_id: str) -> int:
        return sum(1 for r in store.task_steps(store.db(), task_id)
                   if r["action"] == "agent run started")


@pytest.fixture
def pult(light_transition):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield Pult(light_transition, seed)


def rows_text(rows) -> str:
    return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}" for r in rows)


def mentions(rows, word: str) -> list:
    return [r for r in rows if word in f"{r['action']} {r['detail']}".lower()]


def split_spent(rng, total: float, parts: int) -> list:
    """`total` по `parts` задачам эпика (целые центы, сумма точная)."""
    cents = round(total * 100)
    cuts = sorted(rng.randrange(cents + 1) for _ in range(parts - 1))
    bounds = [0, *cuts, cents]
    return [(bounds[i + 1] - bounds[i]) / 100 for i in range(parts)]


def exhausted_epic(pult, total: float) -> str:
    """Эпик с конвертом $10, по задачам которого (уже стартовавшим) потрачено `total`."""
    epic_id = pult.new_epic(10)
    for spent in split_spent(pult.rng, total, pult.rng.randint(1, 3)):
        donor = pult.new_task("in_dev", epic_id, spent)
        pult.mark_started(donor)
    return epic_id


def assert_envelope_refusal(pult, task_id: str, result: dict) -> None:
    note = pult.msg(f"исход {result['outcome']}; вывод:\n{result['text']}\n"
                    f"журнал:\n{rows_text(result['rows'])}")
    assert result["outcome"] == "exit", note
    assert "конверт" in result["text"].lower(), note
    assert mentions(result["rows"], "конверт"), note
    pult.spawn.assert_not_called()
    pult.ensure.assert_not_called()
    pult.preflight.assert_not_called()
    assert pult.started(task_id) == 0, note


def test_ac8_first_step_refused_when_envelope_exceeded(pult):
    """Перерасход конверта отказывает первому шагу аналитика до рабочего каталога и агента.

    Сценарий: эпик с конвертом $10, по его задачам потрачено $10,20
    (разложено по 1–3 задачам случайно); новая задача эпика в
    `spec_writing` с ТЗ, без единой записи «agent run started». `run`
    отказывает текстом о конверте, в журнале задачи — запись отказа с
    причиной «конверт», агент не запущен, `workspace.ensure` и
    предполёт не вызывались.

    Ловит мутацию: проверка конверта отсутствует или стоит после
    pre-flight — `run` доходит до `doctor.preflight_checks`, записи отказа
    о конверте нет.
    """
    exhausted = exhausted_epic(pult, 10.2)
    task_id = pult.new_task("spec_writing", exhausted)
    assert_envelope_refusal(pult, task_id, pult.run(task_id))


def test_ac9_spent_equal_to_envelope_refuses(pult):
    """Потрачено ровно $10,00 из $10 — первый шаг отказан проверкой конверта.

    Сценарий: эпик с конвертом $10, потрачено ровно $10,00; новая задача
    эпика в случайном агентском состоянии без «agent run started».

    Ловит мутацию: сравнение «потрачено > конверта» вместо «≥» — ровно
    исчерпанный конверт пропускает `run` до предполёта.
    """
    epic_id = exhausted_epic(pult, 10.0)
    task_id = pult.new_task(pult.rng.choice(STEP_STATES), epic_id)
    assert_envelope_refusal(pult, task_id, pult.run(task_id))


def test_ac10_refusal_record_does_not_count_as_first_step(pult):
    """Два `run` подряд при $10,20 из $10 отказаны оба.

    Сценарий: задача эпика без «agent run started»; первый `run`
    отказан и пишет запись отказа; второй `run` той же задачи отказан
    так же — запись отказа первого вызова первым шагом не считается.

    Ловит мутацию: «первый шаг» определяется по любой записи журнала роли
    (или по записи отказа) — второй `run` уходит до предполёта.
    """
    epic_id = exhausted_epic(pult, 10.2)
    task_id = pult.new_task(pult.rng.choice(STEP_STATES), epic_id)
    for _ in range(2):
        assert_envelope_refusal(pult, task_id, pult.run(task_id))


def test_ac12_started_task_gets_next_step_and_keeps_ceiling(pult):
    """Задача эпика с уже стартовавшим шагом при исчерпанном конверте получает следующий шаг.

    Сценарий: $10,20 из $10; задача эпика с записью «agent run started»
    и случайным потолком. `run` доходит до предполёта, записи об отказе
    по конверту нет, `budget_usd` задачи не изменён.

    Ловит мутацию: проверка конверта на каждом шаге роли (не только на
    первом) — `run` отказан; либо исчерпанный конверт урезает потолок
    задачи.
    """
    epic_id = exhausted_epic(pult, 10.2)
    task_id = pult.new_task(pult.rng.choice(STEP_STATES), epic_id)
    ceiling = float(pult.rng.randint(20, 90))
    store.update_task(store.db(), task_id, budget_usd=ceiling)
    pult.mark_started(task_id)
    result = pult.run(task_id)
    note = pult.msg(f"{result['text']}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "preflight", note
    assert mentions(result["rows"], "конверт") == [], note
    assert store.get_task(store.db(), task_id)["budget_usd"] == ceiling, note


def test_ac13_envelope_command_raise_lower_and_refusals(pult):
    """`epic envelope` поднимает и понижает конверт с записью журнала и отказывает негодному N.

    Сценарий: задача AC-8 ($10,20 из $10, первый шаг отказан). Подъём
    конверта выше потраченного пишет запись журнала, и следующий `run`
    той же задачи доходит до предполёта без отказа о конверте. Понижение
    принимается и тоже пишет запись. Неразборное N, `0` и отрицательное
    N — отказ команды, конверт прежний.

    Ловит мутацию: команда пишет конверт без записи журнала; проверка
    `run` читает конверт, закэшированный до подъёма; разбор пропускает
    `0`/отрицательное (условие `>= 0` вместо `> 0`) или неразборное
    значение становится `NULL`.
    """
    epic_id = exhausted_epic(pult, 10.2)
    task_id = pult.new_task("spec_writing", epic_id)
    assert_envelope_refusal(pult, task_id, pult.run(task_id))

    raised = pult.rng.choice([11, 15.5, 40])
    steps_before = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
    pult.cli("epic", "envelope", epic_id, f"{raised}")
    steps_after = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
    assert pult.envelope(epic_id) == pytest.approx(raised), pult.msg("подъём")
    assert steps_after > steps_before, pult.msg("подъём конверта без записи журнала")
    result = pult.run(task_id)
    note = pult.msg(f"{result['text']}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "preflight", note
    assert mentions(result["rows"], "конверт") == [], note

    lowered = pult.rng.choice([3, 5.25, 9])
    steps_before = steps_after
    pult.cli("epic", "envelope", epic_id, f"{lowered}")
    steps_after = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
    assert pult.envelope(epic_id) == pytest.approx(lowered), pult.msg("понижение")
    assert steps_after > steps_before, pult.msg("понижение конверта без записи журнала")

    for bad in ("abc", "0", "-5", f"-{pult.rng.randint(1, 99)}.5", "nan"):
        text = pult.cli_refusal("epic", "envelope", epic_id, bad)
        assert text.strip(), pult.msg(f"отказ на {bad!r} без причины")
        assert pult.envelope(epic_id) == pytest.approx(lowered), pult.msg(
            f"{bad!r} изменил конверт: {pult.envelope(epic_id)}")


def status_shape(text: str) -> str:
    """Вывод `status` без чисел: остаётся то, что от сумм не зависит."""
    return re.sub(r"\d+", "#", text)


def test_ac15_epic_without_envelope_has_no_envelope_checks(pult):
    """Эпик без конверта: ни отказа `run`, ни предупреждения 80 %, ни алерта.

    Сценарий: эпик без `--envelope`, по его задачам потрачено случайно
    много ($50–$5000). Новая задача эпика без «agent run started»: `run`
    доходит до предполёта без записи о конверте. Вывод `status` без чисел
    совпадает с выводом при нулевом потраченном (предупреждения нет).
    `budget.check_epic_alert` после «начисления» алертов не заводит.

    Ловит мутацию: пустой конверт читается как $0 — `run` отказан как
    исчерпанный, `status` печатает предупреждение, алерт поднимается.
    """
    epic_id = pult.new_epic()
    donor = pult.new_task("in_dev", epic_id, 0.0)
    pult.mark_started(donor)
    quiet = status_shape(pult.cli("status"))
    store.update_task(store.db(), donor,
                      spent_usd=float(pult.rng.randint(50, 5000)))
    loud = status_shape(pult.cli("status"))
    assert loud == quiet, pult.msg(f"вывод status изменился:\n{quiet}\n---\n{loud}")

    task_id = pult.new_task(pult.rng.choice(STEP_STATES), epic_id)
    result = pult.run(task_id)
    note = pult.msg(f"{result['text']}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "preflight", note
    assert mentions(result["rows"], "конверт") == [], note

    alerts_before = store.db().execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    budget.check_epic_alert(store.db(), donor)
    alerts_after = store.db().execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert alerts_after == alerts_before, pult.msg("алерт у эпика без конверта")


def epic_with_start_after(pult, dep_state: str) -> tuple:
    """(задача, зависимость): задача эпика с `start_after` на зависимость в `dep_state`."""
    epic_id = pult.new_epic()
    dep = pult.new_task("in_dev", epic_id)
    task_id = pult.new_task(pult.rng.choice(STEP_STATES), epic_id)
    pult.cli("epic", "start-after", task_id, dep)
    pult.set_state(dep, dep_state)
    return task_id, dep


def test_ac16_first_step_waits_for_start_after(pult):
    """Первый шаг ждёт задачи `start_after` не в `done`; после `done` — разрешён.

    Сценарий: задача эпика с `start_after` на зависимость в случайном
    состоянии не `done`. `run` отказан до рабочего каталога и агента;
    текст отказа и запись журнала называют id зависимости. Зависимость
    переведена в `done` — `run` доходит до предполёта.

    Ловит мутацию: `start_after` не проверяется перед первым шагом —
    `run` уходит в предполёт; либо отказ без перечня ожидаемых задач.
    """
    waiting = pult.rng.choice(["in_dev", "review", "verifying", "merge_gate",
                               "acceptance", "spec_gate"])
    task_id, dep = epic_with_start_after(pult, waiting)
    result = pult.run(task_id)
    note = pult.msg(f"{result['outcome']}\n{result['text']}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "exit", note
    assert dep in result["text"], note
    assert any(dep in f"{r['action']} {r['detail']}" for r in result["rows"]), note
    pult.spawn.assert_not_called()
    pult.ensure.assert_not_called()
    pult.preflight.assert_not_called()

    pult.set_state(dep, "done")
    result = pult.run(task_id)
    assert result["outcome"] == "preflight", pult.msg(
        f"{result['text']}\n{rows_text(result['rows'])}")


def test_ac22_killed_start_after_refuses_with_hint(pult):
    """Зависимость `start_after` в `killed` без деления — отказ первого шага с подсказкой снять зависимость.

    Сценарий: задача эпика с `start_after` на зависимость, убитую после
    записи (`killed`, `closed_as` пуст). `run` отказан, текст называет
    id зависимости и подсказывает снять её (`start_after`/`start-after`
    и «снять»/«сними»).

    Ловит мутацию: убитая зависимость считается выполненной (`killed`
    как окончательное «готово») — `run` уходит в предполёт; либо отказ
    общим текстом ожидания без подсказки снять зависимость.
    """
    task_id, dep = epic_with_start_after(pult, "killed")
    result = pult.run(task_id)
    text = result["text"]
    note = pult.msg(f"{result['outcome']}\n{text}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "exit", note
    assert dep in text, note
    lowered = text.lower()
    assert "start_after" in lowered or "start-after" in lowered, note
    assert re.search(r"сн[яи]", lowered), note
    pult.preflight.assert_not_called()


def test_ac26_task_without_epic_runs_unchanged(pult):
    """Задача без эпика и без `start_after` проходит `run` без проверок конверта и `start_after`.

    Сценарий: рядом — эпик с исчерпанным конвертом ($10,20 из $10);
    задача без эпика в случайном агентском состоянии, без «agent run
    started». `run` доходит до предполёта; добавленные им записи журнала
    задачи не упоминают ни конверт, ни эпик, ни `start_after`.

    Ловит мутацию: проверка конверта берёт эпик по ошибке (любой эпик
    проекта, `epic_id IS NULL` трактуется как совпадение) и отказывает;
    либо проверки журналируют «пройдено» и для задачи без эпика.
    """
    exhausted_epic(pult, 10.2)
    task_id = pult.new_task(pult.rng.choice(STEP_STATES))
    result = pult.run(task_id)
    note = pult.msg(f"{result['outcome']}\n{result['text']}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "preflight", note
    for word in ("конверт", "эпик", "start_after", "start-after"):
        assert mentions(result["rows"], word) == [], note


def test_ac28_start_after_checked_only_before_first_step(pult):
    """После первого шага `start_after` больше не проверяется, даже если зависимость снова не в `done`.

    Сценарий: задача с `start_after` на D; D в `done`; задача получила
    первый шаг (запись «agent run started»). D переведена в случайное
    состояние не `done` без новой записи `start_after`. Следующий `run`
    доходит до предполёта, записей с id D (отказа `start_after`) нет.

    Ловит мутацию: проверка `start_after` на каждом шаге роли — `run`
    отказан с перечнем, где D.
    """
    task_id, dep = epic_with_start_after(pult, "done")
    first = pult.run(task_id)
    assert first["outcome"] == "preflight", pult.msg(first["text"])
    pult.mark_started(task_id)
    pult.set_state(dep, pult.rng.choice(["in_dev", "review", "escalated"]))
    result = pult.run(task_id)
    note = pult.msg(f"{result['outcome']}\n{result['text']}\n{rows_text(result['rows'])}")
    assert result["outcome"] == "preflight", note
    assert not any(dep in f"{r['action']} {r['detail']}" for r in result["rows"]), note


def header_numbers(text: str, epic_id: str) -> list:
    line = next((ln for ln in text.splitlines() if epic_id in ln), "")
    return [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", line)]


def test_ac24_epic_spent_is_the_single_source(pult):
    """Подмена `budget.epic_spent` меняет показ, решение конверта и алерт 80 %.

    Сценарий: эпик с конвертом $10, по задачам потрачено $1,00. С
    подменой `budget.epic_spent`, отдающей случайную сумму ≥ $10:
    заголовок эпика в `status` и вывод `epic show` несут эту сумму; `run`
    новой задачи эпика отказан проверкой конверта;
    `budget.check_epic_alert` заводит алерт с id эпика. Без подмены та же
    задача доходит до предполёта.

    Ловит мутацию: `board.py`, `runner.py` или `check_epic_alert` считают
    потрачено по эпику своей формулой — подмена не меняет вид, отказа
    нет или алерта нет.
    """
    epic_id = pult.new_epic(10)
    donor = pult.new_task("in_dev", epic_id, 1.0)
    pult.mark_started(donor)
    task_id = pult.new_task(pult.rng.choice(STEP_STATES), epic_id)
    fake = float(pult.rng.randint(1100, 9900)) / 100
    with mock.patch.object(budget, "epic_spent", return_value=fake):
        status_out = pult.cli("status")
        show_out = pult.cli("epic", "show", epic_id)
        refused = pult.run(task_id)
        alerts_before = {r["id"] for r in store.db().execute("SELECT id FROM alerts")}
        budget.check_epic_alert(store.db(), donor)
        new_alerts = [dict(r) for r in store.db().execute("SELECT * FROM alerts")
                      if r["id"] not in alerts_before]
    assert fake in header_numbers(status_out, epic_id), pult.msg(status_out)
    shown = [float(n.replace(",", "."))
             for n in re.findall(r"\d+(?:[.,]\d+)?", show_out)]
    assert fake in shown, pult.msg(show_out)
    assert refused["outcome"] == "exit", pult.msg(refused["text"])
    assert mentions(refused["rows"], "конверт"), pult.msg(rows_text(refused["rows"]))
    assert any(epic_id in str(a) for a in new_alerts), pult.msg(str(new_alerts))

    allowed = pult.run(task_id)
    assert allowed["outcome"] == "preflight", pult.msg(allowed["text"])
