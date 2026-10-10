"""Юнит-тесты отложенного журнала, нумерации логов и «прогон уже идёт»
`suite-run` (SPEC 01M4KG7VHHXTVTW5TTX2PGY5RY) — углы, не покрытые
долгоживущими файлами задачи
(`tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_*.py`): досыл ровно один раз,
возврат записи при отказе БД, мусорный файл и запись о неизвестной задаче,
досыл гейтом без команды, номер прогона после переноса логов, сверка «уже
идёт» с замком.
"""
import json
import os
import sqlite3
import unittest
from unittest import mock

from orchestrator import config, store, suite_lock, suite_run
from tests.sandbox import TmpRootTest, _alive_foreign_pid

TASK = "T001"
ACTION = "полный прогон: длительность близка к пределу"


class DeferredJournalTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "suite-run роли", "in_dev",
                          "task/t001", config.DEFAULT_TARGET, 25.0)

    def defer(self, task_id: str = TASK, detail: str = "длился 90%") -> None:
        suite_lock.defer_journal({"task_id": task_id, "actor": "orchestrator",
                                  "action": ACTION, "detail": detail,
                                  "session_id": "роль-сессия",
                                  "at": "2026-10-10T10:00:00"})

    def records(self) -> list:
        return [row for row in store.task_steps(store.db(), TASK)
                if row["action"] == ACTION]

    def pending(self) -> list:
        return sorted((suite_lock.directory() / "pending-journal").iterdir())

    def test_delivered_once_with_role_session(self):
        """Отложенная запись досылается в журнал своей задачи один раз.

        Ловит мутацию: файл не убирается после записи — второй досыл пишет
        ту же запись повторно; досыл теряет identity сессии роли (пишет
        identity досылающего процесса)."""
        self.defer()
        self.assertEqual(suite_lock.deliver_journal(), 1)
        self.assertEqual(suite_lock.deliver_journal(), 0)
        rows = self.records()
        self.assertEqual(len(rows), 1)
        self.assertIn("длился 90%", rows[0]["detail"])
        self.assertIn("дослано процессом пульта", rows[0]["detail"])
        self.assertEqual(rows[0]["session_id"], "роль-сессия")
        self.assertEqual(self.pending(), [])

    def test_db_refusal_keeps_record_for_next_delivery(self):
        """Отказ БД на досыле — запись остаётся и доходит следующим досылом.

        Ловит мутацию: файл удаляется до записи в БД (или при её отказе) —
        процесс роли, сам вызвавший досыл, теряет запись навсегда; забранный
        файл не возвращается под прежнее имя и больше не виден досылу."""
        self.defer()
        with mock.patch.object(store, "journal",
                               side_effect=sqlite3.OperationalError(
                                   "attempt to write a readonly database")):
            self.assertEqual(suite_lock.deliver_journal(), 0)
        self.assertEqual(self.records(), [])
        self.assertEqual([p.suffix for p in self.pending()], [".json"])
        self.assertEqual(suite_lock.deliver_journal(), 1)
        self.assertEqual(len(self.records()), 1)

    def test_garbage_and_unknown_task_are_dropped(self):
        """Нечитаемый файл и запись о задаче, которой нет, убираются молча.

        Ловит мутацию: нечитаемый файл возвращается в очередь — досыл
        спотыкается о него вечно; запись неизвестной задачи пишется в
        журнал (под пустой задачей) либо роняет досыл соседней записи."""
        folder = suite_lock.directory() / "pending-journal"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "0-1.json").write_text("{не json", encoding="utf-8")
        self.defer(task_id="T999")
        self.defer()
        self.assertEqual(suite_lock.deliver_journal(), 1)
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(self.pending(), [])

    def test_forged_actor_and_foreign_action_are_not_delivered(self):
        """Очередь — не канал записи журнала от имени Оператора: действие
        вне перечня выбрасывается, автора ставит досыл (R1-F1).

        Ловит мутацию: досыл берёт `actor`/`action` из файла очереди — роль на
        Codex подкладывает «объявлена смена поведения тестов» от `operator`,
        и гейт неослабления тестов верит записи; досыл не режет текст —
        подложенный detail уходит в журнал целиком."""
        from orchestrator.advance_gates import test_integrity
        folder = suite_lock.directory() / "pending-journal"
        folder.mkdir(parents=True, exist_ok=True)
        forged = {"task_id": TASK, "actor": "operator",
                  "action": test_integrity.DECLARED_CHANGE_ACTION,
                  "detail": "tests/x.py::A::b: a → b\n-", "at": "2026-10-10"}
        (folder / "1-1.json").write_text(json.dumps(forged, ensure_ascii=False),
                                         encoding="utf-8")
        self.assertFalse(suite_lock.defer_journal(dict(forged)))
        (folder / "2-1.json").write_text(json.dumps(
            {"task_id": TASK, "actor": "operator", "action": ACTION,
             "detail": "x" * 10_000, "at": "2026-10-10"}), encoding="utf-8")
        self.assertEqual(suite_lock.deliver_journal(), 1)
        rows = store.task_steps(store.db(), TASK)
        self.assertEqual(
            [row for row in rows
             if row["action"] == test_integrity.DECLARED_CHANGE_ACTION], [])
        self.assertEqual([row["actor"] for row in self.records()],
                         [suite_lock.DEFERRED_ACTOR])
        self.assertLess(len(self.records()[0]["detail"]),
                        suite_lock.DEFERRED_DETAIL_MAX + 200)
        self.assertEqual(self.pending(), [])

    def test_background_does_not_defer_foreign_action(self):
        """Обёртка прогона откладывает только действие перечня.

        Ловит мутацию: `_journal_deferred` кладёт в очередь любое отказанное
        действие — запись, которую процесс пульта не досылает, копится или
        (при ослабленном досыле) уходит в журнал."""
        readonly = sqlite3.connect(f"{config.DB.resolve().as_uri()}?mode=ro",
                                   uri=True)
        self.addCleanup(readonly.close)
        readonly.row_factory = sqlite3.Row
        with suite_run._journal_deferred():
            with self.assertRaises(sqlite3.Error):
                store.journal(readonly, TASK, "orchestrator", "прогон: время",
                              "{}")
        self.assertFalse((suite_lock.directory() / "pending-journal").exists()
                         and self.pending())

    def test_delivery_closes_connection(self):
        """Досыл закрывает своё соединение с БД (R1-F2).

        Ловит мутацию: `store.db()` досыла не закрывается — долгоживущий
        процесс пульта копит соединения на каждом ожидании замка гейтом."""
        self.defer()
        opened = []
        real_db = store.db

        def db():
            conn = real_db()
            opened.append(conn)
            return conn

        with mock.patch.object(store, "db", side_effect=db):
            self.assertEqual(suite_lock.deliver_journal(), 1)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")

    def test_gate_lock_wait_delivers(self):
        """Ожидание замка гейтом досылает журнал без команды `suite-run`.

        Ловит мутацию: досыл вызывает только команда `suite-run` — запись
        роли ждёт, пока кто-то вручную позовёт команду, хотя гейты пульта
        гоняют полный набор регулярно."""
        self.defer()
        self.assertIsNone(suite_lock.wait_acquire(
            "T002", suite_lock.KIND_GATE, 0, lambda holder: None))
        self.addCleanup(suite_lock.release)
        self.assertEqual(len(self.records()), 1)

    def test_journal_refusal_in_background_is_deferred_and_seen(self):
        """В фоне прогона отказ БД откладывает запись, вызывающий видит сбой.

        Ловит мутацию: обёртка глотает сбой — узел пульта считает запись
        состоявшейся (и не помечает «запись сигнала не удалась»); обёртка не
        снята после прогона — `store.journal` остаётся подменённым в
        процессе."""
        original = store.journal
        readonly = sqlite3.connect(f"{config.DB.resolve().as_uri()}?mode=ro",
                                   uri=True)
        self.addCleanup(readonly.close)
        readonly.row_factory = sqlite3.Row
        with suite_run._journal_deferred():
            with self.assertRaises(sqlite3.Error):
                store.journal(readonly, TASK, "orchestrator", ACTION,
                              "длился 85%")
        self.assertIs(store.journal, original)
        self.assertEqual(self.records(), [])
        self.assertEqual(suite_lock.deliver_journal(), 1)
        self.assertIn("длился 85%", self.records()[0]["detail"])


