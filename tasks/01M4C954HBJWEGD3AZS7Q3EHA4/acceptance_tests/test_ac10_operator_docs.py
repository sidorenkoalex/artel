"""Инструкция Оператора для независимого дозора.

Группа: разовый
Красен до реализации: инструкция ещё велит запускать дозор через Monitor
и завершает его по пустому или терминальному набору задач.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402


class OperatorDocsAcceptanceTest(unittest.TestCase):
    def test_ac10_terminal_restart_and_stop_rules_are_documented(self):
        """Инструкция даёт независимый запуск и завершает дозор лишь по stop.

        Ловит мутацию: старый совет запускать Monitor и завершать дозор
        по `done`/`killed` остаётся в инструкции после изменения команды.
        """
        guide = (Path(CODE_ROOT) / "docs" / "operator-session.md").read_text(
            encoding="utf-8").lower()
        stack = (Path(CODE_ROOT) / "docs" / "stack.md").read_text(
            encoding="utf-8").lower()
        paragraphs = guide.split("\n\n")
        self.assertTrue(any("дозор" in p and "терминал" in p
                            and "оператор" in p for p in paragraphs),
                        "нет правила запуска дозора в терминале Оператора")
        self.assertTrue(any("pin-update" in p and "перезапус" in p
                            for p in paragraphs),
                        "нет перезапуска дозора после pin-update")
        finish = guide.split("#### когда наблюдатель завершается сам", 1)[1]
        finish = finish.split("\n#### ", 1)[0]
        self.assertIn("observe stop", finish)
        self.assertNotIn("все задачи набора стали", finish)
        self.assertNotIn("в наборе не осталось", finish)
        self.assertTrue("дозор" in stack and "независим" in stack,
                        "docs/stack.md не описывает независимый дозор")
