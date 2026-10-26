"""Черновики и решения эпика: `epic draft add|edit|drop|promote`,
`epic decision`, готовность эпика к закрытию с учётом черновиков.

Группа: долгоживущий
Красен до реализации: подкоманд `epic draft` и `epic decision` нет (на ветке до подтяжки main с шагом Э1 — раньше: таблицы `epics` нет) («epic: нужна подкоманда»), таблиц `epic_drafts` и `epic_decisions` нет (чтение строк падает `no such table`), а `epic close` и «эпик готов к закрытию» черновиков не учитывают.

Держит связку «команда CLI `artel.py` — БД»: каждый сценарий идёт через
`artel.main()` в лёгкой песочнице переходов (`light_transition`),
состояние сверяется по строкам `tasks`, `epics`, `epic_drafts`,
`epic_decisions`, `steps`. Имена колонок таблиц черновиков и решений SPEC
не называет — строка черновика (решения) находится по значениям: id
эпика, название, текст ТЗ, рамка, номер, состояние (`draft`, `promoted`,
`dropped`) ищутся среди значений строки, а не в колонке с заданным
именем. Названия, тексты ТЗ, рамки, тексты решений и порядок элементов
порождаются модулем `random` при каждом запуске; зерно печатается и
входит в текст провала.
"""
import contextlib
import importlib
import io
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, budget, config, idgen, store

WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}.*")
TABLES = ("tasks", "epics", "epic_drafts", "epic_decisions", "steps", "leases")


# --- окружение сценария ---

def epics():
    """Модуль эпиков — импортом при вызове: на ветке без шага Э1 его нет,
    а модуль тестов обязан собираться."""
    return importlib.import_module("orchestrator.epics")


@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов с зерном сценария."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
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


def marker(stand) -> str:
    return f"{stand.rng.randrange(1 << 40):x}"


def frame(stand) -> float:
    """Рамка черновика — дробная, чтобы не совпасть ни с номером, ни с rowid."""
    return round(stand.rng.uniform(5, 60), 2) + 0.25


def rows(table: str) -> list[dict]:
    return [dict(r) for r in store.db().execute(f"SELECT * FROM {table}")]


def snapshot() -> dict:
    conn = store.db()
    return {table: [tuple(r) for r in conn.execute(
        f"SELECT * FROM {table} ORDER BY rowid")] for table in TABLES}


def epic_rows() -> dict:
    return {r["id"]: r for r in rows("epics")}


def drafts_of(epic_id: str) -> list[dict]:
    return [r for r in rows("epic_drafts") if epic_id in r.values()]


def draft_titled(stand, epic_id: str, title: str) -> dict:
    found = [r for r in drafts_of(epic_id) if title in r.values()]
    assert len(found) == 1, note(stand, f"черновиков «{title}»: {found}")
    return found[0]


def ints(row: dict) -> set:
    return {v for v in row.values() if isinstance(v, int)
            and not isinstance(v, bool)}


def has_number(row: dict, value: float) -> bool:
    return any(isinstance(v, (int, float)) and not isinstance(v, bool)
               and abs(v - value) < 1e-6 for v in row.values())


def task_ids() -> set:
    return {r["id"] for r in store.all_tasks(store.db())}


def task(task_id: str):
    return store.get_task(store.db(), task_id)


def ids_in(value, known) -> list[str]:
    """Id задач из `known`, названные в значении колонки, по порядку."""
    return [t for t in re.findall(r"\w+", value or "") if t in known]


def epic_new(stand, project: str = config.DEFAULT_TARGET) -> str:
    before = set(epic_rows())
    out, code = cli("epic", "new", project, f"Эпик {words(stand, 3)}",
                    "--goal", f"Цель {words(stand, 3)}")
    added = set(epic_rows()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new ({code}):\n{out}")
    return added.pop()


def insert_task(stand, state: str = "in_dev", *, epic: str | None = None) -> str:
    """Задача артели; если `epic` — привязана `epic add`, затем в `state`."""
    task_id = idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {words(stand)}", "in_dev",
                      f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                      config.DEFAULT_BUDGET_USD)
    if epic is not None:
        out, code = cli("epic", "add", epic, task_id)
        assert task(task_id)["epic_id"] == epic, note(
            stand, f"предпосылка: epic add ({code}):\n{out}")
    set_state(task_id, state)
    return task_id


