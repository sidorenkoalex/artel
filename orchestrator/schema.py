"""Схема БД и миграции: DDL, `migrate(conn)`, `add_column`/`table_columns`.

Выделено из `orchestrator/store.py` (roadmap §3, фаза R, пункт R6):
создание схемы и её догон жили вперемешку с запросами по задачам,
журналу, lease, алертам, канарейке, зонам — каждая новая колонка
правила один и тот же файл, что регулярно конфликтовало на подтяжке.
`store.py` импортирует отсюда `SCHEMA`/`migrate`/`add_column`/
`table_columns` и реэкспортирует `create_schema`/`migrate` под теми же
именами, что и раньше (обратная совместимость вызовов и тестовых
подмен `mock.patch.object(store, ...)`).
"""
import sqlite3

from . import config

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
  budget_usd REAL, spent_usd REAL DEFAULT 0, spent_estimate_usd REAL DEFAULT 0,
  budget_source TEXT,
  target TEXT DEFAULT '{config.DEFAULT_TARGET}', fixed_sha TEXT,
  tests_locked_sha TEXT, is_canary INTEGER DEFAULT 0, paused INTEGER DEFAULT 0,
  answer_baseline INTEGER, verifying_attempts INTEGER DEFAULT 0,
  draft_mr_created INTEGER DEFAULT 0,
  diff_bytes INTEGER, split_assessment TEXT, zones TEXT,
  zones_extension TEXT,
  materialized_artifact_sha TEXT, zone_queue_position INTEGER,
  parent_task_id TEXT,
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
  heartbeat_ts TEXT, pgid INTEGER
);
CREATE TABLE IF NOT EXISTS merge_locks (
  task_id TEXT, session_id TEXT, pid INTEGER, hostname TEXT,
  heartbeat_ts TEXT
);
"""


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
    # sha головы артефактной ветки на момент последней материализации
    # `runner.role_cwd` (SPEC 01M1NKTF173WV5CPDZ1C3WW69K, AC-1/AC-6): NULL —
    # материализации ещё не было (строка старше этой задачи либо у задачи
    # нет артефактной ветки) — конфликт-гвард автокоммита сверять не с чем,
    # тот же вырожденный случай, что и у fixed_sha/tests_locked_sha.
    add_column(conn, "tasks", "materialized_artifact_sha", "TEXT")
    # Верхняя оценка неучтённой стоимости шага (SPEC
    # 01M1NWCM3TDY0YABEKE8DYQA1C, требование 1): накопительная, отдельная от
    # `spent_usd` — таймаут шага роли БЕЗ курса токенов (`config.TOKEN_RATES`)
    # прибавляет сюда именованную константу вместо точной суммы (требование
    # 3). DEFAULT 0 — строки старше этой задачи не несут неучтённой
    # стоимости задним числом (требование 9: пересчёт прошлых шагов не
    # производится).
    add_column(conn, "tasks", "spent_estimate_usd", "REAL DEFAULT 0")
    # Снимок объёма на входе в merge_gate (tasks/01M1KS8K9RXWHX2PW3ZKB0P903,
    # ANSWER-1/ANSWER-2): NULL — задача закрыта до появления колонки, либо
    # снимок не удался (сбой git — не блокирует переход) — `artel report`
    # читает `report._DASH` для обоих случаев одинаково.
    add_column(conn, "tasks", "diff_bytes", "INTEGER")
    add_column(conn, "tasks", "split_assessment", "TEXT")
    # Значение frontmatter-поля `zones:` SPEC, сохранённое при `approve`
    # на `spec_gate` (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-3) — то же поле,
    # что механика «Оценка объёма и деление» уже структурирует для
    # сигналов деления (SPEC, требование 1).
    add_column(conn, "tasks", "zones", "TEXT")
    # Расширение зон, одобренное мандатом Оператора при переходе
    # `in_dev -> review` (01M1P9QCHPHSCEA6TK13PV85SP, ANSWER-1, п.3):
    # список путей через запятую, тем же приёмом, что `zones` выше — NULL,
    # пока расширения не было. Гейт зон (`fsm_advance._zones_gate_refuses`)
    # считает зоной задачи объединение `zones` и `zones_extension`.
    add_column(conn, "tasks", "zones_extension", "TEXT")
    # Явная перестановка очереди ожидания зоны Оператором (SPEC
    # 01M1P9QAG65GVF69YJEV0V18D9, требование 9, AC-9): NULL — очередь не
    # переставлена, естественный порядок по времени approve (`updated_at`)
    # решает (`orchestrator/zone_lock.py::queue_order`).
    add_column(conn, "tasks", "zone_queue_position", "INTEGER")
    # Связь родитель -> подзадача деления (01M29284PTCJXGERV5262E9XMM,
    # требование 1): NULL — задача не подзадача деления. «Родитель
    # поделён» вычисляется каждый раз заново — наличием хотя бы одной
    # строки с parent_task_id = <id родителя> при её состоянии killed,
    # отдельный флаг на строке родителя не заводится.
    add_column(conn, "tasks", "parent_task_id", "TEXT")
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS task_counters ("
        "  target TEXT PRIMARY KEY, next_number INTEGER NOT NULL);")
    # Отложенный импорт: `seed_task_counters` остаётся в `store.py` (не
    # «add_column/проверка версии» по существу, а заведение строк
    # task_counters по наблюдаемому миру, SPEC 01M1SD5NZ79MWCEJDJ9JP6EPWS,
    # требование 1) — `store.py` же импортирует `migrate` ОТСЮДА на уровне
    # модуля, так что прямой импорт `store` здесь, на уровне модуля,
    # закольцевал бы загрузку; вызов внутри функции откладывает его до
    # момента, когда оба модуля уже полностью загружены (тот же приём,
    # что и у `store.record_fixation`/`store._append_passport_line`).
    from . import store
    store.seed_task_counters(conn)
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
    # pid группы (pgid) агентного шага (SPEC 01M1PNBSHR2PMFECMP7C204MF1,
    # AC-2) — рядом с существующим `pid` (представляющим держателя lease,
    # не спавненный агентный процесс): пути group-kill (timeout/kill/
    # pause --now/release, AC-3..AC-6) читают его отсюда. NULL — лиза
    # старше этой задачи либо шаг ещё не успел его записать.
    add_column(conn, "leases", "pgid", "INTEGER")
    # Мьютекс merge-окна (SPEC T053, требование 1): один держатель на весь
    # пульт, не per-task, как `leases` — `task_id` здесь не ключ, а поле
    # «какую задачу держит сессия», по конвенции не более одной строки.
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS merge_locks ("
        "  task_id TEXT, session_id TEXT, pid INTEGER,"
        "  hostname TEXT, heartbeat_ts TEXT);")
    conn.commit()
