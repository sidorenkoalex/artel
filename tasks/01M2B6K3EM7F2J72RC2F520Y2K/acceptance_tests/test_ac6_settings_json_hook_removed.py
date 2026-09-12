"""AC-6 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — `docs/reference/role-home/
claude/settings.json` не несёт больше `hooks.PreToolUse`; файл `docs/
reference/role-home/claude/hooks/bash_guard.py` удалён; `permissions.
deny` сохранён без изменений и без потерь ни одной записи.

Зелёный с рождения: тест `test_ac6_permissions_deny_preserved_verbatim` —
`BASELINE_DENY` точная копия сегодняшнего списка `permissions.deny` в
settings.json на момент написания планки (до правок разработчика) —
критерий требует, чтобы список остался ИМЕННО таким.

Красен до реализации: тесты `test_ac6_hook_file_deleted`/
`test_ac6_pretooluse_key_removed_from_settings` — `hooks.PreToolUse`
всё ещё в settings.json, файл хука всё ещё на месте.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / "docs" / "reference" / "role-home" / "claude" / "settings.json"
HOOK = REPO_ROOT / "docs" / "reference" / "role-home" / "claude" / "hooks" / "bash_guard.py"

# Список permissions.deny settings.json на момент постановки задачи
# (SPEC требование 4/AC-6: "остаётся без изменений").
BASELINE_DENY = [
    "Read(~/.artel-canary/**)",
    "Bash(git clone:*)",
    "Bash(gh repo clone:*)",
    "Bash(git remote add:*)",
    "Bash(python3 orchestrator/artel.py init:*)",
    "Bash(python3 orchestrator/artel.py doctor --restore:*)",
    "Bash(openssl enc -d:*)",
    "Bash(security find-generic-password:*)",
]


class SettingsJsonHookRemovalTest(unittest.TestCase):

    def test_ac6_hook_file_deleted(self):
        """Файл `hooks/bash_guard.py` курируемого слоя удалён физически.

        Ловит мутацию: разработчик снимает подключение хука из
        settings.json, но забывает удалить сам файл — требование 4
        называет удаление файла отдельным пунктом, не только отключение.
        """
        self.assertFalse(HOOK.exists(),
                         f"{HOOK.relative_to(REPO_ROOT)} должен быть удалён")

    def test_ac6_pretooluse_key_removed_from_settings(self):
        """`settings.json` не несёт ключа `hooks.PreToolUse` — ни пустого
        списка, ни отсутствующего вовсе `hooks`, лишь бы не было именно
        `PreToolUse`.

        Ловит мутацию: `PreToolUse` заменён на пустой список `[]` вместо
        полного снятия ключа — формально «хук не подключён», но
        требование 4/AC-6 говорит «не несёт ключа», а не «пуст».
        """
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        hooks = data.get("hooks", {})

        self.assertNotIn("PreToolUse", hooks)

    def test_ac6_permissions_deny_preserved_verbatim(self):
        """`permissions.deny` — тот же список, той же длины, в том же
        порядке, что нёс settings.json до этой задачи.

        Ловит мутацию: правка `settings.json` для снятия хука заодно
        случайно теряет запись `permissions.deny` (например при ручном
        редактировании JSON) — список перестанет совпадать поэлементно.
        """
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))

        self.assertEqual(data["permissions"]["deny"], BASELINE_DENY)


if __name__ == "__main__":
    unittest.main()
