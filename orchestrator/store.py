"""Состояние задач: БД, миграции схемы, журнал шагов, смена состояния.

Единственный модуль, который пишет SQL (ADR-0003 3ж): остальные зовут
здешние функции по имени. Смысл не в слое ради слоя, а в том, что смена
движка (Postgres — по триггеру «второй писатель», не по эпохе) правит
один файл, а не семь. Отсюда же и переносимость схемы: без
SQLite-экзотики, кроме включения WAL — оно и есть настройка движка.

БД одна на все target'ы: кошелёк Оператора один, суммарные лимиты
и тренды считаются одним запросом. Принадлежность строки проекту
хранит колонка `target` и у задач, и у записей журнала.
"""
import re
import sqlite3
import sys
from datetime import datetime, timezone

from . import config

# Схема БД. `target` в обеих таблицах: журнал не должен уметь разойтись
# с каталогом задач по принадлежности проекту. `task_counters` — нумерация
# задач per-target: персистентный счётчик, а не COUNT(*) (ADR-0003 3ж).
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0, budget_source TEXT,
  target TEXT, fixed_sha TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, target TEXT, ts TEXT,
  actor TEXT, action TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS task_counters (
  target TEXT PRIMARY KEY, next_number INTEGER NOT NULL
);
"""

TASK_ID = re.compile(r"\AT(\d+)\Z")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def db() -> sqlite3.Connection:
    config.DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(config.DB)
    conn.row_factory = sqlite3.Row
    enable_wal(conn)
    migrate(conn)
    return conn


def enable_wal(conn: sqlite3.Connection) -> str:
    """Включает WAL и возвращает фактический режим журнала БД.

    Читатель перестаёт блокировать писателя — это подготовка к панели
    и поллеру, которые читают ту же БД (ADR-0003 3ж). Режим хранится
    в файле БД, так что включение идемпотентно.

    Файловая система без поддержки WAL (сетевая шара) оставляет прежний
    режим — и это не повод не запускать CLI: сообщать «журнал БД
    остался в режиме X» есть кому (doctor, A3), а падать здесь незачем.
    """
    try:
        row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    except sqlite3.Error:
        return "unknown"
    return row[0] if row else "unknown"


def create_schema(conn: sqlite3.Connection) -> None:
    """Создаёт схему БД (команда `init`); повторный вызов ничего не ломает."""
    conn.executescript(SCHEMA)
    conn.commit()


def table_columns(conn: sqlite3.Connection, table: str) -> set:
    """Имена колонок таблицы; пустое множество — таблицы нет."""
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def add_column(conn: sqlite3.Connection, table: str, column: str,
               decl: str) -> None:
    """Добавляет колонку, если её нет. Нет таблицы — нечего догонять."""
    columns = table_columns(conn, table)
    if not columns or column in columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    """Догоняет схему БД, созданной прошлой версией (Фаза 0: без alembic)."""
    if not table_columns(conn, "tasks"):
        return  # БД ещё не создана: схему ставит `init`
    add_column(conn, "tasks", "reviewed_iter", "INTEGER DEFAULT 0")
    add_column(conn, "tasks", "escalated_from", "TEXT")
    # NULL в старых строках — «потолок никем не задан», то есть дефолт:
    # значение из SPEC применится к ним на общих основаниях.
    add_column(conn, "tasks", "budget_source", "TEXT")
    # Строки, заведённые до мультитаргета, принадлежат догфуду. DEFAULT
    # проставляет им 'artel' самой ALTER TABLE — отдельный UPDATE не нужен,
    # и конструкция остаётся переносимой (ADR-0003 3ж).
    for table in ("tasks", "steps"):
        add_column(conn, table, "target",
                   f"TEXT DEFAULT '{config.DEFAULT_TARGET}'")
    # NULL — фиксации ещё не было (строка старше T021 или задача ни разу
    # не переходила): approve/run читают это как «сверять не с чем»,
    # не как нарушение (tasks/T021 SPEC, требование 3).
    add_column(conn, "tasks", "fixed_sha", "TEXT")
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS task_counters ("
        "  target TEXT PRIMARY KEY, next_number INTEGER NOT NULL);")
    seed_task_counters(conn)
    conn.commit()


def task_number(task_id: str) -> int:
    """Номер задачи из идентификатора; 0 — идентификатор не нумерованный."""
    match = TASK_ID.match(task_id or "")
    return int(match.group(1)) if match else 0


def seed_task_counters(conn: sqlite3.Connection) -> None:
    """Заводит счётчик номеров каждому target'у, у которого его ещё нет.

    Начальное значение — за МАКСИМАЛЬНЫМ существующим номером задач
    target'а, а не за их количеством: строка, ушедшая в архив, номер
    не освобождает (ADR-0003 3ж). Засев идёт на миграции, то есть до
    любой архивации, которую сделает уже новый код.
    """
    known = {r["target"] for r in
             conn.execute("SELECT target FROM task_counters")}
    top: dict = {}
    for row in conn.execute("SELECT id, target FROM tasks"):
        target = row["target"] or config.DEFAULT_TARGET
        top[target] = max(top.get(target, 0), task_number(row["id"]))
    for target, number in top.items():
        if target not in known:
            conn.execute(
                "INSERT INTO task_counters (target, next_number) VALUES (?,?)",
                (target, number + 1))
    conn.commit()


def next_task_number(conn: sqlite3.Connection, target: str) -> int:
    """Номер следующей задачи target'а; счётчик сдвигается тем же вызовом.

    Номера не переиспользуются: счётчик не смотрит на строки задач вовсе,
    поэтому ни удаление строки, ни её уход в архив номер не возвращают.

    Чтение и сдвиг счётчика — одна транзакция на запись, взятая до чтения
    (`BEGIN IMMEDIATE`). Без неё SELECT остаётся вне транзакции — python
    открывает её только на UPDATE, — и два одновременных `new` читают один
    и тот же номер: второй `insert_task` падает IntegrityError. WAL
    (требование 5) заводится ровно ради второго процесса на этой БД, так
    что гонка перестаёт быть теоретической. Синтаксис у транзакции
    диалектный, схема — нет: переносимость схемы (ADR-0003 3ж) это
    не трогает, у Postgres роль `BEGIN IMMEDIATE` играет `SELECT ... FOR
    UPDATE`.
    """
    conn.commit()  # чужая незакрытая транзакция не даст взять свою
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT next_number FROM task_counters WHERE target=?",
            (target,)).fetchone()
        number = row["next_number"] if row is not None else 1
        if row is None:
            conn.execute(
                "INSERT INTO task_counters (target, next_number) VALUES (?,?)",
                (target, number + 1))
        else:
            conn.execute(
                "UPDATE task_counters SET next_number=? WHERE target=?",
                (number + 1, target))
    except BaseException:
        conn.rollback()
        raise
    conn.commit()
    return number


def insert_task(conn: sqlite3.Connection, task_id: str, title: str,
                state: str, branch: str, target: str,
                budget_usd: float) -> None:
    """Заводит строку задачи (команда `new`)."""
    stamp = now()
    conn.execute(
        "INSERT INTO tasks (id,title,state,branch,target,budget_usd,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (task_id, title, state, branch, target, budget_usd, stamp, stamp))
    conn.commit()


def update_task(conn: sqlite3.Connection, task_id: str, **fields) -> None:
    """Правит поля строки задачи: единственная точка UPDATE tasks.

    Имена полей сверяются со схемой: запрос собирается подстановкой, и
    точка сборки не должна становиться точкой инъекции. Значения уходят
    параметрами, как везде.

    `updated_at` вызывающий передаёт явно там, где он его двигал и
    раньше: у счётчиков итераций своя семантика — они правку задачи
    не отмечают.
    """
    if not fields:
        return
    columns = table_columns(conn, "tasks")
    unknown = fields.keys() - columns
    if unknown:
        raise ValueError(f"tasks: нет колонок {', '.join(sorted(unknown))}")
    assignments = ", ".join(f"{name}=?" for name in fields)
    conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                 (*fields.values(), task_id))
    conn.commit()


def charge(conn: sqlite3.Connection, task_id: str, usd: float) -> None:
    """Прибавляет стоимость шага к израсходованному задачей."""
    conn.execute("UPDATE tasks SET spent_usd=spent_usd+?, updated_at=? "
                 "WHERE id=?", (usd, now(), task_id))
    conn.commit()


def total_spent(conn: sqlite3.Connection) -> float:
    """Суммарный расход по всем задачам всех target'ов (roadmap §5)."""
    row = conn.execute("SELECT SUM(spent_usd) AS total FROM tasks").fetchone()
    return row["total"] or 0.0


