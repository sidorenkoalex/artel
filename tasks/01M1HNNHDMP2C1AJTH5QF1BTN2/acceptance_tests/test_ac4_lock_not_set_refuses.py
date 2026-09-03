"""AC-4 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Команда отказывает
именованно и не меняет tests_locked_sha, если задача ещё не проходила
фиксацию лока (lock ещё не ставился).»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AmendSandbox  # noqa: E402


class LockNotSetRefusalTest(AmendSandbox):

    def test_ac4_task_never_locked_refuses_and_leaves_tests_locked_sha_null(self):
        """Свежесозданная задача ещё не проходила выход из tests_writing
        — `tests_locked_sha` в БД пуст (NULL). Вызов команды правки планки
        обязан отказать именованно, не трогая `tests_locked_sha`.

        Ловит мутацию: команда проверяет ТЕКУЩЕЕ состояние задачи (`state
        != "tests_writing"`) вместо самой колонки `tests_locked_sha` —
        такая проверка либо ложно пропускает задачи в состояниях после
        in_dev с пустым локом (вырожденный случай T023: `NULL — лок
        сверять не с чем`, `orchestrator/store.py`), либо путает
        «лока нет» с «сейчас не tests_writing».
        """
        self.assertIsNone(
            self.row()["tests_locked_sha"],
            "фикстура сломана: у свежей задачи tests_locked_sha должен "
            "быть NULL")

        out = self.run_amend(reason="лока ещё нет, но Оператор пробует")

        self.assertTrue(out.strip(), "отказ обязан называть причину")
        self.assertIsNone(
            self.row()["tests_locked_sha"],
            "tests_locked_sha не должен появиться из ничего — лока не "
            "было и не должно стать")


if __name__ == "__main__":
    unittest.main()
