"""Остановка `auto <id>` на отказе `run` по конверту эпика и по `start_after` — своя причина и подсказка.

Группа: долгоживущий
Красен до реализации: команд `epic new`/`epic start-after` и таблицы `epics` нет — заведение эпика сценария падает отказом «Неизвестная команда epic»; отказа `run` по конверту и `start_after` нет, а неузнанный отказ `auto` сопровождает подсказкой «budget … или kill» и алертом `attention`.

Связка, которую держит файл: «цикл `auto` — настоящий `runner.cmd_run` —
журнал — алерты». Цикл — `auto.cmd_auto(<id>)`; агент
(`runner.spawn_agent`), рабочий каталог (`workspace.ensure`) и
предполётная проверка (`doctor.preflight_checks`) подменены отказом
сценария: шаг, прошедший проверки до предполёта, сценарий валит, и
тест это видит. Эпик — `epic new` (SPEC шага Э1) через `artel.main()`,
зависимость — `epic start-after`.

Суммы и id задач порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.

Провалидировано временным стабом реализации Э1+Э2а (таблица `epics`, команды
`epic …`, проверки `runner`, алерт `budget`, строки `watch`, остановка
`auto`, граф `merge_after`; удалён, не закоммичен): все методы файла
зелёные; правдоподобные мутации стаба, названные в заявках, их красят.
"""
import io
import os
import random
import signal
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import pytest

from orchestrator import alerts, artel, auto, config, store, workspace, runner

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class AutoPult:

    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
        self.counter = 0
        self.spawn = mock.Mock(side_effect=AssertionError("агент запущен"))
        self.ensure = mock.Mock(side_effect=AssertionError("рабочий каталог готовится"))
        self.preflight = mock.Mock(side_effect=AssertionError("дошёл до предполёта"))

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cli(self, *argv: str) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            artel.main()
        return buf.getvalue()

    def new_epic(self, envelope=None) -> str:
        self.counter += 1
        title = f"Эпик auto {self.seed:x}-{self.counter}"
        argv = ["epic", "new", config.DEFAULT_TARGET, title, "--goal", "Цель"]
        if envelope is not None:
            argv += ["--envelope", f"{envelope}"]
        self.cli(*argv)
        return store.db().execute("SELECT id FROM epics WHERE title=?",
                                  (title,)).fetchone()["id"]

    def new_task(self, state: str, epic_id: str, spent: float = 0.0) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-auto", config.DEFAULT_TARGET,
                          1000.0)
        store.update_task(conn, task_id, epic_id=epic_id, spent_usd=spent)
        if state == "spec_writing":
            tdir = config.TASKS / task_id
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "TZ.md").write_text("# ТЗ сценария\n\nЦель.\n", encoding="utf-8")
        return task_id

    def auto(self, task_id: str) -> tuple:
        """(вывод цикла, записи журнала задачи за цикл)."""
        before = len(store.task_steps(store.db(), task_id))
        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", self.spawn), \
                mock.patch.object(workspace, "ensure", self.ensure), \
                mock.patch("orchestrator.doctor.preflight_checks", self.preflight), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                auto.cmd_auto(task_id)
            except SystemExit as exc:
                buf.write(f"\n{exc}")
        return buf.getvalue(), store.task_steps(store.db(), task_id)[before:]


@pytest.fixture
def pult(light_transition):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    previous = signal.getsignal(signal.SIGTERM)
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield AutoPult(seed)
    signal.signal(signal.SIGTERM, previous)


def journal_text(rows) -> str:
    return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}" for r in rows)


def test_ac11_auto_stops_on_envelope_with_its_hint(pult):
    """`auto` задачи эпика с исчерпанным конвертом останавливается с подсказкой «epic envelope <id эпика> N».

    Сценарий: конверт $10, по задачам эпика потрачено $10,20 (случайная
    раскладка); задача эпика в `spec_writing` с ТЗ, без «agent run
    started». `auto <id>`: агент не запущен, в журнале — запись отказа о
    конверте, вывод несёт причину (конверт) и подсказку `epic envelope
    <id эпика>`; подсказки `artel.py budget` нет, алерт `attention` не
    открыт.

    Ловит мутацию: `auto` не узнаёт отказ конверта — остановка общим
    «run отказался стартовать» с подсказкой «artel.py budget … или kill»
    и алертом `attention`.
    """
    epic_id = pult.new_epic(10)
    first = pult.rng.randint(0, 1020) / 100
    pult.new_task("review", epic_id, first)
    pult.new_task("in_dev", epic_id, round(10.2 - first, 2))
    task_id = pult.new_task("spec_writing", epic_id)
    out, rows = pult.auto(task_id)
    note = pult.msg(f"вывод:\n{out}\nжурнал:\n{journal_text(rows)}")
    pult.spawn.assert_not_called()
    assert any("конверт" in f"{r['action']} {r['detail']}".lower() for r in rows), note
    assert "конверт" in out.lower(), note
    assert f"epic envelope {epic_id}" in out, note
    assert "artel.py budget" not in out, note
    assert alerts.open_alerts(store.db(), "attention") == [], note


def test_ac17_auto_stops_waiting_for_start_after(pult):
    """`auto` задачи, ждущей `start_after`, останавливается с подсказкой «ждёт start_after: <ids>».

    Сценарий: задача эпика (без конверта) с `start_after` на 1–2 задачи
    не в `done`, без «agent run started». `auto <id>`: агент не запущен,
    вывод несёт «ждёт start_after:» и id каждой ожидаемой задачи;
    подсказки `artel.py budget` нет, алерт `attention` не открыт.

    Ловит мутацию: `auto` не узнаёт отказ `start_after` — остановка с
    подсказкой «budget … или kill» и алертом `attention`; либо подсказка
    без перечня ожидаемых задач.
    """
    epic_id = pult.new_epic()
    deps = [pult.new_task(pult.rng.choice(["in_dev", "review", "merge_gate"]),
                          epic_id)
            for _ in range(pult.rng.randint(1, 2))]
    task_id = pult.new_task(pult.rng.choice(["tests_writing", "review"]), epic_id)
    pult.cli("epic", "start-after", task_id, *deps)
    out, rows = pult.auto(task_id)
    note = pult.msg(f"вывод:\n{out}\nжурнал:\n{journal_text(rows)}")
    pult.spawn.assert_not_called()
    assert "ждёт start_after:" in out, note
    hint = out[out.index("ждёт start_after:"):]
    for dep in deps:
        assert dep in hint, note
    assert "artel.py budget" not in out, note
    assert alerts.open_alerts(store.db(), "attention") == [], note
