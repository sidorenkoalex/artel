"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-8(б) (SPEC.md).

Дополняет `test_ac4_wait_ceiling.py`: там потолок (`config.
ZONE_WAIT_MAX_SEC = 0`) исчерпан уже на первом опросе — не отличает
верную реализацию от мутации «потолок сверяется РОВНО один раз, при
входе в ожидание, и никогда не перепроверяется на последующих опросах»
(с потолком `0` оба варианта останавливаются одинаково быстро). Этот файл
даёт потолку истечь ПОСЛЕ нескольких РЕАЛЬНЫХ опросов (не подменяет
`time.sleep`/`store.now()` — оба крошечные, но настоящие) — держатель
зоны здесь тоже никогда не освобождает её, поэтому единственный путь
остановки цикла — именно накопленное реальное время.

Красен до реализации: `wait_zone` у `auto.cmd_auto` не существует
(см. соседние файлы этой задачи); при появлении параметра без
подключённого потолка тест зависает — таймаут юнит-теста снаружи ловит
это как честный красный (`skills/test-authoring.md`: «падать на
отсутствующей пока реализации — нормально»).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneWaitSandbox  # noqa: E402

from orchestrator import auto, config  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"

# Настоящие, но крошечные значения (SPEC называет ИМЕНА констант, не
# значения): несколько настоящих опросов укладываются в десятки
# миллисекунд — тест остаётся быстрым, при этом ни `time.sleep`, ни
# источник времени не подменяются вовсе.
REAL_POLL_SEC = 0.02
REAL_CEILING_SEC = REAL_POLL_SEC * 3.5


class Ac8bCeilingEnforcedAcrossMultiplePollsTest(ZoneWaitSandbox):

    def setUp(self):
        super().setUp()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону навсегда", "in_dev",
                      CONFLICT_PATH)
        self.mark_already_started(OCCUPIER)

    def test_ac8_b_ceiling_stops_cycle_only_after_several_real_polls(self):
        """Потолок ожидания срабатывает по НАКОПЛЕННОМУ времени нескольких
        опросов, не по единственной проверке на входе — держатель никогда
        не освобождает зону, поэтому цикл обязан продержаться МЕНЬШЕ
        секунды (несколько настоящих опросов по `REAL_POLL_SEC`) и
        остановиться сам, без внешнего таймаута.

        Ловит мутацию: потолок сверяется один раз в момент входа в
        ожидание (elapsed всегда `0` на этой проверке) и больше никогда
        не перепроверяется — с постоянно занятой зоной цикл продержался
        бы дольше `REAL_CEILING_SEC` на порядок (завис бы до внешнего
        предохранителя раннера тестов), вместо остановки в пределах
        разумного количества опросов.
        """
        with mock.patch.object(config, "ZONE_WAIT_POLL_SEC", REAL_POLL_SEC,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_MAX_SEC", REAL_CEILING_SEC,
                              create=True):
            out, popen = self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION,
                                      wait_zone=True))

        popen.assert_not_called()
        self.assertEqual(self.task_state(), "in_dev")
        self.assertIn("потолок", out.lower())


if __name__ == "__main__":
    import unittest
    unittest.main()
