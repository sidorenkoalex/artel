"""Приёмочный тест 01M3KHQS7EQTHDT1RGCNH4KGTW — AC-3 (SPEC.md).

Две половины критерия: флаг `--wait-zone` остаётся ДОПУСТИМЫМ (разбор
`orchestrator/artel.py` не отказывает и доводит до `auto.cmd_auto(...,
wait_zone=True)`) и тот же цикл, вызванный С флагом, ведёт себя так же,
что и без него, — уходит в ожидание, а не в остановку.

Зелёный с рождения: и флаг, и режим ожидания по нему существуют с задачи
01M1VBEAWZW4EBZHKMGNBBK648 — этот файл держит их от снятия «за
ненадобностью» при включении настройки по умолчанию (требование 3: флаг
сохраняется и при включённой настройке ничего не меняет).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (CONFLICT_PATH, OCCUPIER,  # noqa: E402
                      ZoneWaitSandbox, only_on_poll_interval)

from orchestrator import artel, auto, config, zone_lock  # noqa: E402

WAIT_ZONE_FLAG = "--wait-zone"


class Ac3FlagIsStillAcceptedTest(unittest.TestCase):
    """Разбор аргументов команды `auto` — без БД и без цикла: путь
    `--attach` зовёт `auto.cmd_auto` прямо, и предмет здесь именно он."""

    def test_ac3_flag_is_parsed_without_refusal_and_reaches_cmd_auto(self):
        """`auto <id> --wait-zone` разбирается без отказа и доходит до
        `auto.cmd_auto` с `wait_zone=True`.

        Ловит мутацию: `--wait-zone` снят из `_CYCLE_FLAGS_AUTO`
        (`orchestrator/artel.py:587`) как ставший лишним при включённой
        настройке — разбор объявил бы его неизвестным флагом и завершил
        команду `SystemExit`, так что `cmd_auto` не вызвалась бы вовсе;
        либо проброс `wait_zone` выброшен из `_cmd_auto_or_detach` —
        тогда вызов дошёл бы без `wait_zone=True`.
        """
        with mock.patch.object(artel.auto, "cmd_auto") as cmd_auto:
            artel._cmd_auto_or_detach(["01M3KHQS7EQTHDT1RGCNH4KGTW",
                                       "--attach", WAIT_ZONE_FLAG])

        cmd_auto.assert_called_once()
        self.assertIs(
            cmd_auto.call_args.kwargs.get("wait_zone"), True,
            f"cmd_auto вызвана без wait_zone=True: {cmd_auto.call_args!r}")


class Ac3CycleWithFlagWaitsTest(ZoneWaitSandbox):

    def test_ac3_cycle_called_with_the_flag_enters_waiting_too(self):
        """Тот же сценарий занятой зоны, что и у AC-2, но цикл вызван С
        флагом: поведение то же — запись входа в ожидание в журнале,
        остановки причиной `config.AUTO_STOP_ZONE_WAIT` нет, роль
        стартует тем же вызовом после освобождения зоны.

        Ловит мутацию: параметр `wait_zone` удалён из `auto.cmd_auto` как
        избыточный при включённой настройке — вызов с ним упал бы
        `TypeError: cmd_auto() got an unexpected keyword argument
        'wait_zone'`, и команда `auto <id> --wait-zone`, которую
        требование 3 обязывает сохранить, перестала бы работать.
        """
        def fake_sleep(seconds):
            self.release_zone()

        with mock.patch.object(auto.time, "sleep",
                               side_effect=only_on_poll_interval(fake_sleep)):
            out, popen = self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION,
                                      wait_zone=True))

        expected = zone_lock.wait_enter_action(CONFLICT_PATH, OCCUPIER,
                                               "in_dev")
        self.assertIn(
            expected, self.wait_enter_actions(),
            f"вызов с флагом не вошёл в ожидание зоны; вывод: {out!r}")
        self.assertEqual(
            self.zone_wait_stop_rows(), [],
            f"вызов с флагом остановлен причиной "
            f"{config.AUTO_STOP_ZONE_WAIT[0]!r}; вывод: {out!r}")
        popen.assert_called()


if __name__ == "__main__":
    unittest.main()
