"""AC-7 (tasks/T080/SPEC.md): макет содержит кнопку pause.

Красен до реализации: HTML-файлов ещё нет (см. AC-1) — кнопку искать
негде. Как только появится макет, тест ищет кнопкоподобный элемент
(`<button>`, `<a href>`, `<input>`, либо `role="button"`/класс с "btn"
или "button") с текстом/подписью «pause»/«пауза»/«приостанов…» — то же
действие, что `artel.py pause` (`orchestrator/pause.py`). SPEC.md
«Не входит» явно освобождает макет от рабочей логики кнопки — тест
проверяет только её визуальное присутствие, не поведение при клике.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402

PAUSE_RE = re.compile(r"\bpause\b|пауза|приостанов", re.I)


class PauseButtonPresentTest(unittest.TestCase):

    def test_ac7_pause_button_is_present_in_some_html_file(self):
        files = h.html_files()
        if not files:
            self.fail(
                "в tasks/T080/ нет HTML-файлов макета — проверять AC-7 "
                "не на чем (см. AC-1)")
        found = False
        for path in files:
            root = h.parse(path.read_text(encoding="utf-8"))
            for node in h.walk(root):
                if h.looks_like_button(node, PAUSE_RE):
                    found = True
                    break
            if found:
                break
        self.assertTrue(
            found,
            "не найдена кнопка pause: ни в одном HTML-файле нет "
            "кнопкоподобного элемента (<button>/<a href>/<input>/"
            "role=button/класс btn|button) с подписью «pause»/«пауза»/"
            "«приостановить» (AC-7)")


if __name__ == "__main__":
    unittest.main()
