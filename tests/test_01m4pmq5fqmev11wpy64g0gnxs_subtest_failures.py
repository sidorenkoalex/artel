"""Итог прогона pytest и провал внутри subTest — в разборах пульта.

Свойства разбора вывода pytest: итоговая строка — последняя в выводе, а не
первое совпадение (строка хода подтеста с меткой «1 passed in 0.1s» стоит
раньше); провал подтеста (`SUBFAILED`) виден всем трём разборам упавших —
`acceptance.failed_test_lines`, `acceptance.failed_entries` (и записям
итогов полного набора, которые из него пишутся) и строкам хода
`suite_run.parse`; единица упавшего подтеста — `<nodeid> <метка>`; деление
«новые на ветке / падают и на базе» — по этой единице; повтор `--failed` —
по nodeid родителя; вердикт — по коду выхода pytest.

Образцы вывода — по замеру pytest 9.1.1 и pytest-xdist 3.8.0 (оба вида:
`-vv` без xdist и `-n 2 -p xdist -vv`): строки хода с выравниванием и
процентом, блок «short test summary info», итоговая строка в рамке «=».
Имена тестов, метки подтестов, сообщения и числа — от зерна (`random`),
зерно печатается и входит в текст провала. Один тест гоняет настоящий
pytest под `-n 2 -p xdist` на временном файле с subTest.

Группа: долгоживущий
Красен до реализации: разбор упавших не знает статуса SUBFAILED (подтест не попадает ни в failed_test_lines, ни в failed_entries, ни в строки хода suite_run), run_summary_line берёт первое совпадение итоговой строки, а отчёт suite-run не сверяет число разобранных упавших с итогом pytest.
"""
import contextlib
import io
import os
import random
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, appendix_tree, config, project_profile,
                          repo_context, store, suite_run, workspace)
from tests.sandbox import RealGitSandbox, TmpRootTest

LETTERS = "abcdefghijkmnpqrstuvwxyz"
RULE_WIDTH = 80
# Строка «упавших» в формате до задачи: так прежние `_FAILED_LINE`/
# `_FAILED_ENTRY` узнавали упавший тест в коротком итоге.
OLD_FAILED_LINE = re.compile(r"^(?:FAILED|ERROR) \S+.*$", re.MULTILINE)


def rule(title: str, fill: str = "=") -> str:
    """Строка-рамка pytest: «==== title ====» шириной 80."""
    inner = f" {title} "
    left = (RULE_WIDTH - len(inner)) // 2
    return fill * left + inner + fill * (RULE_WIDTH - len(inner) - left)


def plain_progress(node: str, status: str, percent: int) -> str:
    """Строка хода без xdist: «<nodeid> <статус>   [ NN%]»."""
    return f"{f'{node} {status}':<73} [{percent:>3}%]"


def xdist_progress(worker: int, percent: int, status: str, node: str) -> str:
    """Строка хода с xdist: «[gwN] [ NN%] <статус> <nodeid> » (с хвостовым
    пробелом, как печатает pytest-xdist)."""
    return f"[gw{worker}] [{percent:>3}%] {status} {node} "


def header() -> list[str]:
    return [rule("test session starts"),
            "platform darwin -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0",
            "plugins: xdist-3.8.0, timeout-2.4.0"]


def summary_line(failed: int, passed: int, skipped: int = 0,
                 errors: int = 0, sub_passed: int = 0,
                 seconds: str = "0.83") -> str:
    parts = []
    if failed:
        parts.append(f"{failed} failed")
    parts.append(f"{passed} passed")
    if skipped:
        parts.append(f"{skipped} skipped")
    if errors:
        parts.append(f"{errors} errors" if errors > 1 else "1 error")
    if sub_passed:
        parts.append(f"{sub_passed} subtests passed")
    return f"{', '.join(parts)} in {seconds}s"


