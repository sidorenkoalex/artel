"""Приёмочные тесты 01M1TQ0TRCZPRZX22C4084NCPB — AC-2..AC-8: семь рубежей
перехода `in_dev -> review` переезжают на `in_dev -> verifying` целиком,
без дублирования на `verifying -> review` (требование 1).

Красен до реализации: сегодня рубежи (подтяжка main, гейт зон, гейт
ёмкости, лок приёмочной планки, гейт «замечания ревью не отработаны»)
уже стоят именно на выходе из `in_dev` (`orchestrator/fsm_advance.py::
in_dev`, строки 996-1005) — но этот выход сегодня ведёт в `review`, не
в `verifying` (AC-1 уже ловит это отдельно). Здесь красны конкретно
AC-3 (прогон приёмочной планки) и AC-8 (сверка головы на origin):
сегодня оба вызываются из `review()` (approved-ветка, строки 174-256),
а не из `in_dev()` — до реализации задачи шпион ЭТИХ двух функций
покажет ноль вызовов на переходе `in_dev -> verifying`, и тест
покраснеет на первой же проверке `call_count`.

Каждый тест проверяет ДВЕ вещи одним рубежом: (1) функция вызвана РОВНО
один раз на переходе `in_dev -> verifying`; (2) счётчик вызовов не
вырос на следующем переходе `verifying -> review` (зелёный CI). Логика
самих гейтов (что именно считается нарушением) не в объёме этой задачи
(SPEC «Не входит») — подменяется безобидным "пройдено", предмет
проверки — МЕСТО вызова, не решение гейта.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FsmOrderScenarioTest, green_ci  # noqa: E402
from orchestrator import (acceptance, fsm, fsm_advance,  # noqa: E402
                          github_adapter, gitcmd)


class GateStaysOnInDevToVerifyingTest(FsmOrderScenarioTest):

    def assert_gate_stands_only_on_in_dev_to_verifying(
            self, target, attr: str, return_value, gate_label: str) -> None:
        spy = mock.MagicMock(return_value=return_value)
        with mock.patch.object(target, attr, spy):
            self.enter_in_dev_ready()

            self.advance()
            self.assertEqual(self.state(), "verifying",
                             f"{gate_label}: in_dev не дошёл до verifying")
            self.assertEqual(spy.call_count, 1,
                             f"{gate_label}: рубеж не вызван на "
                             f"in_dev -> verifying")

            with green_ci():
                self.advance()
            self.assertEqual(self.state(), "review",
                             f"{gate_label}: verifying не дошёл до review")
            self.assertEqual(spy.call_count, 1,
                             f"{gate_label}: рубеж вызван повторно на "
                             f"verifying -> review")

    def test_ac2_pull_main_gate_stands_only_on_in_dev_to_verifying(self):
        """Рубеж «подтяжка main» (`fsm._pull_main_or_escalate`) стоит на
        переходе `in_dev -> verifying` и не звонится повторно при выходе
        из `verifying` по зелёному CI.

        Ловит мутацию: рубеж продублирован (вызывается и на
        `in_dev -> verifying`, И на `verifying -> review`) — второй
        `assertEqual(spy.call_count, 1)` вырос бы до 2.
        """
        self.assert_gate_stands_only_on_in_dev_to_verifying(
            fsm, "_pull_main_or_escalate", "fresh", "подтяжка main")

    def test_ac4_zones_gate_stands_only_on_in_dev_to_verifying(self):
        """Гейт зон (`fsm_advance._zones_gate_refuses`) стоит на переходе
        `in_dev -> verifying` и не звонится повторно на `verifying ->
        review`.

        Ловит мутацию: гейт зон продублирован на обоих переходах.
        """
        self.assert_gate_stands_only_on_in_dev_to_verifying(
            fsm_advance, "_zones_gate_refuses", False, "гейт зон")

    def test_ac5_capacity_gate_stands_only_on_in_dev_to_verifying(self):
        """Гейт ёмкости (`fsm_advance._capacity_gate_refuses`) стоит на
        переходе `in_dev -> verifying` и не звонится повторно на
        `verifying -> review`.

        Ловит мутацию: гейт ёмкости продублирован на обоих переходах.
        """
        self.assert_gate_stands_only_on_in_dev_to_verifying(
            fsm_advance, "_capacity_gate_refuses", False, "гейт ёмкости")

    def test_ac7_review_rework_gate_stands_only_on_in_dev_to_verifying(self):
        """Гейт «замечания ревью не отработаны»
        (`fsm_advance._review_rework_gate_refuses`) стоит на переходе
        `in_dev -> verifying` и не звонится повторно на `verifying ->
        review`.

        Ловит мутацию: гейт продублирован на обоих переходах.
        """
        self.assert_gate_stands_only_on_in_dev_to_verifying(
            fsm_advance, "_review_rework_gate_refuses", False,
            "гейт «замечания не отработаны»")

    def test_ac3_acceptance_run_stands_only_on_in_dev_to_verifying(self):
        """Рубеж «прогон приёмочной планки после подтяжки»
        (`acceptance.run`) стоит на переходе `in_dev -> verifying`, а не
        на `review`/`verifying -> review`.

        Ловит мутацию: прогон планки оставлен на старом месте (в
        `review()`, вызывается только оттуда) — первый `call_count`
        остался бы 0 при входе в `verifying`.
        """
        self.assert_gate_stands_only_on_in_dev_to_verifying(
            acceptance, "run", (True, "ok"), "прогон приёмочной планки")

    def test_ac8_origin_head_check_stands_only_on_in_dev_to_verifying(self):
        """Сверка головы ветки задачи на origin
        (`github_adapter.ensure_head_in_origin`) стоит на переходе
        `in_dev -> verifying`, а не на `review`/`verifying -> review`.

        Ловит мутацию: сверка оставлена на старом месте (в `review()`)
        — первый `call_count` остался бы 0 при входе в `verifying`.
        """
        self.assert_gate_stands_only_on_in_dev_to_verifying(
            github_adapter, "ensure_head_in_origin", (True, ""),
            "сверка головы на origin")

    def test_ac6_acceptance_tests_lock_check_stands_only_on_in_dev_to_verifying(self):
        """Лок приёмочной планки (сверка diff `acceptance_tests/` против
        `tests_locked_sha`, `gitcmd.diff_names` с pathspec, оканчивающимся
        на `/acceptance_tests`) стоит на переходе `in_dev -> verifying` и
        не звонится повторно на `verifying -> review`.

        Не отдельная именованная функция (встроена в `fsm_advance.in_dev`
        инлайн) — считаем именно ЭТОТ конкретный вызов `gitcmd.diff_names`
        по форме его аргументов (третий позиционный — путь
        `tasks/<id>/acceptance_tests`), отличая его от вызова той же
        функции гейтом зон (два аргумента, без пути).

        Ловит мутацию: лок продублирован (сверка diff идёт и на
        `in_dev -> verifying`, И повторно на `verifying -> review`).
        """
        self.update_task(tests_locked_sha="a" * 40)
        spy = mock.MagicMock(wraps=gitcmd.diff_names)

        def lock_check_calls():
            return [c for c in spy.call_args_list
                   if len(c.args) >= 3
                   and str(c.args[2]).endswith("/acceptance_tests")]

        with mock.patch.object(gitcmd, "diff_names", spy):
            self.enter_in_dev_ready()

            self.advance()
            self.assertEqual(self.state(), "verifying",
                             "in_dev не дошёл до verifying")
            self.assertEqual(len(lock_check_calls()), 1,
                             "лок acceptance_tests/ не сверен на "
                             "in_dev -> verifying")

            with green_ci():
                self.advance()
            self.assertEqual(self.state(), "review",
                             "verifying не дошёл до review")
            self.assertEqual(len(lock_check_calls()), 1,
                             "лок acceptance_tests/ сверен повторно на "
                             "verifying -> review")


if __name__ == "__main__":
    import unittest
    unittest.main()
