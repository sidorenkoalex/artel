"""Документация механики канарейки в кодовой ветке задачи.

Группа: разовый
Красен до реализации: docs/stack.md сейчас описывает общий с пультом CODEX_HOME вместо отдельного постоянного профиля канарейки.
"""

import re
import unittest
from pathlib import Path


class CanaryDocumentationTest(unittest.TestCase):
    def test_ac13_stack_describes_dedicated_subscription_profile(self):
        """Раздел канарейки объясняет постоянный профиль и подписочный вход.

        Читатель должен найти границы профиля, порядок первого входа,
        проверку и поведение при истёкшем входе.
        Ловит мутацию: документация по-прежнему велит использовать дом
        роли пульта, поэтому в ней нет описания отдельного профиля.
        """
        stack = (Path(__file__).resolve().parents[3] / "docs" / "stack.md")
        text = stack.read_text(encoding="utf-8").lower()
        for term in ("canary", "codex_home", "chatgpt", "оператор",
                     "login status"):
            with self.subTest(term=term):
                self.assertTrue(term in text, f"в docs/stack.md отсутствует {term}")
        paragraphs = text.split("\n\n")
        windows = ["\n\n".join(paragraphs[index:index + 2])
                   for index in range(len(paragraphs))]
        dedicated = any(
            "канарейк" in window and
            ("codex_home" in window or "профил" in window) and
            any(word in window for word in ("отдельн", "выделенн", "собственн")) and
            any(word in window for word in ("постоянн", "между прогон"))
            for window in windows)
        self.assertTrue(dedicated,
                        "нет описания отдельного постоянного профиля канарейки")
        isolation = re.search(
            r"(?:не изменяет|не записывает|не трогает|только читает).{0,100}"
            r"(?:боев|пульт).{0,100}(?:дом|профил)", text, re.S)
        self.assertTrue(isolation, "не описана неизменность боевого дома")


if __name__ == "__main__":
    unittest.main()