class Scenario:
    """Захваченный вывод одного прогона и то, что из него обязан извлечь
    разбор: единицы упавших (`<nodeid> <метка>` для подтеста, nodeid для
    теста) с сообщениями, строки короткого итога, числа итоговой строки."""

    def __init__(self, rng: random.Random, xdist: bool,
                 labels: list[str] | None = None):
        self.rng = rng
        self.xdist = xdist
        word = self.word
        self.unit_parent = f"tests/test_{word()}.py::{word().title()}Test::test_{word()}"
        self.plain = f"tests/test_{word()}.py::test_{word()}"
        self.fixture_parent = f"tests/test_{word()}.py::test_{word()}"
        self.passing = [f"tests/test_{word()}.py::test_{word()}"
                        for _ in range(1 + rng.randrange(4))]
        n = rng.randrange(1, 9)
        if labels is None:
            labels = ([f"[{word()}_{word()}]", f"(i='{n}')"] if xdist
                      else [f"[{word()}_{word()}]", f"(i={n})"])
        self.unit_labels = labels
        x = rng.randrange(2, 9)
        self.fixture_label = (f"[{word()}] (x='{x}')" if xdist
                              else f"[{word()}] (x={x})")
        self.messages = {}
        for label in self.unit_labels:
            self.messages[self.unit(self.unit_parent, label)] = (
                f"AssertionError: {word()} {word()}")
        self.messages[self.plain] = f"ValueError: {word()} {word()}"
        self.messages[self.unit(self.fixture_parent, self.fixture_label)] = (
            f"assert {x} != {x}")
        self.messages[self.fixture_parent] = "contains 1 failed subtest"
        self.skipped = rng.randrange(0, 3)
        self.sub_passed = 1 + rng.randrange(3)
        # Родитель unittest с упавшими подтестами pytest считает «passed».
        self.passed = len(self.passing) + 1

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    @staticmethod
    def unit(node: str, label: str) -> str:
        return f"{node} {label}"

    @property
    def failed_count(self) -> int:
        return len(self.messages)

    def summary_lines(self) -> list[str]:
        """Строки короткого итога в порядке, в котором их печатает pytest."""
        lines = []
        for label in self.unit_labels:
            lines.append(f"SUBFAILED{label} {self.unit_parent} - "
                         f"{self.messages[self.unit(self.unit_parent, label)]}")
        lines.append(f"FAILED {self.plain} - {self.messages[self.plain]}")
        fixture_unit = self.unit(self.fixture_parent, self.fixture_label)
        lines.append(f"SUBFAILED{self.fixture_label} {self.fixture_parent} - "
                     f"{self.messages[fixture_unit]}")
        lines.append(f"FAILED {self.fixture_parent} - "
                     f"{self.messages[self.fixture_parent]}")
        return lines

    def progress_lines(self) -> list[str]:
        """Строки хода: подтесты unittest с xdist — «SUBFAILED<метка>
        <nodeid>», затем «PASSED <nodeid>» родителя; без xdist у провала
        unittest subTest строки хода нет вовсе; фикстура `subtests` — своя
        строка SUBFAILED и FAILED родителя."""
        lines = []
        if self.xdist:
            lines.append(f"{self.unit_parent} ")
            for label in self.unit_labels:
                lines.append(xdist_progress(1, 40, f"SUBFAILED{label}",
                                            self.unit_parent))
            lines.append(xdist_progress(1, 40, "SUBPASSED(i='99')",
                                        self.unit_parent))
            lines.append(xdist_progress(1, 40, "PASSED", self.unit_parent))
            lines.append(f"{self.plain} ")
            lines.append(xdist_progress(0, 50, "FAILED", self.plain))
            lines.append(xdist_progress(0, 60, "SUBPASSED[px] (x='0')",
                                        self.fixture_parent))
            lines.append(xdist_progress(0, 60, f"SUBFAILED{self.fixture_label}",
                                        self.fixture_parent))
            lines.append(xdist_progress(0, 60, "FAILED", self.fixture_parent))
            for index, node in enumerate(self.passing):
                lines.append(f"{node} ")
                lines.append(xdist_progress(index % 2, 70 + index, "PASSED", node))
        else:
            lines.append(plain_progress(self.fixture_parent,
                                        "SUBPASSED[px] (x=0)", 20))
            lines.append(plain_progress(self.fixture_parent,
                                        f"SUBFAILED{self.fixture_label}", 20))
            lines.append(plain_progress(self.fixture_parent, "FAILED", 20))
            lines.append(f"{self.unit_parent} ")
            lines.append(plain_progress(self.unit_parent, "PASSED", 40))
            lines.append(plain_progress(self.plain, "FAILED", 50))
            for index, node in enumerate(self.passing):
                lines.append(plain_progress(node, "PASSED", 70 + index))
        return lines

    def output(self, summary: str | None = None) -> str:
        """Полный вывод завершённого прогона."""
        lines = header()
        if self.xdist:
            lines += ["created: 2/2 workers", "2 workers [9 items]", "",
                      "scheduling tests via LoadScheduling", ""]
        else:
            lines += ["collecting ... collected 9 items", ""]
        lines += self.progress_lines()
        lines += ["", rule("FAILURES"), rule("test_x", "_"), "",
                  "E       AssertionError: сбой", "",
                  rule("short test summary info")]
        lines += self.summary_lines()
        lines.append(rule(summary or summary_line(
            self.failed_count, self.passed, self.skipped,
            sub_passed=self.sub_passed)))
        return "\n".join(lines) + "\n"


def report_numbers(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"прошло: (\d+), упало: (\d+), пропущено: (\d+)", text)
    return tuple(int(g) for g in match.groups()) if match else None


def phrase_number(text: str, phrase: str) -> int | None:
    match = re.search(rf"{phrase}: (\d+)", text)
    return int(match.group(1)) if match else None


class SeededTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def explain(self, text: str = "") -> str:
        return f"зерно: {self.seed}; вывод:\n{text[-4000:]}"

    def scenarios(self) -> list[Scenario]:
        return [Scenario(self.rng, xdist=True), Scenario(self.rng, xdist=False)]

    def render(self, parsed, base_failed=None) -> str:
        return suite_run.render("T1", 1, suite_run.MODE_FULL, parsed,
                                base_failed, "база фикстуры", Path("/x.log"))


