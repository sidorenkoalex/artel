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

from . import config, session

# Схема БД. `target` в обеих таблицах: журнал не должен уметь разойтись
# с каталогом задач по принадлежности проекту. `task_counters` — нумерация
# задач per-target: персистентный счётчик, а не COUNT(*) (ADR-0003 3ж).
#
# DEFAULT колонки `target` — тот же литерал, что и в `migrate()`
# (`add_column(..., "target", f"TEXT DEFAULT '{config.DEFAULT_TARGET}'")`):
# свежая БД (эта схема) и БД, догнанная миграцией со старой версии, обязаны
# давать одну и ту же схему колонки (SPEC T034, требование 6, ревью T019).
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0, budget_source TEXT,
  target TEXT DEFAULT '{config.DEFAULT_TARGET}', fixed_sha TEXT,
  tests_locked_sha TEXT, is_canary INTEGER DEFAULT 0, paused INTEGER DEFAULT 0,
  answer_baseline INTEGER, verifying_attempts INTEGER DEFAULT 0,
  draft_mr_created INTEGER DEFAULT 0,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  target TEXT DEFAULT '{config.DEFAULT_TARGET}', ts TEXT,
  actor TEXT, action TEXT, detail TEXT, session_id TEXT
);
CREATE TABLE IF NOT EXISTS task_counters (
  target TEXT PRIMARY KEY, next_number INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, kind TEXT, source TEXT,
  message TEXT, ts TEXT, ack_ts TEXT, ack_by TEXT, ack_resolution TEXT
);
CREATE TABLE IF NOT EXISTS alerts_archive (
  id INTEGER PRIMARY KEY, target TEXT, kind TEXT, source TEXT,
  message TEXT, ts TEXT, ack_ts TEXT, ack_by TEXT, ack_resolution TEXT,
  archived_ts TEXT
);
CREATE TABLE IF NOT EXISTS leases (
  task_id TEXT PRIMARY KEY, session_id TEXT, pid INTEGER, hostname TEXT,
  heartbeat_ts TEXT
);
CREATE TABLE IF NOT EXISTS merge_locks (
  task_id TEXT, session_id TEXT, pid INTEGER, hostname TEXT,
  heartbeat_ts TEXT
);
"""

TASK_ID = re.compile(r"\AT(\d+)\Z")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


class _AutoClosingConnection(sqlite3.Connection):
    """Соединение, закрывающееся само при потере последней ссылки.

    `db()` зовётся сотнями мест кодовой базы инлайн (`store.get_task(
    store.db(), ...)`), без переменной, которую вызывающий код мог бы
    закрыть явно (tasks/T090/SPEC.md, требование 1) — переписывать каждое
    такое место несоразмерно требованию. `__del__` закрывает БД раньше,
    чем её увидит С-уровневый деаллокатор `sqlite3.Connection` — именно
    он печатает `ResourceWarning: unclosed database`, если объект
    уничтожается незакрытым. CPython уничтожает нециклические объекты по
    счётчику ссылок немедленно (не дожидаясь GC или выхода из процесса),
    так что закрытие происходит на месте, а не «только за счёт завершения
    процесса» — тем же путём для любой точки вызова `db()`.
    """

    def __del__(self):
        self.close()


def db() -> sqlite3.Connection:
    config.DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(config.DB, factory=_AutoClosingConnection)
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
    # Identity сессии, записавшей запись журнала (SPEC 01M1G..., требование
    # 2): NULL в старых строках — записаны до этой задачи, «кем» неизвестно
    # и не восстановимо задним числом, читатели (`catalog.cmd_log`/
    # `cmd_status`) обязаны деградировать на этом молча.
    add_column(conn, "steps", "session_id", "TEXT")
    # NULL — фиксации ещё не было (строка старше T021 или задача ни разу
    # не переходила): approve/run читают это как «сверять не с чем»,
    # не как нарушение (tasks/T021 SPEC, требование 3).
    add_column(conn, "tasks", "fixed_sha", "TEXT")
    # sha, зафиксированный на выходе tests_writing -> in_dev (tasks/T023,
    # требование 5): NULL — задача tests_writing не проходила (skip_tests,
    # SPEC версии 1, либо строка старше T023) — лок acceptance_tests/
    # сверять не с чем, тот же вырожденный случай, что и у fixed_sha.
    add_column(conn, "tasks", "tests_locked_sha", "TEXT")
    # Пометка канареечной задачи (tasks/T065/SPEC.md, требование 6, правка
    # Оператора 28.08): ТОЛЬКО колонка БД — title её не несёт (роль видит
    # title в промпте, а канареечная задача обязана быть неотличимой от
    # продуктовой ДЛЯ РОЛЕЙ). DEFAULT 0 — строки старше T065 не канареечные.
    add_column(conn, "tasks", "is_canary", "INTEGER DEFAULT 0")
    # Пометка штатной паузы задачи (tasks/T070/SPEC.md, требование 4): БД,
    # не файл рабочего каталога — рабочих копий несколько, БД остаётся
    # единственным источником правды (та же логика, что и у lease/
    # merge-lock). DEFAULT 0 — строки старше T070 не на паузе.
    add_column(conn, "tasks", "paused", "INTEGER DEFAULT 0")
    # Снимок числа ANSWER-*.md на момент эскалации (tasks/T075, SPEC AC-3):
    # NULL — эскалация класса «лимит», ответа не требует (как до этой
    # задачи); не-NULL — approve из escalated обязан увидеть на ветке
    # больше файлов ANSWER-*.md, чем было тут зафиксировано, иначе
    # отказывает. Число, не булев флаг: гейт различает НОВЫЙ ответ от уже
    # существующего файла прошлого раунда эскалации той же задачи.
    add_column(conn, "tasks", "answer_baseline", "INTEGER")
    # Счётчик попыток advance в verifying без зелёного CI (SPEC T079,
    # требование 6) — потолок ожидания; сбрасывается на каждом входе в
    # verifying (fsm.py), растёт на каждом не-зелёном advance оттуда же.
    add_column(conn, "tasks", "verifying_attempts", "INTEGER DEFAULT 0")
    # Идемпотентность Draft MR (SPEC T079, требование 1): MR заводится
    # ровно один раз за жизненный цикл задачи — колонка, не запрос к
    # GitHub на каждый вход в in_dev (orchestrator/github_adapter.py).
    add_column(conn, "tasks", "draft_mr_created", "INTEGER DEFAULT 0")
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS task_counters ("
        "  target TEXT PRIMARY KEY, next_number INTEGER NOT NULL);")
    seed_task_counters(conn)
    # Носитель алертов (A3, tasks/T022/SPEC.md требование 7): БД прошлых
    # версий её не имеют — догоняется тем же приёмом, что и task_counters.
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS alerts ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, kind TEXT,"
        "  source TEXT, message TEXT, ts TEXT, ack_ts TEXT, ack_by TEXT,"
        "  ack_resolution TEXT);")
    # Архивная таблица `prune` (tasks/T073/SPEC.md, требование 3): БД
    # прошлых версий её не имеют — догоняется тем же приёмом, что и alerts.
    # `id` без AUTOINCREMENT: `archive_alert` переносит исходный id
    # архивируемой строки alerts, не заводит новый.
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS alerts_archive ("
        "  id INTEGER PRIMARY KEY, target TEXT, kind TEXT, source TEXT,"
        "  message TEXT, ts TEXT, ack_ts TEXT, ack_by TEXT,"
        "  ack_resolution TEXT, archived_ts TEXT);")
    # Носитель advisory-lease задачи (SPEC T044, требование 1): БД прошлых
    # версий её не имеют — догоняется тем же приёмом, что и alerts/task_counters.
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS leases ("
        "  task_id TEXT PRIMARY KEY, session_id TEXT, pid INTEGER,"
        "  hostname TEXT, heartbeat_ts TEXT);")
    # Мьютекс merge-окна (SPEC T053, требование 1): один держатель на весь
    # пульт, не per-task, как `leases` — `task_id` здесь не ключ, а поле
    # «какую задачу держит сессия», по конвенции не более одной строки.
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS merge_locks ("
        "  task_id TEXT, session_id TEXT, pid INTEGER,"
        "  hostname TEXT, heartbeat_ts TEXT);")
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

    Источник максимума — не только строки `tasks` (БД может быть пуста
    или вовсе не существовать, холодный старт), но и наблюдаемый мир:
    `coldstart.observed_max_task_number` (SPEC T049, требование 1–2,
    ADR-0005 п.5) — каталоги задач, ветки `task/*`, RETRO, история main.
    Множество target'ов для посева — не только те, что засветились
    строками `tasks` (у только что подключённого/потерявшего БД target'а
    таких строк нет вовсе), но и все, объявленные `targets.yaml`
    (REVIEW T049 итерации 1, замечание major): именно этой декларации
    соответствуют каталоги `.artel/projects/<target>/tasks/`, которые
    `coldstart` и сканирует для «прочих target». Невалидный
    `targets.yaml` не должен ронять посев счётчиков — используется
    best-effort (пусто при `TargetsError`, ту же проверку файла отдельно
    делает `doctor`). Дорогой скан (FS + git-подпроцессы) платится РОВНО
    ОДИН РАЗ на target — только пока у него ещё нет строки счётчика
    (`target not in known`); эта функция зовётся на КАЖДОМ `store.db()`
    (внутри `migrate`), так что после первого успешного посева следующие
    вызовы его не трогают. Отложенный импорт `coldstart`/`targets` — тем
    же приёмом, что `record_fixation` лениво зовёт `fixation`: `store.py`
    остаётся листом графа импортов на момент загрузки модуля.
    """
    from . import coldstart, targets
    known = {r["target"] for r in
             conn.execute("SELECT target FROM task_counters")}
    top: dict = {config.DEFAULT_TARGET: 0}
    for row in conn.execute("SELECT id, target FROM tasks"):
        target = row["target"] or config.DEFAULT_TARGET
        top[target] = max(top.get(target, 0), task_number(row["id"]))
    try:
        declared = targets.load()
    except targets.TargetsError:
        declared = {}
    for name in declared:
        top.setdefault(name, 0)
    for target, number in top.items():
        if target not in known:
            observed = coldstart.observed_max_task_number(target)
            top[target] = max(number, observed)
    for target, number in top.items():
        if target not in known:
            conn.execute(
                "INSERT INTO task_counters (target, next_number) VALUES (?,?)",
                (target, number + 1))
    conn.commit()


