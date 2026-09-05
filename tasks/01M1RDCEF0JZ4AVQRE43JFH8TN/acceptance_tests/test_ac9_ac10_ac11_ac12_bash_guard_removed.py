"""Приёмочные тесты AC-9..AC-12 (tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/SPEC.md,
«Критерии приёмки»).

AC-9. Файл `docs/reference/role-home/claude/hooks/bash_guard.py` удалён.

AC-10. Запись `hooks.PreToolUse` удалена из
`docs/reference/role-home/claude/settings.json`; поле
`permissions.deny` остаётся без изменений.

AC-11. Файл `tests/test_role_bash_guard.py` удалён.

AC-12. `docs/reference/role-home.md` не содержит упоминаний снятого
хука (`bash_guard.py`, `PreToolUse`).

Красен до реализации: временный хук ещё на месте (AC-9, AC-10, AC-11) —
`docs/reference/role-home/claude/hooks/bash_guard.py` и
`tests/test_role_bash_guard.py` существуют, `settings.json` несёт
`hooks.PreToolUse` — все три `assertFalse`/сверки ниже падают на
СУЩЕСТВОВАНИИ файла/записи.

Зелёный с рождения (AC-12): `docs/reference/role-home.md` на момент
написания этой планки НЕ содержит упоминаний `bash_guard.py`/
`PreToolUse` вовсе (хук был добавлен файлами `hooks/`/`settings.json`
05.09, но текст `role-home.md` не был обновлён под него) — тест
фиксирует это КАК ИНВАРИАНТ, который снятие хука обязано сохранить, а
не как новое поведение, ожидаемое от кода этой задачи.
"""
import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

ROLE_HOME_CLAUDE = _REPO_ROOT / "docs" / "reference" / "role-home" / "claude"
HOOK_FILE = ROLE_HOME_CLAUDE / "hooks" / "bash_guard.py"
SETTINGS_FILE = ROLE_HOME_CLAUDE / "settings.json"
GUARD_TEST_FILE = _REPO_ROOT / "tests" / "test_role_bash_guard.py"
ROLE_HOME_MD = _REPO_ROOT / "docs" / "reference" / "role-home.md"

# Список `permissions.deny`, действовавший на момент написания планки —
# требование 4 SPEC требует, чтобы снятие хука его НЕ тронуло. Сверка —
# «ни одна из этих записей не исчезла», а не байт-в-байт: другие,
# независимо смерженные задачи вправе РАСШИРЯТЬ deny (пул канарейки
# 01M1NSR5M5THYRC0RFWPMVE2DW добавил четыре записи между написанием
# планки и мержем этой задачи — правка планки Оператора по ADR-0012,
# amend-tests 05.09; чувствительность к собственной правке этой задачи
# не ослаблена: удаление любого запрета по-прежнему краснит).
EXPECTED_DENY = [
    "Read(~/.artel-canary/**)",
    "Bash(git clone:*)",
    "Bash(gh repo clone:*)",
    "Bash(git remote add:*)",
]


class BashGuardHookFileRemovedTest(unittest.TestCase):

    def test_ac9_hook_file_is_deleted(self):
        """`hooks/bash_guard.py` референса курируемого слоя удалён.

        Ловит мутацию: хук оставлен на месте («на всякий случай») —
        `assertFalse` находит файл и краснеет.
        """
        self.assertFalse(HOOK_FILE.exists(), f"файл всё ещё существует: {HOOK_FILE}")

    def test_ac11_guard_test_file_is_deleted(self):
        """`tests/test_role_bash_guard.py` (тест снятого хука) удалён.

        Ловит мутацию: тест хука оставлен рядом с уже удалённым хуком —
        `discover` по `tests/` упал бы импортом несуществующего файла
        хука; здесь же ловится сам факт «файл теста не удалён».
        """
        self.assertFalse(GUARD_TEST_FILE.exists(),
                         f"файл теста всё ещё существует: {GUARD_TEST_FILE}")


class SettingsJsonPreToolUseRemovedTest(unittest.TestCase):

    def setUp(self):
        self.settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

    def test_ac10_pretooluse_hook_entry_is_removed(self):
        """`hooks.PreToolUse` отсутствует в `settings.json` целиком (не
        просто опустошён список — самого ключа `hooks` с `PreToolUse`
        внутри быть не должно, если `hooks` только это и нёс).

        Ловит мутацию: запись `PreToolUse` оставлена пустым списком
        `[]` вместо удаления секции — `assertNotIn`/структурная проверка
        ниже ловит остаточный ключ.
        """
        hooks = self.settings.get("hooks", {})
        self.assertNotIn("PreToolUse", hooks,
                         "запись hooks.PreToolUse всё ещё присутствует в settings.json")

    def test_ac10_permissions_deny_is_unchanged(self):
        """`permissions.deny` остаётся тем же списком, что и до снятия
        хука — требование 4 SPEC явно исключает его из правки.

        Ловит мутацию: попутная «уборка» списка запретов вместе с
        удалением хука (например, снятие `git clone`-запрета заодно) —
        проверка подмножества покраснеет на первой же пропавшей записи.
        Расширение списка другой задачей мутацией не считается.
        """
        deny = self.settings.get("permissions", {}).get("deny")
        self.assertIsInstance(deny, list)
        missing = [d for d in EXPECTED_DENY if d not in deny]
        self.assertEqual(missing, [],
                         f"из permissions.deny пропали записи: {missing}")


class RoleHomeDocNoLongerMentionsTheHookTest(unittest.TestCase):

    def test_ac12_role_home_doc_has_no_mention_of_the_removed_hook(self):
        """`docs/reference/role-home.md` не упоминает `bash_guard.py`
        и не упоминает `PreToolUse`.

        Ловит мутацию: правка `role-home.md`, которая ВВОДИТ описание
        снятого хука пост-фактум (например, в раздел «Курирование» как
        историческую заметку) — `assertNotIn` поймает любое из двух
        слов-маркеров.
        """
        text = ROLE_HOME_MD.read_text(encoding="utf-8")
        self.assertNotIn("bash_guard.py", text)
        self.assertNotIn("PreToolUse", text)


if __name__ == "__main__":
    unittest.main()