def all_tasks(conn: sqlite3.Connection) -> list:
    """Все задачи по возрастанию идентификатора (команда `status`)."""
    return conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()


def task_steps(conn: sqlite3.Connection, task_id: str) -> list:
    """Журнал шагов задачи по порядку записи (команда `log`)."""
    return conn.execute("SELECT * FROM steps WHERE task_id=? ORDER BY id",
                        (task_id,)).fetchall()


def task_target(conn: sqlite3.Connection, task_id: str) -> str:
    """Target задачи; для строки без него — target догфуда."""
    row = conn.execute("SELECT target FROM tasks WHERE id=?",
                       (task_id,)).fetchone()
    if row is None:
        return config.DEFAULT_TARGET
    return row["target"] or config.DEFAULT_TARGET


def journal(conn, task_id: str, actor: str, action: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
        " VALUES (?,?,?,?,?,?)",
        (task_id, task_target(conn, task_id), now(), actor, action, detail),
    )
    conn.commit()


def set_state(conn, task_id: str, state: str, actor: str, detail: str = "") -> None:
    update_task(conn, task_id, state=state, updated_at=now())
    journal(conn, task_id, actor, f"state -> {state}", detail)
    print(f"[{task_id}] -> {state}" + (f"  ({detail})" if detail else ""))
    _record_fixation(conn, task_id)


def _record_fixation(conn, task_id: str) -> None:
    """Хэш-фиксация артефактов на каждом переходе (ADR-0003 п.15, tasks/T021).

    `set_state` — единственная функция, через которую проходит любой
    переход FSM (advance, approve, эскалация, kill): хук здесь даёт
    «на каждом переходе» по построению, а не по дисциплине расстановки
    вызовов по десятку мест пакета.

    Отложенный импорт: `fixation` сама читает `store` (`get_task`,
    `task_target`) для сверки при старте шага, поэтому подключается
    только здесь, во время вызова, а не при загрузке `store.py` — иначе
    модуль перестал бы быть независимым листом пакета (ADR-0003 3ж:
    «остальные зовут здешние функции по имени», не наоборот).
    """
    from . import fixation
    target = task_target(conn, task_id)
    sha, clean = fixation.fix(task_id, target)
    update_task(conn, task_id, fixed_sha=sha or None)
    journal(conn, task_id, "fsm", "sha зафиксирован",
           f"target={target}, sha={sha or '—'}, чисто={clean}")


def get_task(conn, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        sys.exit(f"Задача {task_id} не найдена. `status` покажет существующие.")
    return row