def counter_targets(conn: sqlite3.Connection) -> set:
    """Target'ы, у которых уже есть строка счётчика номеров (doctor A3,
    SPEC T049, требование 3)."""
    return {r["target"] for r in conn.execute("SELECT target FROM task_counters")}


def task_exists(conn: sqlite3.Connection, task_id: str) -> bool:
    """Есть ли строка задачи с этим id — без исключения `get_task` при
    отсутствии (SPEC T049: синтетическая строка пересева расхода
    проверяется на существование перед `insert_task`)."""
    return conn.execute("SELECT 1 FROM tasks WHERE id=?",
                        (task_id,)).fetchone() is not None


def peek_task_number(conn: sqlite3.Connection, target: str) -> int:
    """Номер следующей задачи БЕЗ расхода счётчика.

    `cmd_new` (SPEC T048, требование 1) обязан проверить коллизию ветки
    ДО решения расходовать номер — отказ не имеет права стоить задаче
    номера. Читает то же самое, что и первый шаг `next_task_number`, но
    без транзакции и без записи: сам расход остаётся только за
    `next_task_number`.
    """
    row = conn.execute(
        "SELECT next_number FROM task_counters WHERE target=?",
        (target,)).fetchone()
    return row["next_number"] if row is not None else 1


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
                budget_usd: float, *, is_canary: bool = False) -> None:
    """Заводит строку задачи (команда `new`).

    `is_canary` — keyword-only, дефолт `False` не меняет поведение
    существующих вызывателей (tasks/T065/SPEC.md, требование 6):
    единственный, кто передаёт `True`, — `catalog.cmd_new(..., canary=True)`
    из команды `canary`.
    """
    stamp = now()
    conn.execute(
        "INSERT INTO tasks (id,title,state,branch,target,budget_usd,"
        "is_canary,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (task_id, title, state, branch, target, budget_usd,
         int(is_canary), stamp, stamp))
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


