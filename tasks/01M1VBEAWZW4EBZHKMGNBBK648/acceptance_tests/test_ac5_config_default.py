"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-5 (SPEC.md).

Допущение интерфейса (см. также докстринг `_sandbox.py`): настройка
конфига, включающая режим `--wait-zone` по умолчанию для ВСЕХ вызовов
`auto` без явного флага, — `config.AUTO_WAIT_ZONE_DEFAULT` (bool,
патчится `create=True`, дефолт `False` до реализации имени в
`config.py`). SPEC (требование 1, AC-5) фиксирует ТОЛЬКО наблюдаемое
поведение («настройка включает то же поведение для ВСЕХ вызовов без
флага, значение по умолчанию не меняет сегодняшнее поведение») — не имя;
тест ловит и то, и другое по нему.

Красен до реализации: `test_ac5_config_default_true_enables_wait_without_
explicit_flag` — `auto.cmd_auto` не читает `config.AUTO_WAIT_ZONE_DEFAULT`
вовсе (атрибута ещё нет в `config.py`, патч идёт с `create=True`), поэтому
отказ «ждёт зоны» безусловно останавливает цикл вместо ожидания.

Зелёный с рождения: `test_ac5_default_off_keeps_todays_immediate_stop_
behaviour` — сегодняшнее поведение (без флага, без патча конфига) уже
останавливает цикл немедленно с текстом «ждёт зоны» (часть 2 зон,
`orchestrator/auto.py::_run_zone_wait_refusal`/`config.
AUTO_STOP_ZONE_WAIT`, смержена раньше этой задачи) — тест фиксирует эту
планку как регрессионный барьер: появление `wait_zone`/дефолта из этой
задачи не должно случайно включить ожидание там, где Оператор его не
просил (AC-5, «значение по умолчанию не меняет сегодняшнее поведение»).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (ZoneWaitSandbox, fake_now_sequence,  # noqa: E402
                      only_on_poll_interval)

from orchestrator import auto, config, store  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac5ConfigDefaultEnablesWaitZoneTest(ZoneWaitSandbox):

    def setUp(self):
        super().setUp()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "in_dev", CONFLICT_PATH)
        self.mark_already_started(OCCUPIER)

    def test_ac5_default_off_keeps_todays_immediate_stop_behaviour(self):
        """Значение по умолчанию (без патча, без явного `wait_zone=True`)
        НЕ меняет сегодняшнее поведение — `auto` останавливается на
        первом же отказе «ждёт зоны», не входя в цикл ожидания.

        Ловит мутацию: конфиг по умолчанию включён (`True`) «из коробки»
        — режим ожидания активировался бы для ВСЕХ существующих вызовов
        `auto` без единого действия Оператора, хотя SPEC явно требует
        обратного (AC-5: «значение по умолчанию не меняет сегодняшнее
        поведение»).
        """
        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertIn("ждёт зоны", out.lower())

    def test_ac5_config_default_true_enables_wait_without_explicit_flag(self):
        """`config.AUTO_WAIT_ZONE_DEFAULT = True` включает режим ожидания
        для вызова БЕЗ явного `wait_zone=True` — тот же эффект, что и
        явный флаг: цикл не останавливается на первом отказе, дожидается
        освобождения зоны и запускает роль тем же вызовом.

        Ловит мутацию: `cmd_auto` проверяет ТОЛЬКО переданный аргумент
        `wait_zone`, игнорируя конфигурационную настройку по умолчанию —
        Оператору пришлось бы передавать флаг на КАЖДЫЙ вызов `auto`,
        хотя требование 1 прямо просит настройку, действующую «для всех
        вызовов auto без явного флага».
        """
        def fake_sleep(seconds):
            self.set_task_state(OCCUPIER, "done")

        with mock.patch.object(config, "AUTO_WAIT_ZONE_DEFAULT", True,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_POLL_SEC", 0.001,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 3600,
                              create=True), \
             mock.patch.object(auto.time, "sleep",
                              side_effect=only_on_poll_interval(fake_sleep)), \
             mock.patch.object(store, "now", side_effect=fake_now_sequence()):
            out, popen = self.run_with_fake_agent(
                # Явного wait_zone здесь НЕТ — только настройка конфига.
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION))

        popen.assert_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
