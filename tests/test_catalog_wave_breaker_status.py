"""Юнит-тесты `orchestrator.catalog._wave_breaker_suffix`/`cmd_status` —
стоп-кран волны, часть 2 (tasks/01M1THKRK8HPXA7Y2SRB0RFTN2/SPEC.md,
требования 4-5).

Сквозной путь через настоящий алерт несёт залоченная приёмочная планка
задачи (AC-5/AC-7); здесь — сама пометка в изоляции: чистая функция
`_wave_breaker_suffix` (тем же приёмом, что `tests/test_pause.py` уже
применяет к `pause.is_paused`) плюс один smoke-тест `cmd_status`,
подтверждающий, что пометка реально попадает в печатаемую строку.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import BudgetSeededTmpRootTest, capture  # noqa: E402

OTHER_TARGET = "sled"


class WaveBreakerSuffixTest(unittest.TestCase):
    """`_wave_breaker_suffix` — без обращения к БД: (task_row, bool) -> str."""

    def row(self, target: str | None = config.DEFAULT_TARGET) -> dict:
        return {"target": target}

    def test_empty_when_no_alert_open(self):
        self.assertEqual(catalog._wave_breaker_suffix(self.row(), False), "")

    def test_marked_when_alert_open_and_target_self(self):
        suffix = catalog._wave_breaker_suffix(self.row(), True)

        self.assertIn("СТОП-КРАН", suffix)

    def test_marked_when_target_is_null_defaulting_to_self(self):
        """`target=None` в строке БД — тот же self, что и явный
        `config.DEFAULT_TARGET` (соглашение остальных мест кода,
        например `runner._cmd_run`)."""
        suffix = catalog._wave_breaker_suffix(self.row(target=None), True)

        self.assertIn("СТОП-КРАН", suffix)

    def test_empty_for_foreign_target_even_if_alert_open(self):
        """Ловит мутацию: если сверку `target` уберут, задача внешнего
        target получила бы ту же пометку, что и self (требование 5)."""
        suffix = catalog._wave_breaker_suffix(self.row(target=OTHER_TARGET), True)

        self.assertEqual(suffix, "")


class CmdStatusWaveBreakerMarkTest(BudgetSeededTmpRootTest):
    """Smoke: пометка реально доходит до печатаемой строки `cmd_status`."""

    def line_for(self, task_id: str, out: str) -> str:
        return next(line for line in out.splitlines()
                    if line.strip().startswith(task_id))

    def test_status_marks_the_task_while_alert_open(self):
        from orchestrator import alerts
        alerts.raise_alert(store.db(), config.DEFAULT_TARGET, "incident",
                           "wave_breaker",
                           "стоп-кран волны: класс 1б у 3 задач за 15 минут")

        out = capture(catalog.cmd_status)

        self.assertIn("СТОП-КРАН", self.line_for(self.TASK, out))

    def test_status_does_not_mark_without_an_open_alert(self):
        out = capture(catalog.cmd_status)

        self.assertNotIn("СТОП-КРАН", self.line_for(self.TASK, out))


if __name__ == "__main__":
    unittest.main()
