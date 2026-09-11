"""Приёмочные тесты 01M1THKRK8HPXA7Y2SRB0RFTN2 — AC-5 (SPEC.md).

Красен до реализации: `catalog.cmd_status` сейчас не читает
`kind=incident` алерты стоп-крана вовсе — строки задач target self не
несут никакой пометки про стоп-кран, поэтому `mentions_stop_crane(...)`
по каждой из них не совпадёт. Второй тест файла
(`test_ac5_no_open_alert_marks_no_task`) — зелёный уже сегодня (без
алерта помечать нечего), это база сравнения для первого.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (LightSandbox, capture, catalog,  # noqa: E402
                      config, mentions_stop_crane, raise_stop_crane_alert,
                      store)


class Ac5StatusMarksEverySelfTaskTest(LightSandbox):
    """AC-5: `status` несёт пометку у КАЖДОЙ задачи target self, пока
    алерт стоп-крана открыт — блокирует весь target, не только задачи,
    вызвавшие срабатывание."""

    OTHER_SELF_TASK = "T002"

    def setUp(self):
        super().setUp()
        # Вторая задача target self, никак не связанная с тем, что реально
        # вызвало срабатывание стоп-крана — требование 4/AC-5 явно про ВЕСЬ
        # target, не только про виновные задачи.
        store.insert_task(store.db(), self.OTHER_SELF_TASK,
                          "Вторая self задача, не виновник срабатывания",
                          "review", "task/t002-vtoraya",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def status_lines_by_task(self) -> dict:
        out = capture(catalog.cmd_status)
        lines = {}
        for line in out.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            task_id = stripped.split()[0]
            lines[task_id] = line
        return lines

    def test_ac5_every_self_task_is_marked_while_alert_open(self):
        """Обе задачи target self несут пометку стоп-крана в `status`,
        хотя алерт связан лишь с фактом волны отказов, а не с этими
        конкретными задачами.

        Ловит мутацию: если пометка навешивается только на задачу,
        буквально упомянутую сообщением алерта (или вообще ни на одну),
        строка второй/обеих задач не будет содержать слово «стоп-кран».
        """
        raise_stop_crane_alert(store.db())

        lines = self.status_lines_by_task()

        self.assertTrue(mentions_stop_crane(lines[self.TASK]),
                       f"строка {self.TASK} не помечена: {lines[self.TASK]!r}")
        self.assertTrue(mentions_stop_crane(lines[self.OTHER_SELF_TASK]),
                       f"строка {self.OTHER_SELF_TASK} не помечена: "
                       f"{lines[self.OTHER_SELF_TASK]!r}")

    def test_ac5_no_open_alert_marks_no_task(self):
        """Без открытого алерта стоп-крана ни одна строка `status` не
        несёт эту пометку — базовая линия, отличающая предыдущий тест от
        пометки, печатаемой безусловно.

        Ловит мутацию: если пометку станут печатать всегда (не проверяя
        реально ли алерт открыт), она останется и здесь.
        """
        lines = self.status_lines_by_task()

        self.assertFalse(mentions_stop_crane(lines[self.TASK]))
        self.assertFalse(mentions_stop_crane(lines[self.OTHER_SELF_TASK]))


if __name__ == "__main__":
    import unittest
    unittest.main()
