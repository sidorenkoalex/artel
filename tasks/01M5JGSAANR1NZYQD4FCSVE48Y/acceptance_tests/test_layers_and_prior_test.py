"""Явное `layers: []` у компонента pytest (AC-21) и прежний тест границы гейта исходов (AC-10).

Группа: разовый
Красен до реализации: `_with_component_fields`/`layers_of` не различают «поля нет» и «поле пусто» — у компонента pytest с `layers: []` действует `python-ast` по умолчанию, правка `.py` файла `test_support` находки строгого режима не даёт (AC-21); метод AC-10 зелёный и на базе ветки — тест прежнего поведения держит его после правок задачи.

AC-21: предмет — находки строгого режима гейта исходов
(`outcome_integrity._strict_findings` с ролями файлов `_Files`): закрытые
функции модуля, сквозной гейт требует прогонов набора на выписках; профиль
— настоящий `project_profile.decide` записи из одного компонента pytest
(`targets.yaml` песочницы `tests.sandbox.TmpRootTest`).

AC-10: тест `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::
Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate`
исполняется загрузчиком `unittest`, а «без правок» — путь файла не среди
путей задачи (`changed_paths` помощника пульта) — факт задачи, поэтому
файл разовый.

Провалидировано временным стабом реализации (удалён, не закоммичен):
признак «поле `layers` задано» в профиле компонента и `layers_of`,
отдающий пусто при явном `layers: []`, — все методы файла зелёные.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

from orchestrator import config, project_profile  # noqa: E402
from orchestrator.advance_gates import outcome_integrity  # noqa: E402
from tests.sandbox import TmpRootTest, make_project_repo  # noqa: E402

PRIOR_FILE = "tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py"
PRIOR_TEST = ("tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate."
              "Ac1OutOfBoundsTest.test_ac1_decide_skip_refusal_and_canary_no_gate")

ENTRY = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    components:
      api:
        command: [python3, -m, pytest]
        report: junit-xml
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [tests/**]
        mutation_claim_scope: [tests/test_*.py]
        failure_errors: [AssertionError]
        tests: [tests/test_*.py]
        test_support: [testkit/**, tests/conftest_*.py]
{layers}"""


class Ac21LayersTest(TmpRootTest):

    def profile(self, name: str, layers: str):
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.rstrip("\n") + "\n" + ENTRY.format(name=name, layers=layers),
            encoding="utf-8")
        make_project_repo(name, origin=False)
        decision = project_profile.decide(name)
        self.assertIsNotNone(decision.profile, decision.refusal)
        return decision.profile

    @staticmethod
    def findings(profile, path: str) -> list:
        files = outcome_integrity._Files(profile, set(), set())
        return outcome_integrity._strict_findings(profile, files,
                                                  [("M", path, None)])

    def test_ac21_explicit_empty_layers_is_strict(self):
        """Компонент pytest с `layers: []`: правка существующего `.py` файла `test_support` — находка `STRICT_EDIT`; без поля `layers` — находки нет.

        Сценарий: две записи из одного компонента pytest, различающиеся
        только полем `layers` (`[]` и отсутствие). Правка (`M`) файлов
        `testkit/helpers.py` и `tests/conftest_db.py` (оба под
        `test_support`).

        Ловит мутацию: `layers: []` читается как «поля нет» (`fields.get(
        "layers") or ()`) — `python-ast` по умолчанию, находки нет;
        признак пустого поля сделан и для отсутствующего — у компонента без
        `layers` появляется находка строгого режима.
        """
        strict = self.profile("strogiy", "        layers: []\n")
        default = self.profile("obychny", "")
        for path in ("testkit/helpers.py", "tests/conftest_db.py"):
            with self.subTest(path=path):
                got = self.findings(strict, path)
                self.assertEqual([(f.kind, f.id) for f in got],
                                 [(outcome_integrity.STRICT_EDIT, path)])
                self.assertEqual(outcome_integrity.STRICT_EDIT,
                                 "строгий режим — правка существующего файла")
                self.assertEqual(self.findings(default, path), [])


class Ac10PriorBoundsTest(unittest.TestCase):

    def test_ac10_prior_outcome_bounds_test_green_unchanged(self):
        """Тест прежней границы гейта исходов не правлен задачей и зелёный.

        Сценарий: путь файла теста не среди путей задачи (правило гейта
        зон); метод `Ac1OutOfBoundsTest.test_ac1_decide_skip_refusal_and_
        canary_no_gate` загружается и исполняется `unittest` — без провалов
        и ошибок.

        Ловит мутацию: прочие записи (`test_profile`, отказ и пропуск
        `decide`, канарейка) получают гейт исходов через `for_task` —
        метод краснеет; задача правит сам тест под новое поведение — путь
        в диффе задачи.
        """
        self.assertNotIn(PRIOR_FILE, changed_paths())
        suite = unittest.defaultTestLoader.loadTestsFromName(PRIOR_TEST)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        self.assertEqual(result.testsRun, 1, stream.getvalue())
        self.assertTrue(result.wasSuccessful(), stream.getvalue())


if __name__ == "__main__":
    unittest.main()
