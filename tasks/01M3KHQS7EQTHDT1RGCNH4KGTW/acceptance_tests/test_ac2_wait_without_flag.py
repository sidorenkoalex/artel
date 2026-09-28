"""Приёмочный тест 01M3KHQS7EQTHDT1RGCNH4KGTW — AC-2 (SPEC.md).

Сценарий (см. `_sandbox.py`): зона задачи занята другой задачей, цикл
`auto` вызван БЕЗ флага `--wait-zone` и БЕЗ подмены
`config.AUTO_WAIT_ZONE_DEFAULT` — ровно та комбинация, которую называет
критерий.

Красен до реализации: `config.AUTO_WAIT_ZONE_DEFAULT` сегодня `False`
(`orchestrator/config.py:756`), поэтому `auto._role_run_step` на отказе
занятости зоны останавливает цикл причиной `config.AUTO_STOP_ZONE_WAIT`
— записи входа в ожидание в журнале не появляется вовсе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (CONFLICT_PATH, OCCUPIER,  # noqa: E402
                      ZoneWaitSandbox, only_on_poll_interval)

from orchestrator import auto, config, zone_lock  # noqa: E402


class Ac2WaitWithoutFlagTest(ZoneWaitSandbox):

    def test_ac2_busy_zone_without_flag_enters_waiting_not_stop(self):
        """Вызов `auto` без флага на занятой зоне уходит в ожидание:
        журнал задачи несёт запись входа `zone_lock.wait_enter_action`
        («ждёт зоны <путь>: держит <id> (<состояние>)»), и остановки
        цикла причиной `config.AUTO_STOP_ZONE_WAIT` нет ни одной.

        Ловит мутацию: ветка `orchestrator/auto.py:938` сужена обратно до
        `if wait_zone:` (значение настройки в `config.py` поднято, но
        цикл его больше не читает) — вызов без флага снова остановился бы
        немедленно: записи «ждёт зоны <путь>…» в журнале нет, зато есть
        запись остановки «<состояние>: ждёт зоны», и подменённый агент не
        зовётся ни разу.
        """
        def fake_sleep(seconds):
            # Первый же опрос цикла ожидания застаёт зону освобождённой —
            # держатель ушёл из блокирующей фазы.
            self.release_zone()

        with mock.patch.object(auto.time, "sleep",
                               side_effect=only_on_poll_interval(fake_sleep)):
            out, popen = self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION))

        expected = zone_lock.wait_enter_action(CONFLICT_PATH, OCCUPIER,
                                               "in_dev")
        self.assertIn(
            expected, self.wait_enter_actions(),
            f"журнал задачи не несёт записи входа в ожидание зоны "
            f"{expected!r}; вывод цикла: {out!r}")
        self.assertEqual(
            self.zone_wait_stop_rows(), [],
            f"цикл остановлен причиной {config.AUTO_STOP_ZONE_WAIT[0]!r} "
            f"вместо ожидания зоны; вывод цикла: {out!r}")
        popen.assert_called()


if __name__ == "__main__":
    unittest.main()
