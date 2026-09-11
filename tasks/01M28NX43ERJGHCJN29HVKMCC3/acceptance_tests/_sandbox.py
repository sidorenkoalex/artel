"""Тонкая надстройка `LightTransitionSandbox` (tests/sandbox.py) для планки
задачи 01M28NX43ERJGHCJN29HVKMCC3 — только `write_spec`/`write_acceptance_tests`/
`enter_tests_writing`, специфичные сценарию (маркер AC-n с отступом внутри
`acceptance_tests/` ВЛОЖЕННОЙ синтетической задачи-песочницы, не этой самой
задачи). `disk_backed_*`/`advance_from_in_dev` не переопределяются —
импортируются готовыми (skills/test-authoring.md, «Лёгкая песочница
переходов»).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests.sandbox import LightTransitionSandbox  # noqa: E402


class AcMarkerIndentSandbox(LightTransitionSandbox):
    """Песочница для транзишна `tests_writing -> in_dev` вложенной
    синтетической задачи: `self.TASK`/`self.tdir` заведены
    `LightTransitionSandbox.setUp` (реальный `catalog.cmd_new`), здесь
    только запись SPEC.md/acceptance_tests/ этой вложенной задачи на
    диск и перевод её в состояние `tests_writing`."""

    def write_spec(self, text: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            text.format(task=self.TASK), encoding="utf-8")

    def write_acceptance_tests(self, content: str,
                               name: str = "test_x.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def enter_tests_writing(self, spec_text: str) -> None:
        self.write_spec(spec_text)
        self.set_state("tests_writing")
