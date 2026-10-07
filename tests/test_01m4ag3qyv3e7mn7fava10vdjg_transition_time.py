"""Переход с долгоживущими файлами записывает время их прогона.

Группа: долгоживущий
Красен до реализации: рубеж ещё не записывает время отдельных файлов в журнал.

Сценарий использует готовый контур `InDevGatesSandbox`: команда `advance`,
FSM, БД и git проверяются вместе. Отдельные сравнения порога проверяются
модульным тестом в соседнем файле.
"""

import hashlib
import re
import unittest
from unittest import mock

from orchestrator import checkpoint, config, idgen, store, workspace
from scripts import guard
from tests.test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates import InDevGatesSandbox


PLANK = '''"""Исход приёмки в песочнице.

Группа: разовый
Зелёный с рождения: фикстура проверяет заданный исход.
"""
import unittest

class FixturePlank(unittest.TestCase):
    def test_result(self):
        """Фикстура возвращает заданный исход.

        Ловит мутацию: изменение ожидаемого числа красит фикстуру.
        """
        self.assertEqual(1 + 1, {expected})
'''

LONG_LIVED = '''"""Короткий долгоживущий файл песочницы.

Группа: долгоживущий
"""
import unittest

class FixtureLongLived(unittest.TestCase):
    def test_result(self):
        """Файл завершается зелёным.

        Ловит мутацию: изменение ожидаемого числа красит файл.
        """
        self.assertEqual(2 + 2, 4)
'''


class TransitionTimeTest(InDevGatesSandbox):
    def prepare(self, *, green):
        """Создаёт задачу готовым контуром и фиксирует два файла для рубежа."""
        task_id = idgen.new_task_id()
        rels = [f"tests/test_{task_id.lower()}_{name}.py"
                for name in ("first", "second")]
        with mock.patch.object(idgen, "new_task_id", return_value=task_id):
            self.new_task(config.DEFAULT_TARGET, ["tests/"],
                          {rel: LONG_LIVED for rel in rels})
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / task_id
        plank_dir = docs / "acceptance_tests"
        plank_dir.mkdir(parents=True, exist_ok=True)
        (plank_dir / "test_plank.py").write_text(
            PLANK.format(expected=2 if green else 3), encoding="utf-8")
        worktree = workspace.path(task_id)
        manifest = "".join(
            f"{hashlib.sha256((worktree / rel).read_bytes()).hexdigest()}  {rel}\n"
            for rel in rels)
        (plank_dir / guard.LONG_LIVED_MANIFEST_NAME).write_text(
            manifest, encoding="utf-8")
        detail = checkpoint.commit_step_artifacts(self.conn, task_id, "developer")
        locked = re.search(r"\bsha ([0-9a-f]{40})\b", detail)
        self.assertIsNotNone(locked, self.explain("ссылка документов не создана"))
        store.update_task(self.conn, task_id, tests_locked_sha=locked.group(1),
                          draft_mr_created=1)
        store.record_fixation(self.conn, task_id)
        return task_id, rels

    def test_ac4_transition_journals_each_file_time(self):
        """Связка команда–FSM–БД–git пишет путь и время каждого файла.

        Ловит мутацию: рубеж гоняет долгоживущие файлы, но пропускает
        запись времени одного из них — его путь с числом секунд исчезает.
        """
        task_id, rels = self.prepare(green=True)
        rows, out = self.advance(task_id)
        journal = self.text_of(rows, out)
        self.assertEqual(self.state(task_id), "verifying", self.explain(journal))
        for rel in rels:
            with self.subTest(rel=rel):
                self.assertRegex(journal, re.escape(rel) + r"[^\n]*\d+(?:[.,]\d+)?",
                                 self.explain(journal))

    def test_ac7_warning_keeps_green_and_red_outcomes(self):
        """Связка команда–FSM–БД–git сохраняет исход при предупреждении.

        Две задачи с файлами сверх порога получают предупреждение: зелёная
        переходит в verifying, красная остаётся в in_dev.

        Ловит мутацию: предупреждение превращено в отказ либо красный
        прогон ошибочно пропускается — состояние задачи расходится с исходом.
        """
        for green, expected in ((True, "verifying"), (False, "in_dev")):
            with self.subTest(green=green):
                task_id, rels = self.prepare(green=green)
                with mock.patch.object(config, "LONG_LIVED_FILE_WARN_SEC", -1,
                                       create=True):
                    rows, out = self.advance(task_id)
                journal = self.text_of(rows, out)
                self.assertEqual(self.state(task_id), expected,
                                 self.explain(journal))
                self.assertIn(rels[0], journal, self.explain(journal))
                self.assertRegex(journal.lower(), r"предупрежд|превыш|сверх",
                                 self.explain(journal))


if __name__ == "__main__":
    unittest.main()
