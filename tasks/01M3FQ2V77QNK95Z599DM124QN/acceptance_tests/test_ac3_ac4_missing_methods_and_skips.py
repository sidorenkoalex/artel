"""AC-3 и AC-4 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): исчезнувший из
head тестовый метод изменённого файла и ПОЯВИВШИЙСЯ в head пропуск
(декоратор на методе или на классе, вызов `self.skipTest(`) отказывают
переходу; тот же пропуск, уже стоявший в base, отказа не даёт.

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
                      ALPHA_WITH_SKIP_DECORATOR,
                      ALREADY_SKIPPED_PLUS_NEW_METHOD,
                      MOVABLE_WITH_XFAIL_ON_CLASS,
                      NESTED_WITH_SKIPTEST_CALL, REFUSAL_ACTION,
                      TestIntegritySandbox)


class VanishedTestMethodTest(TestIntegritySandbox):

    def test_ac3_method_gone_from_changed_file_refuses_with_class_name(self):
        """Файл `tests/test_alpha.py` остался, но метод `test_alpha_two`
        класса `AlphaTest` из него исчез: гейт отказывает, detail несёт
        путь файла, имя метода И имя класса, внутри которого он жил.

        Ловит мутацию: ast-сравнение base против head сделано по
        ДОБАВЛЕННЫМ именам (как у соседнего гейта заявки мутации, который
        ищет новые и изменённые методы) вместо ИСЧЕЗНУВШИХ — удаление
        метода из живого файла проходит гейт молча; либо имя класса
        теряется по дороге (собраны голые имена методов, как в
        `guard._collect_test_functions`), и Оператор не знает, какой из
        одноимённых методов двух классов пропал.
        """
        self.write("tests/test_alpha.py", ALPHA_WITHOUT_SECOND_METHOD)
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("tests/test_alpha.py", outcome.detail)
        self.assertIn("test_alpha_two", outcome.detail)
        self.assertIn("AlphaTest", outcome.detail,
                      f"метод внутри класса называется вместе с классом "
                      f"(AC-3); detail: {outcome.detail}")


class NewSkipMarkerTest(TestIntegritySandbox):

    def test_ac4_new_unittest_skip_decorator_on_method_refuses(self):
        """На `test_alpha_one` в head появился `@unittest.skip` — гейт
        отказывает и называет файл, имя метода и сам маркер пропуска.

        Ловит мутацию: распознаются только исчезнувшие методы (класс «в»),
        а класс «г» не реализован или сузился до `pytest.mark.skip` —
        `@unittest.skip`, самый частый способ «временно» погасить тест в
        этом репозитории, проходит рубеж без единого слова.
        """
        self.write("tests/test_alpha.py", ALPHA_WITH_SKIP_DECORATOR)
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("tests/test_alpha.py", outcome.detail)
        self.assertIn("test_alpha_one", outcome.detail)
        self.assertIn("skip", outcome.detail,
                      f"detail обязан назвать сам маркер пропуска (AC-4); "
                      f"detail: {outcome.detail}")

    def test_ac4_new_xfail_marker_on_class_refuses(self):
        """Маркер поставлен не на метод, а на КЛАСС
        (`@pytest.mark.xfail` над `MovableTest`) — гейт отказывает и
        называет файл, имя класса и маркер.

        Ловит мутацию: декораторы собираются только с узлов
        `FunctionDef` (обход `node.body` класса, как в
        `guard._collect_test_functions`), а сам `ClassDef` не
        осматривается — один декоратор над классом гасит весь файл
        тестов и проходит рубеж целиком.
        """
        self.write("tests/test_movable.py", MOVABLE_WITH_XFAIL_ON_CLASS)
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("tests/test_movable.py", outcome.detail)
        self.assertIn("MovableTest", outcome.detail)
        self.assertIn("xfail", outcome.detail,
                      f"detail обязан назвать сам маркер пропуска (AC-4); "
                      f"detail: {outcome.detail}")

    def test_ac4_new_skiptest_call_in_body_refuses(self):
        """Декоратора нет вовсе — пропуск сделан ВЫЗОВОМ
        `self.skipTest(` в теле `test_nested_one`: гейт отказывает и
        называет файл, метод и маркер.

        Ловит мутацию: осматриваются только `node.decorator_list`, а тело
        метода — нет; вызов `self.skipTest(`/`pytest.skip(` остаётся
        законным способом выключить тест мимо рубежа, хотя требование 1
        (класс «г») называет его наравне с декораторами.
        """
        self.write("tests/deep/test_nested.py", NESTED_WITH_SKIPTEST_CALL)
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("tests/deep/test_nested.py", outcome.detail)
        self.assertIn("test_nested_one", outcome.detail)
        self.assertIn("skipTest", outcome.detail,
                      f"detail обязан назвать сам маркер пропуска (AC-4); "
                      f"detail: {outcome.detail}")

    def test_ac4_skip_already_present_in_base_gives_no_refusal(self):
        """Файл `tests/test_already_skipped.py` попал в дифф (на ветке
        добавлен новый метод), но `@unittest.skip` на
        `test_skipped_from_base` стоял ещё в base — это не ПОЯВИВШИЙСЯ
        пропуск, и отказа быть не должно.

        Ловит мутацию: класс «г» собирается по одному только head
        («в файле есть skip») без сверки с base на том же имени — каждая
        правка любого файла, где уже стоял давний законный пропуск,
        начинает отказывать переходу на ровном месте, и рубеж придётся
        обходить мандатом за чужое решение.
        """
        self.write("tests/test_already_skipped.py",
                   ALREADY_SKIPPED_PLUS_NEW_METHOD)
        self.commit()

        outcome = self.run_gate()

        self.assertFalse(
            outcome.refused,
            f"пропуск из base отказа не даёт (AC-4, вторая фраза); "
            f"журнал: {outcome.journal}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)


if __name__ == "__main__":
    unittest.main()
