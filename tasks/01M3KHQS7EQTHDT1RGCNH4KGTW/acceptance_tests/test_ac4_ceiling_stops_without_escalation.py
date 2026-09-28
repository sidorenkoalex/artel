"""Приёмочный тест 01M3KHQS7EQTHDT1RGCNH4KGTW — AC-4 (SPEC.md).

Потолок проверяется без реального многочасового ожидания: `config.
ZONE_WAIT_MAX_SEC` патчится в `0` — исчерпанным он оказывается на первом
же круге опроса независимо от того, сверяет ли реализация накопленный
счётчик до паузы или после неё. Держатель зоны в этом сценарии НИКОГДА её
не освобождает: остановить цикл обязан ровно потолок.

Цикл вызван без флага `--wait-zone` — то есть в ожидание он попадает
настройкой этой задачи, а поведение потолка внутри ожидания остаётся
прежним (требование 2).

Красен до реализации: `config.AUTO_WAIT_ZONE_DEFAULT` сегодня `False`,
вызов без флага останавливается причиной `config.AUTO_STOP_ZONE_WAIT`
(«ждёт зоны») до всякого ожидания — до ветки потолка
(`orchestrator/auto.py:125-129`) исполнение не доходит.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneWaitSandbox, only_on_poll_interval  # noqa: E402

from orchestrator import auto, config  # noqa: E402

CEILING_REASON = "потолок ожидания зоны исчерпан"


class Ac4CeilingStopsCycleTest(ZoneWaitSandbox):

    def test_ac4_exhausted_ceiling_stops_named_and_keeps_the_state(self):
        """Исчерпанный `config.ZONE_WAIT_MAX_SEC` останавливает цикл
        причиной «потолок ожидания зоны исчерпан»; задача остаётся в том
        состоянии, в котором ждала (`in_dev`), в `escalated` не уходит и
        роль не стартует.

        Ловит мутацию: истечение потолка уводит задачу в `escalated`
        (спутано с обычной эскалацией по бюджету/провалу агента) —
        состояние задачи в БД стало бы `escalated`, а Оператор получил бы
        задачу, требующую его ответа, вместо задачи, ждущей чужого мержа.
        """
        with mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 0), \
             mock.patch.object(auto.time, "sleep",
                               side_effect=only_on_poll_interval(
                                   lambda seconds: None)):
            out, popen = self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION))

        self.assertIn(
            CEILING_REASON, out,
            f"цикл остановлен не по исчерпанному потолку ожидания: {out!r}")
        self.assertEqual(
            self.task_state(), "in_dev",
            f"задача не осталась в состоянии, в котором ждала; вывод: {out!r}")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
