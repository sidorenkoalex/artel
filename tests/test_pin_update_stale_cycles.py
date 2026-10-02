"""Юнит-тесты отбора циклов на коде старше пина
(`orchestrator/doctor/stale_cycles.py`, общий с `orchestrator/pin.py`;
SPEC 01M3Y75GCRESC2KDS9VPRJK4PS).

Свойства, не покрытые долгоживущим файлом задачи
(`tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`): чужая машина,
разбор местного времени `ps -o lstart=` и `doctor` без записи пина.
"""
import os
import subprocess
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import config, doctor, store
from tests.sandbox import TmpRootTest


class StaleCyclesSelectionTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.create_schema(self.conn)

    def test_lease_of_another_host_is_not_named(self):
        """Lease с живым pid (этого процесса), но с именем другой машины.

        Ловит мутацию: отбор не сверяет `hostname` lease с этой машиной —
        pid чужой машины проверяется на живость локально и цикл другой
        машины попадает в перечень с командами `stop`/`auto`.
        """
        store.insert_task(self.conn, "01AAAAAAAAAAAAAAAAAAAAAAAA", "t", "in_dev",
                          "task/x", config.DEFAULT_TARGET, 5.0)
        store.insert_lease(self.conn, "01AAAAAAAAAAAAAAAAAAAAAAAA", "s",
                           os.getpid(), "другая-машина.invalid", store.now())

        cycles = doctor.stale_cycles(
            self.conn, datetime.now(timezone.utc) + timedelta(days=1))

        self.assertEqual(cycles, [])

    def test_doctor_without_pin_record_does_not_warn(self):
        """В журнале нет ни одной записи «pin обновлён».

        Ловит мутацию: отсутствие момента пина читается как «пин сколь
        угодно новый» — `doctor` предупреждает о любом живом цикле.
        """
        with mock.patch.object(doctor, "stale_cycles",
                               return_value=[{"task_id": "X"}]) as selection:
            check = doctor.check_stale_cycles(self.conn)

        self.assertEqual(check.status, "ok")
        selection.assert_not_called()


class ProcessStartTimeTest(unittest.TestCase):
    def setUp(self):
        saved = os.environ.get("TZ")

        def restore():
            if saved is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = saved
            time.tzset()

        self.addCleanup(restore)
        os.environ["TZ"] = "Europe/Moscow"
        time.tzset()

    def test_lstart_is_local_time_converted_to_utc(self):
        """`ps -o lstart=` отвечает местным временем машины (UTC+3).

        Ловит мутацию: ответ `ps` читается как UTC (`replace(tzinfo=utc)`)
        — время старта сдвигается на часы, и цикл, загрузивший старый код,
        сравнивается с моментом пина неверно.
        """
        res = subprocess.CompletedProcess([], 0, " Fri Oct  2 15:07:45 2026\n", "")
        with mock.patch.object(doctor.subprocess, "run", return_value=res) as run:
            started = doctor.process_start_time(4242)

        self.assertEqual(started, datetime(2026, 10, 2, 12, 7, 45, tzinfo=timezone.utc))
        argv = run.call_args.args[0]
        self.assertEqual(argv[1:], ["-o", "lstart=", "-p", "4242"])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")


class CycleCommandTest(unittest.TestCase):
    def test_restart_line_is_built_by_cycle_hint(self):
        """Строка `auto` перечня собирается `cycle_hint.cycle_command`.

        Ловит мутацию: `stale_cycle_lines` снова собирает `artel.py auto`
        сам, мимо `cycle_hint` (подменённый `cycle_command` в строку не
        попадает), либо `cycle_command` теряет `--client`/`--chat`
        наблюдения или подставляет их без наблюдения.
        """
        from orchestrator import cycle_hint
        self.assertEqual(cycle_hint.cycle_command("auto", "T1"), "artel.py auto T1")
        self.assertEqual(cycle_hint.cycle_command("auto", "T1", "codex", "c-9"),
                         "artel.py auto T1 --client codex --chat c-9")
        cycle = {"task_id": "T1", "pid": 7, "started": None, "state": "in_dev",
                 "observation_args": ("codex", "c-9")}
        with mock.patch.object(cycle_hint, "cycle_command",
                               return_value="<из cycle_hint>") as built:
            line, = doctor.stale_cycle_lines([cycle])
        built.assert_called_once_with("auto", "T1", "codex", "c-9")
        self.assertTrue(line.endswith("затем <из cycle_hint>"), line)


if __name__ == "__main__":
    unittest.main()
