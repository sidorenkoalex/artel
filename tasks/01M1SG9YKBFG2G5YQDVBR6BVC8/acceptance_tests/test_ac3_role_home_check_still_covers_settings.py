"""Приёмочный тест 01M1SG9YKBFG2G5YQDVBR6BVC8 — AC-3: сверка
`orchestrator.doctor.check_role_home_reference` не ослаблена задачей и
продолжает покрывать `settings.json`.

Зелёный с рождения: `check_role_home_reference`/`_role_home_diff`
(orchestrator/doctor.py) уже сравнивают `settings.json` побайтово
между референсом и деплоем на СЕГОДНЯШНЕМ main — задача
01M1SG9YKBFG2G5YQDVBR6BVC8 не трогает эту функцию (зона ограничена
`docs/reference/role-home/claude/settings.json` и `tests/`), так что
тест проходит уже сейчас; он служит регресс-щитом на то, чтобы
реализация AC-1/AC-2 не завела попутно исключение settings.json из
сравнения ради тишины по новому ключу autoMemoryEnabled.
"""
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, doctor  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class RoleHomeReferenceStillCoversSettingsJsonTest(TmpRootTest):
    """Развёрнутый курируемый слой копируется из настоящего референса,
    затем его settings.json портится — doctor обязан это заметить."""

    PATCHED_ATTRS = ("ROLE_HOME", "ROLE_CONFIG_DIR")

    def setUp(self):
        super().setUp()
        reference = (REPO_ROOT / "docs" / "reference" / "role-home"
                     / "claude")
        shutil.copytree(reference, config.ROLE_CONFIG_DIR)

    def test_ac3_settings_json_diff_from_reference_still_detected(self):
        """Развёрнутый settings.json подменён на текст, отличный от
        референса — doctor обязан вернуть WARN с упоминанием
        settings.json в перечне расхождений.

        Ловит мутацию: правка `_role_home_diff`/`check_role_home_reference`,
        исключающая `settings.json` из сравнения (например, чтобы
        погасить шум от нового ключа `autoMemoryEnabled`) — AC-3 SPEC
        прямо запрещает такое ослабление; без settings.json в списке
        сравниваемых файлов WARN здесь не наступит или не назовёт файл,
        и тест покраснеет.
        """
        deployed_settings = config.ROLE_CONFIG_DIR / "settings.json"
        deployed_settings.write_text('{"permissions": {"deny": []}}',
                                      encoding="utf-8")

        check = doctor.check_role_home_reference()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("settings.json", check.detail)


if __name__ == "__main__":
    unittest.main()
