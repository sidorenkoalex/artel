"""AC-29: `status` без единой задачи с эпиком — прежний вывод, без блоков
проектов.

Группа: разовый
Зелёный с рождения: без эпиков `status` кода до задачи печатает ровно строку на задачу по возрастанию id без заголовков проектов — тест держит этот прежний вывод.

Факт задачи — «вывод не изменился относительно базы»: эталон — вывод
`status` кода main после мержа Э0 (01M5TB6VDVV6AM8DWPGVQE8CDW) на этой же
фикстуре. На шаге tests_writing эталона нет (SPEC, AC-29): тест строится
от фикстуры и держит форму прежнего вывода — строки задач по возрастанию
id, без заголовков блоков проектов. Эталон `REFERENCE_STATUS` вносит
сессия при Операторе командой `amend-tests` (ADR-0012), сняв его кодом
main после мержа Э0; с ним тест сверяет вывод целиком. Разработчик эталон
не вписывает.

Фикстура детерминирована (id, названия, состояния, суммы — литералы),
иначе эталон не воспроизводим: задачи трёх проектов (артель и два
внешних), в том числе часть деления и задача с зависимостью мержа, ни
одной задачи в эпике.
"""
import contextlib
import io

from orchestrator import catalog, store
from tests.sandbox import declare_target

# Эталон вывода `status` кода main после мержа Э0 на фикстуре ниже —
# вносится командой `amend-tests` (AC-29); `None` — эталона ещё нет.
REFERENCE_STATUS = None

TASKS = (
    # (id, название, состояние, проект, потрачено, потолок)
    ("01M5AC29TEST0000000000000A", "Артель первая", "in_dev", "artel", 1.25, 25.0),
    ("01M5AC29TEST0000000000000B", "Внешняя бета", "spec_gate", "beta-proj", 0.0, 40.0),
    ("01M5AC29TEST0000000000000C", "Внешняя альфа", "review", "alpha-proj", 3.5, 30.0),
    ("01M5AC29TEST0000000000000D", "Артель часть", "spec_writing", "artel", 0.0, 50.0),
    ("01M5AC29TEST0000000000000E", "Артель готовая", "done", "artel", 7.0, 20.0),
    ("01M5AC29TEST0000000000000F", "Бета зависимая", "acceptance", "beta-proj", 2.0, 35.0),
)
PARENT_LINK = ("01M5AC29TEST0000000000000D", "01M5AC29TEST0000000000000A")
DEPENDENCY = ("01M5AC29TEST0000000000000F", "01M5AC29TEST0000000000000B")


def status_of_fixture() -> str:
    for project in ("alpha-proj", "beta-proj"):
        declare_target(project)
    conn = store.db()
    for task_id, title, state, project, spent, budget in TASKS:
        store.insert_task(conn, task_id, title, state,
                          f"task/{task_id.lower()}-x", project, budget)
        conn.execute("UPDATE tasks SET spent_usd=? WHERE id=?", (spent, task_id))
    part, parent = PARENT_LINK
    conn.execute("UPDATE tasks SET parent_task_id=? WHERE id=?", (parent, part))
    dependent, dependency = DEPENDENCY
    conn.execute("UPDATE tasks SET merge_after=? WHERE id=?",
                 (dependency, dependent))
    conn.commit()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        catalog.cmd_status()
    return buf.getvalue()


def test_ac29_status_without_epics_is_unchanged(initialized_tmp_root):
    """Фикстура трёх проектов без эпиков: `status` — строка на задачу по возрастанию id, без заголовков блоков проектов; при внесённом эталоне — тот же текст, что `status` кода main после мержа Э0.

    Ловит мутацию: блоки проектов печатаются всегда, а не только при
    задаче с эпиком (строка-заголовок «alpha-proj» перед её задачами);
    задачи группируются по проекту и теряют порядок по id.
    """
    out = status_of_fixture()
    lines = [line for line in out.splitlines() if line.strip()]
    ids = sorted(task_id for task_id, *_ in TASKS)
    assert [line.split()[0] for line in lines] == ids, out
    assert all(not line.startswith(" ") for line in lines), out
    if REFERENCE_STATUS is not None:
        assert out == REFERENCE_STATUS, out
