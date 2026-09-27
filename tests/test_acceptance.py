"""Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,
tasks/T066/SPEC.md, требование 2в — условие "полный набор tests/ в
worktree ветки зелёный" автогейта acceptance) и узла разбора вывода
прогона pytest (`run_digest`/`full_suite`, SPEC
01M3FQ3JVC3DGGM33XCX8TC7ME, требования 1-3).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, ci, config  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

PASSING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_always_passes(self):
        self.assertTrue(True)
"""

FAILING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_deliberately_fails(self):
        self.fail("MARKER-RED")
"""

SLEEPING_TEST = """import time
import unittest


class MarkerTest(unittest.TestCase):
    def test_sleeps_past_the_timeout(self):
        time.sleep(3)
"""


class RunFullSuiteTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write_test(self, content: str) -> None:
        tests_dir = self.root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def test_missing_tests_dir_is_not_green(self):
        green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("tests/", tail)

    def test_passing_suite_is_green(self):
        self.write_test(PASSING_TEST)
        green, _ = acceptance.run_full_suite(self.root)
        self.assertTrue(green)

    def test_failing_suite_is_not_green(self):
        self.write_test(FAILING_TEST)
        green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("MARKER-RED", tail)

    def test_timeout_is_not_green(self):
        self.write_test(SLEEPING_TEST)
        with mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 1):
            green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("превысил", tail)


class RunFullSuiteUsesWorkersAndXdistTest(unittest.TestCase):
    """01M291M2Z76M84GVP25J387A66, требование 1/AC-1/AC-7(а): полный набор
    гонится через pytest-xdist — `-n <config.FULL_SUITE_WORKERS>` и явная
    загрузка `-p xdist`, тем же приёмом, что `_pytest_command` уже несёт
    для `-p timeout`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "tests").mkdir()

    def test_command_carries_worker_count_and_explicit_xdist_plugin(self):
        """Ловит мутацию: параллель снята из `run_full_suite` (`-n`/
        `-p xdist` отсутствуют в команде) — полный набор снова гонится
        последовательно без предупреждения."""
        with mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "3 passed", "")
            acceptance.run_full_suite(self.root)

        command = run_.call_args.args[0]
        self.assertIn("-n", command, f"команда без -n: {command}")
        n_pos = command.index("-n")
        self.assertEqual(
            command[n_pos + 1], str(config.FULL_SUITE_WORKERS),
            f"-n несёт не значение config.FULL_SUITE_WORKERS: {command}")
        p_values = [command[i + 1] for i, token in enumerate(command)
                   if token == "-p" and i + 1 < len(command)]
        self.assertIn("xdist", p_values,
                      f"нет явной загрузки -p xdist в команде: {command}")

    def test_full_suite_workers_set_to_one_is_still_a_valid_command(self):
        """AC-7(б): `config.FULL_SUITE_WORKERS = 1` — команда остаётся
        валидной (`-n 1`), параллель не выключается тихо."""
        with mock.patch.object(config, "FULL_SUITE_WORKERS", 1), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "3 passed", "")
            green, _ = acceptance.run_full_suite(self.root)

        command = run_.call_args.args[0]
        n_pos = command.index("-n")
        self.assertEqual(command[n_pos + 1], "1", f"-n не несёт '1': {command}")
        self.assertTrue(green)


SUMMARY_LINE = "1 failed, 1 error, 304 passed in 71.23s"
FAILED_NODEID = ("tests/test_fsm_autogate.py::FullSuiteDetailTest"
                 "::test_detail_names_failed")
ERROR_NODEID = "tests/test_acceptance.py::RunFullSuiteTest::test_log_file"
HEAD_MARKER = "MARKER-ZAGOLOVKA-SESSII"
TRACEBACK_MARKER = "MARKER-TELA-TRACEBACK"

RED_OUTPUT = (
    "============================= test session starts ===========================\n"
    f"platform darwin -- Python 3.13.2, pytest-8.3.4 -- {HEAD_MARKER}\n"
    "8 workers [306 items]\n"
    "=================================== FAILURES ===============================\n"
    "________________ FullSuiteDetailTest.test_detail_names_failed ______________\n"
    "    self.assertIn(nodeid, detail)\n"
    f"AssertionError: {TRACEBACK_MARKER} not found in 'автогейт: ...'\n"
    "=========================== short test summary info ========================\n"
    f"FAILED {FAILED_NODEID} - AssertionError: имя упавшего теста\n"
    f"ERROR {ERROR_NODEID} - fixture 'wt_root' not found\n"
    f"================= {SUMMARY_LINE} =================\n"
)