def set_state(task_id: str, state: str) -> None:
    conn = store.db()
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()


def tz_file(stand, title: str | None = None) -> tuple[str, str, str]:
    """Файл ТЗ: (путь, название — первый заголовок `# `, полный текст)."""
    title = title or f"Черновик {words(stand)} {marker(stand)}"
    text = (f"# {title}\n\nИсточник: фикстура {stand.seed}.\n\n"
            f"Требуется:\n1. Поправить {words(stand, 3)} {marker(stand)}.\n")
    if stand.rng.random() < 0.5:
        text += f"\n## Подробности\n\nТекст {words(stand)}.\n"
    path = stand.root / f"tz-{marker(stand)}.md"
    path.write_text(text, encoding="utf-8")
    return str(path), title, text


def draft_add(stand, epic_id: str, *flags: str) -> dict:
    """`epic draft add`: заведённый черновик (строка БД) с полями сценария."""
    path, title, text = tz_file(stand)
    out, code = cli("epic", "draft", "add", epic_id, "--tz", path, *flags)
    found = [r for r in drafts_of(epic_id) if title in r.values()]
    assert len(found) == 1, note(
        stand, f"предпосылка: epic draft add ({code}):\n{out}")
    return {"title": title, "text": text, "row": found[0]}


def noise_drafts(stand) -> None:
    """Черновики соседнего эпика: rowid строк сценария не совпадут с
    номерами черновиков в его эпике."""
    other = epic_new(stand)
    for _ in range(stand.rng.randint(3, 5)):
        draft_add(stand, other)


def promote(stand, address: str) -> str:
    before = task_ids()
    out, code = cli("epic", "draft", "promote", address)
    created = task_ids() - before
    assert len(created) == 1, note(
        stand, f"promote {address} завёл {created} ({code}):\n{out}")
    return created.pop()


# --- AC-1 ---

def test_ac1_draft_add_numbers_text_title_frame_and_refusals(stand):
    """Два `epic draft add` в открытый эпик: черновики `draft` с номерами 1 и 2, текст ТЗ дословно равен файлу, название — первый заголовок `# `, рамка — `--budget N`; `add` в закрытый и в несуществующий эпик отказывает, строк черновиков не прибавляется.

    Ловит мутацию: номер черновика считается по всей таблице, а не в
    эпике (у первого черновика эпика — не 1); текст ТЗ хранится с
    обрезанными концами или без заголовка; название берётся из имени
    файла или второго заголовка; `--budget` не записывается рамкой;
    `add` не проверяет состояние эпика — в закрытый эпик черновик
    заводится.
    """
    noise_drafts(stand)
    epic_id = epic_new(stand)
    first_frame, second_frame = frame(stand), frame(stand)

    first = draft_add(stand, epic_id, "--budget", str(first_frame))
    second = draft_add(stand, epic_id, "--budget", str(second_frame))

    for item, number, frame_value in ((first, 1, first_frame),
                                      (second, 2, second_frame)):
        row = item["row"]
        assert "draft" in row.values(), note(stand, f"состояние: {row}")
        assert item["text"] in row.values(), note(
            stand, f"текст ТЗ не равен файлу дословно: {row}")
        assert item["title"] in row.values(), note(stand, f"название: {row}")
        assert has_number(row, frame_value), note(
            stand, f"рамка {frame_value} не записана: {row}")
        assert number in ints(row), note(stand, f"номер {number}: {row}")
    assert 1 not in ints(second["row"]), note(
        stand, f"второй черновик несёт номер 1: {second['row']}")

    closed = epic_new(stand)
    insert_task(stand, "done", epic=closed)
    out, code = cli("epic", "close", closed, f"Итог {words(stand)}")
    assert epic_rows()[closed]["state"] == "closed", note(
        stand, f"предпосылка: epic close ({code}):\n{out}")
    ghost = epics().EPIC_PREFIX + idgen.new_task_id()
    for target in (closed, ghost):
        count = len(rows("epic_drafts"))
        path, _, _ = tz_file(stand)
        out, code = cli("epic", "draft", "add", target, "--tz", path,
                        "--budget", str(frame(stand)))
        assert code != 0, note(stand, f"add в {target} не отказал:\n{out}")
        assert out.strip(), note(stand, "отказ без причины")
        assert len(rows("epic_drafts")) == count, note(
            stand, f"add в {target} завёл черновик:\n{out}")


