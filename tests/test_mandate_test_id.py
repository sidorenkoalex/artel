"""Юнит-тесты мандата на ослабление теста по идентификатору (SPEC
01M5D02N3B428V8BWC3PAM9QCT) — свойства, которых не кроют долгоживущие файлы
задачи `tests/test_01m5d02n3b428v8bwc3pam9qct_*.py`: формы строки маркера,
отказ без решения профиля задачи и с отказом решения, двойные обратные
кавычки в «Что меняется», покрытие находки гейта исходов только точным
равенством.
"""
import unittest
from dataclasses import replace
from unittest import mock

from orchestrator import project_profile
from orchestrator.advance_gates import mandate, outcome_integrity
from tests import mandate_matrix

MARKER = mandate.TEST_ID_MANDATE_MARKER
CID = "web:src/a.test.ts::suite > case, more"

COMPONENT_PROFILE = replace(
    project_profile.Profile(
        command=("node_modules/.bin/vitest",), long_lived_dir="src",
        long_lived_name="<name>.<id>.test.ts", weakening_scope=("src/**",),
        mutation_claim_scope=("src/**",), report="pult-vitest"),
    component="web", project="uchebnyy", from_components=True)


class IdElementsFormTest(unittest.TestCase):

    def test_line_forms(self):
        """Строка не о маркере — `None`; голый маркер — пустой список; маркер, процитированный внутри абзаца, — не строка мандата; остаток — один элемент целиком.

        Ловит мутацию: голый маркер даёт `None` (ошибка Оператора молча
        сходит за «нет мандата»); распознавание по вхождению, а не по
        началу строки — цитата в абзаце становится мандатом; остаток
        делится по запятым — элементов два.
        """
        self.assertIsNone(mandate.id_elements("Ответ Оператора."))
        self.assertEqual([], mandate.id_elements(f"  {MARKER}   "))
        self.assertIsNone(mandate.id_elements(f"см. строку «{MARKER} {CID}»"))
        self.assertEqual([CID], mandate.id_elements(f"\t{MARKER}  {CID}  "))
        self.assertIsNone(mandate.elements(f"{MARKER} {CID}",
                                           mandate.TEST_WEAKENING_MANDATE_MARKER))


class RefusalWithoutBoundsTest(unittest.TestCase):

    def test_no_task_and_refused_decision_refuse(self):
        """Без задачи (решения профиля нет) и при отказе решения профиля строка нового маркера отказана; при профиле компонента в границе — принята.

        Ловит мутацию: без решения профиля проверка границы пропускается
        (fail-open) — идентификатор без задачи принят; отказ решения
        профиля не останавливает проверку — строка принята, хотя гейт
        исходов её не засчитает.
        """
        text = f"{MARKER} {CID}\n"
        self.assertTrue(mandate.refusals(text, None))
        refused = project_profile.Decision("uchebnyy", refusal="сломан")
        with mock.patch.object(project_profile, "for_task",
                               return_value=refused):
            found = mandate.refusals(text, None, conn=object(), task_id="T1")
        self.assertTrue(found and "сломан" in found[0], found)
        good = project_profile.Decision("uchebnyy", profile=COMPONENT_PROFILE)
        with mock.patch.object(project_profile, "for_task", return_value=good):
            self.assertEqual([], mandate.refusals(text, None, conn=object(),
                                                  task_id="T1"))


class DoubleBacktickNotNamedTest(unittest.TestCase):

    def test_double_backticks_do_not_name_id(self):
        """Идентификатор между двойными обратными кавычками в «Что меняется» не назван; между одинарными — назван.

        Ловит мутацию: span ищется любой парой обратных кавычек (в том
        числе ``…``) — ячейка с двойными кавычками засчитана.
        """
        def refusals(cell: str) -> list[str]:
            text = ("## Матрица неослабления\n\n"
                    "| " + " | ".join(mandate_matrix.HEADERS) + " |\n"
                    "|---|---|---|---|---|\n"
                    f"| {cell} | гейт | нет | не покрыто | ок |\n")
            return mandate.matrix_refusals(text, [], test_ids=[CID])

        self.assertTrue(refusals(f"``{CID}``"))
        self.assertEqual([], refusals(f"`{CID}`"))


class ExactCoverageTest(unittest.TestCase):

    def test_id_mandate_covers_only_equal_id(self):
        """Мандат по идентификатору покрывает только равный идентификатор: не вложенное имя, не вариант с `#n`; прежний мандат на путь по-прежнему покрывает.

        Ловит мутацию: к элементам нового маркера применено префиксное
        правило `covering` — `…::case, more::inner` и `…#2` покрыты.
        """
        ids = {CID: "ANSWER-1"}
        self.assertEqual("ANSWER-1", outcome_integrity._covering(CID, {}, ids))
        for other in (f"{CID}::inner", f"{CID}#2"):
            self.assertIsNone(outcome_integrity._covering(other, {}, ids), other)
        self.assertEqual("ANSWER-2", outcome_integrity._covering(
            f"{CID}#2", {"src/a.test.ts": "ANSWER-2"}, ids))


if __name__ == "__main__":
    unittest.main()
