"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-4 (SPEC.md).

Допущения интерфейса — см. докстринг `_sandbox.py`. Потолок ожидания
проверяется без реального многочасового ожидания: `config.
ZONE_WAIT_MAX_SEC` патчится в `0` — истёкшим считается уже самый первый
опрос (`прошло >= 0` истинно всегда), поэтому тест остаётся быстрым
независимо от того, меряет ли реализация elapsed по разнице `store.
now()` или по внутреннему счётчику опросов внутри `auto.cmd_auto`.

Красен до реализации: `config.ZONE_WAIT_MAX_SEC` сегодня не существует
(`AttributeError`, снимается `create=True` патчем ниже), а сам потолок —
не существующая ветка кода: `auto.cmd_auto` не принимает `wait_zone`
вовсе (см. `test_ac1_ac2_ac3_wait_zone_cycle.py`).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneWaitSandbox, fake_now_sequence  # noqa: E402

from orchestrator import auto, config, store  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac4WaitCeilingStopsCycleTest(ZoneWaitSandbox):

    def setUp(self):
        super().setUp()
        self.set_own_zones(CONFLICT_PATH)
        # Держатель НИКОГДА не освобождает зону в этом сценарии — только
        # исчерпанный потолок обязан остановить цикл.
        self.seed_task(OCCUPIER, "Занявшая зону навсегда", "in_dev",
                      CONFLICT_PATH)
        self.mark_already_started(OCCUPIER)

    def test_ac4_exhausted_ceiling_stops_cycle_named_reason_stays_in_dev(self):
        """По истечении `config.ZONE_WAIT_MAX_SEC` цикл останавливается с
        именованной причиной; задача остаётся в `in_dev`, НЕ переводится
        в `escalated` — потолок ожидания зоны не эскалация (SPEC,
        требование 3, буквально).

        Ловит мутацию: потолок не проверяется вовсе (цикл ждёт держателя
        зоны бесконечно — при НИКОГДА не освобождающемся держателе тест
        зависал бы вечно, что для юнита однозначно неверно) — либо
        потолок исчерпан ошибочно уводит задачу в `escalated` вместо
        `in_dev` (спутал бы истечение ожидания зоны с обычной
        эскалацией по бюджету/провалу агента).
        """
        with mock.patch.object(config, "ZONE_WAIT_POLL_SEC", 0.001,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 0, create=True), \
             mock.patch.object(store, "now", side_effect=fake_now_sequence()):
            out, popen = self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION,
                                      wait_zone=True))

        popen.assert_not_called()
        self.assertEqual(
            self.task_state(), "in_dev",
            f"потолок ожидания зоны обязан оставить задачу в in_dev, "
            f"фактическое состояние: {self.task_state()!r}; вывод: {out!r}")
        self.assertIn(
            "потолок", out.lower(),
            f"причина остановки обязана называть исчерпанный потолок "
            f"ожидания буквально (SPEC требование 3 использует именно это "
            f"слово): {out!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
