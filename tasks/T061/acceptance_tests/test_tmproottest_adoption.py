"""Приёмочные тесты T061 — AC-3 (SPEC.md, «Критерии приёмки»):

Шесть файлов, перечисленных в требовании 3, наследуются от
`sandbox.TmpRootTest` (либо используют его полный набор путей); ручного
частичного патчинга `config` в них нет.

Подход — как `tasks/T037/acceptance_tests/test_sandbox.py`
(`SandboxDefaultPatchesCoverAllConfigPathsTest`): не грепать код на
конкретную форму цикла `mock.patch.object` (некоторые из этих файлов
оборачивают патч в свой хелпер-метод — статическая проверка текста тела
`setUp` такое пропустит), а поведенчески доказать, что после `setUp`
патчится ПОЛНЫЙ набор `sandbox.ALL_CONFIG_ATTRS`, а не подмножество —
именно это и означает «переход на TmpRootTest с полным набором путей».
Точечные однократные оверрайды внутри ОТДЕЛЬНЫХ тестовых методов (не в
`setUp`) — легитимный приём для симуляции сбоя (например, битый ROOT в
`tests/test_fsm_retro.py`) и не то, что запрещает требование 3 — эта
проверка их не трогает, потому что запускает только `setUp`, не сами
тестовые методы.
"""
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# файл (модуль tests.*) -> класс-песочница, вокруг которого построен файл
# (SPEC требование 3, перечисление шести файлов).
TARGET_CLASSES = {
    "tests.test_brief": "BriefUnitTest",
    "tests.test_fsm_map_regen": "RegenerateAndCommitMapTest",
    "tests.test_fsm_retro": "GenerateAndCommitRetroTest",
    "tests.test_fsm_branch_correct_status_reads": "RealGitBranchTest",
    "tests.test_gitcmd_branch_reads": "RealGitSandbox",
    "tests.test_retro": "RetroGenerationTest",
}


def _run_setup_only(test_cls):
    """Запускает `setUp`/`tearDown`/`addCleanup` реального класса через
    пустой тестовый метод — тот же приём, что `_Probe` в
    `tasks/T037/acceptance_tests/test_sandbox.py`."""
    probe = {}

    class _Probe(test_cls):
        def test_probe(self):
            from orchestrator import config
            probe["observed"] = {
                attr: getattr(config, attr) for attr in sandbox.ALL_CONFIG_ATTRS}

    case = _Probe("test_probe")
    result = unittest.TestResult()
    case.run(result)
    return result, probe.get("observed")


sandbox = importlib.import_module("tests.sandbox")


class SixFilesInheritTmpRootTestTest(unittest.TestCase):
    """AC-3: наследование `sandbox.TmpRootTest` — структурная часть."""

    def test_ac3_all_six_sandbox_classes_subclass_tmproottest(self):
        not_subclassed = []
        for module_name, class_name in TARGET_CLASSES.items():
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            if not issubclass(cls, sandbox.TmpRootTest):
                not_subclassed.append(f"{module_name}.{class_name}")

        self.assertEqual(
            not_subclassed, [],
            f"классы не наследуют sandbox.TmpRootTest: {not_subclassed}")


class SixFilesPatchTheFullConfigAttrSetTest(unittest.TestCase):
    """AC-3: после `setUp` патчится ПОЛНЫЙ набор `ALL_CONFIG_ATTRS`, не
    подмножество — поведенческое доказательство отсутствия точечного
    частичного патчинга."""

    def test_ac3_all_six_sandboxes_patch_every_config_attr(self):
        from orchestrator import config

        originals = {attr: getattr(config, attr) for attr in sandbox.ALL_CONFIG_ATTRS}
        problems = {}

        for module_name, class_name in TARGET_CLASSES.items():
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)

            result, observed = _run_setup_only(cls)

            if result.errors:
                problems[f"{module_name}.{class_name}"] = (
                    f"setUp упал: {result.errors}")
                continue

            unpatched = [attr for attr in sandbox.ALL_CONFIG_ATTRS
                        if observed[attr] == originals[attr]]
            if unpatched:
                problems[f"{module_name}.{class_name}"] = (
                    f"не патчит config.{unpatched} — частичный набор "
                    f"путей вместо sandbox.ALL_CONFIG_ATTRS")

        self.assertEqual(
            problems, {},
            f"песочницы шести файлов не патчат полный набор путей "
            f"config: {problems}")


if __name__ == "__main__":
    unittest.main()
