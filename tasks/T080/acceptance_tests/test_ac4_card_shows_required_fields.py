"""AC-4 (tasks/T080/SPEC.md): макет содержит карточку задачи с
отображением полей: статус, бюджет/расход, итерации ревью, lease.

Красен до реализации: HTML-файлов ещё нет (см. AC-1). Как только
появится макет, тест ищет наименьший по тексту узел документа, который
одновременно содержит (a) идентификатор задачи вида `T\\d+` (реальные
карточки завязаны на конкретную задачу — SPEC AC-8) и (b) метки всех
четырёх полей — статус, бюджет/расход, итерации ревью, lease
(`orchestrator/catalog.py:200-203` — `state`, `spent_usd`/`budget_usd`,
`review_iters`, и `orchestrator/lease.py`/`orchestrator/store.py:56-59`
для lease). Наименьший подходящий узел — эвристика «сфокусированная
карточка», а не весь документ целиком.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402

STATUS_RE = re.compile(r"статус|состояни|\bstatus\b|\bstate\b", re.I)
BUDGET_RE = re.compile(
    r"бюджет|budget|расход|spent|\$\s*[\d.]+\s*/\s*\$?\s*[\d.]+", re.I)
REVIEW_ITERS_RE = re.compile(r"итерац|review[\s_-]?iter", re.I)
LEASE_RE = re.compile(r"\blease\b|аренда", re.I)


def _card_predicate(text):
    return bool(
        h.TASK_ID_RE.search(text)
        and STATUS_RE.search(text)
        and BUDGET_RE.search(text)
        and REVIEW_ITERS_RE.search(text)
        and LEASE_RE.search(text)
    )


class CardShowsRequiredFieldsTest(unittest.TestCase):

    def test_ac4_a_task_card_shows_status_budget_review_iters_and_lease(self):
        files = h.html_files()
        if not files:
            self.fail(
                "в tasks/T080/ нет HTML-файлов макета — проверять AC-4 "
                "не на чем (см. AC-1)")
        best = None
        for path in files:
            root = h.parse(path.read_text(encoding="utf-8"))
            node = h.smallest_matching(root, _card_predicate)
            if node is not None:
                best = node
                break
        self.assertIsNotNone(
            best,
            "не найдена карточка задачи, показывающая ВСЕ четыре поля "
            "разом рядом с идентификатором задачи (T<номер>): статус "
            "(«статус»/«состояние»/status), бюджет/расход "
            "(«бюджет»/«расход»/$X/$Y), итерации ревью («итерации»/"
            "review iterations) и lease (AC-4)")


if __name__ == "__main__":
    unittest.main()
