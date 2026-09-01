"""Приёмочный тест T096 — AC-3 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-3: Если ни `tasks/T080/mockup.html`, ни `orchestrator/report.py` не
несут тёмной темы (медиа-запрос `prefers-color-scheme` или аналог) —
`docs/design-system.md` фиксирует это явно как текущую границу
стандарта (светлая тема), а не домысливает тёмную тему.

Предпосылка критерия (условие «если») проверена по факту репозитория на
момент написания теста: ни `tasks/T080/mockup.html`, ни
`orchestrator/report.py` не содержат `prefers-color-scheme` (grep по
обоим файлам — пусто), то есть условие AC-3 сейчас истинно и критерий
обязателен к исполнению. Первый под-тест фиксирует эту предпосылку как
регрессионный барьер: если источники обзаведутся тёмной темой, этот
критерий в текущей формулировке станет неприменим, и красный тест здесь
будет сигналом пересмотреть SPEC, а не багом реализации.

Красен до реализации: `docs/design-system.md` ещё не существует — падает
на отсутствии файла.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DOC_PATH = REPO_ROOT / "docs" / "design-system.md"
MOCKUP_PATH = REPO_ROOT / "tasks" / "T080" / "mockup.html"
REPORT_PATH = REPO_ROOT / "orchestrator" / "report.py"


class Ac3DarkThemeBoundaryTest(unittest.TestCase):

    def test_ac3_precondition_neither_source_carries_dark_theme(self):
        mockup_text = MOCKUP_PATH.read_text(encoding="utf-8")
        report_text = REPORT_PATH.read_text(encoding="utf-8")

        self.assertNotIn("prefers-color-scheme", mockup_text,
                         "предпосылка AC-3 нарушена: mockup.html теперь "
                         "несёт тёмную тему — критерий AC-3 в текущей "
                         "формулировке неприменим, нужен пересмотр SPEC")
        self.assertNotIn("prefers-color-scheme", report_text,
                         "предпосылка AC-3 нарушена: report.py теперь "
                         "несёт тёмную тему — критерий AC-3 в текущей "
                         "формулировке неприменим, нужен пересмотр SPEC")

    def test_ac3_doc_fixes_light_theme_as_current_boundary(self):
        if not DOC_PATH.exists():
            self.fail(f"{DOC_PATH} не существует (AC-3: документ должен "
                     f"явно фиксировать текущую границу — светлая тема)")
        text = DOC_PATH.read_text(encoding="utf-8").lower()

        self.assertIn("тёмн", text,
                     "AC-3 требует явное упоминание тёмной темы (как "
                     "текущего ограничения, а не факта поддержки)")
        self.assertTrue(
            "границ" in text or "не поддержив" in text
            or "не несёт" in text or "не несут" in text,
            "AC-3 требует явную формулировку границы стандарта "
            "(«граница»/«не поддерживает»/«не несёт»), а не просто "
            "упоминание слова «тёмная»")


if __name__ == "__main__":
    unittest.main()
