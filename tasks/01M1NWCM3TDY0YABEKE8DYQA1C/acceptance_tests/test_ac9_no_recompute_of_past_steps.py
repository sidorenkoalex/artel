"""AC-9 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «Пересчёт spent_usd/spent_estimate_usd и RETRO
прошлых (уже завершённых до этой задачи) шагов и задач не
производится — требования 1-6 применяются только к новым шагам,
посчитанным после появления курса/таблицы.»

Проверяется на миграции существующей (легаси, без колонки
`spent_estimate_usd`) БД: строка задачи, заведённая ДО появления
колонки, с уже ненулевым `spent_usd` — после `store.migrate` обязана
получить `spent_estimate_usd=0` (просто дефолт новой колонки) и
СОХРАНИТЬ прежний `spent_usd` байт-в-байт, без какого-либо пересчёта
или бэкфилла оценки задним числом. Тот же приём, что
`tests/test_spec_budget.py::LegacyDbMigrationTest` (легаси-схема,
прямая вставка строки в обход `store.create_schema`, затем `store.db()`
триггерит миграцию).

`LEGACY_SCHEMA` ниже — снимок `orchestrator/store.py::SCHEMA` ДО этой
задачи (без колонки `spent_estimate_usd`), зафиксированный буквально —
не текущая `store.SCHEMA` в момент прогона теста: после реализации
задачи `store.SCHEMA` для СВЕЖИХ БД уже будет нести новую колонку с
рождения, и тест обязан упражнять именно путь МИГРАЦИИ старой БД, а не
случайно превратиться в тест свежей схемы.

Красен до реализации: `orchestrator/store.py::migrate` сегодня не знает
колонки `spent_estimate_usd` — `add_column` её не добавляет, и
`SELECT spent_usd, spent_estimate_usd FROM tasks` падает
`sqlite3.OperationalError: no such column: spent_estimate_usd`.
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402

# Схема tasks/steps до этой задачи (orchestrator/store.py::SCHEMA на
# момент написания этого теста) — колонки spent_estimate_usd ещё нет.
LEGACY_SCHEMA = """
CREATE TABLE tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0, budget_source TEXT,
  target TEXT DEFAULT 'artel', fixed_sha TEXT,
  tests_locked_sha TEXT, is_canary INTEGER DEFAULT 0, paused INTEGER DEFAULT 0,
  answer_baseline INTEGER, verifying_attempts INTEGER DEFAULT 0,
  draft_mr_created INTEGER DEFAULT 0,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  target TEXT DEFAULT 'artel', ts TEXT,
  actor TEXT, action TEXT, detail TEXT, session_id TEXT
);
"""

TASK = "T900"


class NoRecomputeOfPastStepsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        db_patcher = mock.patch.object(config, "DB", root / "state.db")
        db_patcher.start()
        self.addCleanup(db_patcher.stop)

        config.DB.parent.mkdir(parents=True, exist_ok=True)
        legacy = sqlite3.connect(config.DB)
        legacy.executescript(LEGACY_SCHEMA)
        legacy.execute(
            "INSERT INTO tasks (id,title,state,branch,budget_usd,spent_usd,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (TASK, "Задача до появления курса токенов", "done",
             "task/t900-x", 50.0, 12.34, store.now(), store.now()))
        legacy.commit()
        legacy.close()

    def test_ac9_migration_zeroes_the_estimate_without_touching_past_spend(self):
        """Миграция существующей БД добавляет `spent_estimate_usd` с
        дефолтом 0 старой строке и не трогает её `spent_usd`.

        Ловит мутацию: миграция «догоняет» задним числом старые
        `done`-задачи расчётной оценкой (например, по числу токенов из
        их журнала) вместо простого дефолта новой колонки — старое
        `spent_usd=12.34` либо новая `spent_estimate_usd` перестанут
        быть исходными значениями, тест покраснеет.
        """
        conn = store.db()  # триггерит orchestrator.store.migrate()

        row = conn.execute(
            "SELECT spent_usd, spent_estimate_usd FROM tasks "
            "WHERE id=?", (TASK,)).fetchone()

        self.assertAlmostEqual(row["spent_usd"], 12.34,
                               "требование 9: точная сумма прошлой задачи "
                               "не пересчитывается")
        self.assertEqual(row["spent_estimate_usd"] or 0.0, 0.0,
                         "требование 9: колонка не бэкфиллится оценкой "
                         "задним числом")
