"""Деление на гейте SPEC и эпик: наследование эпика частями, `approve
--as-epic`, отказы `--as-epic` до lease и без записей.

Группа: долгоживущий
Красен до реализации: таблицы `epics` и колонки `tasks.epic_id` нет, команды `epic` нет, `approve` не знает флага `--as-epic` (флаг уходит позиционным `sha`), а колонка `closed_as` появится только с мержем Э0.

Держит связку «команда `approve` CLI — FSM — БД»: родитель заводится
штатным `catalog.cmd_new` в лёгкой песочнице переходов
(`light_transition`), его SPEC с секцией «## Деление» лежит на диске
песочницы и читается гейтом через `disk_backed_show`; `approve` идёт
через `artel.main()`. Названия, цель (первый абзац «Контекст»), число
частей и состояние родителя порождаются модулем `random` при каждом
запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, catalog, config, fsm, lease, store
from orchestrator.advance_gates import spec_audit
from tests.sandbox import capture_new_task_id

FIRST = "первая, без зависимостей"
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")


@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов с зерном случайных входов и счётчиком зон."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.zone_counter = 0
    return light_transition


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода)."""
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def epics() -> dict:
    return {r["id"]: dict(r) for r in store.db().execute("SELECT * FROM epics")}


def row(task_id: str):
    return store.get_task(store.db(), task_id)


def parts_of(parent: str) -> list[str]:
    return [r["id"] for r in store.all_tasks(store.db())
            if r["parent_task_id"] == parent]


def snapshot() -> dict:
    conn = store.db()
    return {table: [tuple(r) for r in conn.execute(
        f"SELECT * FROM {table} ORDER BY rowid")]
        for table in ("tasks", "epics", "steps")}


def next_zone(stand) -> str:
    stand.zone_counter += 1
    return f"orchestrator/t_epic_division_zone_{stand.zone_counter}.py"


def spec_text(task_id: str, zone: str, context: str, parts: list,
              requirement: str = "Фикстура.") -> str:
    """SPEC родителя; `parts` — названия частей (пусто — без деления)."""
    orders = [FIRST] + [f"после части {n}" for n in range(1, len(parts))]
    division = "".join(
        f"### {title}\n\nЗоны: {zone}\nПорядок: {order}\n\n"
        f"Текст ТЗ части «{title}».\n\n"
        for title, order in zip(parts, orders))
    section = (f"## Оценка объёма и деление\nФикстура.\n\n## Деление\n\n"
               f"{division}" if parts else "")
    return f"""---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: 15
zones: {zone}
---

# SPEC: Родитель деления

## Контекст
{context}

Второй абзац контекста — не цель эпика.

## Требования
1. {requirement}

## Критерии приёмки
AC-1. Фикстура.

{section}## Не входит
- Всё остальное.
"""


def parent_on_gate(stand, *, divided: bool = True,
                   requirement: str = "Фикстура.") -> dict:
    """Родитель на `spec_gate` с SPEC на диске песочницы: (id, название,
    первый абзац «Контекст», названия частей)."""
    title = f"Родитель {words(stand, 3)}"
    _, parent = capture_new_task_id(catalog.cmd_new, title)
    context = f"Цель фикстуры: {words(stand, 4)} {stand.rng.randrange(1 << 20)}."
    parts = ([f"Часть {w}" for w in stand.rng.sample(WORDS, stand.rng.randint(2, 3))]
             if divided else [])
    folder = stand.tdir.parent / parent
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SPEC.md").write_text(
        spec_text(parent, next_zone(stand), context, parts, requirement),
        encoding="utf-8")
    conn = store.db()
    conn.execute("UPDATE tasks SET state='spec_gate' WHERE id=?", (parent,))
    conn.commit()
    return {"id": parent, "title": title, "context": context, "parts": parts}


def epic_new(stand) -> str:
    before = set(epics())
    out, code = cli("epic", "new", config.DEFAULT_TARGET, f"Эпик {words(stand)}",
                    "--goal", f"Цель {words(stand)}")
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new ({code}):\n{out}")
    return added.pop()


def in_epic(stand, parent: str) -> str:
    epic_id = epic_new(stand)
    out, code = cli("epic", "add", epic_id, parent)
    assert row(parent)["epic_id"] == epic_id, note(
        stand, f"предпосылка: epic add ({code}):\n{out}")
    return epic_id


# --- AC-11 ---

def test_ac11_parts_inherit_parent_epic(stand):
    """Родитель в эпике, `approve` деления на гейте SPEC: каждая часть заведена с тем же `epic_id`, что у родителя.

    Ловит мутацию: `spawn_subtask` заводит части без `epic_id` (эпик
    родителя не передаётся); части получают эпик только при
    `--as-epic`.
    """
    parent = parent_on_gate(stand)
    epic_id = in_epic(stand, parent["id"])

    out, code = cli("approve", parent["id"])

    parts = parts_of(parent["id"])
    assert len(parts) == len(parent["parts"]), note(stand, f"части {parts}:\n{out}")
    assert [row(p)["epic_id"] for p in parts] == [epic_id] * len(parts), note(
        stand, f"epic_id частей: {[row(p)['epic_id'] for p in parts]}")