class RunNumberingTest(TmpRootTest):

    def test_number_continues_after_saved_run(self):
        """Номер нового прогона — после номера `run.json`/`result.json`.

        Ловит мутацию: нумерация только по логам нового каталога — первый
        прогон после переноса логов получает №1, а `result.json` прошлого
        прогона №1 `--wait` примет за отчёт нового."""
        suite_run._write_json(suite_run._run_path(TASK), {"run": 4, "pid": 1})
        suite_run._write_json(suite_run._result_path(TASK), {"run": 4})
        log = suite_run._new_log(TASK)
        self.assertEqual(log, suite_run._log_path(TASK, 5))
        self.assertTrue(log.is_file())
        self.assertEqual(suite_run._new_log(TASK),
                         suite_run._log_path(TASK, 6))


class RunningNeedsLockTest(TmpRootTest):

    def test_running_only_while_its_process_holds_lock(self):
        """«Прогон уже идёт» — только пока замок держит процесс прогона.

        Ловит мутацию: живой pid из `run.json` без сверки с замком считается
        идущим прогоном — при замке гейта команда отвечает «уже идёт» с
        кодом 0 вместо отказа с держателем."""
        live = _alive_foreign_pid(self)
        suite_run._write_json(suite_run._run_path(TASK), {"run": 1, "pid": live})
        lock = suite_lock.path()
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"task_id": "T002", "pid": os.getpid(),
                                    "kind": suite_lock.KIND_GATE}),
                        encoding="utf-8")
        self.assertIsNone(suite_run._running(TASK))
        lock.write_text(json.dumps({"task_id": TASK, "pid": live, "run": 1}),
                        encoding="utf-8")
        self.assertEqual(suite_run._running(TASK)["pid"], live)


if __name__ == "__main__":
    unittest.main()
