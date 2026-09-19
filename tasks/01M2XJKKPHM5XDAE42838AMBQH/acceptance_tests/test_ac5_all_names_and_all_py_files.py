"""AC-5 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): каждое из имён
`PLAN.md`, `SPEC.md`, `REVIEW.md`, `TZ.md`, `QUESTIONS.md`,
`TEST_REPORT.md`, `ANSWER-` в выражении доступа к файловой системе даёт
ошибку; область проверки — ВСЕ `*.py` каталога `acceptance_tests/`, не
только `test_*.py`.

Красен до реализации: гейта «переход отклонён: планка читает артефакты с
диска» на выходе `tests_writing` ещё нет — вложенная задача уходит в
`in_dev` на любом из семи имён и на нарушающем `_helper.py` тоже.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

HELPER_OFFENDING = 'PLAN_PATH = Path(__file__).parents[1] / "PLAN.md"'

HELPER_SOURCE = f'''"""Общий модуль подставной планки: читает артефакт с
диска — файл не `test_*.py`, но такой же `*.py` каталога планки."""
from pathlib import Path

{HELPER_OFFENDING}
PLAN_TEXT = PLAN_PATH.read_text(encoding="utf-8")
'''


class EveryArtifactNameRefusesTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac5_each_artifact_name_in_a_filesystem_expression_refuses(self):
        """Семь имён артефактов из AC-5 разыгрываются по одному в одном и
        том же выражении доступа к файловой системе — каждое отклоняет
        выход из `tests_writing`, называя файл планки и номер строки.

        Ловит мутацию: список имён неполон — реализован по образцу
        инцидентов («PLAN.md» и «SPEC.md», на которых класс срабатывал
        12-13.09), а `TZ.md`/`QUESTIONS.md`/`TEST_REPORT.md`/`ANSWER-`
        забыты — цикл покраснеет на первом непокрытом имени: вложенная
        задача уйдёт в `in_dev` без записи отказа.
        """
        self.enter_tests_writing()
        for name in _sandbox.ARTIFACT_NAMES:
            with self.subTest(artifact=name):
                offending = (f'path = (Path(__file__).resolve().parents[1] '
                             f'/ "{name}")')
                source = _sandbox.plank_source([offending])
                self.write_plank(source)

                out = self.advance()

                self.assert_disk_read_refused(out, source, offending)


class NonTestModuleIsInScopeTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac5_disk_read_in_a_non_test_module_refuses_too(self):
        """Тестовые файлы планки чисты, а артефакт с диска читает
        соседний `_helper.py` — выход из `tests_writing` всё равно
        отклоняется, и в тексте отказа назван именно `_helper.py` с
        номером его строки.

        Ловит мутацию: область проверки сужена до `test_*.py` (копипаста
        `rglob("test_*.py")` из `scan_redness_markers`/
        `scan_indented_ac_markers`, где такое сужение осознанно) —
        нарушение в общем модуле планки остаётся незамеченным, вложенная
        задача уходит в `in_dev`.
        """
        self.enter_tests_writing()
        self.write_plank(_sandbox.plank_source(_sandbox.CLEAN_BODY))
        self.add_plank_file(HELPER_SOURCE, "_helper.py")

        out = self.advance()

        self.assert_disk_read_refused(out, HELPER_SOURCE, HELPER_OFFENDING,
                                      file_name="_helper.py")


if __name__ == "__main__":
    unittest.main()
