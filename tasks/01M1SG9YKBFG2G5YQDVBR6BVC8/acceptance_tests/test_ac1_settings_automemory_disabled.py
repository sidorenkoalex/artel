"""Приёмочный тест 01M1SG9YKBFG2G5YQDVBR6BVC8 — AC-1: референсный
settings.json курируемого слоя ролей отключает автопамять CLI.

Красен до реализации: `docs/reference/role-home/claude/settings.json`
сейчас не содержит ключ `autoMemoryEnabled` вовсе — чтение вернёт
`None`, что не равно `False`, и тест упадёт до правки референса.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PATH = (REPO_ROOT / "docs" / "reference" / "role-home" / "claude"
                  / "settings.json")


class SettingsAutoMemoryDisabledTest(unittest.TestCase):
    def test_ac1_settings_json_has_automemory_disabled(self):
        """Референсный settings.json курируемого слоя ролей содержит
        ключ `autoMemoryEnabled` со значением `false` (булевым, не строкой).

        Ловит мутацию: ключ добавлен со значением `true`, опущен вовсе,
        либо записан строкой `"false"` вместо булева `false` — во всех
        трёх случаях сравнение `is False` не проходит.
        """
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

        self.assertIn("autoMemoryEnabled", data,
                      f"{SETTINGS_PATH}: нет ключа autoMemoryEnabled")
        self.assertIs(data["autoMemoryEnabled"], False,
                       f"{SETTINGS_PATH}: autoMemoryEnabled должен быть "
                       f"булевым false, получено {data['autoMemoryEnabled']!r}")


if __name__ == "__main__":
    unittest.main()