# --- AC-12, AC-14 ---

def test_ac12_as_epic_creates_epic_from_parent(stand):
    """`approve <id> --as-epic` у родителя без эпика с делением: эпик проекта родителя с его названием, целью — первым абзацем «Контекст», без конверта; части и родитель (с `closed_as='divided'`) в эпике, родитель — строкой `epic show`; журнал родителя называет эпик.

    Ловит мутацию: цель берётся всем разделом «Контекст» (со вторым
    абзацем) или названием; родитель остаётся вне эпика (`epic_id`
    пишется только частям); запись журнала родителя об эпике не пишется;
    конверт ставится потолком родителя.
    """
    parent = parent_on_gate(stand)
    before = set(epics())

    out, code = cli("approve", parent["id"], "--as-epic")

    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"эпиков заведено {added} ({code}):\n{out}")
    epic_id = added.pop()
    epic = epics()[epic_id]
    assert (epic["project"], epic["title"], epic["goal"].strip(),
            epic["envelope_usd"]) == (config.DEFAULT_TARGET, parent["title"],
                                      parent["context"], None), note(
        stand, f"эпик {epic}")
    parts = parts_of(parent["id"])
    assert len(parts) == len(parent["parts"]), note(stand, out)
    assert [row(p)["epic_id"] for p in parts] == [epic_id] * len(parts)
    assert row(parent["id"])["epic_id"] == epic_id, note(stand, "родитель вне эпика")
    assert row(parent["id"])["closed_as"] == "divided", note(stand, "closed_as")
    shown, _ = cli("epic", "show", epic_id)
    assert any(parent["id"] in line for line in shown.splitlines()), note(
        stand, f"родителя нет в epic show:\n{shown}")
    journal = [f"{r['action']} {r['detail'] or ''}"
               for r in store.task_steps(store.db(), parent["id"])]
    assert any(epic_id in entry for entry in journal), note(
        stand, f"журнал родителя не называет {epic_id}: {journal}")


def test_ac14_cli_flag_is_not_taken_for_sha(stand):
    """CLI: `approve <id> --as-epic` идёт как approve без позиционного `sha` и заводит эпик; `approve <id> <sha> --as-epic` передаёт `<sha>` позиционным `sha` и флаг.

    Флаг во втором вызове распознаётся сравнением с вызовом без флага:
    в вызове с флагом есть аргумент, которого (или чьей истинности) нет
    в вызове без флага.

    Ловит мутацию: `_approve_sha_arg` не пропускает `--as-epic` —
    флаг уходит позиционным `sha`, approve отказывает сверкой sha и
    эпика не заводит; при позиционном `sha` флаг теряется.
    """
    parent = parent_on_gate(stand)
    before = set(epics())
    with mock.patch.object(fsm, "cmd_approve", wraps=fsm.cmd_approve) as spy:
        out, code = cli("approve", parent["id"], "--as-epic")
    assert spy.called, note(stand, f"fsm.cmd_approve не вызван:\n{out}")
    call = spy.call_args
    sha = call.args[1] if len(call.args) > 1 else call.kwargs.get("sha")
    assert sha is None, note(stand, f"флаг принят за sha: {sha!r}")
    assert len(set(epics()) - before) == 1, note(stand, f"эпик не заведён:\n{out}")

    other = parent_on_gate(stand)
    sha_value = "".join(stand.rng.choice("0123456789abcdef") for _ in range(40))
    calls = {}
    for flagged in (True, False):
        args = ["approve", other["id"], sha_value] + (["--as-epic"] if flagged else [])
        with mock.patch.object(fsm, "cmd_approve") as fake:
            cli(*args)
        assert fake.called, note(stand, f"cmd_approve не вызван для {args}")
        calls[flagged] = fake.call_args
    flagged_call, plain_call = calls[True], calls[False]
    passed = (flagged_call.args[1] if len(flagged_call.args) > 1
              else flagged_call.kwargs.get("sha"))
    assert passed == sha_value, note(stand, f"sha {passed!r}")
    plain = dict(enumerate(plain_call.args)) | plain_call.kwargs
    marked = dict(enumerate(flagged_call.args)) | flagged_call.kwargs
    assert any(value and not plain.get(key) for key, value in marked.items()), (
        note(stand, f"флаг не передан: {flagged_call} против {plain_call}"))


# --- AC-13, AC-37: отказы до lease ---

