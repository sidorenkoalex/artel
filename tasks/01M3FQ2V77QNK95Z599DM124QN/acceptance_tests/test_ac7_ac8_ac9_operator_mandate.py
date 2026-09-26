"""AC-7, AC-8 и AC-9 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): мандат
Оператора строкой `Ослабление тестов разрешено: …` в `ANSWER-n.md` снимает
отказ ровно по перечисленным элементам, покрытые находки уходят в журнал
как разрешённые, а `ANSWER-n.md`, чей последний коммит — автокоммит
артефактов шага роли, мандатом не считается.

Все три сценария стоят на одном и том же диффе из трёх находок:
удалённый `tests/test_doomed.py`, исчезнувший `AlphaTest::test_alpha_two`
в `tests/test_alpha.py` и исчезнувший `test_movable_three` в
`tests/test_movable.py` — различается только мандат.

Красен до реализации: обёртки `_test_integrity_gate_refuses` в
`orchestrator/fsm_advance.py` (требование 6) ещё нет — вызов падает
`AttributeError` на каждом сценарии.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (ALPHA_WITHOUT_SECOND_METHOD,  # noqa: E402
                      MOVABLE_WITHOUT_THIRD_METHOD, REFUSAL_ACTION,
                      TestIntegritySandbox)

# Элемент-путь покрывает ВСЕ находки файла; элемент с `::` — только
# названный метод (требование 4).
COVERS_TWO = ("tests/test_doomed.py, "
              "tests/test_alpha.py::AlphaTest::test_alpha_two")
COVERS_ALL = (COVERS_TWO
              + ", tests/test_movable.py::MovableTest::test_movable_three")


class _ThreeFindingsSandbox(TestIntegritySandbox):
    """Дифф из трёх находок в трёх разных файлах — общая завязка AC-7,
    AC-8 и AC-9."""

    def setUp(self):
        super().setUp()
        self.remove("tests/test_doomed.py")
        self.write("tests/test_alpha.py", ALPHA_WITHOUT_SECOND_METHOD)
        self.write("tests/test_movable.py", MOVABLE_WITHOUT_THIRD_METHOD)
        self.commit()


class MandateCoverageTest(_ThreeFindingsSandbox):

    def test_ac7_mandate_lifts_refusal_only_for_listed_elements(self):
        """Мандат называет путь `tests/test_doomed.py` и метод
        `tests/test_alpha.py::AlphaTest::test_alpha_two`: гейт всё равно
        отказывает — из-за третьей, НЕ названной находки, — и detail
        называет только её.

        Ловит мутацию: элемент-путь и элемент с `::` сравниваются одним и
        тем же правилом (например, оба как префикс пути) — тогда
        `tests/test_alpha.py::AlphaTest::test_alpha_two` покрыл бы ЛЮБУЮ
        находку файла `tests/test_alpha.py`, а разрешение на один метод
        молча стало бы разрешением на весь файл.
        """
        self.write_answer(1, COVERS_TWO)

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"непокрытая находка обязана отказать (AC-7); "
                        f"журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("test_movable_three", outcome.detail)
        self.assertNotIn(
            "test_alpha_two", outcome.detail,
            f"покрытая мандатом находка в текст отказа не попадает "
            f"(AC-7/AC-8); detail: {outcome.detail}")
        self.assertNotIn(
            "tests/test_doomed.py", outcome.detail,
            f"покрытый мандатом путь в текст отказа не попадает "
            f"(AC-7/AC-8); detail: {outcome.detail}")

    def test_ac7_mandate_covering_every_finding_passes_the_gate(self):
        """Мандат называет все три элемента — гейт пропускает переход.

        Ловит мутацию: мандат читается, но применяется только к
        собственному классу находок (скажем, к удалённым файлам) —
        исчезнувший метод, названный элементом с `::`, продолжает
        отказывать, и разрешение Оператора не срабатывает вовсе.
        """
        self.write_answer(1, COVERS_ALL)

        outcome = self.run_gate()

        self.assertFalse(
            outcome.refused,
            f"мандат покрывает все находки — отказа быть не должно "
            f"(AC-7); журнал: {outcome.journal}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)


class MandateJournalTest(_ThreeFindingsSandbox):

    def test_ac8_covered_findings_are_journaled_as_allowed_by_answer(self):
        """Покрытые мандатом находки названы в журнале шага строкой,
        привязывающей их к ANSWER-1, — и при этом их нет в тексте отказа.

        Ловит мутацию: покрытые находки просто отфильтровываются из
        списка перед сборкой detail, без единой записи в журнал —
        Оператор на приёмке видит отказ об одной находке и не узнаёт, что
        две другие прошли по его мандату (ровно та ручная сверка, которую
        задача из гейта мержа убирает).
        """
        self.write_answer(1, COVERS_TWO)

        outcome = self.run_gate()

        self.assertIn("ANSWER-1", outcome.journal,
                      f"журнал обязан назвать источник разрешения (AC-8); "
                      f"журнал: {outcome.journal}")
        self.assertIn("разрешено", outcome.journal,
                      f"журнал обязан назвать находки разрешёнными (AC-8); "
                      f"журнал: {outcome.journal}")
        self.assertIn("tests/test_doomed.py", outcome.journal)
        self.assertIn("test_alpha_two", outcome.journal)


class RoleAutocommitIsNotMandateTest(_ThreeFindingsSandbox):

    def test_ac9_answer_committed_by_role_autocommit_is_not_a_mandate(self):
        """Тот же `ANSWER-1.md` с тем же перечнем, но его последний
        коммит — автокоммит артефактов шага роли (`developer`), а не
        команда `answer`: мандатом он не считается, отказ остаётся и
        называет все три находки.

        Ловит мутацию: `_answer_commit_is_role_step_autocommit` не
        вызывается (мандат читается по одному тексту файла) — developer
        кладёт себе `ANSWER-n.md` в собственный `tasks/<id>/` прямо в
        шаге `in_dev`, автокоммит переносит файл в ветку без разбора, и
        роль сама себе выписывает разрешение ослаблять тесты.
        """
        self.write_answer(1, COVERS_ALL, autocommit_role="developer")

        outcome = self.run_gate()

        self.assertTrue(
            outcome.refused,
            f"автокоммит роли мандатом не считается (AC-9); журнал: "
            f"{outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("tests/test_doomed.py", outcome.detail)
        self.assertIn("test_alpha_two", outcome.detail)
        self.assertIn("test_movable_three", outcome.detail)


if __name__ == "__main__":
    unittest.main()
