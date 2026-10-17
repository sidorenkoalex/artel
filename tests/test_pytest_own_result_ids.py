"""Идентификаторы в результатах мест запуска `pytest-own` — в форме от
корня репозитория, хотя pytest работает из `workdir` (SPEC
01M52EEFNA1WH31962HVNT0YZ9, ANSWER-1 п.1-2): узел отчёта двустороннего
прогона, `RedTest.node` у `run_repeat`, id упавших тестов полного набора.
"""
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from orchestrator import acceptance, project_profile, stack, targets
from orchestrator.advance_gates import two_sided
from tests.sandbox import RealGitSandbox

WORKDIR = "backend"
CHECKS = f"{WORKDIR}/checks"
MODULE_REL = f"{CHECKS}/test_probe.py"
# Файл настроек pytest в `workdir`: без явного `--rootdir` корень pytest —
# `workdir`, и id узлов шли бы от него, а не от корня репозитория.
PYTEST_INI = "[pytest]\n"
MODULE = '''import unittest


class ProbeTest(unittest.TestCase):
    def test_probe(self):
        self.assertEqual(1, 2)
'''


def own_profile(command) -> project_profile.Profile:
    return project_profile.Profile(
        command=tuple(command), long_lived_dir=CHECKS,
        long_lived_name="test_<id>_<name>.py",
        weakening_scope=(f"{CHECKS}/**",), mutation_claim_scope=(f"{CHECKS}/**",),
        runner=targets.PROFILE_RUNNER_OWN, workdir=WORKDIR,
        env=MappingProxyType({}))


class PytestOwnResultIdsTest(RealGitSandbox):
    """Учебный проект `pytest-own` с `workdir` ≠ корня и своим `pytest.ini`."""

    def setUp(self):
        super().setUp()
        module = self.root / MODULE_REL
        module.parent.mkdir(parents=True)
        module.write_text(MODULE, encoding="utf-8")
        (self.root / WORKDIR / "pytest.ini").write_text(PYTEST_INI,
                                                         encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "учебный проект")
        self.git("branch", "probe")
        self.base_sha = self.git("rev-parse", "HEAD").strip()
        self.profile = own_profile(
            [stack.pytest_python_executable(), "-m", "pytest"])

    def test_two_sided_verdict_by_method_from_workdir(self):
        """Двусторонний прогон `pytest-own` с `workdir` ≠ корня судит метод.

        Новая и старая версии метода падают на утверждении — обе стороны
        засчитаны по отчёту узла `<путь от корня>::ProbeTest::test_probe`:
        отказов нет, у обеих сторон исход «утверждение».

        Ловит мутацию: узлы отчёта двустороннего прогона остаются в форме
        от `workdir` (нет ни `--rootdir` дерева, ни приведения к корню
        `_root_form`) — вердикт «узел не найден», и отказ рубежа вместо
        доказательства.
        """
        method = two_sided.Method(MODULE_REL, MODULE_REL,
                                  "ProbeTest::test_probe", MODULE, MODULE)
        outcome = two_sided.run(self.root, "probe", self.base_sha, [method],
                                profile=self.profile)
        self.assertEqual([], outcome.refusals)
        self.assertEqual(two_sided.PASSED, outcome.results[method.address])
        sides = outcome.sides[method.address]
        self.assertEqual({two_sided.SIDE_ASSERTION},
                         {side["outcome"] for side in sides.values()})
        self.assertTrue(all(side.get("path") == MODULE_REL
                            for side in sides.values()), sides)

    def test_run_repeat_red_node_from_root(self):
        """`RedTest.node` повтора `pytest-own` — id от корня репозитория.

        Ловит мутацию: `run_repeat` отдаёт узел так, как его назвал pytest
        из `workdir` (`checks/test_probe.py::…` или `classname::name`), —
        имя красного теста расходится с путём долгоживущего файла.
        """
        reds = acceptance.run_repeat([MODULE_REL], self.root,
                                     command=self.profile)
        self.assertEqual([f"{MODULE_REL}::ProbeTest::test_probe"],
                         [red.node for red in reds])

    def test_full_suite_test_ids_passed_untranslated(self):
        """id упавших тестов полного набора (`test_ids`) идут в argv как есть.

        Цели от корня переводятся к `workdir`, а id, напечатанный pytest
        из `workdir`, — нет: он уже в форме, верной из `workdir`.

        Ловит мутацию: `test_ids` переводятся от корня к `workdir`
        (`../checks/…`) или теряются — argv не несёт id в исходной форме.
        """
        failed = "checks/test_probe.py::ProbeTest::test_probe"
        seen = []

        def fake_now(argv, root, *args, **kwargs):
            seen.append((list(argv), Path(root)))
            return True, "1 passed in 0.01s"

        with mock.patch.object(acceptance, "_run_full_suite_now", fake_now):
            acceptance.run_full_suite(self.root, command=self.profile,
                                      targets=(), test_ids=(failed,))
        argv, cwd = seen[0]
        self.assertIn(failed, argv)
        self.assertNotIn(f"../{failed}", argv)
        self.assertEqual(self.root / WORKDIR, cwd)

    def test_full_suite_pult_runner_test_ids_after_targets(self):
        """У раннера пульта `test_ids` идут после целей тем же argv.

        Ловит мутацию: `test_ids` у `pult-pytest` теряются — повтор
        упавших гонял бы пустой набор целей.
        """
        seen = []

        def fake_now(argv, root, *args, **kwargs):
            seen.append(list(argv))
            return True, "1 passed in 0.01s"

        node = "tests/test_x.py::T::test_a"
        (self.root / "tests").mkdir()
        with mock.patch.object(acceptance, "_run_full_suite_now", fake_now):
            acceptance.run_full_suite(self.root, targets=(),
                                      test_ids=(node,))
        self.assertEqual(acceptance._pytest_command(node)
                         + ["-n", str(acceptance.config.FULL_SUITE_WORKERS),
                            "-p", "xdist"], seen[0])
