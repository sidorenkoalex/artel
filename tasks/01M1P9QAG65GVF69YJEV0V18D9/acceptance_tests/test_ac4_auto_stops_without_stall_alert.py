"""Приёмочные тесты 01M1P9QAG65GVF69YJEV0V18D9 — AC-4 (SPEC.md).

Допущения интерфейса — см. докстринг `_sandbox.py`. AC-4 не называет
внутреннюю точку входа — тест бьёт по наблюдаемому поведению `auto.
cmd_auto` (стдаут + `alerts.open_alerts`), тем же приёмом, что уже
применён к штатной паузе (`orchestrator/auto.py::_run_paused_refusal`,
`config.AUTO_STOP_PAUSE`, `alert=False`) — эта задача вводит для отказа
по зоне симметричную ветку с тем же исходом (остановка без алерта).

Красен до реализации: `auto.cmd_auto` сегодня не отличает отказ по
пересечению зон от любого другого отказа `run` — единственная ветка
`SystemExit` в `_cmd_auto` (`orchestrator/auto.py`, вокруг
`runner.cmd_run(...)`) при не-паузе всегда останавливает цикл с
`alert=True` и текстом «run отказался стартовать» — тест ниже ищет
буквальную фразу «ждёт зоны» в выводе и `len(open_alerts) == 0`, ни то,
ни другое сегодня не выполняется.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneSandbox  # noqa: E402

from orchestrator import alerts, auto, store  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac4AutoStopsWaitingForZoneWithoutStallAlertTest(ZoneSandbox):
    """AC-4: при пересечении `auto` останавливается с причиной «ждёт
    зоны» и не открывает алерт буксования.

    Ловит мутацию: ветка отказа зоны в `_cmd_auto` переиспользует общий
    путь отказа `run` (текст «run отказался стартовать», `alert=True`)
    вместо специальной причины «ждёт зоны» и `alert=False` — тест ловит
    ОБА симптома отдельными assert'ами, так что подмена одного текста
    другим при сохранении алерта (или наоборот) всё равно красит тест.
    """

    def setUp(self):
        super().setUp()
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "in_dev", CONFLICT_PATH)

    def test_ac4_auto_stop_reason_says_waiting_for_zone(self):
        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertIn(
            "ждёт зоны", out.lower(),
            f"auto не назвал причину остановки «ждёт зоны» буквально: {out!r}")

    def test_ac4_auto_stop_on_zone_wait_does_not_raise_stall_alert(self):
        before = len(alerts.open_alerts(store.db(), "attention"))

        self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))

        after = len(alerts.open_alerts(store.db(), "attention"))
        self.assertEqual(
            before, after,
            "auto открыл алерт буксования (kind=attention) при остановке "
            "по ожиданию зоны — SPEC требует остановки без алерта")


if __name__ == "__main__":
    import unittest
    unittest.main()