class RunSummaryTest(SeededTest):

    def test_ac1_last_summary_line_wins_over_subtest_label(self):
        """Итоговая строка — последняя в выводе, не метка подтеста раньше неё.

        Сценарий: вывод с xdist, где метка упавшего подтеста —
        `(output="'1 passed in 0.1s'")`: она стоит и в строке хода, и в
        коротком итоге, раньше настоящей итоговой строки «F failed, P
        passed, S skipped, K subtests passed in Xs» (P ≠ 1, числа от
        зерна). `run_summary_line` возвращает настоящую строку, а отчёт
        `suite-run` по тому же выводу — «прошло: P, упало: F, пропущено: S».

        Ловит мутацию: возврат к первому совпадению `_RUN_SUMMARY.search` —
        функция отдаёт «1 passed in 0.1s», отчёт — «прошло: 1, упало: 0».
        """
        fake = "1 passed in 0.1s"
        for xdist in (True, False):
            with self.subTest(xdist=xdist):
                label = (f"(output=\"'{fake}'\")" if xdist
                         else f"(output='{fake}')")
                scenario = Scenario(self.rng, xdist=xdist,
                                    labels=[label, f"[{self.rng.choice(LETTERS)}gate]"])
                scenario.passed += 1 + self.rng.randrange(5)
                scenario.skipped = 1 + self.rng.randrange(3)
                seconds = f"{self.rng.randrange(2, 500)}.{self.rng.randrange(10, 99)}"
                real = summary_line(scenario.failed_count, scenario.passed,
                                    scenario.skipped,
                                    sub_passed=scenario.sub_passed,
                                    seconds=seconds)
                output = scenario.output(real)
                self.assertLess(output.index(fake), output.index(real))
                self.assertEqual(acceptance.run_summary_line(output), real,
                                 self.explain(output))
                text = self.render(suite_run.parse(False, output))
                self.assertEqual(report_numbers(text),
                                 (scenario.passed, scenario.failed_count,
                                  scenario.skipped), self.explain(text))


class FailedLinesTest(SeededTest):

    def test_ac2_failed_test_lines_include_subfailed_and_keep_failed(self):
        """`failed_test_lines` отдаёт строки SUBFAILED и прежние FAILED/ERROR.

        Сценарий: вывод обоих видов (с xdist и без) с подтестами меток
        `[merge_gate]`, `(i=1)`/`(i='1')` и меткой от зерна, обычным
        упавшим тестом, упавшим родителем фикстуры `subtests` и строкой
        `ERROR <файл>` сбора. Результат содержит каждую строку короткого
        итога `SUBFAILED…` и каждую строку `FAILED`/`ERROR`, которую на том
        же выводе находило прежнее правило (якорь на начало строки).

        Ловит мутацию: статус SUBFAILED не добавлен в `_FAILED_LINE` — строк
        подтестов в результате нет; новое правило заменило прежнее и
        потеряло строку `ERROR <файл>` или `FAILED <nodeid>`.
        """
        for xdist in (True, False):
            with self.subTest(xdist=xdist):
                labels = (["[merge_gate]", "(i='1')", f"[{self.rng.choice(LETTERS)}x y]"]
                          if xdist else ["[merge_gate]", "(i=1)",
                                         f"[{self.rng.choice(LETTERS)}x y]"])
                scenario = Scenario(self.rng, xdist=xdist, labels=labels)
                broken = f"tests/test_{scenario.word()}.py"
                output = scenario.output().replace(
                    rule("short test summary info") + "\n",
                    rule("short test summary info") + f"\nERROR {broken}\n")
                lines = acceptance.failed_test_lines(output)
                for line in scenario.summary_lines():
                    if line.startswith("SUBFAILED"):
                        self.assertIn(line, lines, self.explain(output))
                for line in OLD_FAILED_LINE.findall(output):
                    self.assertIn(line.strip(), lines, self.explain(output))
                self.assertIn(f"ERROR {broken}", lines, self.explain(output))


class FailedEntriesTest(SeededTest):

    def test_ac3_failed_entries_give_subtest_units_with_messages(self):
        """`failed_entries` отдаёт единицу `<nodeid> <метка>` и сообщение.

        Сценарий: вывод обоих видов; метки подтестов несут пробелы, скобки
        и кавычки (`[px] (x='2')`, `(i=1)`, `[a b]` от зерна). Для каждого
        упавшего подтеста в результате есть пара (`<nodeid> <метка>`,
        сообщение после « - »); записи `FAILED` обычного теста и родителя
        фикстуры `subtests` — с прежними id и сообщениями.

        Ловит мутацию: статус SUBFAILED не добавлен в `_FAILED_ENTRY` —
        единиц подтестов нет; метка обрезана до первого пробела или
        скобки — единица `<nodeid> [px]` вместо `<nodeid> [px] (x='2')`;
        nodeid берётся первым словом строки — единица начинается с метки.
        """
        for scenario in self.scenarios():
            with self.subTest(xdist=scenario.xdist):
                scenario.unit_labels.append(
                    f"[{scenario.word()} {scenario.word()}]")
                unit = scenario.unit(scenario.unit_parent,
                                     scenario.unit_labels[-1])
                scenario.messages[unit] = f"AssertionError: {scenario.word()}"
                output = scenario.output()
                entries = dict(acceptance.failed_entries(output))
                for node, message in scenario.messages.items():
                    self.assertIn(node, entries, self.explain(output))
                    self.assertEqual(entries[node], message, self.explain(output))


class SavedRecordsTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def test_ac3_suite_records_and_gate_failures_carry_subtest_units(self):
        """Записи итога гейта и базы и перечень по sha несут единицы подтестов.

        Сценарий: чистое git-дерево песочницы; узел гейта
        `acceptance.full_suite` получает (подменой публичного
        `run_full_suite`) красный вывод обоих видов с упавшими подтестами.
        Поле `failed` записи `saved_suite_result("gate", …)` и записи
        `saved_suite_result("base", …)` (ключи — публичные
        `suite_tree_hash`/`suite_result_key`) и перечень
        `saved_failures(<sha HEAD>)` содержат каждую единицу
        `<nodeid> <метка>` и прежние nodeid упавших тестов.

        Ловит мутацию: записи пишутся прежним разбором без SUBFAILED —
        единиц подтестов в `failed` нет; `_remember_gate_failures` берёт
        перечень не из `failed_entries` — в перечне по sha подтестов нет.
        """
        for xdist in (True, False):
            with self.subTest(xdist=xdist):
                scenario = Scenario(self.rng, xdist=xdist)
                output = scenario.output()
                with mock.patch.object(acceptance, "run_full_suite",
                                       return_value=(False, output)):
                    run = acceptance.full_suite(self.root, "T1", fresh=True)
                self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED,
                                 f"зерно: {self.seed}; {run.detail}")
                tree = acceptance.suite_tree_hash(self.root)
                base_tree = acceptance.suite_tree_hash(self.root, base=True)
                gate = acceptance.saved_suite_result(
                    "gate", acceptance.suite_result_key(tree), tree=tree)
                base = acceptance.saved_suite_result(
                    "base", acceptance.suite_result_key(base_tree, base=True),
                    tree=base_tree)
                sha = acceptance.clean_tree_sha(self.root)
                self.assertIsNotNone(sha, f"зерно: {self.seed}")
                by_sha = acceptance.saved_failures(sha)
                for name, failed in (("gate", gate and gate["failed"]),
                                     ("base", base and base["failed"]),
                                     ("save_failures", by_sha)):
                    self.assertIsNotNone(failed, f"{name}; зерно: {self.seed}")
                    for node in scenario.messages:
                        self.assertIn(node, failed,
                                      f"{name}: {failed}; зерно: {self.seed}")

    def test_ac9_gate_verdict_follows_exit_code(self):
        """Вердикт узла гейта — по коду выхода pytest, не по разбору упавших.

        Сценарий: `acceptance.full_suite` (свежий прогон) получает зелёный
        код выхода с выводом, где есть строки `SUBFAILED` и итог «N
        failed», — исход зелёный; затем красный код выхода с выводом без
        единой упавшей строки («N passed») — исход красный.

        Ловит мутацию: вердикт гейта выводится из найденных SUBFAILED или из
        итоговой строки — зелёный код с подтестами становится красным, а
        красный код без упавших — зелёным.
        """
        scenario = Scenario(self.rng, xdist=self.rng.choice([True, False]))
        with mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, scenario.output())):
            green = acceptance.full_suite(self.root, "T1", fresh=True)
        self.assertTrue(green.green, f"зерно: {self.seed}; {green.detail}")
        self.assertEqual(green.outcome, acceptance.FULL_SUITE_GREEN)
        passed = 1 + self.rng.randrange(9)
        clean = "\n".join(header() + [rule(summary_line(0, passed))]) + "\n"
        with mock.patch.object(acceptance, "run_full_suite",
                               return_value=(False, clean)):
            red = acceptance.full_suite(self.root, "T1", fresh=True)
        self.assertFalse(red.green, f"зерно: {self.seed}; {red.detail}")
        self.assertEqual(red.outcome, acceptance.FULL_SUITE_RED)


def broken_output(scenario: Scenario) -> str:
    """Оборванный прогон: только строки хода, без блока «short test summary
    info» и без итоговой строки. Строки хода с xdist (unittest subTest) и
    без xdist (фикстура `subtests`) — в одном выводе."""
    xd = scenario
    lines = header() + ["created: 2/2 workers", ""]
    lines.append(f"{xd.unit_parent} ")
    for label in xd.unit_labels:
        lines.append(xdist_progress(1, 30, f"SUBFAILED{label}", xd.unit_parent))
    lines.append(xdist_progress(1, 30, "SUBPASSED(i='99')", xd.unit_parent))
    lines.append(xdist_progress(1, 30, "PASSED", xd.unit_parent))
    lines.append(xdist_progress(0, 40, "FAILED", xd.plain))
    lines.append(plain_progress(xd.fixture_parent, "SUBPASSED[px] (x=0)", 50))
    lines.append(plain_progress(xd.fixture_parent,
                                f"SUBFAILED{xd.fixture_label}", 50))
    lines.append(plain_progress(xd.fixture_parent, "FAILED", 50))
    for index, node in enumerate(xd.passing):
        lines.append(xdist_progress(index % 2, 60 + index, "PASSED", node))
    lines.append(f"tests/test_{xd.word()}.py::test_{xd.word()} ")
    return "\n".join(lines) + "\n"


