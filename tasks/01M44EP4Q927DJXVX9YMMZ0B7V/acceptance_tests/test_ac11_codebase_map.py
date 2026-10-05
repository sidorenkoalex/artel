"""AC-11: карта кода называет модуль-помощник и его выкладку.

`docs/codebase-map.md` содержит строку о модуле
`orchestrator/plank_helper.py` и о выкладке помощника рядом с планкой.
Карта читается из рабочей копии кода задачи — той, где исполняется
планка.

Группа: разовый
Красен до реализации: модуля `orchestrator/plank_helper.py` нет — карта о нём молчит.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

MODULE = "orchestrator/plank_helper.py"
LAYOUT_WORDS = ("_pult.py", "выклад", "вылож")


class CodebaseMapTest(unittest.TestCase):

    def test_ac11_map_has_helper_module_and_its_layout(self):
        """В карте есть раздел модуля-помощника, говорящий о выкладке.

        Сценарий: в `docs/codebase-map.md` есть строка, называющая
        `orchestrator/plank_helper.py`, а в разделе этого модуля — строка о
        выкладке помощника рядом с планкой (`_pult.py` или «выкладка»).

        Ловит мутацию: модуль добавлен, а карта не регенерирована
        (`scripts/codebase_map.py` не прогнан) — строки о модуле нет; либо
        докстринг модуля не говорит о выкладке — в его разделе карты нет
        слова о ней."""
        text = (config.ROOT / "docs" / "codebase-map.md").read_text(
            encoding="utf-8")

        self.assertTrue(MODULE in text, f"в карте нет строки о {MODULE}")
        match = re.search(rf"^## {re.escape(MODULE)}\s*$(.*?)(?=^## |\Z)",
                          text, re.M | re.S)
        candidates = (match.group(1).splitlines() if match else
                      [line for line in text.splitlines() if MODULE in line])
        lines = [line for line in candidates
                 if any(w in line.lower() for w in LAYOUT_WORDS)]
        self.assertTrue(lines, f"в карте о {MODULE} нет строки о выкладке "
                               f"помощника рядом с планкой")


if __name__ == "__main__":
    unittest.main()
