"""Показ конверта эпика: «потрачено / конверт» и предупреждение 80 % в `status` и `epic show`, предупреждение `new --epic`, `waiting_on` модели доски.

Группа: долгоживущий
Красен до реализации: команд `epic new`/`epic show`/`epic start-after`, флага `new --epic`, модуля `board` и таблицы `epics` нет — заведение эпика сценария падает отказом «Неизвестная команда epic».

Публичная поверхность: команды `status`, `epic new`, `epic show`, `epic
start-after`, `new "<название>" --tz <файл> --target <проект> --epic <id>`
через `artel.main()`; модель доски — `board.build_model(conn, project)`
(SPEC шага Э1, требование 10: `cards` с ключами `task` и `waiting_on`).

Предупреждение 80 % наблюдается без опоры на его текст: вывод вида с
вычеркнутыми числами при потрачено не ниже порога обязан отличаться от
того же вывода при потрачено ниже порога (суммы в строках задач и в
заголовке эпика при вычеркнутых числах совпадают — отличие даёт только
предупреждение).

Раскладка потраченного по задачам эпика и id задач порождаются модулем
`random` при каждом запуске; зерно печатается и входит в текст провала.

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

from orchestrator import artel, config, store

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class Viewer:

    def __init__(self, sandbox, seed: int):
        self.sandbox = sandbox
        self.seed = seed
        self.rng = random.Random(seed)
        self.counter = 0

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cli(self, *argv: str) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            artel.main()
        return buf.getvalue()

    def new_epic(self, envelope=None) -> tuple:
        """(id, название) нового эпика."""
        self.counter += 1
        title = f"Эпик показа {self.seed:x}-{self.counter}"
        argv = ["epic", "new", config.DEFAULT_TARGET, title, "--goal", "Цель"]
        if envelope is not None:
            argv += ["--envelope", f"{envelope}"]
        self.cli(*argv)
        row = store.db().execute("SELECT id FROM epics WHERE title=?",
                                 (title,)).fetchone()
        assert row is not None, self.msg(f"эпик «{title}» не заведён")
        return row["id"], title

    def new_task(self, state: str, epic_id: str | None) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        store.insert_task(store.db(), task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-pokaz", config.DEFAULT_TARGET,
                          1000.0)
        if epic_id is not None:
            store.update_task(store.db(), task_id, epic_id=epic_id)
        return task_id

    def epic_with_tasks(self, envelope) -> tuple:
        epic_id, title = self.new_epic(envelope)
        tasks = [self.new_task(self.rng.choice(["in_dev", "review", "done"]),
                               epic_id)
                 for _ in range(self.rng.randint(1, 3))]
        return epic_id, title, tasks

    def set_spent(self, tasks: list, total: float) -> None:
        """Потрачено по эпику — ровно `total` (целые центы по задачам)."""
        cents = round(total * 100)
        cuts = sorted(self.rng.randrange(cents + 1) for _ in range(len(tasks) - 1))
        bounds = [0, *cuts, cents]
        for i, task_id in enumerate(tasks):
            store.update_task(store.db(), task_id,
                              spent_usd=(bounds[i + 1] - bounds[i]) / 100)


@pytest.fixture
def viewer(light_transition):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield Viewer(light_transition, seed)


def shape(text: str) -> str:
    return re.sub(r"\d+", "#", text)


def numbers(line: str) -> list:
    return [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", line)]


def epic_header(text: str, epic_id: str) -> str:
    return next((ln for ln in text.splitlines() if epic_id in ln), "")


def db_dump() -> list:
    return list(store.db().iterdump())


def test_ac1_status_shows_spent_envelope_and_warning_without_writing(viewer):
    """`status` при $8,50 из $10 показывает «потрачено / конверт» и предупреждение; повтор `status` БД не меняет.

    Сценарий: эпик с конвертом $10, по 1–3 задачам эпика потрачено ровно
    $8,50. Строка заголовка эпика несёт 8,5 и 10. Вывод без чисел
    отличается от вывода того же эпика при $7,00 (предупреждение).
    Вызов `status` при $8,50 после первого не меняет дамп БД (алертов и
    записей журнала нет).

    Ловит мутацию: предупреждения нет (выводы без чисел равны); заголовок
    несёт только потраченное без конверта; показ поднимает алерт или
    пишет журнал при пересечении порога.
    """
    epic_id, _, tasks = viewer.epic_with_tasks(10)
    viewer.set_spent(tasks, 7.0)
    below = viewer.cli("status")
    viewer.set_spent(tasks, 8.5)
    above = viewer.cli("status")
    header = epic_header(above, epic_id)
    assert 8.5 in numbers(header) and 10 in numbers(header), viewer.msg(above)
    assert shape(above) != shape(below), viewer.msg(f"нет предупреждения:\n{above}")
    before = db_dump()
    again = viewer.cli("status")
    assert db_dump() == before, viewer.msg("повторный status изменил БД")
    assert shape(again) == shape(above), viewer.msg(again)


def test_ac2_status_warns_at_exact_threshold(viewer):
    """`status` при ровно $8,00 из $10 показывает предупреждение 80 %.

    Сценарий: потрачено по эпику ровно $8,00 против $7,99 — выводы
    `status` без чисел различаются.

    Ловит мутацию: сравнение «> порога» вместо «≥ порога» — при $8,00
    предупреждения нет, выводы равны.
    """
    _, _, tasks = viewer.epic_with_tasks(10)
    viewer.set_spent(tasks, 7.99)
    below = viewer.cli("status")
    viewer.set_spent(tasks, 8.0)
    at = viewer.cli("status")
    assert shape(at) != shape(below), viewer.msg(f"нет предупреждения:\n{at}")


def test_ac14_new_with_exhausted_envelope_creates_task_and_warns(viewer):
    """`new --epic <id>` при исчерпанном конверте заводит задачу и печатает предупреждение о конверте.

    Сценарий: конверт $10, по задачам эпика потрачено случайно $10–$30.
    `new "<название>" --tz <файл> --target <проект> --epic <id>` не
    отказывает; задача с этим названием в эпике есть; вывод упоминает
    конверт.

    Ловит мутацию: `new --epic` отказывает при исчерпанном конверте
    (задачи нет); либо заводит молча, без предупреждения.
    """
    epic_id, _, tasks = viewer.epic_with_tasks(10)
    viewer.set_spent(tasks, viewer.rng.randint(1000, 3000) / 100)
    title = f"Задача в исчерпанном эпике {viewer.seed:x}"
    tz = viewer.sandbox.root / "tz-envelope.md"
    tz.write_text(f"# {title}\n\nЦель сценария.\n", encoding="utf-8")
    out = viewer.cli("new", title, "--tz", str(tz), "--target",
                     config.DEFAULT_TARGET, "--epic", epic_id)
    rows = list(store.db().execute("SELECT * FROM tasks WHERE title=?", (title,)))
    assert len(rows) == 1 and rows[0]["epic_id"] == epic_id, viewer.msg(out)
    assert "конверт" in out.lower(), viewer.msg(f"нет предупреждения:\n{out}")


def test_ac25_epic_show_and_board_waiting_on_dependency(viewer):
    """`epic show` несёт «потрачено / конверт» и предупреждение; модель доски даёт `waiting_on='dependency'` задаче, ждущей `start_after`.

    Сценарий: эпик с конвертом $10; `epic show` при $8,50 несёт 8,5 и 10,
    и вывод без чисел отличается от вывода при $7,00. Задача эпика в
    агентском состоянии без шага роли с `start_after` на задачу не в
    `done`: её карточка `board.build_model` — `waiting_on == 'dependency'`.

    Ловит мутацию: `epic show` без предупреждения или без конверта;
    правило `dependency` модели доски не смотрит на `start_after` —
    карточка получает `role`.
    """
    epic_id, _, tasks = viewer.epic_with_tasks(10)
    viewer.set_spent(tasks, 7.0)
    below = viewer.cli("epic", "show", epic_id)
    viewer.set_spent(tasks, 8.5)
    above = viewer.cli("epic", "show", epic_id)
    shown = numbers(above)
    assert 8.5 in shown and 10 in shown, viewer.msg(above)
    assert shape(above) != shape(below), viewer.msg(f"нет предупреждения:\n{above}")

    dep = viewer.new_task(viewer.rng.choice(["in_dev", "review"]), epic_id)
    waiting = viewer.new_task(viewer.rng.choice(["spec_writing", "tests_writing",
                                                 "review"]), epic_id)
    viewer.cli("epic", "start-after", waiting, dep)
    from orchestrator import board
    model = board.build_model(store.db(), config.DEFAULT_TARGET)
    card = next((c for c in model["cards"] if c["task"] == waiting), None)
    assert card is not None, viewer.msg(f"нет карточки {waiting}")
    assert card["waiting_on"] == "dependency", viewer.msg(f"{card}")