# --- AC-2 ---

def test_ac2_promote_creates_task_with_epic_frame_and_dependencies(stand):
    """`epic draft promote <id>/<n>` черновика с рамкой, `--start-after A` и `--after B`: задача с `epic_id` эпика, потолком, равным рамке, `start_after` = [A], `merge_after` = [B]; черновик `promoted`, задача-результат — id заведённой задачи.

    Ловит мутацию: `promote` зовёт путь `new` без `epic_id` (задача вне
    эпика); `start_after` черновика уходит в `merge_after` задачи (или
    теряется); рамка не становится потолком (потолок по умолчанию);
    черновик остаётся `draft` или задача-результат не записана.
    """
    noise_drafts(stand)
    epic_id = epic_new(stand)
    a, b = insert_task(stand), insert_task(stand)
    frame_value = frame(stand)
    item = draft_add(stand, epic_id, "--budget", str(frame_value),
                     "--start-after", a, "--after", b)

    new_id = promote(stand, f"{epic_id}/1")

    row = task(new_id)
    known = task_ids()
    assert row["epic_id"] == epic_id, note(stand, f"epic_id {row['epic_id']!r}")
    assert row["budget_usd"] == pytest.approx(frame_value), note(
        stand, f"потолок {row['budget_usd']} ≠ рамке {frame_value}")
    assert ids_in(row["start_after"], known) == [a], note(
        stand, f"start_after {row['start_after']!r}")
    assert ids_in(row["merge_after"], known) == [b], note(
        stand, f"merge_after {row['merge_after']!r}")
    draft = draft_titled(stand, epic_id, item["title"])
    assert "promoted" in draft.values(), note(stand, f"состояние: {draft}")
    assert new_id in draft.values(), note(stand, f"задача-результат: {draft}")


# --- AC-3 ---

@pytest.mark.parametrize("flag,column", [("--start-after", "start_after"),
                                         ("--after", "merge_after")])
def test_ac3_promote_waits_for_referenced_draft_then_resolves_it(stand, flag,
                                                                 column):
    """Черновик B ссылается адресом на черновик A: пока A `draft`, `promote` B отказывает, называя A, задача не заводится, B — `draft`; после `promote` A `promote` B заводит задачу, у которой на месте адреса A — id задачи-результата A.

    Ловит мутацию: `promote` не проверяет состояние черновиков из
    перечня — B заводится с адресом A вместо id задачи; адрес черновика
    не разрешается в id задачи-результата (в колонке задачи остаётся
    `<id эпика>/<n>`); отказ не перечисляет незаведённый черновик.
    """
    noise_drafts(stand)
    epic_id = epic_new(stand)
    first = draft_add(stand, epic_id)
    second = draft_add(stand, epic_id, flag, f"{epic_id}/1")

    before, tasks_before = snapshot(), task_ids()
    out, code = cli("epic", "draft", "promote", f"{epic_id}/2")
    assert code != 0, note(stand, f"promote B не отказал:\n{out}")
    assert f"{epic_id}/1" in out or first["title"] in out, note(
        stand, f"отказ не называет черновик A:\n{out}")
    assert task_ids() == tasks_before, note(stand, "задача заведена")
    assert "draft" in draft_titled(stand, epic_id, second["title"]).values()
    assert snapshot()["epic_drafts"] == before["epic_drafts"]

    a_task = promote(stand, f"{epic_id}/1")
    b_task = promote(stand, f"{epic_id}/2")

    value = task(b_task)[column]
    assert ids_in(value, task_ids()) == [a_task], note(
        stand, f"{column} задачи B: {value!r}, ждали [{a_task}]")
    assert f"{epic_id}/" not in (value or ""), note(
        stand, f"адрес черновика не разрешён: {value!r}")