class BrokenRunTest(SeededTest):

    def expected(self, scenario: Scenario) -> tuple[set, set]:
        units = {scenario.unit(scenario.unit_parent, label)
                 for label in scenario.unit_labels}
        units.add(scenario.plain)
        units.add(scenario.unit(scenario.fixture_parent, scenario.fixture_label))
        units.add(scenario.fixture_parent)
        return units

    def test_ac4_broken_run_counts_subtest_units_from_progress(self):
        """Оборванный прогон: упавшие подтесты из строк хода — единицами.

        Сценарий: вывод без короткого итога и итоговой строки; строки хода
        xdist `SUBFAILED<метка> <nodeid>` двух подтестов unittest, затем
        `PASSED <nodeid>` родителя; `FAILED` обычного теста; строка без
        xdist `<nodeid> SUBFAILED<метка> [NN%]` фикстуры `subtests` и
        `FAILED` её родителя; метки с пробелами и кавычками.
        `suite_run.parse` даёт незавершённый прогон, число упавших — число
        единиц, а состав `failures` — ровно `<nodeid> <метка>` каждого
        подтеста и nodeid упавших тестов; строка PASSED родителя провал
        подтеста не снимает.

        Ловит мутацию: SUBFAILED не добавлен в `_STATUS`/`_PROGRESS` — в
        составе один обычный тест; ключ строки хода — только nodeid
        родителя, а PASSED родителя перезаписывает его — единиц подтестов
        unittest нет; метка без xdist захватывает « [NN%]» — единица не
        совпадает.
        """
        scenario = Scenario(self.rng, xdist=True)
        scenario.fixture_label = f"[{scenario.word()}] (x={self.rng.randrange(2, 9)})"
        output = broken_output(scenario)
        units = self.expected(scenario)
        self.assertGreater(len(units), 1)
        parsed = suite_run.parse(False, output)
        self.assertFalse(parsed.finished, self.explain(output))
        self.assertEqual({node for node, _ in parsed.failures}, units,
                         self.explain(output))
        self.assertEqual(parsed.failed, len(units), self.explain(output))


