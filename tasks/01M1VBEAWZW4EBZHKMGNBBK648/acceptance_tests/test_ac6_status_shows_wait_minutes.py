"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-6 (SPEC.md).

`status` — самостоятельный, независимый от `auto` снимок текущего
состояния (`catalog.cmd_status`/`_zone_wait_suffix` уже сегодня читают
`zone_lock.blocking_conflict`/`queue_position` заново на каждый вызов, не
кеш). Тест ловит `cmd_status` РОВНО в момент, когда задача реально
заблокирована И уже находится в цикле ожидания `--wait-zone` — перехватом
точки `time.sleep` внутри самого цикла ожидания (тот же приём, что
`test_ac1_ac2_ac3_wait_zone_cycle.py`), а не подделкой строки журнала
напрямую: реальный источник данных `status` для времени ожидания SPEC не
называет по имени (допущение интерфейса, докстринг `_sandbox.py`), и
подделка не той структуры дала бы ложно зелёный тест, не проверяющий
настоящую реализацию (урок 03.09, skills/test-authoring.md).

Красен до реализации: `catalog.cmd_status` сегодня показывает держателя
зоны и очередь (`_zone_wait_suffix`), но НЕ время ожидания в минутах —
регэксп `\\d+\\s*мин` в строке задачи не находит совпадения; `wait_zone`
у `auto.cmd_auto` тоже ещё не существует (см. соседние файлы).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (ZoneWaitSandbox, fake_now_sequence,  # noqa: E402
                      only_on_poll_interval)

from orchestrator import auto, catalog, config, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac6StatusShowsZoneWaitMinutesTest(ZoneWaitSandbox):

    def setUp(self):
        super().setUp()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "in_dev", CONFLICT_PATH)
        self.mark_already_started(OCCUPIER)

    def test_ac6_status_line_of_blocked_task_names_wait_minutes(self):
        """Пока задача заблокирована зоной, `status` несёт строку с числом
        минут ожидания — добавкой к уже показанному держателю (SPEC,
        требование 4: «добавкой к уже показываемому держателю зоны»).

        Ловит мутацию: `status` продолжает показывать держателя/очередь
        (уже смерженная часть 2, `_zone_wait_suffix`) БЕЗ добавки времени
        ожидания — регэксп ниже не находит числа с «мин» рядом со строкой
        заблокированной задачи, хотя держатель и так уже показан
        (`assertIn(OCCUPIER, ...)` прошёл бы и без фикса, не отличая
        старое поведение от нового).
        """
        captured = []

        def fake_sleep(seconds):
            captured.append(capture(catalog.cmd_status))
            self.set_task_state(OCCUPIER, "done")

        with mock.patch.object(config, "ZONE_WAIT_POLL_SEC", 0.001,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 3600,
                              create=True), \
             mock.patch.object(auto.time, "sleep",
                              side_effect=only_on_poll_interval(fake_sleep)), \
             mock.patch.object(store, "now", side_effect=fake_now_sequence()):
            self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION,
                                      wait_zone=True))

        self.assertEqual(
            len(captured), 1,
            "status не был снят ровно один раз во время ожидания — "
            "проверь, что `time.sleep` цикла ожидания реально вызывался")
        out = captured[0]
        own_line = next(
            (line for line in out.splitlines() if line.startswith(self.TASK)),
            None)
        self.assertIsNotNone(
            own_line, f"строка заблокированной задачи не найдена в status: {out!r}")
        self.assertIn(OCCUPIER, own_line, "держатель зоны обязан остаться в строке")
        self.assertRegex(
            own_line, r"\d+\s*мин",
            f"строка status заблокированной задачи не называет время "
            f"ожидания в минутах: {own_line!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