# --- AC-5 ---

def test_ac5_edit_and_drop_change_draft_then_non_draft_refused(stand):
    """`edit --budget` меняет только рамку; `edit --tz --start-after --after` — текст, название и перечни (их видно в задаче после `promote`); `drop` даёт `dropped`; `edit`, `drop`, `promote` черновика `promoted` и `dropped` — отказ, БД не меняется.

    Ловит мутацию: `edit` перезаписывает неназванные поля пустыми
    (после `--budget` пропадает текст ТЗ); новый `--tz` меняет текст, но
    не название; `edit`/`drop`/`promote` не проверяют состояние —
    повторный `promote` заводит вторую задачу, `drop` переводит
    `promoted` в `dropped`.
    """
    noise_drafts(stand)
    epic_id = epic_new(stand)
    old_frame, new_frame = frame(stand), frame(stand)
    item = draft_add(stand, epic_id, "--budget", str(old_frame))

    out, code = cli("epic", "draft", "edit", f"{epic_id}/1", "--budget",
                    str(new_frame))
    row = draft_titled(stand, epic_id, item["title"])
    assert has_number(row, new_frame) and not has_number(row, old_frame), note(
        stand, f"рамка после edit ({code}): {row}\n{out}")
    assert item["text"] in row.values(), note(stand, f"текст ТЗ задет: {row}")

    x, y = insert_task(stand), insert_task(stand)
    path, title, text = tz_file(stand)
    out, code = cli("epic", "draft", "edit", f"{epic_id}/1", "--tz", path,
                    "--start-after", x, "--after", y)
    row = draft_titled(stand, epic_id, title)
    assert text in row.values(), note(stand, f"текст после edit: {row}\n{out}")
    assert item["text"] not in row.values() and item["title"] not in row.values()
    assert has_number(row, new_frame), note(stand, f"рамка задета: {row}")

    promoted = promote(stand, f"{epic_id}/1")
    known = task_ids()
    assert ids_in(task(promoted)["start_after"], known) == [x], note(
        stand, f"start_after: {task(promoted)['start_after']!r}")
    assert ids_in(task(promoted)["merge_after"], known) == [y], note(
        stand, f"merge_after: {task(promoted)['merge_after']!r}")

    dropped = draft_add(stand, epic_id)
    out, code = cli("epic", "draft", "drop", f"{epic_id}/2")
    assert "dropped" in draft_titled(stand, epic_id, dropped["title"]).values(), \
        note(stand, f"drop ({code}):\n{out}")

    path, _, _ = tz_file(stand)
    for address in (f"{epic_id}/1", f"{epic_id}/2"):
        for args in (("edit", address, "--budget", str(frame(stand))),
                     ("edit", address, "--tz", path),
                     ("drop", address), ("promote", address)):
            before = snapshot()
            out, code = cli("epic", "draft", *args)
            assert code != 0, note(stand, f"{args} не отказал:\n{out}")
            assert snapshot() == before, note(stand, f"{args} изменил БД:\n{out}")


# --- AC-6, AC-17 ---

def decision_rows(epic_id: str) -> list[dict]:
    """Строки решений эпика с rowid (ключ `fixture_rowid`)."""
    return [dict(r) for r in store.db().execute(
        "SELECT rowid AS fixture_rowid, * FROM epic_decisions")
        if epic_id in dict(r).values()]


