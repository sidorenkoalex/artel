"""AC-10 (tasks/T092/SPEC.md): прогон команды `report` не меняет ни
одной строки в `state.db` (состояния задач, счётчики, алерты и прочие
таблицы остаются побайтово прежними) и не порождает записей в журнале
шагов.

Две независимые проверки: побайтовое сравнение самого файла `state.db`
(буквальная формулировка AC-10) и, отдельно, логическое содержимое
таблиц `tasks`/`steps`/`alerts` — чтобы страховаться от ложного red/green
на файловом уровне (WAL/чекпоинт), если он вдруг не будет байт-в-байт
детерминирован на каком-то окружении.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402
from orchestrator import config, store  # noqa: E402


class ReportReadOnlyTest(ReportSandboxTest):

    def setUp(self):
        super().setUp()
        self.mk_task("T001", "Задача-фикстура для report", "in_dev",
                    budget_usd=25.0, spent_usd=3.5)
        self.mk_task("T002", "Вторая задача-фикстура", "merge_gate")
        self.mk_step("T001", "operator", "approve", "фикстура AC-10")
        self.mk_alert("incident", "test.ac10", "фикстура алерта AC-10")

        # Соединения выше уже закрыты (`_AutoClosingConnection.__del__`) —
        # файл БД стабилен перед снимком, никаких висящих транзакций.
        self.db_bytes_before = config.DB.read_bytes()
        self.tasks_before = self._dump("tasks")
        self.steps_before = self._dump("steps")
        self.alerts_before = self._dump("alerts")
        self.steps_count_before = len(self.steps_before)

    @staticmethod
    def _dump(table: str) -> list:
        conn = store.db()
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        return [tuple(r) for r in rows]

    def test_ac10_db_file_byte_identical_after_report(self):
        out, new_files, _, _ = self.run_report()

        after = config.DB.read_bytes()
        self.assertEqual(
            self.db_bytes_before, after,
            "state.db изменился побайтово после прогона report")

    def test_ac10_no_new_journal_records(self):
        out, new_files, _, _ = self.run_report()

        steps_after = self._dump("steps")
        self.assertEqual(
            self.steps_count_before, len(steps_after),
            "report породил новые записи в журнале шагов")
        self.assertEqual(self.steps_before, steps_after)

    def test_ac10_tasks_and_alerts_rows_unchanged(self):
        out, new_files, _, _ = self.run_report()

        self.assertEqual(self.tasks_before, self._dump("tasks"),
                         "report изменил строки таблицы tasks")
        self.assertEqual(self.alerts_before, self._dump("alerts"),
                         "report изменил строки таблицы alerts")


if __name__ == "__main__":
    unittest.main()