def refusal_parent(stand, case: str) -> dict:
    if case == "no-division":
        return parent_on_gate(stand, divided=False)
    parent = parent_on_gate(stand)
    in_epic(stand, parent["id"])
    return parent


@pytest.mark.parametrize("case", ["no-division", "already-in-epic"])
def test_ac13_as_epic_refused_without_any_write(stand, case):
    """`approve --as-epic` у задачи без деления или уже в эпике: отказ; строки `tasks`, `epics`, `steps` равны снимку, `lease.run_locked` не вызывался.

    Ловит мутацию: проверка «есть деление/нет эпика» идёт внутри
    `lease.run_locked` (запись «lease взят» в журнале, вызов run_locked);
    у задачи без деления `--as-epic` молча игнорируется и approve
    переводит её дальше; эпик заводится до проверки.
    """
    parent = refusal_parent(stand, case)
    before = snapshot()
    with mock.patch.object(lease, "run_locked", wraps=lease.run_locked) as spy:
        out, code = cli("approve", parent["id"], "--as-epic")
    assert not spy.called, note(stand, f"run_locked вызван:\n{out}")
    assert snapshot() == before, note(stand, f"БД изменена:\n{out}")
    assert out.strip(), note(stand, "отказ без причины")


@pytest.mark.parametrize("case", ["no-division", "already-in-epic"])
def test_ac37_refusal_after_spec_read_writes_no_steps(stand, case):
    """Отказ `--as-epic` после чтения SPEC родителя (SPEC читается): в `steps` не добавлено ни одной записи.

    Ловит мутацию: предварительное чтение SPEC идёт общим узлом гейта
    `_read_branch_text_or_refuse`/журналирующим отказом — запись
    «approve отклонён» в журнале.
    """
    parent = refusal_parent(stand, case)
    since = store.db().execute("SELECT COALESCE(MAX(id), 0) FROM steps").fetchone()[0]
    out, code = cli("approve", parent["id"], "--as-epic")
    added = [tuple(r) for r in store.db().execute(
        "SELECT task_id, action FROM steps WHERE id > ?", (since,))]
    assert added == [], note(stand, f"записи журнала: {added}\n{out}")


def test_ac37_unreadable_parent_spec_refused(stand):
    """SPEC родителя без эпика на ветке не читается: `approve --as-epic` — отказ, текст говорит, что SPEC родителя не прочитан; `tasks`, `epics`, `steps` равны снимку, `lease.run_locked` не вызывался.

    Ловит мутацию: нечитаемый SPEC принимается за «нет деления» (текст
    отказа о делении, а не о чтении SPEC); отказ идёт гейтом под lease
    с записью журнала.
    """
    parent = parent_on_gate(stand)
    (stand.tdir.parent / parent["id"] / "SPEC.md").unlink()
    before = snapshot()
    with mock.patch.object(lease, "run_locked", wraps=lease.run_locked) as spy:
        out, code = cli("approve", parent["id"], "--as-epic")
    assert re.search(r"SPEC.*не прочитан|не прочитан.*SPEC", out, re.S), note(
        stand, f"отказ не говорит о непрочитанном SPEC:\n{out}")
    assert not spy.called, note(stand, "run_locked вызван")
    assert snapshot() == before, note(stand, f"БД изменена:\n{out}")


# --- AC-36 ---

@pytest.mark.parametrize("case", ["audit-fail", "unclassified-path"])
def test_ac36_soft_gate_refusal_creates_no_epic(stand, case):
    """Мягкий отказ гейта SPEC (вердикт аудита `fail` без `--accept-audit-fail`; путь SPEC вне `zones:`): `approve --as-epic` не заводит эпик, родитель на `spec_gate` без `epic_id`, частей нет.

    Ловит мутацию: эпик заводится до обработчика гейта (в обёртке
    `--as-epic`), а не вместе с частями — мягкий отказ оставляет пустой
    эпик и `epic_id` родителя.
    """
    if case == "audit-fail":
        parent = parent_on_gate(stand)
        store.journal(store.db(), parent["id"], "fsm", spec_audit.VERDICT_ACTION,
                      "вердикт fail; сигналы: нет")
    else:
        stray = f"orchestrator/t_epic_stray_{stand.rng.randrange(1 << 20)}.py"
        (config.ROOT / stray).parent.mkdir(parents=True, exist_ok=True)
        (config.ROOT / stray).write_text("# фикстура\n", encoding="utf-8")
        parent = parent_on_gate(stand, requirement=f"Правка {stray}.")
    before = epics()

    out, code = cli("approve", parent["id"], "--as-epic")

    assert epics() == before, note(stand, f"эпик заведён:\n{out}")
    assert row(parent["id"])["state"] == "spec_gate", note(stand, out)
    assert not row(parent["id"])["epic_id"], note(stand, "epic_id родителя")
    assert parts_of(parent["id"]) == [], note(stand, "части заведены")