COLLECT_ERROR_OUTPUT = (
    "ImportError while loading conftest '/wt/tests/conftest.py'.\n"
    "Traceback (most recent call last):\n"
    "  File \"/wt/tests/conftest.py\", line 4, in <module>\n"
    "    import orchestrator.net_takogo_modulya\n"
    "ModuleNotFoundError: No module named 'net_takogo_modulya'\n"
)


class RunDigestTest(unittest.TestCase):
    """Узел разбора вывода прогона pytest (SPEC
    01M3FQ3JVC3DGGM33XCX8TC7ME, требования 1-2) — один на весь пульт."""

    def test_digest_names_failed_tests_and_the_summary_line(self):
        """Выжимка красного прогона несёт имена упавших тестов (включая
        `ERROR <nodeid>`) и итоговую строку pytest, но не тело вывода.

        Ловит мутацию: узел собирает только итоговую строку (как прежняя
        `amend._RUN_SUMMARY`) либо, наоборот, отдаёт срез всего вывода —
        в первом случае из выжимки исчезнут имена упавших тестов, во
        втором в неё попадут заголовок сессии и traceback, и запись
        журнала снова утопит причину в простыне.
        """
        digest = acceptance.run_digest(RED_OUTPUT)

        self.assertIn(SUMMARY_LINE, digest)
        self.assertIn(FAILED_NODEID, digest)
        self.assertIn(ERROR_NODEID, digest,
                      "строка ERROR <nodeid> — тот же упавший тест")
        self.assertNotIn(HEAD_MARKER, digest)
        self.assertNotIn(TRACEBACK_MARKER, digest)

    def test_digest_falls_back_to_the_output_tail(self):
        """Вывод без итоговой строки и без строк `FAILED`/`ERROR` (сбор
        оборвался на conftest) — выжимка отдаёт хвост вывода.

        Ловит мутацию: ветка «ни итога, ни упавших» возвращает пустую
        строку — единственная имевшаяся диагностика (причина обрыва
        сбора) исчезает и из журнала, и из отказа.
        """
        digest = acceptance.run_digest(COLLECT_ERROR_OUTPUT)

        self.assertIn("ModuleNotFoundError", digest)

    def test_digest_is_bounded_by_the_log_tail_config(self):
        """Выжимка двухсот упавших тестов с длинными именами ограничена
        теми же потолками, что выжимка логов ролей: `config.LOG_TAIL_LINES`
        строк И `config.LOG_TAIL_CHARS` символов.

        Ловит мутацию: ограничение применено только по символам или
        только по строкам — красный полный набор на двести тестов уедет в
        журнал целиком.
        """
        huge = "\n".join(
            f"FAILED tests/test_module_{i:03d}.py::VeryLongNamedCase{i:03d}"
            f"::test_rather_long_scenario_name_{i:03d} - AssertionError"
            for i in range(200)) + f"\n===== {SUMMARY_LINE} =====\n"

        digest = acceptance.run_digest(huge)

        self.assertLessEqual(len(digest.splitlines()), config.LOG_TAIL_LINES)
        self.assertLessEqual(len(digest), config.LOG_TAIL_CHARS)

    def test_summary_line_is_empty_when_the_output_has_none(self):
        """`run_summary_line` на выводе без сводки отдаёт пустую строку —
        именно на этом `amend._run_summary` падает обратно на весь хвост
        (AC-3: выжимка правки планки не меняется).

        Ловит мутацию: узел вместо пустой строки возвращает весь вывод
        (или `None`) — `amend._run_summary` начал бы писать в журнал
        правки планки не то, что писал, либо падать на `None`.
        """
        self.assertEqual(acceptance.run_summary_line(COLLECT_ERROR_OUTPUT), "")
        self.assertEqual(acceptance.run_summary_line(RED_OUTPUT), SUMMARY_LINE)


class PytestRunStub:
    """Подмена `subprocess.run` для модуля `orchestrator.acceptance`:
    pytest-команда отвечает заданным исходом, всё остальное уходит в
    `fallback` (git-спай песочницы) — подмена этого атрибута глобальна на
    модуль `subprocess`, и отобрать git у песочницы нельзя."""

    def __init__(self, fallback):
        self.fallback = fallback
        self.returncode = 1
        self.output = RED_OUTPUT
        self.timeout = False

    def __call__(self, cmd, *args, **kwargs):
        if not any("pytest" in str(part) for part in cmd):
            return self.fallback(cmd, *args, **kwargs)
        if self.timeout:
            raise subprocess.TimeoutExpired(
                list(cmd), config.FULL_SUITE_TIMEOUT_SEC, output=self.output)
        return subprocess.CompletedProcess(list(cmd), self.returncode,
                                           self.output, "")


