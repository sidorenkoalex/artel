"""Приёмочный тест T094 — AC-3 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-3: «CLI-команда, принимающая id задачи, разрешает уникальный
префикс id в полный идентификатор и отказывает с явным сообщением
о неоднозначности, если префиксу соответствует более одной задачи.»

Красен до реализации: сегодня `store.get_task` (общая точка резолва id
для всех команд, включая `catalog.cmd_show`) ищет СТРОГО по точному
совпадению (`WHERE id=?`) — префикс, не совпадающий буквально ни с
одним id, приводит к тому же отказу «Задача ... не найдена», что и
опечатка, без различения «нет вовсе» и «неоднозначно». Обе проверки
ниже (уникальный префикс резолвится, неоднозначный — именованно
отказывает) падают на этом сегодняшнем поведении.

Проверяется через `catalog.cmd_show` — самая простая read-only команда
из тех, что уже принимают `task_id` строкой (`orchestrator/artel.py`,
таблица диспетчера `main()`); формулировка AC-3 — про CLI-команды
вообще, не про одну конкретную, но резолв id — общий код одной точки
входа (`store.get_task`), и одной команды достаточно, чтобы предъявить
его поведение.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class Ac3PrefixResolutionTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()
        store.insert_task(conn, "AAAAUNIQ1", "Первая из пары", "in_dev",
                          "task/aaaauniq1-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.insert_task(conn, "AAAAUNIQ2", "Вторая из пары", "in_dev",
                          "task/aaaauniq2-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.insert_task(conn, "BBBBSOLO9", "Задача-одиночка", "in_dev",
                          "task/bbbbsolo9-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac3_unique_prefix_resolves_to_the_full_task_id(self):
        out = capture(catalog.cmd_show, "BBBB")

        self.assertIn("BBBBSOLO9", out)

    def test_ac3_ambiguous_prefix_refuses_by_name_not_as_not_found(self):
        with self.assertRaises(SystemExit) as ctx:
            capture(catalog.cmd_show, "AAAA")

        message = str(ctx.exception)
        self.assertIn("AAAAUNIQ1", message)
        self.assertIn("AAAAUNIQ2", message)
        self.assertNotIn("не найдена", message,
                         "неоднозначный префикс не должен выглядеть как "
                         "«задача не найдена» — сообщение обязано называть "
                         "неоднозначность явно (AC-3)")

if __name__ == "__main__":
    unittest.main()