def binding(row: dict, text: str, epic_id: str) -> tuple:
    """Значения строки решения помимо текста, эпика, времени и rowid."""
    rest = [v for k, v in row.items() if k != "fixture_rowid" and v is not None
            and v != text and v != epic_id and v != row["fixture_rowid"]
            and not (isinstance(v, str) and TIME_RE.fullmatch(v))]
    return tuple(sorted(map(repr, rest)))


def decision_text(stand) -> str:
    return (f"  «Решение {words(stand)} {marker(stand)}» \"в кавычках\" "
            f"'и так'\n  вторая строка {words(stand)}\t  ")


def test_ac6_decision_text_is_byte_exact_and_carries_binding(stand):
    """`epic decision` с текстом с пробелами по краям, кавычками и переводом строки пишет строку с текстом, равным аргументу; без `--for`, с `--for <id>/<n>`, `--for <задача>` и `--for envelope` привязки строк различны, задача и номер черновика в своих строках названы; `--for` на несуществующий черновик — отказ, строка не пишется.

    Ловит мутацию: текст решения проходит `strip()` или нормализацию
    пробелов; `--for` разбирается, но не записывается (все строки
    одинаковы помимо текста); `--for envelope` пишется как решение
    эпика целиком; проверка черновика из `--for` пропущена — строка
    решения пишется на адрес без черновика.
    """
    epic_id = epic_new(stand)
    for _ in range(stand.rng.randint(4, 7)):
        cli("epic", "decision", epic_id, f"Шум {marker(stand)}")
    item = draft_add(stand, epic_id)
    member = insert_task(stand, epic=epic_id)
    cases = [("эпик", ()), ("черновик", ("--for", f"{epic_id}/1")),
             ("задача", ("--for", member)), ("конверт", ("--for", "envelope"))]
    stand.rng.shuffle(cases)

    found = {}
    for kind, flags in cases:
        text = decision_text(stand)
        out, code = cli("epic", "decision", epic_id, text, *flags)
        exact = [r for r in decision_rows(epic_id) if text in r.values()]
        assert len(exact) == 1, note(
            stand, f"{kind}: строк с дословным текстом {len(exact)} ({code}):\n"
                   f"{out}\n{decision_rows(epic_id)}")
        found[kind] = (exact[0], text)

    sigs = {kind: binding(row, text, epic_id) for kind, (row, text) in found.items()}
    assert len(set(sigs.values())) == len(sigs), note(
        stand, f"привязки не различаются: {sigs}")
    assert any(isinstance(v, str) and member in v
               for v in found["задача"][0].values()), note(
        stand, f"строка не называет задачу {member}: {found['задача'][0]}")
    draft_sig = sigs["черновик"]
    assert any(token in draft_sig for token in (repr(f"{epic_id}/1"), repr(1),
                                                repr("1"))), note(
        stand, f"строка не называет черновик 1 «{item['title']}»: {draft_sig}")

    count = len(decision_rows(epic_id))
    out, code = cli("epic", "decision", epic_id, decision_text(stand),
                    "--for", f"{epic_id}/{stand.rng.randint(5, 99)}")
    assert code != 0, note(stand, f"--for без черновика не отказал:\n{out}")
    assert len(decision_rows(epic_id)) == count, note(stand, "строка записана")


def test_ac17_decision_for_unknown_task_refused(stand):
    """`epic decision <id> "<текст>" --for <id>`, где id не задача БД: отказ, строка решения не пишется; тот же вызов с id задачи БД строку пишет.

    Ловит мутацию: `--for` с любым значением, не адресом черновика и не
    `envelope`, пишется без проверки по `tasks` — решение привязано к
    несуществующей задаче.
    """
    epic_id = epic_new(stand)
    member = insert_task(stand, epic=epic_id)
    out, code = cli("epic", "decision", epic_id, decision_text(stand),
                    "--for", member)
    assert len(decision_rows(epic_id)) == 1, note(
        stand, f"предпосылка: решение по задаче БД ({code}):\n{out}")

    before = snapshot()["epic_decisions"]
    out, code = cli("epic", "decision", epic_id, decision_text(stand),
                    "--for", idgen.new_task_id())
    assert code != 0, note(stand, f"--for не задачи не отказал:\n{out}")
    assert snapshot()["epic_decisions"] == before, note(stand, "строка записана")