def closed_external_tasks(conn: sqlite3.Connection) -> list:
    """Задачи внешнего target'а в `done`/`killed`, не канарейка (SPEC
    T094, требование 13, AC-15) — кандидаты на дожим недоставленного
    снапшота закрытия. Читатель — `doctor.check_pending_snapshots`
    (SQL живёт только здесь, ADR-0003 3ж)."""
    return conn.execute(
        "SELECT id, target FROM tasks WHERE state IN ('done','killed') "
        "AND is_canary=0 AND target IS NOT NULL AND target != ?",
        (config.DEFAULT_TARGET,)).fetchall()


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


def task_branch(conn: sqlite3.Connection, task_id: str) -> str:
    """Ветка задачи; пустая строка — задачи нет в БД.

    Та же деградация, что у `task_target`: читатели вроде
    `brief.developer_brief` (SPEC T031) зовутся и до `insert_task`
    (юнит-тесты компонентов брифа без заведённой задачи) — `get_task`
    там бы упал `sys.exit`, а тут есть с чем сравнить чекаут дальше.
    """
    row = conn.execute("SELECT branch FROM tasks WHERE id=?",
                       (task_id,)).fetchone()
    return (row["branch"] or "") if row is not None else ""


def journal(conn, task_id: str, actor: str, action: str, detail: str = "",
           *, session_id: str | None = None) -> None:
    """Пишет запись журнала `steps` — каждая новая запись несёт identity
    сессии, её записавшей (SPEC 01M1G..., требование 1-2, AC-1/AC-2).

    `session_id` — keyword-only, `None` по умолчанию: тогда identity
    резолвится ЗДЕСЬ, тем же источником, что и `lease.resolve_session_id`
    (`session.resolve_session_id`) — identity ТЕКУЩЕГО процесса. Это и
    есть единая точка требования 1: подавляющее большинство ~70
    вызывающих мест `journal()` по всей кодовой базе сами не имеют дела с
    чужой identity и не передают параметр вовсе — они уже исполняются
    внутри одного и того же процесса CLI-вызова, чей `ARTEL_SESSION_ID`/
    ppid не меняется по его ходу, так что дефолтный резолв здесь даёт ТУ
    ЖЕ identity, что дала бы явная прокидка через десяток модулей.

    Явный параметр — только для мест, уже владеющих ЧУЖОЙ или иначе
    полученной identity, отличной от «резолвящейся из окружения этого же
    процесса прямо сейчас» (`lease.acquire`: identity, взявшая/перехватившая
    lease, — уже готовый аргумент функции, не обязана совпадать с тем, что
    резолвил бы повторный вызов `resolve_session_id` в контексте теста).
    """
    if session_id is None:
        session_id = session.resolve_session_id(None)
    conn.execute(
        "INSERT INTO steps (task_id, target, ts, actor, action, detail,"
        " session_id) VALUES (?,?,?,?,?,?,?)",
        (task_id, task_target(conn, task_id), now(), actor, action, detail,
         session_id),
    )
    conn.commit()


