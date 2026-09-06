"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-7 (`docs/invariants.md`,
инвариант 10, переформулирован (SPEC-часть): «поднять потолок выше
`ROLE_BUDGET_CAP` может только Оператор командой `budget`; в пределах
потолка ролей потолок задаёт SPEC на гейте SPEC»).

Читает `docs/invariants.md` как текст и ищет строку таблицы реестра
инвариантов с номером 10 — та же таблица, что `tests/test_invariants.py`
(докстринг модуля) держит эталоном по номерам строк.

Красен до реализации: сегодняшняя строка 10 — «Поднять потолок может
только Оператор командой `budget`» — не называет ни `ROLE_BUDGET_CAP`,
ни «потолок ролей», ни того, что в его пределах потолок задаёт SPEC.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

INVARIANTS_PATH = REPO_ROOT / "docs" / "invariants.md"


def _row_10() -> str:
    text = INVARIANTS_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if re.match(r"^\|\s*10\s*\|", line):
            return line
    raise AssertionError("строка реестра инвариантов с номером 10 не "
                         "найдена в docs/invariants.md")


class Invariant10ReformulatedTest(unittest.TestCase):

    def test_ac7_names_role_budget_cap_as_the_upper_limit(self):
        row = _row_10()

        self.assertRegex(
            row, r"выше\s*`?ROLE_BUDGET_CAP`?\s*может только Оператор "
                r"командой\s*`?budget`?",
            f"AC-7: строка 10 обязана говорить «поднять потолок выше "
            f"ROLE_BUDGET_CAP может только Оператор командой budget»; "
            f"сейчас: {row!r}")

    def test_ac7_names_spec_as_the_ceiling_within_the_role_cap(self):
        row = _row_10()

        self.assertRegex(
            row, r"в пределах потолка ролей потолок задаёт SPEC на "
                r"гейте SPEC",
            f"AC-7: строка 10 обязана говорить, что в пределах потолка "
            f"ролей потолок задаёт SPEC на гейте SPEC; сейчас: {row!r}")


if __name__ == "__main__":
    unittest.main()
