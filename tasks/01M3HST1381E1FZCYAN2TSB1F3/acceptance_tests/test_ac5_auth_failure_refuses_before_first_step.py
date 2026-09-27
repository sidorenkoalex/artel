"""AC-5 — 01M3HST1381E1FZCYAN2TSB1F3: проверка входа домом клона не `ok` —
отказ до первого шага роли, с названной причиной в отчёте.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Проверка входа домом клона вернула не `ok` — прогон отказывает до
первого шага роли: ни один шаг роли не исполнен, а в отчёте прогона
напечатана причина отказа с именем проверки (`codex-chatgpt-auth`) и её
`detail`, включающим рецепт.

Исход «не `ok`» получается не подменой самого узла проверки, а ответом
фикстуры на `codex login status` (`_util.RunSpy(status=NOT_LOGGED_IN)`):
узел `doctor.check_codex_chatgpt_auth` работает настоящий и сам решает, что
вход не подтверждён. Подмена узла проверяла бы только ветку обработки
результата, а не то, что прогон читает результат настоящей проверки.

«Ни один шаг роли не исполнен» — вождение задачи (`canary._drive_task`) не
вызвано: шаг роли идёт только оттуда, и остановка до вождения и есть
остановка до первого шага.

Имя проверки и рецепт сверяются с константами `doctor.CODEX_AUTH_CHECK` и
`doctor.CODEX_AUTH_RECIPE`; поток вывода критерий не фиксирует, поэтому
сверка идёт по всему тексту прогона (stdout, stderr и сообщение
`SystemExit`), сведённому к одному пробелу.

Красен до реализации: проверки входа домом клона нет вовсе — `codex login
status` не зовётся, прогон доводит задачу до конца, и первый же ассерт
(«вождение не начиналось») падает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import doctor  # noqa: E402


class AuthFailureRefusesBeforeFirstStepTest(_util.CodexClonePlankSandbox):

    def failed_auth_run(self) -> _util.Outcome:
        """Прогон на наборе с ролью Codex, где `codex login status` отвечает
        «вход не выполнен» — настоящий узел `doctor` вернёт на этом не
        `ok`."""
        return self.run_canary(
            set_name=_util.SET_NAME,
            spy=_util.RunSpy(status=_util.NOT_LOGGED_IN))

    def test_ac5_no_role_step_runs_when_the_clone_home_is_not_logged_in(self):
        """Вход домом клона не подтверждён — ни один шаг роли не исполнен.

        Ловит мутацию: результат проверки собран, но не влияет на ход
        прогона (записан в отчёт и забыт) — прогон тратил бы шаг роли на
        заведомо неавторизованном доме, то есть платил бы ровно тем
        падением авторизации, ради устранения которого проверка и заводится.
        """
        outcome = self.failed_auth_run()

        self.assertTrue(outcome.spy.login_calls,
                        f"проверка входа не звалась: {outcome.text}")
        self.assertEqual([], outcome.drive_calls,
                         "задача поехала по FSM после неудачной проверки "
                         f"входа: {outcome.text}")

    def test_ac5_report_names_the_check_and_its_detail_with_the_recipe(self):
        """В отчёте прогона напечатаны имя проверки `codex-chatgpt-auth` и
        её `detail` с рецептом.

        Ловит мутацию: отказ печатает свою формулировку («вход в клоне не
        выполнен») вместо `detail` проверки — Оператор не узнал бы ни
        какая именно строка красная, ни двух однократных шагов, которыми
        она чинится, и искал бы причину в коде канарейки.
        """
        outcome = self.failed_auth_run()

        text = _util.normalized(outcome.text)

        self.assertIn(doctor.CODEX_AUTH_CHECK, text)
        self.assertIn(_util.normalized(doctor.CODEX_AUTH_RECIPE), text)

    def test_ac5_a_confirmed_login_lets_the_run_reach_the_task(self):
        """Тот же набор при подтверждённом входе прогон не отказывает:
        отказ привязан к исходу проверки, а не к самому факту набора с
        Codex.

        Ловит мутацию: отказ поставлен на «набор ведёт роль Codex» без
        чтения исхода проверки (или исход трактуется наоборот) — прогон на
        Codex был бы невозможен вообще, при любом состоянии входа.
        """
        outcome = self.run_canary(set_name=_util.SET_NAME)

        self.assertTrue(outcome.auth_calls,
                        f"проверка входа не звалась: {outcome.text}")
        self.assertEqual("ok", outcome.auth_calls[0].check.status,
                         outcome.auth_calls[0].check.detail)
        self.assertIsNone(outcome.exited,
                          f"прогон отказал при подтверждённом входе: "
                          f"{outcome.text}")
        self.assertEqual(1, len(outcome.drive_calls),
                         f"задача не проведена: {outcome.text}")


if __name__ == "__main__":
    unittest.main()