class ProgressCountTest(TmpRootTest):
    """Связка «команда `suite-run --wait` — лог идущего прогона»: счёт
    «выполнено тестов по логу» печатает команда, поэтому сценарий идёт через
    `cmd_suite_run`; запуск фонового процесса подменён (`subprocess.Popen`
    — «процесс» с pid самого теста, то есть живой)."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        conn = store.db()
        store.create_schema(conn)
        self.task_id = "T" + "".join(self.rng.choice("0123456789")
                                     for _ in range(6))
        store.insert_task(conn, self.task_id, "Прогон", "in_dev",
                          f"task/{self.task_id.lower()}-progon",
                          config.DEFAULT_TARGET, 25.0)
        self.wt = self.root / "wt"
        self.wt.mkdir()
        self.addCleanup(suite_run.suite_lock.release)

    def profile(self):
        return mock.patch.object(
            repo_context, "profile_of",
            return_value=repo_context.ProfileAnswer(
                repo_context.PROFILE_PRESENT,
                values={"command": ["python3", "-m", "pytest"]}))

    def cli(self, *args: str) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.suppress(SystemExit):
            suite_run.cmd_suite_run([self.task_id, *args])
        return out.getvalue()

    def test_ac4_progress_count_is_by_test_nodeids(self):
        """«Выполнено тестов по логу» — по различным nodeid, без подтестов.

        Сценарий: `suite-run <id>` (фоновый процесс подменён) заводит
        прогон и называет лог; в лог записан оборванный вывод с упавшими
        подтестами (xdist и без) и PASSED родителя. `suite-run <id> --wait
        0` печатает «ещё идёт» и «выполнено тестов по логу N», где N —
        число различных nodeid тестов со статусом в строках хода.

        Ловит мутацию: единицы подтестов (и SUBPASSED) входят в счёт хода —
        N больше числа тестов на число подтестов.
        """
        scenario = Scenario(self.rng, xdist=True)
        output = broken_output(scenario)
        nodes = {scenario.unit_parent, scenario.plain, scenario.fixture_parent,
                 *scenario.passing}
        real_popen = subprocess.Popen

        def popen(argv, *args, **kwargs):
            # Только запуск фонового процесса прогона подменяется «живым»
            # процессом с pid теста; прочие вызовы идут как есть.
            if list(argv[:2]) == [sys.executable, "-c"]:
                return mock.Mock(pid=os.getpid())
            return real_popen(argv, *args, **kwargs)

        with self.profile(), \
                mock.patch.object(workspace, "path", return_value=self.wt), \
                mock.patch.object(subprocess, "Popen", side_effect=popen):
            started = self.cli()
        match = re.search(r"лог: (\S+)", started)
        self.assertIsNotNone(match, f"зерно: {self.seed}; {started}")
        Path(match.group(1)).write_text(output, encoding="utf-8")
        waited = self.cli("--wait", "0")
        self.assertIn(suite_run.STILL_RUNNING, waited, f"зерно: {self.seed}; {waited}")
        count = re.search(r"прогон ветки: выполнено тестов по логу (\d+)", waited)
        self.assertIsNotNone(count, f"зерно: {self.seed}; {waited}")
        self.assertEqual(int(count.group(1)), len(nodes),
                         f"зерно: {self.seed}; {waited}\n{output}")

    def test_ac8_failed_rerun_targets_parent_nodeids(self):
        """`--failed` после упавшего подтеста повторяет nodeid родителя.

        Сценарий: фоновый прогон `suite_run.background` (полный набор,
        публичный `acceptance.run_full_suite` подменён) получает
        завершённый красный вывод с двумя упавшими подтестами одного
        теста unittest, упавшим подтестом фикстуры и обычным упавшим
        тестом. Затем фоновый прогон в режиме `MODE_FAILED`: цели, переданные
        `run_full_suite`, — ровно nodeid родителей и обычного теста, ни одна
        не несёт метку подтеста.

        Ловит мутацию: перечень упавших для повтора пишется единицами
        `<nodeid> <метка>` — в целях повтора строки с меткой, которых
        pytest не найдёт; единицы подтестов в перечень не попадают — родителя
        unittest (сам он PASSED) в целях нет.
        """
        scenario = Scenario(self.rng, xdist=self.rng.choice([True, False]))
        output = scenario.output()
        calls = []

        def run(root, *args, **kwargs):
            calls.append(tuple(kwargs.get("targets") or ()))
            return False, output

        tree = appendix_tree.SuiteTree(self.wt, "", "", "")
        with self.profile(), \
                mock.patch.object(project_profile, "full_suite_limit",
                                  return_value=(60, "config")), \
                mock.patch.object(workspace, "path", return_value=self.wt), \
                mock.patch.object(workspace, "repo",
                                  return_value=self.root / "нет-клона"), \
                mock.patch.object(appendix_tree, "suite_tree",
                                  return_value=contextlib.nullcontext(tree)), \
                mock.patch.object(acceptance, "run_full_suite", side_effect=run):
            suite_run.background(self.task_id, "1", suite_run.MODE_FULL)
            first = len(calls)
            suite_run.background(self.task_id, "2", suite_run.MODE_FAILED)
        self.assertGreater(len(calls), first, f"зерно: {self.seed}; повтора нет")
        targets = set(calls[first])
        self.assertEqual(targets, {scenario.unit_parent, scenario.plain,
                                   scenario.fixture_parent},
                         f"зерно: {self.seed}; цели {calls[first]}")


class ReportCountTest(SeededTest):

    def test_ac5_report_count_matches_pytest_summary_on_captured_output(self):
        """Число упавших отчёта = единицы подтестов + упавшие тесты = итог pytest.

        Сценарий: захваченный вывод обоих видов (с xdist подтест назван и в
        строке хода, и в коротком итоге). `suite_run.parse` отдаёт в
        `failures` каждую единицу ровно один раз — подтесты unittest и
        фикстуры `subtests` парами `<nodeid> <метка>`, родителя фикстуры,
        помеченного FAILED, отдельной единицей, обычный упавший тест; их
        число равно сумме «N failed» итоговой строки; отчёт — «упало: N».

        Ловит мутацию: ключ строки хода и ключ короткого итога разного вида
        (лишний пробел, метка с « [NN%]») — подтест считается дважды;
        родитель фикстуры склеен со своим подтестом — единиц меньше итога.
        """
        for scenario in self.scenarios():
            with self.subTest(xdist=scenario.xdist):
                output = scenario.output()
                parsed = suite_run.parse(False, output)
                nodes = [node for node, _ in parsed.failures]
                self.assertEqual(sorted(nodes), sorted(scenario.messages),
                                 self.explain(output))
                self.assertEqual(parsed.failed, scenario.failed_count,
                                 self.explain(output))
                text = self.render(parsed)
                self.assertEqual(report_numbers(text)[1], scenario.failed_count,
                                 self.explain(text))

    def test_ac5_real_xdist_run_counts_subtest_units(self):
        """Настоящий pytest под `-n 2 -p xdist`: число упавших = итог pytest.

        Сценарий: во временном каталоге файл с тестом unittest (два упавших
        subTest с метками от зерна и один зелёный), обычным упавшим тестом,
        тестом с фикстурой `subtests` (один упавший подтест) и зелёным
        тестом; `python -m pytest -vv -n 2 -p xdist`. Сбой подпроцесса
        (код не 0/1, нет итоговой строки) — красный тест, не skip. Число
        упавших разбора равно сумме «N failed»/«N errors» итоговой строки,
        у родителя unittest — ровно две единицы, отчёт — «упало: N».

        Ловит мутацию: SUBFAILED не распознаётся — у родителя unittest нет
        единиц, упавших меньше итога; подтест строки хода и короткого итога
        считается дважды — упавших больше итога.
        """
        word = lambda: "".join(self.rng.choice(LETTERS) for _ in range(6))
        cls, method, gate = word().title(), word(), word()
        index = self.rng.randrange(1, 9)
        source = textwrap.dedent(f"""\
            import unittest


            class {cls}Test(unittest.TestCase):
                def test_{method}(self):
                    with self.subTest("{gate}"):
                        self.assertEqual(1, 2)
                    with self.subTest(i={index}):
                        self.fail("сбой {index}")
                    with self.subTest(i=0):
                        pass


            def test_plain():
                assert False, "обычный"


            def test_fixture(subtests):
                for x in range(3):
                    with subtests.test(msg="px", x=x):
                        assert x != 2


            def test_ok():
                pass
            """)
        with tempfile.TemporaryDirectory() as raw:
            holder = str(Path(raw).resolve())
            folder = Path(holder) / "tests"
            folder.mkdir()
            (folder / "test_sub.py").write_text(source, encoding="utf-8")
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("PYTEST_") and k != config.ARTEL_ROLE_ENV}
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "tests", "-vv", "-n", "2",
                 "-p", "xdist", "-p", "no:cacheprovider",
                 f"--rootdir={holder}"],
                cwd=holder, env=env, capture_output=True, text=True,
                timeout=110)
        output = proc.stdout
        summary = acceptance.run_summary_line(output)
        self.assertIn(proc.returncode, (0, 1),
                      f"сбой прогона pytest: код {proc.returncode}\n"
                      f"{output[-3000:]}\n{proc.stderr[-3000:]}")
        self.assertRegex(summary, r"\d+ failed",
                         f"нет итоговой строки: {self.explain(output)}")
        total = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b",
                                               summary))
        parsed = suite_run.parse(proc.returncode == 0, output)
        nodes = [node for node, _ in parsed.failures]
        self.assertEqual(len(nodes), total, self.explain(output))
        self.assertEqual(len(set(nodes)), len(nodes), self.explain(output))
        parent = f"tests/test_sub.py::{cls}Test::test_{method}"
        units = [n for n in nodes if n.startswith(parent + " ")]
        self.assertEqual(len(units), 2, self.explain(output))
        self.assertTrue(any(gate in n for n in units), self.explain(output))
        self.assertEqual(report_numbers(self.render(parsed))[1], total,
                         self.explain(output))

    def test_ac6_report_names_mismatch_with_pytest_summary(self):
        """Разобрано меньше упавших, чем в итоге pytest, — отчёт говорит прямо.

        Сценарий: завершённый вывод, где итоговая строка называет F failed и
        E errors (N = F + E ≥ 5), а короткий итог и строки хода называют
        только M < N упавших (часть строк потеряна). Отчёт `suite-run`
        содержит «итог pytest: N упавших, разобрано M» с этими числами и не
        содержит «упало: 0».

        Ловит мутацию: сверки числа разобранных с итоговой строкой нет —
        строки «итог pytest: …» в отчёте нет; сверяется с числом строк
        хода или берётся M за N — числа в строке не те.
        """
        word = lambda: "".join(self.rng.choice(LETTERS) for _ in range(6))
        errors = self.rng.randrange(0, 3)
        failed = 5 + self.rng.randrange(5)
        total = failed + errors
        shown = self.rng.randrange(0, total)
        listed = [f"FAILED tests/test_{word()}.py::test_{word()} - "
                  f"ValueError: {word()}" for _ in range(shown)]
        lines = header() + ["", rule("short test summary info"), *listed,
                            rule(summary_line(failed, 3, errors=errors))]
        output = "\n".join(lines) + "\n"
        text = self.render(suite_run.parse(False, output))
        self.assertIn(f"итог pytest: {total} упавших, разобрано {shown}", text,
                      self.explain(text))
        self.assertNotIn("упало: 0", text, self.explain(text))


class BaseSplitTest(SeededTest):

    def outputs(self, base_label: str, branch_labels: list[str],
                xdist: bool) -> tuple[str, str, Scenario]:
        branch = Scenario(self.rng, xdist=xdist, labels=branch_labels)
        base = Scenario(self.rng, xdist=xdist, labels=[base_label])
        # Те же тесты на базе: родитель, обычный и фикстура — общие.
        base.unit_parent = branch.unit_parent
        base.plain = branch.plain
        base.fixture_parent = branch.fixture_parent
        base.fixture_label = branch.fixture_label
        base.passing = branch.passing
        base.messages = {}
        base.messages[base.unit(base.unit_parent, base_label)] = "AssertionError: база"
        base.messages[base.plain] = branch.messages[branch.plain]
        fixture_unit = base.unit(base.fixture_parent, base.fixture_label)
        base.messages[fixture_unit] = branch.messages[fixture_unit]
        base.messages[base.fixture_parent] = branch.messages[branch.fixture_parent]
        return base.output(), branch.output(), branch

    def split(self, base_output: str, branch_output: str) -> list[str]:
        sources = {
            "итог базы из failed_entries": {
                n for n, _ in acceptance.failed_entries(base_output)},
            "прогон базы suite-run": {
                n for n, _ in suite_run.parse(False, base_output).failures},
        }
        parsed = suite_run.parse(False, branch_output)
        return [(name, base, self.render(parsed, base))
                for name, base in sources.items()]

    def test_ac7_new_and_base_split_by_parent_and_label(self):
        """«Новые на ветке / падают и на базе» — по паре «родитель + метка».

        Сценарий: подтест A теста unittest падает и на базе, и на ветке,
        подтест B того же теста — только на ветке; обычный тест и подтест
        фикстуры падают и там, и там. Итог базы — множество единиц разбора
        вывода базы (`failed_entries`, как пишет запись итога, и
        `suite_run.parse`, как прогон базы). Отчёт: «новые на ветке: 1»,
        единица B названа, единица A не названа.

        Ловит мутацию: ключ сравнения — только nodeid родителя — A и B оба
        «падают и на базе», новых 0; сравнение по полной единице, но итог
        базы пишется nodeid родителя — A и B оба новые.
        """
        for xdist in (True, False):
            with self.subTest(xdist=xdist):
                label_a = f"[{self.rng.choice(LETTERS)}{self.rng.choice(LETTERS)}a]"
                label_b = f"[{self.rng.choice(LETTERS)}{self.rng.choice(LETTERS)}b]"
                base_output, branch_output, branch = self.outputs(
                    label_a, [label_a, label_b], xdist)
                unit_a = branch.unit(branch.unit_parent, label_a)
                unit_b = branch.unit(branch.unit_parent, label_b)
                for name, base, text in self.split(base_output, branch_output):
                    with self.subTest(source=name):
                        self.assertEqual(phrase_number(text, suite_run.NEW_ON_BRANCH), 1,
                                         f"{name}; база {base}; {self.explain(text)}")
                        self.assertEqual(phrase_number(text, suite_run.ALSO_ON_BASE),
                                         branch.failed_count - 1, self.explain(text))
                        self.assertIn(unit_b, text, self.explain(text))
                        self.assertNotIn(unit_a, text, self.explain(text))

    def test_ac7_label_form_mismatch_counts_as_new(self):
        """Разный вид метки одного подтеста на базе и ветке — провал новый.

        Сценарий: на базе подтест помечен без xdist `(i=N)`, на ветке тот же
        подтест — с xdist `(i='N')`; остальное падает одинаково. Отчёт
        относит этот подтест к «новые на ветке» (одна новая единица).

        Ловит мутацию: метка нормализуется к одному виду или отбрасывается
        при сравнении — подтест «падает и на базе», новых 0.
        """
        n = self.rng.randrange(1, 9)
        base_output, branch_output, branch = self.outputs(
            f"(i={n})", [f"(i='{n}')"], xdist=False)
        for name, base, text in self.split(base_output, branch_output):
            with self.subTest(source=name):
                self.assertEqual(phrase_number(text, suite_run.NEW_ON_BRANCH), 1,
                                 f"{name}; база {base}; {self.explain(text)}")
                self.assertIn(branch.unit(branch.unit_parent, f"(i='{n}')"), text,
                              self.explain(text))


class VerdictTest(SeededTest):

    def test_ac9_suite_run_verdict_follows_exit_code(self):
        """Исход `suite-run` — по коду выхода pytest, разбор его не меняет.

        Сценарий: зелёный код выхода с выводом, где есть SUBFAILED и итог
        «N failed», — `parse` даёт зелёный исход, отчёт — «зелёный прогон»;
        красный код с выводом «N passed» без упавших — красный исход и
        «красный прогон».

        Ловит мутацию: найденные SUBFAILED или «failed» итога переводят
        прогон в красный — зелёный код даёт «красный прогон»; пустой
        перечень упавших делает красный код зелёным.
        """
        scenario = Scenario(self.rng, xdist=self.rng.choice([True, False]))
        parsed = suite_run.parse(True, scenario.output())
        self.assertEqual(parsed.outcome, acceptance.FULL_SUITE_GREEN)
        self.assertIn("зелёный прогон", self.render(parsed))
        passed = 1 + self.rng.randrange(9)
        clean = "\n".join(header() + [rule(summary_line(0, passed))]) + "\n"
        parsed = suite_run.parse(False, clean)
        self.assertEqual(parsed.outcome, acceptance.FULL_SUITE_RED)
        self.assertIn("красный прогон", self.render(parsed))


class SpacedNodeIdTest(SeededTest):

    def test_ac10_nodeid_with_space_in_param_id_is_kept_whole(self):
        """nodeid с пробелом в id параметризации разбирается целиком.

        Сценарий: короткий итог с `FAILED tests/x.py::test_x[a b] - …` и
        `ERROR tests/y.py::test_y[c d] - …` (слова от зерна):
        `failed_entries` отдаёт эти nodeid целиком, `failed_test_lines` —
        эти строки. Оборванный вывод со строками хода
        `[gw0] [ NN%] FAILED <id с пробелом>` и
        `<id с пробелом> FAILED [ NN%]`: `suite_run.parse` называет упавшими
        оба id целиком.

        Ловит мутацию: новое правило разбора берёт nodeid как первое или
        последнее слово и для FAILED/ERROR — id обрезан до `…[a` или `b]`.
        """
        word = lambda: "".join(self.rng.choice(LETTERS) for _ in range(5))
        failed = f"tests/test_{word()}.py::test_{word()}[{word()} {word()}]"
        errored = f"tests/test_{word()}.py::test_{word()}[{word()} {word()}]"
        msg_f, msg_e = f"ValueError: {word()}", f"RuntimeError: {word()}"
        lines = [f"FAILED {failed} - {msg_f}", f"ERROR {errored} - {msg_e}"]
        output = "\n".join(header() + ["", rule("short test summary info"),
                                       *lines,
                                       rule(summary_line(1, 2, errors=1))]) + "\n"
        entries = dict(acceptance.failed_entries(output))
        self.assertEqual(entries.get(failed), msg_f, self.explain(output))
        self.assertEqual(entries.get(errored), msg_e, self.explain(output))
        found = acceptance.failed_test_lines(output)
        for line in lines:
            self.assertIn(line, found, self.explain(output))

        xdist_node = f"tests/test_{word()}.py::test_{word()}[{word()} {word()}]"
        plain_node = f"tests/test_{word()}.py::test_{word()}[{word()} {word()}]"
        broken = "\n".join(header() + [
            xdist_progress(0, 50, "FAILED", xdist_node),
            plain_progress(plain_node, "FAILED", 75)]) + "\n"
        parsed = suite_run.parse(False, broken)
        nodes = {node for node, _ in parsed.failures}
        self.assertIn(xdist_node, nodes, self.explain(broken))
        self.assertIn(plain_node, nodes, self.explain(broken))


if __name__ == "__main__":
    unittest.main()
