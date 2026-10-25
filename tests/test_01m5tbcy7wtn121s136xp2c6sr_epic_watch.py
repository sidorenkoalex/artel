"""Строка предупреждения 80 % по эпику в сессии `watch` — по событиям начисления стоимости шага.

Группа: долгоживущий
Красен до реализации: команды `epic new` и таблицы `epics` нет — заведение эпика сценария падает отказом «Неизвестная команда epic»; `watch` строк по эпику не печатает.

Связка, которую держит файл: «журнал задачи — цикл `watch` — вывод».
Сессия — настоящий `watch.cmd_watch(["--tasks", <id>])`; пауза между
итерациями подменена (`tests.sandbox.patch_sleep`) сценарием: на каждой
паузе сценарий пишет следующее событие начисления (запись журнала задачи
«agent cost KNOWN»/«agent cost PARTIAL»/«agent cost ESTIMATED» и сумму в
`tasks.spent_usd`/`tasks.spent_estimate_usd` — слагаемые
`budget.spent_with_estimate`), после последнего события переводит задачу
в `done`, и сессия завершается сама. Вывод между паузами — отклик
`watch` на одно событие. Строка предупреждения по эпику — строка вывода
с id или названием эпика (ни запись журнала сценария, ни строки задачи их
не несут).

Тексты подробностей записей журнала и раскладка потраченного по задачам
эпика порождаются модулем `random` при каждом запуске; зерно печатается и
входит в текст провала.

Провалидировано временным стабом реализации Э1+Э2а (таблица `epics`, команды
`epic …`, проверки `runner`, алерт `budget`, строки `watch`, остановка
`auto`, граф `merge_after`; удалён, не закоммичен): все методы файла
зелёные; правдоподобные мутации стаба, названные в заявках, их красят.
"""
import io
import os
import random
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import pytest

from orchestrator import artel, config, store, watch
from tests.sandbox import patch_sleep

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def cli(*argv: str) -> str:
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
            redirect_stdout(buf), redirect_stderr(buf):
        artel.main()
    return buf.getvalue()


