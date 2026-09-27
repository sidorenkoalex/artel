"""AC-10 — 01M3GKJ84XM5QPC6TK5EE307Q9: хотя бы один не-документ в наборе
конфликтных файлов оставляет прежнюю эскалацию.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Конфликт, набор которого включает хотя бы один не-документ
(например `.py`), эскалирует как прежде — даже если остальные файлы
набора документные и аддитивные.

Определение документа — SPEC требование 4: путь внутри `docs/**` либо
путь, оканчивающийся на `.md`. Второй метод проверяет именно вторую
половину определения (`.md` вне `docs/`), чтобы «документ» не выродился
в «всё, что под docs/».

Зелёный с рождения: сегодня любой набор, отличный от одиночной
`docs/codebase-map.md`, эскалирует — файл фиксирует поведение, которое
задача обязана сохранить, и краснеет, если авторазрешение начнёт
хватать наборы с кодом.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

CODE_FILE = "orchestrator/fixture_module.py"
ROOT_DOC = "KOPILKA.md"


class NonDocInConflictSetEscalatesTest(_sandbox.AdditivePullSandbox):

    def test_ac10_python_file_in_the_set_keeps_the_old_escalation(self):
        """Набор — аддитивный документ И аддитивный `.py`: обе стороны
        только дописали строки, но код в наборе есть, и подтяжка
        эскалирует прежним путём.

        Ловит мутацию: проверка «все файлы — документы» заменена на
        «хотя бы один файл — документ» (или применяется к каждому файлу
        по отдельности, разрешая документы и оставляя код конфликтным) —
        подтяжка слила бы документ и попыталась завершить merge с
        неразрешённым `.py`.
        """
        self.seed_additive_conflict(_sandbox.DOC_A, CODE_FILE)

        outcome = self.evaluate()

        self.assert_escalated_as_before(outcome, [CODE_FILE, _sandbox.DOC_A])

    def test_ac10_markdown_outside_docs_is_still_a_document(self):
        """Набор — `.md` в корне и документ под `docs/`, оба аддитивные:
        не-документов в наборе нет, и эскалации быть не должно.

        Ловит мутацию: определение документа сведено к префиксу `docs/`
        (или взят чужой `ci_push_class.is_doc_path`, который считает
        `.md` только в корне, зато документом объявляет `tasks/**`) —
        корневой `.md` попал бы в не-документы, и подтяжка эскалировала
        бы вместо слияния.
        """
        self.seed_additive_conflict(_sandbox.DOC_A, ROOT_DOC)

        self.evaluate()

        self.assertEqual(
            "in_dev", self.state(),
            "`.md` в корне — документ по определению SPEC требования 4, "
            "набор из двух документов обязан слиться без эскалации")
        self.assert_all_lines_present(ROOT_DOC)
        self.assert_all_lines_present(_sandbox.DOC_A)


if __name__ == "__main__":
    unittest.main()
