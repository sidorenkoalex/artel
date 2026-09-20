"""AC-6: защищённый путь в разделе «Зоны:» ТЗ — отказ `new`.

Красен до реализации: `catalog.cmd_new` сегодня вовсе не читает раздел «Зоны:» на предмет `config.PROTECTED_PATHS` (`_tz_calibration_inputs` только считает число путей через `budget.count_zone_paths`), поэтому отказа с текстом «защищённый путь только приложением» не будет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from _new_sandbox import NewWithTzSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


class ProtectedPathInZonesTest(NewWithTzSandbox):

    def test_ac6_protected_path_in_zones_section_refuses_new(self):
        """ТЗ называет в «Зоны:» путь, попадающий под
        `config.PROTECTED_PATHS` (каталог `templates/` и файл под ним —
        как `templates/SPEC.md` из формулировки критерия), — `new --tz`
        отказывает с текстом «защищённый путь только приложением».

        Защищённый каталог берётся из `config.PROTECTED_PATHS`
        динамически: правка списка Оператором не должна ронять планку.

        Ловит мутацию: попадание в `PROTECTED_PATHS` сверяется
        буквальным совпадением строк — `templates/SPEC.md` не равен
        записи `templates/`, отказ бы не сработал вовсе.
        """
        self.assertIn(_util.PROTECTED_DIR, config.PROTECTED_PATHS)

        text = self.run_new(_util.tz_text(
            requires="Поправить формат разделов.",
            zones=f"{_util.ZONE_PATH}, {_util.PROTECTED_FILE}"))

        self.assertIn(_util.PROTECTED_REFUSAL_TEXT, text,
                      f"нет отказа по защищённому пути:\n{text}")
        self.assert_no_task_created(text)


if __name__ == "__main__":
    unittest.main()
