"""Приёмочный тест AC-8 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
`sqlite3 .schema` новой пустой БД, созданной `create_schema` (в т.ч.
реэкспортом `store.create_schema`), идентична байт-в-байт схеме до
рефакторинга.

`config.DEFAULT_TARGET` встроен в `SCHEMA` литералом через f-string
(значение по умолчанию колонки `target` таблиц `tasks`/`steps`,
`orchestrator/store.py`, требование ADR-0003 3ж — то же значение,
которое использует и `add_column` в `migrate()`) — это крутилка
Оператора, не то, что должно ломать тест при её повороте, поэтому
ожидаемый DDL — шаблон с `{target}`, подставляемым из ЖИВОГО
`config.DEFAULT_TARGET` в момент прогона, а не литерал «artel».

Зелёный с рождения: DDL снят с сегодняшнего (дорефакторингового)
`store.create_schema` — обязан остаться байт-в-байт тем же после
переноса схемы в `schema.py` (AC-1) и группировки запросов (AC-3),
поскольку сама схема не меняется по существу (SPEC, требование 6,
«Не входит»: новые колонки).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402

# `sqlite3 <файл> .schema` на пустой БД, созданной сегодняшним
# (дорефакторинговым) `store.create_schema` — DDL воспроизводится
# byte-in-byte напрямую из `sqlite_master.sql` (CLI ничего не
# переформатирует), поэтому шаблон совпадает буквально с исходником
# `SCHEMA` в orchestrator/store.py.
_EXPECTED_SCHEMA_TEMPLATE = """CREATE TABLE tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0, spent_estimate_usd REAL DEFAULT 0,
  budget_source TEXT,
  target TEXT DEFAULT '{target}', fixed_sha TEXT,
  tests_locked_sha TEXT, is_canary INTEGER DEFAULT 0, paused INTEGER DEFAULT 0,
  answer_baseline INTEGER, verifying_attempts INTEGER DEFAULT 0,
  draft_mr_created INTEGER DEFAULT 0,
  diff_bytes INTEGER, split_assessment TEXT, zones TEXT,
  zones_extension TEXT,
  materialized_artifact_sha TEXT, zone_queue_position INTEGER,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  target TEXT DEFAULT '{target}', ts TEXT,
  actor TEXT, action TEXT, detail TEXT, session_id TEXT
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE task_counters (
  target TEXT PRIMARY KEY, next_number INTEGER NOT NULL
);
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, kind TEXT, source TEXT,
  message TEXT, ts TEXT, ack_ts TEXT, ack_by TEXT, ack_resolution TEXT
);
CREATE TABLE alerts_archive (
  id INTEGER PRIMARY KEY, target TEXT, kind TEXT, source TEXT,
  message TEXT, ts TEXT, ack_ts TEXT, ack_by TEXT, ack_resolution TEXT,
  archived_ts TEXT
);
CREATE TABLE leases (
  task_id TEXT PRIMARY KEY, session_id TEXT, pid INTEGER, hostname TEXT,
  heartbeat_ts TEXT, pgid INTEGER
);
CREATE TABLE merge_locks (
  task_id TEXT, session_id TEXT, pid INTEGER, hostname TEXT,
  heartbeat_ts TEXT
);
"""


@unittest.skipUnless(shutil.which("sqlite3"),
                     "CLI sqlite3 недоступен в этом окружении — "
                     "критерий буквально называет `sqlite3 .schema`")
class SchemaDdlByteParityTest(unittest.TestCase):

    def test_ac8_sqlite3_schema_output_matches_pre_refactor_ddl(self):
        """Свежая БД, созданная `store.create_schema`, даёт `sqlite3
        <файл> .schema`, байт-в-байт совпадающий со снимком DDL,
        снятым до переноса схемы в `schema.py`.

        Ловит мутацию: перенос `SCHEMA`/`create_schema` в `schema.py`
        по пути незаметно поменял DDL (например, слетел один из
        DEFAULT, порядок колонок или порядок `CREATE TABLE`
        инструкций внутри `executescript`) — вывод `sqlite3 .schema`
        для новой пустой БД перестаёт совпадать с зафиксированным
        шаблоном.
        """
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            import sqlite3
            conn = sqlite3.connect(db_path)
            store.create_schema(conn)
            conn.close()

            result = subprocess.run(
                ["sqlite3", str(db_path), ".schema"],
                capture_output=True, text=True, timeout=10)

        expected = _EXPECTED_SCHEMA_TEMPLATE.format(
            target=config.DEFAULT_TARGET)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