REFUSAL_ACTION_PREFIX = "переход отклонён"


def refusal_history(conn, task_id: str, state: str, limit: int) -> list:
    """Последние `limit` записей `"переход отклонён..."` этой задачи,
    принадлежащие ТЕКУЩЕМУ визиту состояния `state` (SPEC T078,
    требования 1, 3, 4).

    Скоуп без новой колонки: нижняя граница — id последней записи
    `"state -> {state}"` этой задачи, которую `set_state` журналирует на
    каждом переходе. Отказ advance не меняет состояние, так что всё,
    что журналируется после входа в `state` и до следующего перехода,
    по построению происходит, пока задача в нём — включая повторный
    визит того же состояния позже (новая запись `state -> {state}`
    сдвигает границу вперёд и отсекает отказы прошлого визита).

    Первое состояние задачи (`spec_writing`) в него не входит через
    `set_state` — задача рождается там напрямую (`insert_task`), такой
    записи нет никогда, граница 0: в выборку идут все отказы задачи,
    что верно — раньше первого состояния задачи не существовало.
    """
    steps = task_steps(conn, task_id)
    marker = f"state -> {state}"
    since_id = 0
    for row in reversed(steps):
        if row["action"] == marker:
            since_id = row["id"]
            break
    matches = [row for row in steps
              if row["id"] > since_id
              and row["action"].startswith(REFUSAL_ACTION_PREFIX)]
    return matches[-limit:]


