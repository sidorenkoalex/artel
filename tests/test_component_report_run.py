"""Узлы итога из отчёта компонента вне долгоживущего файла задачи 01M590GJAF0EDV4NBC4C99MFVH.

Разбор JUnit без атрибута `file` (форма pytest), вердикт по коду возврата
при отчёте без падений, перевод id упавших `suite-run --failed` в пути
подмножества, решающий исход узла по компонентам и заголовок отчёта
`suite-run` для исхода «неизвестно». Без песочницы и без git: чистые
функции и подменённый `acceptance.full_suite`.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, project_profile, suite_run
from orchestrator.reporters import outcome

JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
         '<testsuite name="pytest" tests="2">'
         '<testcase classname="tests.test_x.T" name="test_a" time="0.5"/>'
         '<testcase classname="tests.test_x.T" name="test_b" time="0.25">'
         '<failure message="boom">AssertionError: boom</failure></testcase>'
         '</testsuite></testsuites>')


def profile(name: str, **extra) -> project_profile.Profile:
    return project_profile.Profile(
        command=("./run",), long_lived_dir="", long_lived_name="",
        weakening_scope=(), mutation_claim_scope=(), report="junit-xml",
        component=name, project="p", from_components=True, **extra)


class JunitPytestFormTest(unittest.TestCase):

    def test_dotted_classname_maps_to_file_and_class(self):
        """Отчёт pytest без `file`: точечный `classname` — файл, найденный в `cwd`, и класс; путь id — от корня с `workdir`.

        Ловит мутацию: точечный `classname` берётся путём как есть
        (`comp:wd/tests.test_x.T::test_a`) либо класс теряется из имени.
        """
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "tests").mkdir()
            (cwd / "tests" / "test_x.py").write_text("", encoding="utf-8")
            report = cwd / "r.xml"
            report.write_text(JUNIT, encoding="utf-8")
            records, reason = outcome.parse_junit(report, "comp", "wd", cwd)
        self.assertEqual(reason, "")
        self.assertEqual([(r.id, r.outcome) for r in records],
                         [("comp:wd/tests/test_x.py::T::test_a", "passed"),
                          ("comp:wd/tests/test_x.py::T::test_b", "failed")])
        self.assertEqual(records[1].failure, "boom")


class VerdictTest(unittest.TestCase):

    def test_nonzero_code_with_clean_report_is_unknown(self):
        """Ненулевой код возврата при отчёте без упавших тестов — «неизвестно», а не зелёный; упавший тест — красный при любом коде.

        Ловит мутацию: вердикт читает только записи отчёта — сбой раннера
        вне тестов отчёта (код 1 при зелёном отчёте) даёт зелёный итог.
        """
        green = [outcome.CaseResult("c:a::t", outcome.PASSED)]
        red = [outcome.CaseResult("c:a::t", outcome.FAILED, "AssertionError")]
        self.assertEqual(outcome.verdict(green, 1)[0], outcome.UNKNOWN)
        self.assertEqual(outcome.verdict(green, 0)[0], outcome.GREEN)
        self.assertEqual(outcome.verdict(red, 0)[0], outcome.RED)
        self.assertEqual(outcome.verdict(red, 1)[0], outcome.RED)


class FailedIdsSubsetTest(unittest.TestCase):

    def test_own_component_ids_become_file_paths(self):
        """`suite-run --failed`: id упавших своего компонента — пути их файлов (без повторов), прочие цели — как есть; полный прогон — `None`.

        Ловит мутацию: id `<компонент>:<путь>::<имя>` уходит раннеру как
        есть (раннер его не найдёт) либо полный прогон читается как
        подмножество.
        """
        comp = profile("web")
        ids = ("web:fe/src/a.test.js::t one", "web:fe/src/a.test.js::t two",
               "other:fe/src/b.test.js::t", "fe/src/c.test.js")
        self.assertEqual(acceptance._report_subset(comp, ids, ()),
                         ["fe/src/a.test.js", "other:fe/src/b.test.js::t",
                          "fe/src/c.test.js"])
        self.assertEqual(acceptance._report_subset(comp, (), ids[:1]),
                         ["fe/src/a.test.js"])
        self.assertIsNone(acceptance._report_subset(comp, ("tests",), ()))


class ComponentsFullSuiteTest(unittest.TestCase):

    def run_with(self, outcomes: dict):
        """Итог узла по компонентам при подменённом `full_suite`: исход
        каждого компонента — по имени."""
        def fake(root, task_id, command=None, fresh=False):
            green, value, detail = outcomes[command.component]
            return acceptance.FullSuiteRun(green, value, "", None, detail)
        with mock.patch.object(acceptance, "full_suite", fake):
            return acceptance.components_full_suite(
                Path("/nonexistent"), "T1",
                tuple(profile(name) for name in outcomes))

    def test_green_only_if_all_green_and_unknown_decides_before_red(self):
        """Узел по компонентам зелёный, только если зелены все; «неизвестно» решает раньше красного и стоит первой строкой детали.

        Ловит мутацию: итог узла — по последнему компоненту либо красный
        компонент перекрывает «неизвестно», и `approve --accept-red` принял
        бы прогон с неизвестным итогом.
        """
        green = (True, acceptance.FULL_SUITE_GREEN, "зелёный")
        red = (False, acceptance.FULL_SUITE_RED, "красный")
        unknown = (False, acceptance.FULL_SUITE_NOT_STARTED,
                   acceptance.unknown_line("отчёта нет"))
        self.assertTrue(self.run_with({"a": green, "b": green}).green)
        self.assertFalse(self.run_with({"a": green, "b": red}).green)
        run = self.run_with({"a": red, "b": unknown})
        self.assertFalse(run.green)
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_NOT_STARTED)
        self.assertTrue(acceptance.is_unknown(run), run.detail)
        self.assertIn("компонент a: красный", run.detail)


class SuiteRunUnknownTitleTest(unittest.TestCase):

    def test_unknown_outcome_is_named_in_report_title(self):
        """Отчёт `suite-run` на исходе «неизвестно» называет его и причину, а не «прогон не начат».

        Ловит мутацию: разбор `suite-run` не различает «неизвестно» и «не
        начат» — заголовок отчёта роли советует ждать, а не читать лог.
        """
        output = (f"{acceptance.unknown_line('отчёт /tmp/r.xml не создан')}\n"
                  f"1 passed in 0.01s\n")
        parsed = suite_run.parse(False, output)
        self.assertEqual(parsed.outcome, acceptance.FULL_SUITE_NOT_STARTED)
        head = suite_run.render("T1", 2, suite_run.MODE_FULL, parsed, None,
                                "база", Path("/tmp/l.log")).splitlines()[0]
        self.assertIn("неизвестно", head)
        self.assertIn("отчёт /tmp/r.xml не создан", head)


if __name__ == "__main__":
    unittest.main()
