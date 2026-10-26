"""Запись `start_after`: проверки элемента, подстановка поделённой задачи и цикл по объединённому графу `merge_after` ∪ `start_after`.

Группа: долгоживущий
Красен до реализации: команд `epic new`/`epic start-after`, флага `new --start-after` и колонки `tasks.start_after` нет — заведение эпика сценария падает отказом «Неизвестная команда epic»; граф цикла `merge_after.check` не знает рёбер `start_after`.

Публичная поверхность: команды `epic new` (SPEC шага Э1), `epic
start-after <задача> <id>…`, `new "<название>" --tz <файл> --target <проект>
--epic <id> --start-after <id>` через `artel.main()`; каналы записи
`merge_after` — `merge_after.spec_gate_value`, `merge_after.apply_plan`,
`merge_after.value_refusals`, `merge_after.mandate_value`; деление —
`closed_as='divided'` и запись журнала родителя «поделена на: …» тем же
`store.set_state`, что пишет гейт SPEC; замена после деления —
`merge_after.replace_divided`. Значение `start_after` читается колонкой
`tasks.start_after` как текст: проверяется, какие id в нём есть, — не
формат перечня.

Цикл через `start_after` в каналах `new` (`new --after`, строка ТЗ
«Порядок: после …», `new --start-after`) не строится в принципе: на
заводимую задачу ещё никто не ссылается, входящего ребра у неё нет —
свойство «цикл — отказ» там выполняется пусто, и сценарий цикла держит
каналы записи для уже заведённых задач.

Id задач порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.

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

from orchestrator import artel, config, merge_after, store
from orchestrator.advance_gates.mandate import MERGE_AFTER_MANDATE_MARKER
from tests.sandbox import declare_target

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class Writer:

    def __init__(self, sandbox, seed: int):
        self.sandbox = sandbox
        self.seed = seed
        self.rng = random.Random(seed)
        self.counter = 0
        self.epic_id = None

    @property
    def epic(self) -> str:
        """Эпик сценария — заводится командой `epic new` при первом обращении
        (в теле теста, не в фикстуре)."""
        if self.epic_id is None:
            title = f"Эпик зависимостей {self.seed:x}"
            self.cli("epic", "new", config.DEFAULT_TARGET, title, "--goal",
                     "Цель сценария")
            self.epic_id = store.db().execute(
                "SELECT id FROM epics WHERE title=?", (title,)).fetchone()["id"]
        return self.epic_id

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cli(self, *argv: str) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            artel.main()
        return buf.getvalue()

    def refused(self, *argv: str) -> str | None:
        """Текст отказа команды (`SystemExit`); `None` — команда прошла."""
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                return f"{buf.getvalue()}\n{exc}"
        return None

    def task(self, state: str = "in_dev", target: str = config.DEFAULT_TARGET,
             epic: bool = True) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        store.insert_task(store.db(), task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-zavisimost", target, 50.0)
        if epic:
            store.update_task(store.db(), task_id, epic_id=self.epic)
        return task_id

    def start_after(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["start_after"] or ""

    def divide(self, parent: str) -> list:
        """Родитель поделён на 2–3 части: `closed_as='divided'`, `killed`,
        запись журнала «поделена на: …»; возврат — части по порядку."""
        parts = [self.task("spec_writing") for _ in range(self.rng.randint(2, 3))]
        conn = store.db()
        state = store.get_task(conn, parent)["state"]
        store.set_state(conn, parent, "killed", "operator", expected_state=state,
                        detail=f"поделена на: {', '.join(parts)}")
        store.update_task(conn, parent, closed_as="divided")
        return parts

    def new_with_start_after(self, dep: str) -> str | None:
        self.counter += 1
        title = f"Новая с зависимостью {self.seed:x}-{self.counter}"
        tz = self.sandbox.root / f"tz-{self.counter}.md"
        tz.write_text(f"# {title}\n\nЦель сценария.\n", encoding="utf-8")
        refusal = self.refused("new", title, "--tz", str(tz), "--target",
                               config.DEFAULT_TARGET, "--epic", self.epic,
                               "--start-after", dep)
        self.last_title = title
        return refusal

    def titled(self, title: str) -> list:
        return list(store.db().execute("SELECT * FROM tasks WHERE title=?", (title,)))


@pytest.fixture
def writer(light_transition):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield Writer(light_transition, seed)


def bad_dependency(writer, case: str) -> tuple:
    """(id элемента записи, задача-источник цикла или None) для случая `case`."""
    if case == "missing":
        return "01" + "".join(writer.rng.choices(ULID_ALPHABET, k=24)), None
    if case == "other_project":
        ext = "proekt" + "".join(writer.rng.choices("abcdefgh", k=5))
        declare_target(ext)
        return writer.task(target=ext, epic=False), None
    if case == "killed":
        dep = writer.task()
        store.set_state(store.db(), dep, "killed", "operator",
                        expected_state="in_dev", detail="убита сценарием")
        return dep, None
    dep = writer.task()
    return dep, dep


@pytest.mark.parametrize("case, channel", [
    ("missing", "epic"), ("missing", "new"),
    ("other_project", "epic"), ("other_project", "new"),
    ("killed", "epic"), ("killed", "new"),
    ("cycle", "epic"),
])
def test_ac18_bad_start_after_refused_value_kept(writer, case, channel):
    """Запись `start_after` на негодный элемент отказывает, значение не меняется.

    Сценарий (случай × канал): элемент — несуществующая задача; задача
    другого проекта; задача в `killed` без деления (текст отказа называет
    её id); цикл через `merge_after` (A `start_after` B при B
    `merge_after` A — только канал `epic start-after`, см. докстринг
    модуля). Канал `epic start-after` — у задачи значение прежнее
    (пусто); канал `new --epic … --start-after` — команда отказывает, ни
    у одной задачи с этим названием `start_after` не записан.

    Ловит мутацию: запись `start_after` идёт без `merge_after.check` (или
    без графа `merge_after` в поиске цикла) — элемент записан.
    """
    dep, cycle_source = bad_dependency(writer, case)
    if channel == "epic":
        task_id = writer.task()
        if cycle_source is not None:
            store.update_task(store.db(), cycle_source,
                              merge_after=merge_after.column([task_id]))
        refusal = writer.refused("epic", "start-after", task_id, dep)
        assert refusal is not None, writer.msg(f"{case}: запись не отказана")
        assert writer.start_after(task_id) == "", writer.msg(
            f"{case}: значение {writer.start_after(task_id)!r}")
    else:
        refusal = writer.new_with_start_after(dep)
        assert refusal is not None, writer.msg(f"{case}: new не отказал")
        assert all(not (r["start_after"] or "") for r in writer.titled(writer.last_title)), \
            writer.msg(f"{case}: start_after записан новой задаче")
    if case == "killed":
        assert dep in refusal, writer.msg(f"причина без id убитой задачи:\n{refusal}")


def test_ac19_merge_after_cycle_through_start_after_refused_in_all_channels(writer):
    """Запись `merge_after` B = A при A `start_after` B отказывает во всех каналах записи уже заведённой задачи.

    Сценарий: A `start_after` B (`epic start-after`). Значение
    `merge_after` B = A через поле SPEC на гейте SPEC
    (`merge_after.spec_gate_value` — причина отказа), поле PLAN
    (`merge_after.apply_plan` с обоснованием в «Влияние на систему» —
    запись «merge_after из PLAN отклонён», колонка прежняя), строку
    мандата ответа (`merge_after.value_refusals` — причины не пусты,
    `merge_after.mandate_value` не отдаёт [A]). `merge_after` B не
    изменился. Каналы `new` — см. докстринг модуля.

    Ловит мутацию: граф цикла `merge_after.check` строится только из
    `merge_after` — каждый канал принимает значение, PLAN переписывает
    колонку.
    """
    a, b = writer.task(), writer.task()
    writer.cli("epic", "start-after", a, b)
    assert b in writer.start_after(a), writer.msg("start_after A не записан")
    conn = store.db()

    value, reason = merge_after.spec_gate_value(conn, b, {merge_after.FIELD: a})
    assert reason, writer.msg(f"гейт SPEC принял цикл: {value!r}")

    plan = (f"---\n{merge_after.FIELD}: {a}\n---\n\n# PLAN\n\n"
            f"## {merge_after.IMPACT_SECTION}\n{merge_after.FIELD} меняется на {a}.\n")
    merge_after.apply_plan(conn, b, store.get_task(conn, b),
                           {merge_after.FIELD: a}, plan)
    assert store.get_task(store.db(), b)["merge_after"] is None, writer.msg(
        "PLAN записал цикл")
    assert any(r["action"] == merge_after.PLAN_REJECTED_ACTION
               for r in store.task_steps(store.db(), b)), writer.msg(
        "нет записи отказа PLAN")

    assert merge_after.value_refusals(conn, b, [a]), writer.msg(
        "мандат принял цикл")
    assert merge_after.mandate_value(
        conn, b, f"{MERGE_AFTER_MANDATE_MARKER} {a}\n") != [a], writer.msg(
        "mandate_value отдал значение с циклом")
    assert store.get_task(store.db(), b)["merge_after"] is None, writer.msg(
        "merge_after B изменён")


def test_ac20_divided_dependency_replaced_by_last_part(writer):
    """Запись `start_after` на уже поделённую задачу записывает последний id записи «поделена на: …».

    Сценарий: P поделена на 2–3 части (`closed_as='divided'`, `killed`).
    `epic start-after T P` проходит (не отказ `killed`), в `start_after`
    T — последняя часть, P нет.

    Ловит мутацию: подстановки нет — запись отказана как `killed` или
    записан P; берётся первая часть вместо последней.
    """
    parent = writer.task()
    parts = writer.divide(parent)
    task_id = writer.task()
    refusal = writer.refused("epic", "start-after", task_id, parent)
    assert refusal is None, writer.msg(f"запись отказана:\n{refusal}")
    value = writer.start_after(task_id)
    assert parts[-1] in value, writer.msg(f"{value!r}, части {parts}")
    assert parent not in value, writer.msg(value)
    assert all(p not in value for p in parts[:-1]), writer.msg(value)


def test_ac21_division_chain_resolved_to_undivided(writer):
    """Цепочка делений P → Q → R: запись `start_after` на P записывает R.

    Сценарий: P поделена, последняя часть Q; Q поделена, последняя часть
    R (R не поделена). `epic start-after T P` — в `start_after` T только R
    из цепочки.

    Ловит мутацию: подстановка на один шаг — записан Q (поделённая
    задача) или запись отказана как `killed`.
    """
    p = writer.task()
    q = writer.divide(p)[-1]
    r = writer.divide(q)[-1]
    task_id = writer.task()
    refusal = writer.refused("epic", "start-after", task_id, p)
    assert refusal is None, writer.msg(f"запись отказана:\n{refusal}")
    value = writer.start_after(task_id)
    assert r in value, writer.msg(f"{value!r}: ждали {r}")
    assert p not in value and q not in value, writer.msg(value)


def test_ac23_replace_divided_updates_start_after(writer):
    """Деление зависимости после записи: `merge_after.replace_divided` заменяет её в `start_after` последней частью.

    Сценарий: T `start_after` [X, D]; D поделена (последняя часть L), затем
    `merge_after.replace_divided(conn, D, L)`. В `start_after` T — X и L,
    D нет.

    Ловит мутацию: `replace_divided` обходит только колонку
    `merge_after` — в `start_after` остаётся D.
    """
    x, d = writer.task(), writer.task()
    task_id = writer.task()
    writer.cli("epic", "start-after", task_id, x, d)
    assert d in writer.start_after(task_id), writer.msg("start_after не записан")
    last = writer.divide(d)[-1]
    merge_after.replace_divided(store.db(), d, last)
    value = writer.start_after(task_id)
    assert last in value and x in value, writer.msg(f"{value!r}")
    assert d not in value, writer.msg(value)
