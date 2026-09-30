"""Факты документации и запуска нынешних тестов под маркером роли.

Группа: разовый
Красен до реализации: docs/stack.md ещё не называет in_role_environment и не содержит строку паритета отказа команд.
"""

import os
import subprocess
import sys
import unittest

from orchestrator import config


class RoleEnvironmentAcceptanceTest(unittest.TestCase):
    def test_ac4_stack_describes_role_marker_and_parity(self):
        """Описание признака и оба значения «да» стоят в таблице паритета.

        Ловит мутацию: строка отказа команд пульта добавлена только для
        Claude — ячейка Codex не содержит «да» и проверка краснеет.
        """
        text = (config.ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
        self.assertTrue("ARTEL_ROLE" in text, "stack.md не называет ARTEL_ROLE")
        self.assertTrue("in_role_environment" in text,
                        "stack.md не называет признак in_role_environment")
        self.assertTrue("CLAUDE_CONFIG_DIR" in text,
                        "stack.md не объясняет прежний признак Claude")
        section = text.split("## Паритет безопасности роли", 1)
        self.assertEqual(len(section), 2, "в stack.md нет таблицы паритета")
        table = section[1].split("\n## ", 1)[0]
        rows = [line for line in table.splitlines() if line.lstrip().startswith("|")]
        matches = [line for line in rows if "команд пульта" in line.lower()
                   and ("отказ" in line.lower() or "запрет" in line.lower())]
        self.assertTrue(matches, "нет строки отказа команд пульта из-под роли")
        cells = [cell.strip().strip("*`") for cell in matches[0].strip().strip("|").split("|")]
        self.assertGreaterEqual(len(cells), 3)
        self.assertEqual(cells[1].lower(), "да", matches[0])
        self.assertEqual(cells[2].lower(), "да", matches[0])

    def test_ac6_ambient_role_keeps_command_tests_green(self):
        """Названные и соседние сценарии команд проходят под ARTEL_ROLE.

        Ловит мутацию: тесты обычных вызовов наследуют ARTEL_ROLE pytest
        и получают отказ роли вместо ожидаемого результата команды.
        """
        env = os.environ.copy()
        env[config.ARTEL_ROLE_ENV] = "test_author"
        files = (
            "tests/test_answer.py",
            "tests/test_notes.py",
            "tests/test_notes_apply.py",
            "tests/test_notes_row_format.py",
            "tests/test_canary.py",
            "tests/test_doctor_canary_pool.py",
            "tests/test_conftest_role_guard.py",
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *files, "-q", "-p", "no:cacheprovider",
             "-p", "timeout", "-o", "timeout=120"],
            cwd=config.ROOT, env=env, text=True, capture_output=True, timeout=100)
        self.assertEqual(result.returncode, 0,
                         (result.stdout + "\n" + result.stderr)[-12000:])


if __name__ == "__main__":
    unittest.main()