# --- AC-16 ---

@pytest.mark.parametrize("flag", ["--start-after", "--after"])
@pytest.mark.parametrize("command", ["add", "edit"])
def test_ac16_unknown_list_elements_refused_with_full_listing(stand, flag,
                                                              command):
    """Перечень `--start-after`/`--after` с несуществующей задачей и адресом без черновика (вперемешку с годной задачей): `add` и `edit` отказывают, называя оба элемента; черновик не заводится и не меняется.

    Ловит мутацию: перечень черновика не проверяется вовсе; проверка
    останавливается на первом негодном элементе — второй в отказе не
    назван; адрес `<id эпика>/<n>` принимается без проверки черновика.
    """
    noise_drafts(stand)
    epic_id = epic_new(stand)
    draft_add(stand, epic_id)
    ghosts = [idgen.new_task_id(), f"{epic_id}/{stand.rng.randint(5, 99)}"]
    items = ghosts + [insert_task(stand)]
    stand.rng.shuffle(items)
    value = ",".join(items)

    before = snapshot()
    if command == "add":
        path, _, _ = tz_file(stand)
        out, code = cli("epic", "draft", "add", epic_id, "--tz", path, flag, value)
    else:
        out, code = cli("epic", "draft", "edit", f"{epic_id}/1", flag, value)

    assert code != 0, note(stand, f"{command} {flag} {value} не отказал:\n{out}")
    for ghost in ghosts:
        assert ghost in out, note(stand, f"отказ не называет {ghost}:\n{out}")
    assert snapshot()["epic_drafts"] == before["epic_drafts"], note(
        stand, f"черновики изменены:\n{out}")


# --- AC-18 ---

def test_ac18_number_after_drop_is_max_plus_one(stand):
    """Три черновика, `drop` третьего, новый `add`: номер нового — 4, не 3; адрес `<id>/3` по-прежнему указывает на отброшенный черновик — `promote` по нему отказывает его состоянием `dropped`, задача не заводится.

    Ловит мутацию: номер — число черновиков в состоянии `draft` плюс
    один (новый получает 3); `drop` удаляет строку, и номер
    переиспользуется; адрес разрешается в черновик по позиции в
    перечне, а не по номеру — `promote <id>/3` заводит задачу из нового
    черновика.
    """
    noise_drafts(stand)
    epic_id = epic_new(stand)
    third = None
    for _ in range(3):
        third = draft_add(stand, epic_id)
    out, code = cli("epic", "draft", "drop", f"{epic_id}/3")
    assert "dropped" in draft_titled(stand, epic_id, third["title"]).values(), \
        note(stand, f"предпосылка: drop ({code}):\n{out}")

    fresh = draft_add(stand, epic_id)

    assert 4 in ints(fresh["row"]) and 3 not in ints(fresh["row"]), note(
        stand, f"номер нового черновика: {fresh['row']}")
    tasks_before = task_ids()
    out, code = cli("epic", "draft", "promote", f"{epic_id}/3")
    assert code != 0 and "dropped" in out, note(
        stand, f"promote <id>/3 не отказал состоянием dropped:\n{out}")
    assert task_ids() == tasks_before, note(stand, "задача заведена")
    assert "dropped" in draft_titled(stand, epic_id, third["title"]).values()
    assert "draft" in draft_titled(stand, epic_id, fresh["title"]).values()


# --- AC-19 ---

