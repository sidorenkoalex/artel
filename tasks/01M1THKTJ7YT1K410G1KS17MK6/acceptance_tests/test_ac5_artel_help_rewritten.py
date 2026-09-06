"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-5 (абзац о бюджете из
SPEC в справке `orchestrator/artel.py` переписан под новую семантику: обе
стороны, потолок ролей, не только понижение от дефолта).

Читает исходник `orchestrator/artel.py` как текст (докстринг модуля,
абзац об `budget_usd`) — тот же приём, что `test_ac1_...` этой же планки
применяет к комментарию `ROLE_BUDGET_CAP`.

Красен до реализации: сегодняшний абзац (`orchestrator/artel.py`,
строки 31-37) буквально говорит «Понижать потолок так можно, поднимать —
нет: значение выше DEFAULT_BUDGET_USD отвергается» — ни слова про
`ROLE_BUDGET_CAP`/потолок ролей, а старая фраза о запрете поднятия ещё
на месте.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

ARTEL_PATH = REPO_ROOT / "orchestrator" / "artel.py"


def _budget_paragraph() -> str:
    """Абзац докстринга модуля, посвящённый потолку из SPEC — тот, что
    сегодня начинается с «Потолок по умолчанию один на все задачи...» и
    упоминает `budget_usd`. Переносы строк внутри абзаца схлопнуты в
    пробелы — исходный текст оборачивается по ширине строки, и фраза
    может делиться переносом посередине (как сегодняшнее «...можно,\n
    поднимать...»); тест ищет по смыслу, не по конкретной раскладке
    переносов."""
    text = ARTEL_PATH.read_text(encoding="utf-8")
    match = re.search(r"^Потолок.*?(?=\n\n)", text, re.M | re.S)
    assert match, "абзац о потолке из SPEC не найден в orchestrator/artel.py"
    return re.sub(r"\s+", " ", match.group(0)).strip()


class ArtelHelpRewrittenTest(unittest.TestCase):

    def test_ac5_paragraph_mentions_role_cap(self):
        paragraph = _budget_paragraph()

        self.assertRegex(
            paragraph, r"ROLE_BUDGET_CAP|потолок[а-я]* ролей",
            f"AC-5: абзац обязан называть потолок ролей; сейчас: "
            f"{paragraph!r}")

    def test_ac5_paragraph_no_longer_says_only_lowering_is_allowed(self):
        paragraph = _budget_paragraph()

        self.assertNotRegex(
            paragraph, r"Понижать потолок так можно, поднимать\s*—?\s*нет",
            f"AC-5: старая формулировка «поднимать нельзя» обязана быть "
            f"переписана; сейчас: {paragraph!r}")

    def test_ac5_paragraph_describes_both_directions(self):
        paragraph = _budget_paragraph()

        self.assertRegex(
            paragraph, r"обе стороны|в обе стороны|и выше.{0,20}и ниже|"
                      r"и понижа.{0,40}и повыша",
            f"AC-5: абзац обязан описывать применение в обе стороны; "
            f"сейчас: {paragraph!r}")


if __name__ == "__main__":
    unittest.main()