class FullSuiteNodeTest(TmpRootTest):
    """Узел `acceptance.full_suite` (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
    требования 3-4): файл лога с полным выводом прогона и различимая
    причина каждого исхода. Подменён `subprocess.run` модуля — прогон
    настоящей команды pytest в юнит-тесте не нужен, а сообщения
    вырожденных исходов обязаны прийти от самой `run_full_suite`, не от
    фикстуры теста."""

    TASK = "01FULLSUITENODETEST00001"

    def setUp(self):
        super().setUp()
        self.wt_root = self.root / "wt"
        (self.wt_root / "tests").mkdir(parents=True)
        self.pytest_run = PytestRunStub(self.git_spy)
        patcher = mock.patch.object(acceptance.subprocess, "run",
                                    self.pytest_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def log_files(self) -> list:
        return sorted(p for p in config.LOGS.glob("*.log") if p.is_file())

    def test_log_file_carries_the_whole_output_and_is_named_in_detail(self):
        """Прогон оставляет в каталоге логов ролей файл с ПОЛНЫМ выводом
        (включая заголовок сессии, которого в выжимке нет), а `detail`
        называет путь к нему.

        Ловит мутацию: в файл пишется та же выжимка, что уходит в журнал
        (или файл не пишется вовсе) — раскопать причину красноты по логу
        снова будет нечем, а путь в записи будет указывать в пустоту.
        """
        run = acceptance.full_suite(self.wt_root, self.TASK)

        self.assertEqual(len(self.log_files()), 1, self.log_files())
        log_path = self.log_files()[0]
        self.assertEqual(log_path.read_text(encoding="utf-8"), RED_OUTPUT)
        self.assertEqual(run.log_path, log_path)
        self.assertIn(str(log_path), run.detail)
        self.assertIn(SUMMARY_LINE, run.detail)
        self.assertIn(FAILED_NODEID, run.detail)

    def test_second_run_takes_the_next_number_and_keeps_the_first(self):
        """Второй прогон той же задачи пишет файл со следующим номером,
        первый остаётся на диске.

        Ловит мутацию: имя файла собрано из одного `task_id` без номера
        (или номер считается заново) — второй прогон перезатирает первый,
        и сравнить два прогона между собой нечем.
        """
        first = acceptance.full_suite(self.wt_root, self.TASK).log_path
        second = acceptance.full_suite(self.wt_root, self.TASK).log_path

        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file() and second.is_file())
        self.assertEqual(first.name, f"{self.TASK}-fullsuite-1.log")
        self.assertEqual(second.name, f"{self.TASK}-fullsuite-2.log")

    def test_three_outcomes_carry_three_different_details(self):
        """Красный прогон, таймаут и отсутствие `tests/` в рабочей копии
        различимы в `detail` и `outcome`: таймаут называет потолок
        `config.FULL_SUITE_TIMEOUT_SEC`, отсутствие набора — сам факт.

        Ловит мутацию: две ветви из трёх собирают `detail` одним и тем же
        выражением (`green` ложно во всех трёх случаях, причина одна) —
        Оператор ищет упавшие тесты там, где не запускалось ни одного.
        """
        red = acceptance.full_suite(self.wt_root, self.TASK)

        self.pytest_run.timeout = True
        timeout = acceptance.full_suite(self.wt_root, self.TASK)

        self.pytest_run.timeout = False
        (self.wt_root / "tests").rmdir()
        missing = acceptance.full_suite(self.wt_root, self.TASK)

        self.assertEqual(
            len({red.outcome, timeout.outcome, missing.outcome}), 3,
            f"исходы неразличимы: {red.outcome}, {timeout.outcome}, "
            f"{missing.outcome}")
        self.assertEqual(
            len({red.detail, timeout.detail, missing.detail}), 3,
            f"detail неразличимы: {red.detail!r}, {timeout.detail!r}, "
            f"{missing.detail!r}")
        self.assertIn(str(config.FULL_SUITE_TIMEOUT_SEC), timeout.detail)
        self.assertIn("tests/", missing.detail)
        self.assertIn("worktree", missing.detail)

    def test_missing_tests_dir_writes_no_log_file(self):
        """Отсутствие `tests/` — прогона не было: файл лога не заводится,
        `log_path` пуст.

        Ловит мутацию: файл лога пишется безусловно — каталог логов
        засоряется пустыми файлами, а `detail` обещает лог прогона,
        которого не было.
        """
        (self.wt_root / "tests").rmdir()

        run = acceptance.full_suite(self.wt_root, self.TASK)

        self.assertIsNone(run.log_path)
        self.assertEqual(self.log_files(), [])

    def test_green_run_is_green_and_keeps_its_log(self):
        """Зелёный прогон — `green=True`, исход `FULL_SUITE_GREEN`, лог на
        месте: журналу зелёного условия автогейта тоже есть что назвать.

        Ловит мутацию: узел считает зелёным только отсутствие красноты по
        тексту (а не код возврата прогона) — зелёный прогон с непустым
        выводом попал бы в красную ветвь и остановил бы приёмку насмерть.
        """
        self.pytest_run.returncode = 0
        self.pytest_run.output = "306 passed in 70.11s\n"

        run = acceptance.full_suite(self.wt_root, self.TASK)

        self.assertTrue(run.green)
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_GREEN)
        self.assertEqual(len(self.log_files()), 1)
        self.assertIn("306 passed in 70.11s", run.digest)

    def test_log_write_failure_degrades_to_no_path(self):
        """Запись лога не удалась (`OSError`) — `log_path` пуст, исход и
        выжимка на месте: гейт не падает из-за файла лога.

        Ловит мутацию: `OSError` записи лога летит наружу — сбой ФС в
        каталоге логов роняет приёмку и гейт мержа вместо того, чтобы
        стоить одной строки в записи журнала.
        """
        with mock.patch.object(acceptance.agent_log, "new_agent_log",
                               side_effect=OSError("диск переполнен")):
            run = acceptance.full_suite(self.wt_root, self.TASK)

        self.assertIsNone(run.log_path)
        self.assertIn(SUMMARY_LINE, run.detail)
        self.assertNotIn("лог прогона", run.detail)