class WatchSession:
    """Эпик с конвертом $10, задача эпика и сценарий событий начисления."""

    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)

    def start(self, spent: float) -> None:
        """Эпик, его задачи и потрачено по эпику `spent` до сессии."""
        self.title = f"Эпик дозора {self.seed:x}"
        cli("epic", "new", config.DEFAULT_TARGET, self.title, "--goal",
            "Цель сценария", "--envelope", "10")
        row = store.db().execute("SELECT id FROM epics WHERE title=?",
                                 (self.title,)).fetchone()
        assert row is not None, self.msg("эпик не заведён")
        self.epic = row["id"]
        conn = store.db()
        self.task = self.new_task("in_dev")
        self.donor = self.new_task("review")
        for task_id in (self.task, self.donor):
            store.update_task(conn, task_id, epic_id=self.epic)
        self.set_spent(spent)

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def new_task(self, state: str) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        store.insert_task(store.db(), task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-dozor",
                          config.DEFAULT_TARGET, 1000.0)
        return task_id

    def set_spent(self, total: float) -> None:
        """Потрачено по эпику — `total`: часть на соседней задаче эпика."""
        donor = self.rng.randint(0, round(total * 100) // 2) / 100
        conn = store.db()
        store.update_task(conn, self.donor, spent_usd=donor,
                          spent_estimate_usd=0.0)
        store.update_task(conn, self.task, spent_usd=round(total - donor, 2),
                          spent_estimate_usd=0.0)

    def charge(self, action: str, total: float) -> None:
        """Событие начисления задачи: потрачено по эпику становится `total`."""
        conn = store.db()
        t = store.get_task(conn, self.task)
        d = store.get_task(conn, self.donor)
        current = ((t["spent_usd"] or 0) + (t["spent_estimate_usd"] or 0)
                   + (d["spent_usd"] or 0) + (d["spent_estimate_usd"] or 0))
        delta = round(total - current, 2)
        column = ("spent_estimate_usd" if action == "agent cost ESTIMATED"
                  else "spent_usd")
        store.update_task(conn, self.task, **{column: (t[column] or 0) + delta})
        store.journal(conn, self.task, "developer", action,
                      f"попытка 1/3: сценарий {self.rng.randrange(1 << 30):x}")

    def watch(self, events: list) -> list:
        """Сессия `watch` по задаче; `events` — [(действие, потрачено после)].
        Возврат — вывод сессии, нарезанный по событиям: i-й кусок — отклик
        на i-е событие."""
        buf = io.StringIO()
        marks: list = []
        script = list(events)

        def pause(_seconds) -> None:
            marks.append(len(buf.getvalue()))
            if len(marks) > len(events) + 3:
                raise RuntimeError("watch не завершился")
            if script:
                action, total = script.pop(0)
                self.charge(action, total)
                if not script:
                    conn = store.db()
                    conn.execute("UPDATE tasks SET state='done' WHERE id=?",
                                 (self.task,))
                    conn.commit()

        with patch_sleep(watch, pause), redirect_stdout(buf), redirect_stderr(buf):
            watch.cmd_watch(["--tasks", self.task, "--interval", "1"])
        out = buf.getvalue()
        bounds = [*marks, len(out)]
        return [out[bounds[i]:bounds[i + 1]] for i in range(len(events))]

    def warnings(self, text: str) -> list:
        return [ln for ln in text.splitlines()
                if self.epic in ln or self.title in ln]


@pytest.fixture
def session(light_transition):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield WatchSession(seed)


def test_ac7_one_warning_line_on_crossing(session):
    """Пересечение порога 80 % в сессии `watch` даёт ровно одну строку предупреждения по эпику.

    Сценарий: сессия начата при потрачено $7,00 из $10. События
    «agent cost KNOWN»: $7,50 — строки нет (предыдущего события в сессии
    нет); $8,50 — ровно одна строка предупреждения с id/названием эпика;
    $9,00 — второй строки нет. За сессию строк ровно одна.

    Ловит мутацию: «потрачено до события» берётся как текущее потрачено
    без памяти сессии (каждое событие выше порога печатает строку — их
    две); либо «до» — значение на старте сессии без обновления; либо
    строка печатается и на первом событии сессии.
    """
    session.start(7.0)
    pieces = session.watch([("agent cost KNOWN", 7.5), ("agent cost KNOWN", 8.5),
                            ("agent cost KNOWN", 9.0)])
    counts = [len(session.warnings(p)) for p in pieces]
    assert counts == [0, 1, 0], session.msg(f"строк по событиям {counts}:\n"
                                            + "\n=====\n".join(pieces))


def test_ac27_session_started_above_threshold_prints_nothing(session):
    """Сессия, начатая при $8,50 из $10, не печатает строк предупреждения по эпику.

    Сценарий: потрачено по эпику на старте $8,50; события «agent cost
    KNOWN» $8,70 и $9,00. Строк с id/названием эпика нет ни на одном.

    Ловит мутацию: «до» первого события сессии считается нулём (или
    значением ниже порога) — первое событие печатает строку.
    """
    session.start(8.5)
    pieces = session.watch([("agent cost KNOWN", 8.7), ("agent cost KNOWN", 9.0)])
    counts = [len(session.warnings(p)) for p in pieces]
    assert counts == [0, 0], session.msg(f"строк по событиям {counts}:\n"
                                         + "\n=====\n".join(pieces))


@pytest.mark.parametrize("crossing_action", ["agent cost PARTIAL",
                                             "agent cost ESTIMATED"])
def test_ac29_partial_and_estimated_are_charge_events(session, crossing_action):
    """Пересечение порога записью «agent cost PARTIAL» или «agent cost ESTIMATED» даёт ровно одну строку.

    Сценарий (отдельная сессия на каждое действие): старт при $7,00 из
    $10; первое событие — «agent cost KNOWN», $7,50; второе — запись
    `crossing_action`, $8,50. Отклик на первое событие без строки, на
    второе — ровно одна строка предупреждения по эпику.

    Ловит мутацию: событием начисления для `watch` считается только
    «agent cost KNOWN» — пересечение записью PARTIAL/ESTIMATED строки не
    даёт.
    """
    session.start(7.0)
    pieces = session.watch([("agent cost KNOWN", 7.5), (crossing_action, 8.5)])
    counts = [len(session.warnings(p)) for p in pieces]
    assert counts == [0, 1], session.msg(f"строк по событиям {counts}:\n"
                                         + "\n=====\n".join(pieces))
