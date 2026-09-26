"""AC-11: повторный `ci-rerun` допустим только с новым основанием.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

CI ветки в фикстуре остаётся красным и после первого повтора (тот же флейк
упал снова) — иначе предусловие требования 2 отказывало бы второй вызов само
и критерий не разыгрывался бы вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import REASON, REASON_NEW, CiRerunSandbox  # noqa: E402


class RepeatedReasonRefusedTest(CiRerunSandbox):

    def test_ac11_same_reason_refused_new_reason_reruns(self):
        """Дословно то же основание — отказ; новое основание — повтор.

        Первый вызов проходит штатно и оставляет основание в журнале. Второй
        вызов с ДОСЛОВНО тем же основанием обязан отказать, не запуская
        повтора (иначе команда превращается в кнопку «жать до зелёного» без
        решения Оператора по существу). Третий вызов с новым основанием
        снова проходит штатным путём AC-7.

        Ловит мутацию: сверка основания читает не последнюю запись `ci-rerun`
        этой задачи, а любую запись журнала (или сверяет с точностью до
        регистра/обрезки) — тогда либо новое основание тоже отказывает, либо
        то же самое проходит, и `trigger_calls` расходится с ожидаемым
        числом повторов.
        """
        self.enter_verifying_red()

        first = self.run_ci_rerun(REASON)
        self.assertEqual(
            self.trigger_calls, [self.branch],
            f"первый вызов обязан пройти штатно; сказано: {first!r}")

        before_repeat = self.last_step_id()
        repeated = self.run_ci_rerun(REASON)

        self.assertEqual(
            self.trigger_calls, [self.branch],
            f"повтор с дословно тем же основанием не имеет права запустить "
            f"второй ре-ран; сказано: {repeated!r}")
        self.assertTrue(
            repeated.strip(),
            "отказ обязан быть именованным — команда промолчала")
        self.assertEqual(
            self.state_transitions_since(before_repeat), [],
            "отказ не имеет права журналировать переход состояния")

        third = self.run_ci_rerun(REASON_NEW)

        self.assertEqual(
            self.trigger_calls, [self.branch, self.branch],
            f"с новым основанием команда обязана пройти штатным путём; "
            f"сказано: {third!r}")
        self.assertEqual(
            self.state(), "verifying",
            "команда не меняет состояние задачи (требование 9)")


if __name__ == "__main__":
    unittest.main()
