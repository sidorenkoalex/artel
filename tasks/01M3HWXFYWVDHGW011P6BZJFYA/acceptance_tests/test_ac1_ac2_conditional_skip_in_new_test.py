"""AC-1 и AC-2 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): новый тестовый
метод с условным пропуском и непустой строковой причиной находки не даёт
и переходу `in_dev -> verifying` не отказывает, а сами такие пропуски не
теряются — они уходят в журнал задачи записью «новый тест с условным
пропуском».

Красен до реализации: узел сравнения сегодня даёт находку на ЛЮБОЙ
появившийся в head маркер пропуска — для нового файла база пуста, и все
три формы AC-1 отказывают переходу; журнальной записи AC-2 нет вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (CONDITIONAL_SKIP_ACTION, CONDITIONAL_SKIPS,  # noqa: E402
                      NEW_CONDITIONAL, NEW_CONDITIONAL_CLASS,
                      NEW_CONDITIONAL_PATH, REFUSAL_ACTION, GateSandbox,
                      journal_item)


class ConditionalSkipInNewTestTest(GateSandbox):

    def setUp(self):
        super().setUp()
        # Единственная правка ветки — новый файл с тремя формами
        # условного пропуска, названными AC-1 поимённо.
        self.apply(NEW_CONDITIONAL_PATH, NEW_CONDITIONAL)

    def test_ac1_conditional_skip_with_reason_in_new_test_does_not_refuse(self):
        """Ветка добавляет НОВЫЙ файл тестов, в котором три метода
        выключены условно и с названной причиной (`self.skipTest` внутри
        `if`, `@skipUnless(<условие>, "<причина>")`,
        `@pytest.mark.skipif(<условие>, reason="<причина>")`): узел находок
        по ним ничего не возвращает, и переход `in_dev -> verifying` по
        этой единственной правке не отказывает.

        Ловит мутацию: послабление реализовано только для одной из трёх
        названных форм — например разбирается лишь декоратор, а вызов
        `self.skipTest` внутри `if` по-прежнему считается находкой (или
        наоборот, читается только `reason=`, а второй позиционный аргумент
        `@skipUnless` — нет): переход продолжает отказывать, и честный
        неприменимый тест снова гонят за мандатом Оператора, то есть цена
        прецедента 27.09 остаётся неоплаченной.
        """
        outcome = self.run_gate()

        self.assertFalse(
            outcome.refused,
            f"условный пропуск с названной причиной на НОВОМ методе "
            f"находкой не считается (AC-1); журнал: {outcome.journal}; "
            f"stdout: {outcome.printed}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        for method, _reason in CONDITIONAL_SKIPS:
            self.assertNotIn(
                method, outcome.detail,
                f"метод {method} не имеет права попасть в отказ (AC-1); "
                f"detail: {outcome.detail}")

    def test_ac2_conditional_skips_are_listed_in_the_task_journal(self):
        """В том же случае журнал задачи несёт запись действия «новый тест
        с условным пропуском», в detail которой для КАЖДОГО пропуска
        стоит «<файл>::<квалифицированное имя метода> — <причина>».

        Ловит мутацию: послабление сделано молча — находка просто не
        заводится, а журнальная запись не пишется (либо пишется, но
        detail собран из голого имени метода без класса и файла, как в
        `guard._collect_test_functions`): на приёмке ни Оператор, ни
        ревьювер не видят, какие именно тесты выключены на части машин, и
        послабление превращается в дыру без следа.
        """
        outcome = self.run_gate()

        self.assertIn(
            CONDITIONAL_SKIP_ACTION, outcome.actions,
            f"записи о прошедших пропусках в журнале нет (AC-2); "
            f"журнал: {outcome.journal}")
        detail = outcome.detail_of(CONDITIONAL_SKIP_ACTION)
        for method, reason in CONDITIONAL_SKIPS:
            self.assertIn(
                journal_item(NEW_CONDITIONAL_PATH, NEW_CONDITIONAL_CLASS,
                             method, reason),
                detail,
                f"detail записи обязан нести «<файл>::<квалифицированное "
                f"имя метода> — <причина>» по каждому пропуску (AC-2); "
                f"detail: {detail}")


if __name__ == "__main__":
    unittest.main()
