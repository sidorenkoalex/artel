"""AC-3, AC-5 — медленные тесты ревизии TR-1 вне `tests/test_invariants.py` проходят без настоящего сна паузы повтора.

Каждый названный тест (места 3, 4, 5, 6, 7, 8, 10, 11, 12 перечня
«Контекста» SPEC) запускается в этом же процессе штатным загрузчиком
`unittest` под наблюдателем сна: настоящий `time.sleep` заменён обёрткой,
которая вызов из кода `orchestrator.runner` (единственный сон модуля —
пауза повтора `_run_attempts`) записывает и НЕ исполняет, а прочие вызовы
(опрос дочерних процессов стандартной библиотекой и т.п.) отдаёт
настоящему сну. Подмена песочницы или точечная подмена в файле стоит
ближе к `runner`, чем эта обёртка, и до неё вызов не доходит. Длительность
паузы не ждётся ни в зелёном, ни в красном исходе; время прогона не
утверждается (SPEC, требование 6).

Группа: разовый
Красен до реализации: паузу повтора не снимают ни умолчание `TmpRootTest`, ни файлы `tests/test_agent_prompt.py`/`tests/test_review_freshness.py` — каждый названный тест доходит до настоящего `time.sleep` в `orchestrator/runner.py`, обёртка записывает вызов.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

RUNNER_MODULE = "orchestrator.runner"

# AC-3: классы на голом `unittest.TestCase` — точечная подмена в файле.
AC3_TESTS = (
    "tests.test_agent_prompt.PromptChannelTest."
    "test_the_prompt_is_not_echoed_to_the_terminal",
    "tests.test_review_freshness.ReviewFreshnessScenarioTest."
    "test_reviewer_prompt_asks_for_next_iteration",
)

# AC-5: места 3, 4, 5, 6, 8, 10, 11 перечня «Контекста».
AC5_TESTS = (
    "tests.test_multitarget_invariants.ExternalWorkspaceIsolationTest."
    "test_external_target_cwd_is_its_workspace",
    "tests.test_multitarget_invariants.ExternalWorkspaceIsolationTest."
    "test_pult_root_marker_is_unreachable_from_external_workspace_cwd",
    "tests.test_multitarget.RoleEnvTest."
    "test_agent_process_gets_that_environment",
    "tests.test_multitarget.ProgramSpendTest."
    "test_a_step_run_is_what_moves_the_program_counter",
    "tests.test_multitarget_invariants.ExternalWorkspaceIsolationTest."
    "test_dogfood_cwd_is_its_worktree",
    "tests.test_agent_log.CmdRunLoggingTest.test_second_run_writes_new_file",
    "tests.test_analyst_role.RunAnalystTest."
    "test_run_starts_analyst_when_tz_present",
)


def run_watched(name: str) -> tuple[unittest.TestResult, list]:
    """Прогон теста `name` под наблюдателем сна: (итог, вызовы настоящего
    сна из `orchestrator.runner` — длительность и строка)."""
    real_sleep = time.sleep
    hits = []

    def watched_sleep(seconds):
        caller = sys._getframe(1)
        if caller.f_globals.get("__name__") == RUNNER_MODULE:
            hits.append((seconds, caller.f_lineno))
            return None
        return real_sleep(seconds)

    suite = unittest.defaultTestLoader.loadTestsFromName(name)
    result = unittest.TestResult()
    with mock.patch.object(time, "sleep", watched_sleep):
        suite.run(result)
    return result, hits


class NamedTestsSkipRetrySleepTest(unittest.TestCase):

    def check(self, names):
        for name in names:
            with self.subTest(test=name):
                result, hits = run_watched(name)
                problems = [text for _, text in result.errors + result.failures]
                self.assertEqual(result.testsRun, 1, f"{name}: тест не найден")
                self.assertEqual(problems, [], f"{name} не зелёный")
                self.assertEqual(hits, [],
                                 f"{name}: настоящий time.sleep пульта на "
                                 f"паузе повтора (длительность, строка "
                                 f"runner.py): {hits}")

    def test_ac3_bare_testcase_classes_do_not_sleep_on_retry(self):
        """Два теста на голом `unittest.TestCase` зелёные и не зовут настоящий сон паузы повтора.

        Сценарий: `PromptChannelTest::test_the_prompt_is_not_echoed_to_the_terminal`
        и `ReviewFreshnessScenarioTest::test_reviewer_prompt_asks_for_next_iteration`
        запускаются под наблюдателем сна; каждый проходит без ошибок и
        провалов, а наблюдатель не видел вызова сна из `orchestrator.runner`.

        Ловит мутацию: точечная подмена паузы повтора добавлена только в
        `tests/test_agent_prompt.py`, а `tests/test_review_freshness.py`
        забыт (или подмена стоит не в `setUp` класса, а в соседнем
        классе файла) — наблюдатель записывает вызов сна `runner` с
        `RETRY_BACKOFF_SEC`, список непуст.
        """
        self.check(AC3_TESTS)

    def test_ac5_sandbox_tests_do_not_sleep_on_retry(self):
        """Семь тестов песочницы мест 3–6, 8, 10, 11 зелёные и не зовут настоящий сон паузы повтора.

        Сценарий: каждый тест запускается под наблюдателем сна; проходит
        без ошибок и провалов, а наблюдатель не видел вызова сна из
        `orchestrator.runner`.

        Ловит мутацию: подмена паузы повтора повешена на подкласс
        песочницы (`DeveloperBriefTmpRootTest`/`InitializedTmpRootTest`), а
        не на `TmpRootTest` — тесты прямо на `TmpRootTest`
        (`ExternalWorkspaceIsolationTest`, `RoleEnvTest`) снова зовут
        настоящий сон `runner`, список вызовов непуст.
        """
        self.check(AC5_TESTS)


if __name__ == "__main__":
    unittest.main()