class CasConflict(Exception):
    """Проигрыш CAS-перехода `set_state`: строка уже в другом состоянии
    (SPEC T050, требования 3-4).

    `actual` — состояние, реально прочитанное из БД сразу после проигрыша:
    `kill` (единственный вызыватель, которому SPEC разрешает повторять,
    требование 6) берёт его как `expected_state` следующей попытки без
    лишнего `get_task`.
    """

    def __init__(self, task_id: str, expected: str, actual: str) -> None:
        self.task_id = task_id
        self.expected = expected
        self.actual = actual
        super().__init__(f"[{task_id}] CAS-переход отклонён: ожидалось "
                         f"{expected}, в БД {actual}")


def set_state(conn, task_id: str, state: str, actor: str, *,
              expected_state: str, detail: str = "") -> None:
    """Атомарный переход `tasks.state` — единственная точка его мутации.

    CAS (SPEC T050, требования 1-4): `expected_state` обязателен и
    keyword-only — молчаливый дефолт («не проверять») свёл бы сверку на
    нет для любого пропущенного вызова. Вызыватель обязан передать
    состояние, которое сам прочитал и на основании которого принял
    решение о переходе (требование 5) — не перечитывать его прямо перед
    этим вызовом ради успеха сверки: тогда CAS перестаёт отличать
    «решение было верным» от «проиграли гонку и подстроились под неё».

    Проигрыш (строка уже не в `expected_state` — конкурентная сессия
    успела перейти первой) не пишет ни в `journal`, ни хэш-фиксацию
    (обе строки ниже проверки `rowcount`, требования 2-3, AC-2) и
    бросает `CasConflict` с фактическим состоянием (требование 3, AC-3).
    Не `sys.exit` — `store.py` остаётся листом графа импортов, а
    `sys.exit` сделал бы проигрыш неперехватываемым даже для `kill`,
    которому требование 6 прямо предписывает перехват и повтор.

    `updated_at` — с точностью до микросекунд, не через `now()`
    (секундная): переход и предшествующая ему запись строки (`insert_task`/
    `update_task`) регулярно попадают в одну и ту же секунду в тестах и
    под нагрузкой, а AC-4 требует, чтобы именно `updated_at` менялся
    вместе со `state` при каждом успешном CAS. `now()` (секундная
    точность) остаётся общим форматом для `leases.heartbeat_ts`/
    `steps.ts` — его строго парсит `strptime` за пределами этого файла
    (`liveness._age_seconds` и приёмочный тест tasks/T044); `tasks.updated_at`
    обратно не парсится нигде в кодовой базе, так что более точный формат
    именно здесь ничего не ломает.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%fZ")
    cur = conn.execute(
        "UPDATE tasks SET state=?, updated_at=? WHERE id=? AND state=?",
        (state, stamp, task_id, expected_state))
    conn.commit()
    if cur.rowcount == 0:
        actual = get_task(conn, task_id)["state"]
        raise CasConflict(task_id, expected_state, actual)
    journal(conn, task_id, actor, f"state -> {state}", detail)
    print(f"[{task_id}] -> {state}" + (f"  ({detail})" if detail else ""))
    # СТАБ (валидация приёмочных тестов test_author, не коммитить):
    # авто-закрытие attention на любом успешном переходе (ANSWER-1, в.1).
    from . import alerts as _alerts_stub
    for row in _alerts_stub.open_alerts(conn, "attention"):
        if row["target"] == task_id:
            _alerts_stub.ack(conn, row["id"], "auto", "закрыт переходом состояния")
    record_fixation(conn, task_id)
    _append_passport_line(conn, task_id, state, actor)


def _append_passport_line(conn, task_id: str, state: str, actor: str) -> None:
    """Паспорт живой задачи (SPEC T094, требование 11, AC-12): на каждом
    переходе FSM — строка в артефактную ветку пульта, «только для глаз»
    (не входит в автоматические решения). Только внешний target —
    self/догфуд не заводит артефактную ветку вовсе (требование 16/AC-18).

    Отложенный импорт: `artifact_branch` не читает `store` на уровне
    модуля, но `store.py` остаётся листом графа импортов при загрузке
    (тот же приём, что `record_fixation` уже применяет к `fixation`).
    """
    target = task_target(conn, task_id)
    if target == config.DEFAULT_TARGET:
        return
    from . import artifact_branch
    artifact_branch.append_passport_line(task_id, state, actor)


def record_fixation(conn, task_id: str) -> None:
    """Хэш-фиксация артефактов: на каждом переходе FSM и на WIP-чекпоинте.

    `set_state` — единственная функция, через которую проходит любой
    переход FSM (advance, approve, эскалация, kill): хук здесь даёт
    «на каждом переходе» по построению, а не по дисциплине расстановки
    вызовов по десятку мест пакета.

    Второй, не-транзиционный вызывающий — `runner.commit_timeout_checkpoint`
    (tasks/T041): WIP-чекпоинт при таймауте шага легитимно сдвигает HEAD
    ветки задачи мимо `set_state`, и без повторной фиксации следующий
    `check_integrity` увидел бы этот сдвиг как расхождение sha, а не как
    ожидаемое состояние после чекпоинта.

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
    if target == config.DEFAULT_TARGET:
        detail = f"target={target}, sha={sha or '—'}, чисто={clean}"
    else:
        # Два sha (SPEC T094, требование 9, AC-10): голова кодовой ветки
        # ЦЕЛЕВОГО и голова артефактной ветки ПУЛЬТА — `sha`/`clean` выше
        # (легаси-фиксация `.artel/projects/<target>/`, требование 2 в
        # процессе перевода на артефактную ветку) остаются в detail без
        # изменений — этот блок ДОБАВЛЯЕТ, не заменяет.
        code_sha = fixation.external_code_sha(target)
        artifact_sha = fixation.external_artifact_sha(task_id)
        detail = (f"target={target}, sha={sha or '—'}, чисто={clean}, "
                  f"код={code_sha or '—'}, артефакты={artifact_sha or '—'}")
    journal(conn, task_id, "fsm", "sha зафиксирован", detail)


