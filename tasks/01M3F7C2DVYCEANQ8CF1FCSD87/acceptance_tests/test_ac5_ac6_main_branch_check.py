"""AC-5/AC-6: сверка с вершиной главной ветки перед повтором.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

AC-5 — то же задание красно и на вершине главной ветки: это дефект главной
ветки, не флейк ветки задачи (урок 12.09: перезапуск замаскировал реальный
дефект; красная главная ветка 22-26.09). AC-6 — статус вершины главной ветки
неизвестен (вершина не определена либо `gh` не ответил на её проверки):
неизвестный статус — не зелёный (инвариант 19), значит отказ, а не повтор.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FAILED_JOB, MAIN_RED_SAME_JOB, MAIN_SHA,  # noqa: E402
                      REASON, CiRerunSandbox)


class MainBranchCheckTest(CiRerunSandbox):

    def test_ac5_same_failed_job_on_main_refuses_as_main_defect(self):
        """То же задание красно на вершине main — отказ «дефект main».

        На ветке задачи упало задание `python`; на вершине главной ветки
        завершённые не-зелёные задания дают непустое пересечение по имени с
        ним. Команда обязана отказать, назвав имя совпавшего задания и sha
        вершины главной ветки, и ничего не перезапускать.

        Ловит мутацию: пересечение считается не по именам заданий, а по
        заключениям либо по sha/id прогона (у двух разных коммитов они
        различны по определению) — пересечение оказалось бы пустым всегда,
        и команда перезапустила бы CI поверх дефекта главной ветки.
        """
        self.enter_verifying_red()
        self.main_check_runs = MAIN_RED_SAME_JOB
        before = self.last_step_id()

        text = self.run_ci_rerun(REASON)

        self.assertEqual(
            self.trigger_calls, [],
            "краснота того же задания на main — не флейк: повтор не "
            "запускается")
        self.assertIn(
            FAILED_JOB, text,
            f"отказ обязан называть имя совпавшего задания; сказано: {text!r}")
        self.assertIn(
            MAIN_SHA[:8], text,
            f"отказ обязан называть sha вершины главной ветки; сказано: "
            f"{text!r}")
        self.assertIn(
            "main", text.lower(),
            f"отказ обязан говорить именно про дефект main; сказано: {text!r}")
        self.assertEqual(
            self.state(), "verifying",
            "команда не меняет состояние задачи (требование 9)")
        self.assertEqual(
            self.state_transitions_since(before), [],
            "отказ не имеет права журналировать переход состояния")

    def test_ac6_unknown_main_status_refuses_instead_of_rerun(self):
        """Статус вершины main неизвестен — отказ, а не повтор.

        Два обстоятельства неизвестности: `gh` отвечает ошибкой на проверки
        вершины главной ветки и сама вершина не определена (голова
        `origin/<MAIN_BRANCH>` не читается ни через `fsm._origin_main_sha`,
        ни через `git rev-parse`). В обоих случаях сверка требования 5
        невыполнима, и повтор маскировал бы дефект главной ветки.

        Ловит мутацию: неизвестный статус главной ветки трактуется как
        «пересечения нет» (пустой список имён при сбое `gh`) вместо отказа —
        первый же сбой `gh` возвращал бы систему к слепому перезапуску.
        """
        cases = (("gh не ответил на проверки main", "fail"),
                 ("вершина main не определена", "undetermined"))
        for label, kind in cases:
            with self.subTest(case=label):
                # Фикстура и счётчик повторов собираются заново в НАЧАЛЕ
                # каждого подслучая: провал ассерта внутри `subTest` до
                # конца блока не доходит, и уборка в его хвосте оставила бы
                # следующий подслучай на чужой фикстуре.
                self.main_check_runs_fail = False
                self.main_sha = MAIN_SHA
                self.trigger_calls.clear()
                self.enter_verifying_red()
                if kind == "fail":
                    self.main_check_runs_fail = True
                else:
                    self.main_sha = ""
                before = self.last_step_id()

                text = self.run_ci_rerun(REASON)

                self.assertEqual(
                    self.trigger_calls, [],
                    f"{label}: неизвестный статус — не зелёный, повтор не "
                    f"запускается")
                self.assertTrue(
                    text.strip(),
                    f"{label}: отказ обязан быть именованным — команда "
                    f"промолчала")
                self.assertEqual(
                    self.state(), "verifying",
                    "команда не меняет состояние задачи (требование 9)")
                self.assertEqual(
                    self.state_transitions_since(before), [],
                    "отказ не имеет права журналировать переход состояния")


if __name__ == "__main__":
    unittest.main()
