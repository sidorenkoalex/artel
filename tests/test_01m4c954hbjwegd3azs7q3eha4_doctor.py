"""Диагностика старого фонового hook и инструкция Оператора.

Группа: долгоживущий
Красен до реализации: `doctor` не распознаёт `guard-artel-bg` в двух
местах, а документация не содержит обновлённого порядка независимого дозора.
"""

import io
import os
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import artel, config
from tests.sandbox import TaskSeededTmpRootTest


class HookAndDocumentationTest(TaskSeededTmpRootTest):
    def test_ac10_doctor_names_migration_for_both_hook_locations(self):
        """Два старых подключения дают оператору одну явную команду миграции.

        Ловит мутацию: `doctor` проверяет только один файл hooks.json
        или перестаёт называть `hook-migrate` при найденном guard.
        """
        project_hook = config.ROOT / ".codex" / "hooks.json"
        home = self.root / "operator-home"
        user_hook = home / ".codex" / "hooks.json"
        content = ('{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":'
                   '[{"type":"command","command":"guard-artel-bg '
                   'artel.py run/auto run_in_background"}]}]}}')
        for path in (project_hook, user_hook):
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                with mock.patch.dict(os.environ, {"HOME": str(home),
                                               config.ARTEL_ROLE_ENV: ""}), \
                     mock.patch("sys.argv", ["artel.py", "doctor"]):
                    stream = io.StringIO()
                    with redirect_stdout(stream):
                        try:
                            artel.main()
                        except SystemExit as exc:
                            self.assertEqual(exc.code, 1)
                    output = stream.getvalue()
                self.assertTrue("guard-artel-bg" in output,
                                f"doctor не назвал guard для {path}")
                self.assertTrue("hook-migrate" in output,
                                f"doctor не предложил миграцию для {path}")
                self.assertEqual(path.read_text(encoding="utf-8"), content)
                path.unlink()
        guide = (Path(__file__).resolve().parents[1]
                 / "docs" / "operator-session.md").read_text(encoding="utf-8")
        stack = (Path(__file__).resolve().parents[1]
                 / "docs" / "stack.md").read_text(encoding="utf-8")
        guide_lower = guide.lower()
        for phrase in ("pin-update", "перезапус", "терминал", "дозор"):
            self.assertTrue(phrase in guide_lower, f"в инструкции нет {phrase}")
        self.assertTrue("дозор" in stack.lower(), "в docs/stack.md нет дозора")
