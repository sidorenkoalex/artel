"""Юнит-тесты области мандата ослабления и ссылки матрицы по профилю
проекта задачи (SPEC 01M55VDVVDVWW2MTJ01F88N5FM) — свойства, которых не
кроет долгоживущий файл задачи
`tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`: ответ
без строки мандата ослабления решения профиля не читает, ссылка матрицы
внешнего проекта — путь `*.py` в области профиля и только он.
"""
import unittest
from unittest import mock

from orchestrator import project_profile
from orchestrator.advance_gates import mandate
from tests import mandate_matrix

HEADER_ROW = "| " + " | ".join(mandate_matrix.HEADERS) + " |"
SEPARATOR = "|---|---|---|---|---|"
EXT = "uchebnyy"

EXT_PROFILE = project_profile.Profile(
    command=("python3", "-m", "pytest"), long_lived_dir="backend/tests",
    long_lived_name="test_<id>_<name>.py",
    weakening_scope=("backend/tests/**/*.py",),
    mutation_claim_scope=("backend/tests/**/test_*.py",))


def matrix(covered_by: str) -> str:
    return ("## Матрица неослабления\n\n"
            f"{HEADER_ROW}\n{SEPARATOR}\n"
            f"| `src/a.py` | гейт | да | {covered_by} | ок |\n")


class ProfileReadOnlyForWeakeningTest(unittest.TestCase):

    def test_zones_only_answer_does_not_consult_profile(self):
        """Ответ только с мандатом зон решения профиля задачи не читает — сбой `targets.yaml` ему не отказывает.

        Ловит мутацию: решение профиля считается на каждом вызове
        `refusals` с задачей, а не только при строке «Ослабление тестов
        разрешено:» — `for_task` вызван, и отказ профиля (сломанный
        `targets.yaml`) роняет ответ, мандата ослабления не несущий.
        """
        with mock.patch.object(project_profile, "for_task",
                               side_effect=AssertionError("профиль прочитан")):
            found = mandate.refusals("Расширение зон разрешено: src/a.py\n",
                                     None, conn=object(), task_id="T1")
        self.assertEqual([], found)


class MatrixReferenceByProfileTest(unittest.TestCase):

    def refusals(self, covered_by: str) -> list[str]:
        decision = project_profile.Decision(EXT, profile=EXT_PROFILE)
        with mock.patch.object(project_profile, "for_task",
                               return_value=decision):
            return mandate.matrix_refusals(matrix(covered_by), ["src/a.py"],
                                           conn=object(), task_id="T1")

    def test_reference_inside_text_and_with_line_counts(self):
        """Путь области профиля в окружении текста и с `:строка` — покрытие; путь `.py` вне области рядом — не мешает.

        Ловит мутацию: ссылкой считается только ячейка целиком либо только
        первый путь `.py` ячейки — «см. src/b.py и backend/tests/x/test_y.py:12»
        получает отказ «не покрыто».
        """
        self.assertEqual([], self.refusals(
            "см. `src/b.py` и **backend/tests/x/test_y.py:12**"))

    def test_any_py_path_outside_scope_is_not_coverage(self):
        """Путь `.py` вне области профиля (код, хвост чужого пути) покрытием не считается.

        Ловит мутацию: ссылкой стала любая `*.py` либо подстрока пути
        сверяется с маской — `src/backend/tests/test_y.py` (хвост под
        маской) или `src/b.py` засчитаны покрытием.
        """
        for cell in ("src/b.py", "src/backend/tests/test_y.py"):
            with self.subTest(cell=cell):
                found = self.refusals(cell)
                self.assertEqual(1, len(found), found)
                self.assertIn("не покрыто", found[0])


if __name__ == "__main__":
    unittest.main()
