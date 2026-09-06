"""Приёмочный тест AC-2 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-2. `docs/reference/role-home/claude/settings.json` несёт
`hooks.PreToolUse` с записью `{"matcher": "Bash", "hooks": [{"type":
"command", "command": "python3 \"$CLAUDE_CONFIG_DIR/hooks/bash_guard.py\"",
"timeout": 10}]}`; текущий список `permissions.deny` (8 записей на
момент SPEC) сохранён без изменений и без потерь ни одной записи.

Красен до реализации: `settings.json` на момент написания планки не
несёт ключа `hooks` вовсе (снят коммитом dea8016b) — `test_ac2_*`
падает на отсутствующем ключе `hooks.PreToolUse`.

Зелёный с рождения (`test_ac2_permissions_deny_has_no_losses`): список
`permissions.deny`, зафиксированный ниже как `EXPECTED_DENY`, — снимок
РЕАЛЬНОГО `settings.json` на момент написания этой планки (8 записей,
см. SPEC.md «Критерии приёмки», AC-2); тест проверяет подмножество, а
не байт-в-байт, поэтому расширение списка независимой задачей между
написанием планки и мержем этой задачи не мутация (тот же приём, что и
`tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/acceptance_tests/
test_ac9_ac10_ac11_ac12_bash_guard_removed.py::EXPECTED_DENY`, только в
обратную сторону — там снятие хука не должно было тронуть deny, здесь
восстановление хука тоже не должно.
"""
import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

SETTINGS_FILE = (_REPO_ROOT / "docs" / "reference" / "role-home" / "claude"
                 / "settings.json")

# Снимок permissions.deny на момент написания планки (8 записей, SPEC.md
# «Критерии приёмки», AC-2) — восстановление хука не должно потерять ни
# одну из них.
EXPECTED_DENY = [
    "Read(~/.artel-canary/**)",
    "Bash(git clone:*)",
    "Bash(gh repo clone:*)",
    "Bash(git remote add:*)",
    "Bash(python3 orchestrator/artel.py init:*)",
    "Bash(python3 orchestrator/artel.py doctor --restore:*)",
    "Bash(openssl enc -d:*)",
    "Bash(security find-generic-password:*)",
]

EXPECTED_HOOK_ENTRY = {
    "matcher": "Bash",
    "hooks": [
        {
            "type": "command",
            "command": 'python3 "$CLAUDE_CONFIG_DIR/hooks/bash_guard.py"',
            "timeout": 10,
        }
    ],
}


class SettingsJsonWiringTest(unittest.TestCase):

    def setUp(self):
        self.settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

    def test_ac2_pretooluse_hook_entry_matches_the_reference_edition(self):
        """`hooks.PreToolUse` несёт запись с matcher `Bash`, командой и
        таймаутом 10 — редакция коммита 80c38245.

        Ловит мутацию: опечатка в команде (например, без кавычек вокруг
        `$CLAUDE_CONFIG_DIR/hooks/bash_guard.py` — хук получил бы путь
        только до первого пробела) или другое значение `timeout` —
        `assertIn` ниже не найдёт запись, совпадающую целиком.
        """
        entries = self.settings.get("hooks", {}).get("PreToolUse", [])
        self.assertIn(EXPECTED_HOOK_ENTRY, entries,
                      f"запись hook не найдена дословно в PreToolUse: {entries!r}")

    def test_ac2_permissions_deny_has_no_losses(self):
        """`permissions.deny` не теряет ни одной из 8 записей, действовавших
        на момент SPEC, после восстановления хука.

        Ловит мутацию: восстановление `settings.json` из редакции
        80c38245 целиком (у той редакции deny — только 4 записи) вместо
        добавления к ТЕКУЩЕМУ файлу — 4 более поздние записи (например,
        `Bash(openssl enc -d:*)`) пропали бы, и `assertEqual` ниже
        покажет непустой `missing`.
        """
        deny = self.settings.get("permissions", {}).get("deny")
        self.assertIsInstance(deny, list)
        missing = [d for d in EXPECTED_DENY if d not in deny]
        self.assertEqual(missing, [],
                         f"из permissions.deny пропали записи: {missing}")


if __name__ == "__main__":
    unittest.main()
