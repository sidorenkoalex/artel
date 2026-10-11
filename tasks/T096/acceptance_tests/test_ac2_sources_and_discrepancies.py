"""Приёмочный тест T096 — AC-2 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-2: `docs/design-system.md` явно ссылается на `tasks/T080/mockup.html`
и `orchestrator/report.py` как источники и содержит раздел с выявленными
расхождениями между ними — минимум расхождение по цветовому кодированию
состояний борда (в `mockup.html` колонки/карточки несут цвет по
состоянию через `--ok`/`--warn`/`--danger`/`--killed` и классы
`.col.done`/`.col.killed`/`.col.escalated`/`.col.in_dev`/
`.col.merge_gate`/`.col.review`; в `orchestrator/report.py` таких
токенов и классов нет) — с предложенной нормой для каждого выявленного
расхождения.

Красен до реализации: файл `docs/design-system.md` ещё не создан
разработчиком — тест падает на отсутствии файла, не на опечатке.

Литеральные пути (`tasks/T080/mockup.html`, `orchestrator/report.py`) и
литеральные токены (`--ok`, `--warn`, `--danger`, `--killed`) взяты
дословно из формулировки AC-2 — их присутствие в документе проверяется
точным вхождением подстроки, а не эвристикой синонимов, так как сама
формулировка задаёт точные строки.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DOC_PATH = REPO_ROOT / "docs" / "design-system.md"


class Ac2SourcesAndDiscrepanciesTest(unittest.TestCase):

    def setUp(self):
        if not DOC_PATH.exists():
            self.fail(f"{DOC_PATH} не существует (AC-2: документ должен "
                     f"ссылаться на источники и фиксировать расхождения)")
        self.text = DOC_PATH.read_text(encoding="utf-8")
        self.text_lower = self.text.lower()

    def test_ac2_references_both_sources_explicitly(self):
        self.assertIn("tasks/T080/mockup.html", self.text,
                     "AC-2 требует явную ссылку на tasks/T080/mockup.html")
        self.assertIn("orchestrator/report.py", self.text,
                     "AC-2 требует явную ссылку на orchestrator/report.py")

    def test_ac2_has_discrepancies_section(self):
        self.assertIn("расхожден", self.text_lower,
                     "AC-2 требует раздел с выявленными расхождениями "
                     "между источниками")

    def test_ac2_documents_minimum_state_color_coding_discrepancy(self):
        for token in ("--ok", "--warn", "--danger", "--killed"):
            self.assertIn(token, self.text,
                         f"AC-2 требует упоминание токена {token} — "
                         f"минимальное расхождение по цветовому "
                         f"кодированию состояний борда")

    def test_ac2_proposes_a_norm_for_discrepancies(self):
        self.assertTrue(
            "норм" in self.text_lower or "предлож" in self.text_lower,
            "AC-2 требует предложенную норму для каждого выявленного "
            "расхождения — в документе нет ни «норм*», ни «предлож*»")


if __name__ == "__main__":
    unittest.main()