def resolve_task_id(conn, task_id: str) -> str:
    """Разрешает уникальный префикс `task_id` в полный id (SPEC T094,
    требование 3, AC-3) — БЕЗ предположений о формате/длине id (AC-2):
    точное совпадение проверяется первым (легаси `Tnnn` и ULID обоих
    видов совпадают с собой буквально), иначе — поиск по префиксу через
    `LIKE` со всеми существующими id.

    Точного совпадения и ровно одного префиксного совпадения нет — id
    возвращается как есть: вызывающий код (`get_task`) сам отказывает
    «не найдена», сохраняя прежнее сообщение для опечатки. Больше одного
    префиксного совпадения — явный отказ ЗДЕСЬ, с перечислением всех
    совпавших id (AC-3): не тот же текст, что «не найдена», иначе
    неоднозначность неотличима от отсутствия задачи.
    """
    if not task_id:
        return task_id
    if conn.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
        return task_id
    escaped = task_id.replace("%", r"\%").replace("_", r"\_")
    matches = [r["id"] for r in conn.execute(
        "SELECT id FROM tasks WHERE id LIKE ? ESCAPE '\\'", (f"{escaped}%",))]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        sys.exit(f"Префикс {task_id!r} неоднозначен — совпадает с "
                 f"{len(matches)} задачами: {', '.join(sorted(matches))}")
    return task_id


