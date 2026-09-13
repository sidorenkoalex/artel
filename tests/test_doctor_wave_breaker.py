"""Юнит-тесты первой строки `doctor.cmd_doctor` — стоп-кран волны, часть 2
(tasks/01M1THKRK8HPXA7Y2SRB0RFTN2/SPEC.md, требование 3).

Базовый сценарий (один открытый алерт — первая строка вывода, без алерта
упоминания нет) несёт залоченная приёмочная планка задачи (AC-4); здесь —
случай, который приёмка не кроет: НЕСКОЛЬКО одновременно открытых
алертов стоп-крана — все перечислены, порядок относительно остальных
проверок не меняется. Тот же приём песочницы (`all_checks`/`_orphan_
artifact_branches` замоканы пустышкой), что уже применяет `tests/
test_doctor.py::DoctorCommandTest`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, doctor, store  # noqa: E402
from tests.sandbox import SchemaTmpRootTest, capture  # noqa: E402


class DoctorWaveBreakerFirstLineTest(SchemaTmpRootTest):

    def run_doctor(self) -> str:
        with mock.patch.object(doctor, "_orphan_artifact_branches",
                               return_value=[]), \
                mock.patch.object(doctor, "all_checks", return_value=[]):
            return capture(doctor.cmd_doctor)

    def raise_wave_breaker(self, message: str) -> None:
        opened = alerts.raise_alert(store.db(), config.DEFAULT_TARGET,
                                    "incident", "wave_breaker", message)
        assert opened, "фикстура не смогла завести алерт"

    def test_multiple_open_alerts_are_all_listed_first(self):
        """Два одновременно открытых класса стоп-крана (1б и таймаут) —
        обе строки печатаются до остального вывода, ни одна не потеряна.

        Ловит мутацию: если `cmd_doctor` печатал бы только ПЕРВЫЙ
        найденный алерт (например, `[0]` вместо цикла по списку), второй
        класс пропал бы из вывода бесследно — Оператор не узнал бы о
        втором активном стоп-кране."""
        self.raise_wave_breaker("стоп-кран волны: класс 1б у 3 задач за 15 минут")
        self.raise_wave_breaker("стоп-кран волны: таймаут шага у 3 задач за 15 минут")

        out = self.run_doctor()
        lines = [line for line in out.splitlines() if line.strip()]
        head = "\n".join(lines[:3])

        self.assertIn("стоп-кран", lines[0].lower())
        self.assertIn("1б", head)
        self.assertIn("таймаут", head.lower())

    def test_ack_removes_the_alert_from_the_first_line(self):
        """`alert-ack` снимает строку из первой позиции вывода — тот же
        источник данных (`open_alerts`), что уже проверяет блокировку
        `run`/`auto` (требование 2)."""
        self.raise_wave_breaker("стоп-кран волны: класс 1б у 3 задач за 15 минут")
        alert_id = alerts.open_alerts(store.db(), "incident")[0]["id"]
        alerts.ack(store.db(), alert_id, "operator", "")

        out = self.run_doctor()

        self.assertNotIn("стоп-кран", out.lower())


if __name__ == "__main__":
    unittest.main()