def test_ac19_promoted_frame_is_operator_ceiling_not_overridden_by_spec(stand):
    """Задача из `promote` черновика с рамкой N: потолок N с источником `operator`; `budget.apply_spec_budget` (переход гейта SPEC) с `budget_usd` M ≠ N её потолок не меняет, а потолок обычной задачи тем же вызовом меняет на M.

    Ловит мутацию: рамка пишется потолком с источником `spec` (или без
    источника) — `budget_usd` из SPEC её перебивает; рамка игнорируется
    и задача получает потолок по умолчанию.
    """
    epic_id = epic_new(stand)
    frame_value = frame(stand)
    draft_add(stand, epic_id, "--budget", str(frame_value))
    new_id = promote(stand, f"{epic_id}/1")
    spec_value = round(stand.rng.uniform(1, config.ROLE_BUDGET_CAP - 1), 2)
    while abs(spec_value - frame_value) < 1:
        spec_value = round(stand.rng.uniform(1, config.ROLE_BUDGET_CAP - 1), 2)

    row = task(new_id)
    assert row["budget_usd"] == pytest.approx(frame_value), note(
        stand, f"потолок {row['budget_usd']} ≠ рамке {frame_value}")
    assert row["budget_source"] == config.BUDGET_SOURCE_OPERATOR, note(
        stand, f"источник потолка {row['budget_source']!r}")

    plain = insert_task(stand)
    conn = store.db()
    for task_id in (new_id, plain):
        budget.apply_spec_budget(conn, task(task_id), {"budget_usd": spec_value})
        conn.commit()
    assert task(plain)["budget_usd"] == pytest.approx(spec_value), note(
        stand, "предпосылка: apply_spec_budget не меняет потолок обычной задачи")
    assert task(new_id)["budget_usd"] == pytest.approx(frame_value), note(
        stand, f"SPEC перебил рамку: {task(new_id)['budget_usd']}")


# --- AC-20 ---

@pytest.mark.parametrize("release", ["drop", "promote"])
def test_ac20_draft_in_draft_state_blocks_ready_and_close(stand, release):
    """Все задачи эпика окончательны, черновик — `draft`: ни `epic show`, ни `status` не пишут «эпик готов к закрытию», `epic close` отказывает, называя черновик, эпик `open`; после `drop` (или `promote` и `done` задачи) эпик показан готовым и `epic close` его закрывает.

    Ловит мутацию: `ready_to_close` модели доски не смотрит на
    черновики; `epic close` проверяет только задачи — закрывает эпик с
    черновиком `draft`; черновик `dropped`/`promoted` по-прежнему
    мешает закрытию.
    """
    epic_id = epic_new(stand)
    insert_task(stand, "done", epic=epic_id)
    item = draft_add(stand, epic_id)

    for args in (("status",), ("epic", "show", epic_id)):
        out, _ = cli(*args)
        assert epics().READY_TEXT not in out, note(stand, f"{args}:\n{out}")
    out, code = cli("epic", "close", epic_id, f"Итог {words(stand)}")
    assert code != 0, note(stand, f"close не отказал:\n{out}")
    assert f"{epic_id}/1" in out or item["title"] in out, note(
        stand, f"отказ не называет черновик:\n{out}")
    assert epic_rows()[epic_id]["state"] == "open", note(stand, "эпик закрыт")

    if release == "drop":
        out, code = cli("epic", "draft", "drop", f"{epic_id}/1")
        assert "dropped" in draft_titled(stand, epic_id, item["title"]).values(), \
            note(stand, f"предпосылка: drop ({code}):\n{out}")
    else:
        set_state(promote(stand, f"{epic_id}/1"), "done")

    for args in (("status",), ("epic", "show", epic_id)):
        out, _ = cli(*args)
        assert epics().READY_TEXT in out, note(stand, f"{args}:\n{out}")
    outcome = f"Итог {words(stand, 3)}"
    out, code = cli("epic", "close", epic_id, outcome)
    row = epic_rows()[epic_id]
    assert (row["state"], row["outcome"]) == ("closed", outcome), note(
        stand, f"close после {release} ({code}): {dict(row)}\n{out}")