def get_task(conn, task_id: str) -> sqlite3.Row:
    task_id = resolve_task_id(conn, task_id)
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        sys.exit(f"Задача {task_id} не найдена. `status` покажет существующие.")
    return row


def latest_fixed_sha(conn, target: str) -> sqlite3.Row:
    """Последняя (по updated_at) задача target'а с непустым fixed_sha.

    Читатель — doctor.recovery_check (A3): точка сравнения для sha головы
    артефактного репо против того, что реально зафиксировал последний
    переход FSM этого target'а.
    """
    return conn.execute(
        "SELECT id, fixed_sha FROM tasks WHERE target=? AND fixed_sha IS NOT NULL "
        "ORDER BY updated_at DESC, id DESC LIMIT 1", (target,)).fetchone()


def open_alert_exists(conn, target: str | None, kind: str, source: str,
                      message: str) -> bool:
    """Есть ли уже НЕподтверждённый алерт с тем же ключом (дедуп alerts.raise_alert)."""
    row = conn.execute(
        "SELECT 1 FROM alerts WHERE target IS ? AND kind=? AND source=? "
        "AND message=? AND ack_ts IS NULL",
        (target, kind, source, message)).fetchone()
    return row is not None


def insert_alert(conn, target: str | None, kind: str, source: str,
                 message: str) -> None:
    conn.execute(
        "INSERT INTO alerts (target, kind, source, message, ts) "
        "VALUES (?,?,?,?,?)",
        (target, kind, source, message, now()))
    conn.commit()


def open_alerts(conn, kind: str | None = None) -> list:
    """Неподтверждённые алерты, свежие сверху; kind — фильтр по типу."""
    if kind is None:
        return conn.execute(
            "SELECT * FROM alerts WHERE ack_ts IS NULL "
            "ORDER BY id DESC").fetchall()
    return conn.execute(
        "SELECT * FROM alerts WHERE ack_ts IS NULL AND kind=? "
        "ORDER BY id DESC", (kind,)).fetchall()


def lease_row(conn, task_id: str) -> sqlite3.Row | None:
    """Строка lease задачи; None — свободна (SPEC T044, требование 1)."""
    return conn.execute("SELECT * FROM leases WHERE task_id=?",
                        (task_id,)).fetchone()


def insert_lease(conn, task_id: str, session_id: str, pid: int,
                 hostname: str, heartbeat_ts: str) -> None:
    """Заводит lease задачи, до этого свободной (`lease.acquire`)."""
    conn.execute(
        "INSERT INTO leases (task_id, session_id, pid, hostname,"
        " heartbeat_ts) VALUES (?,?,?,?,?)",
        (task_id, session_id, pid, hostname, heartbeat_ts))
    conn.commit()


def update_lease(conn, task_id: str, session_id: str, pid: int,
                 hostname: str, heartbeat_ts: str) -> None:
    """Продление своего lease либо перехват чужого протухшего — обе ветки
    переписывают все поля строки (`lease.acquire`, требования 3, 5)."""
    conn.execute(
        "UPDATE leases SET session_id=?, pid=?, hostname=?, heartbeat_ts=? "
        "WHERE task_id=?", (session_id, pid, hostname, heartbeat_ts, task_id))
    conn.commit()