class MaterializeFromBranchGitFailureTest(unittest.TestCase):
    """R2-F2 (REVIEW.md 01M1RNZ6V7TTTTYAHBMF8JBQQS итерации 2): фикс R1-F1
    (`orchestrator/acceptance.py::materialize_from_branch`) до сих пор был
    подтверждён только ручным репро в тексте REVIEW.md, не персистентным
    тестом — по образцу
    `tests/test_artifact_materialization.py::MaterializeTaskDirTest::
    test_no_branch_returns_empty_sha_and_leaves_disk_untouched`, но для
    `acceptance.materialize_from_branch`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.code_dir = Path(tmp.name)

    def test_none_from_ls_tree_files_leaves_existing_plank_untouched(self):
        """Ловит мутацию: `ls_tree_files(...) or []` смешивает `None`
        (git не ответил) с легитимно пустой веткой (`[]`) — прунинг ниже
        стирал бы уже материализованную планку транзиентным сбоем git."""
        task_id = "01UTMATERIALIZEGITFAIL"
        tests_dir = self.code_dir / "tasks" / task_id / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        existing = tests_dir / "test_ac.py"
        existing.write_text("реальный тест\n", encoding="utf-8")

        with mock.patch.object(acceptance.gitcmd, "ls_tree_files",
                               return_value=None):
            tdir = acceptance.materialize_from_branch(
                task_id, "artifact/does-not-matter", self.code_dir)

        self.assertEqual(tdir, self.code_dir / "tasks" / task_id)
        self.assertEqual(existing.read_text(encoding="utf-8"),
                         "реальный тест\n")


class SummaryCiCriteriaTest(unittest.TestCase):
    """`acceptance.summary` — категория `ci` в сводке гейта приёмки
    (01M1SHJTT0V516BWHYXWS50F3G, требование 4/AC-6): показывается вместе
    с результатом проверки CI, так же явно, как manual-критерии."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_marker.py").write_text(
            '"""Планка с единственной пометкой ci."""\n'
            "# AC-1: ci — CI ветки уже подтверждает зелёный набор.\n",
            encoding="utf-8")

    def test_ci_criterion_is_counted_in_the_header_line(self):
        summary = acceptance.summary(self.tdir)

        self.assertIn("1 ci", summary)

    def test_without_a_branch_ci_criteria_are_named_but_not_polled(self):
        """`branch=None` (вызывающий не назвал ветку) — критерии `ci`
        всё равно называются, но CI не опрашивается (нечем)."""
        with mock.patch.object(
                ci, "verifying_status",
                side_effect=AssertionError("CI не должен опрашиваться "
                                           "без ветки")):
            summary = acceptance.summary(self.tdir)

        self.assertIn("AC-1", summary)
        self.assertIn("ветка не названа", summary)

    def test_with_a_branch_ci_criteria_show_the_verifying_status(self):
        with mock.patch.object(
                ci, "verifying_status",
                return_value=(ci.VERIFYING_GREEN,
                              "CI коммита abc12345 зелёный (2 проверок)")):
            summary = acceptance.summary(self.tdir, branch="task/t001-x")

        self.assertIn("AC-1", summary)
        self.assertIn("CI ветки уже подтверждает зелёный набор", summary)
        self.assertIn("CI коммита abc12345 зелёный (2 проверок)", summary)


if __name__ == "__main__":
    unittest.main()