def release_lease(conn, task_id: str, session_id: str) -> bool:
    """Снимает lease задачи, если он всё ещё принадлежит этой сессии.

    Возвращает `True`, только если строка реально была удалена — строка
    могла уже сменить держателя между чтением вызывающим кодом и этим
    вызовом (перехват чужим `lease.acquire`), тогда `DELETE` сносит 0
    строк и вызывающий код обязан не журналировать/не печатать успех как
    свершившийся факт (REVIEW T062, итерация 1, Замечание 1)."""
    cur = conn.execute("DELETE FROM leases WHERE task_id=? AND session_id=?",
                       (task_id, session_id))
    conn.commit()
    return cur.rowcount > 0


def all_leases(conn) -> list:
    """Все lease (команда `doctor`, требование 11)."""
    return conn.execute("SELECT * FROM leases").fetchall()


def merge_lock_row(conn) -> sqlite3.Row | None:
    """Строка мьютекса merge-окна — не более одной на весь пульт; None —
    свободен (SPEC T053, требование 1-2)."""
    return conn.execute("SELECT * FROM merge_locks").fetchone()


def set_merge_lock(conn, task_id: str, session_id: str, pid: int,
                   hostname: str, heartbeat_ts: str) -> None:
    """Заводит мьютекс merge-окна либо переписывает держателя (свежий
    вход, продление своего или перехват протухшего чужого — все три
    ветки `merge_lock.acquire`). Таблица несёт не более одной строки
    (требование 2), поэтому запись всегда идёт через снос предыдущей —
    не `INSERT`/`UPDATE` порознь, как у `leases`: там раздельные ветки
    нужны только ради различения «взято с нуля» (`lease.acquire`
    требование, из которого `auto` решает, снимать ли за собой чужой
    lease); мьютекс merge живёт ровно одну операцию окна, и это различие
    ему не нужно (`orchestrator/merge_lock.py`)."""
    conn.execute("DELETE FROM merge_locks")
    conn.execute(
        "INSERT INTO merge_locks (task_id, session_id, pid, hostname,"
        " heartbeat_ts) VALUES (?,?,?,?,?)",
        (task_id, session_id, pid, hostname, heartbeat_ts))
    conn.commit()


def release_merge_lock(conn, session_id: str) -> None:
    """Снимает мьютекс merge-окна, если он всё ещё принадлежит этой
    сессии (SPEC T053, требование 3)."""
    conn.execute("DELETE FROM merge_locks WHERE session_id=?", (session_id,))
    conn.commit()


def get_alert(conn, alert_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM alerts WHERE id=?",
                        (alert_id,)).fetchone()


def alerts_older_than(conn, cutoff_ts: str) -> list:
    """Alerts (любой `kind`, вне зависимости от `ack`) старше `cutoff_ts` —
    кандидаты архивации `prune` (tasks/T073/SPEC.md, требование 3, AC-6).

    `ts` — тот же формат, что и `now()` (`%Y-%m-%d %H:%M:%SZ`), фиксированной
    ширины: лексикографическое сравнение строк совпадает с хронологическим.
    """
    return conn.execute(
        "SELECT * FROM alerts WHERE ts < ? ORDER BY id", (cutoff_ts,)).fetchall()


def archive_alert(conn, alert_id: int) -> None:
    """Переносит alert в `alerts_archive`: перенос, не дублирование
    (tasks/T073/SPEC.md, требование 3, AC-6) — строка покидает `alerts`
    ровно туда, куда попадает в `alerts_archive`, с тем же `id`."""
    row = get_alert(conn, alert_id)
    if row is None:
        return
    conn.execute(
        "INSERT INTO alerts_archive (id, target, kind, source, message, ts,"
        " ack_ts, ack_by, ack_resolution, archived_ts)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (row["id"], row["target"], row["kind"], row["source"], row["message"],
         row["ts"], row["ack_ts"], row["ack_by"], row["ack_resolution"], now()))
    conn.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    conn.commit()


def ack_alert(conn, alert_id: int, actor: str, resolution: str) -> None:
    conn.execute(
        "UPDATE alerts SET ack_ts=?, ack_by=?, ack_resolution=? WHERE id=?",
        (now(), actor, resolution, alert_id))
    conn.commit()
