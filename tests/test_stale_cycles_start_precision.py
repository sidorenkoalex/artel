"""Юнит-тесты погрешности времени старта процесса цикла в отборе циклов на
коде старше пина (`orchestrator/doctor/stale_cycles.py`; SPEC
01M3YQB4KMADY0BET5N8279N6B).

Свойства, не покрытые долгоживущим файлом задачи
(`tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`): сценарий
огрублённого ответа `ps -o lstart=` на уровне отбора без git и часов
песочницы, арифметика точного источника `/proc` (на macOS — подменой
таблицы и часов) и границы интервала старта.
"""
import contextlib
import os
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import config, doctor, store
from tests.sandbox import TmpRootTest

# Фасад doctor переэкспортирует функцию `stale_cycles` под именем модуля —
# сам модуль берётся из `sys.modules`.
selection = sys.modules["orchestrator.doctor.stale_cycles"]

TASK_ID = "01AAAAAAAAAAAAAAAAAAAAAAAA"


def lstart_answer(moment: datetime) -> subprocess.CompletedProcess:
    """Ответ `ps -o lstart=` под `LC_ALL=C`: местное время, до секунды."""
    local = moment.astimezone()
    text = f"{local:%a %b} {local.day:2d} {local:%H:%M:%S %Y}\n"
    return subprocess.CompletedProcess([], 0, text, "")


class LiveCycleMixin:
    """Lease этой машины с живым pid (этого процесса) и его задача."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.create_schema(self.conn)
        store.insert_task(self.conn, TASK_ID, "t", "in_dev", "task/x",
                          config.DEFAULT_TARGET, 5.0)
        store.insert_lease(self.conn, TASK_ID, "s", os.getpid(),
                           socket.gethostname(), store.now())


class LstartTwoSecondsEarlyTest(LiveCycleMixin, TmpRootTest):
    def test_lstart_two_seconds_early_after_shift_is_not_named_silently(self):
        """Цикл стартовал через 0,2 с после сдвига пина, ровно на границе
        секунды, точного источника нет, а `ps -o lstart=` отдаёт старт так,
        как его огрубляет Linux, — на 2 с раньше настоящего, то есть
        раньше сдвига.

        Цикл либо не назван, либо назван с пометкой «время старта не
        различимо от сдвига» — в отборе (`borderline`) и в строке перечня.

        Ловит мутацию: отбор сравнивает с моментом сдвига голый ответ `ps`
        (`lstart < pin_moment` — значит старый) и называет цикл без
        пометки; либо пометка вычислена, но строка перечня её теряет.
        """
        real_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
        pin_moment = real_start - timedelta(seconds=0.2)
        coarse = real_start - timedelta(seconds=2)

        with mock.patch.object(selection, "_proc_start_interval", return_value=None), \
                mock.patch.object(doctor.subprocess, "run",
                                  return_value=lstart_answer(coarse)):
            cycles = doctor.stale_cycles(self.conn, pin_moment)

        for cycle in cycles:
            self.assertTrue(cycle["borderline"], cycle)
            line, = doctor.stale_cycle_lines([cycle])
            self.assertIn(selection.START_BORDERLINE, line)


class ProcStartIntervalTest(unittest.TestCase):
    """Точный источник Linux, разыгранный подменой таблицы и часов."""

    HZ = 100
    BOOT = 1_790_000_000.25  # момент загрузки с дробной секундой
    TICKS = 123_456

    @contextlib.contextmanager
    def linux_proc(self, stat_text: str):
        """Linux с таблицей `/proc`, где `/proc/4242/stat` — `stat_text`."""
        def fake_open(path, *args, **kwargs):
            self.assertEqual(path, "/proc/4242/stat")
            return mock.mock_open(read_data=stat_text)()

        now = self.BOOT + 50_000.0
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(time, "CLOCK_BOOTTIME", 7, create=True), \
                mock.patch("builtins.open", fake_open), \
                mock.patch.object(os, "sysconf", return_value=self.HZ), \
                mock.patch.object(time, "time", return_value=now), \
                mock.patch.object(time, "clock_gettime",
                                  return_value=now - self.BOOT):
            yield

    def test_proc_start_has_subsecond_precision_without_btime(self):
        """`/proc/<pid>/stat` с именем команды, несущим пробел и `)`.

        Интервал старта накрывает настоящий старт (загрузка + тики /
        `CLK_TCK`), а оба его края отстоят от него не больше чем на 0,1 с.

        Ловит мутацию: момент загрузки берётся отброшенным до целой
        секунды (`btime`) — интервал уходит от настоящего старта на
        0,25 с; либо поле `starttime` берётся по счёту от начала строки и
        имя команды с пробелом сдвигает его; либо тики делятся не на
        `CLK_TCK`.
        """
        fields = ["S"] + ["0"] * 18 + [str(self.TICKS), "999", "888"]
        with self.linux_proc(f"4242 (artel ) py) {' '.join(fields)}\n"):
            interval = selection.start_interval(4242)

        real = datetime.fromtimestamp(self.BOOT + self.TICKS / self.HZ, timezone.utc)
        self.assertIsNotNone(interval)
        lo, hi = interval
        self.assertLessEqual(lo, real)
        self.assertGreater(hi, real)
        self.assertLessEqual(real - lo, timedelta(seconds=0.1))
        self.assertLessEqual(hi - real, timedelta(seconds=0.1))

    def test_unreadable_proc_falls_back_to_lstart(self):
        """Таблица `/proc` отвечает неразборчиво — источником служит
        `ps -o lstart=`, интервал `[ответ, ответ + 2 с)`.

        Ловит мутацию: сбой разбора `/proc` не перехвачен (исключение
        уходит в `pin-update` после сдвига пина) либо время считается
        неопределимым, хотя `ps` ответил.
        """
        answer = datetime(2026, 10, 2, 12, 0, 1, tzinfo=timezone.utc)
        with self.linux_proc("4242 (artel) S мусор\n"), \
                mock.patch.object(doctor.subprocess, "run",
                                  return_value=lstart_answer(answer)):
            interval = selection.start_interval(4242)

        self.assertEqual(interval, (answer, answer + timedelta(seconds=2)))


class IntervalBoundaryTest(LiveCycleMixin, TmpRootTest):
    def classify(self, lo: datetime, hi: datetime, pin_moment: datetime):
        with mock.patch.object(selection, "start_interval", return_value=(lo, hi)):
            return doctor.stale_cycles(self.conn, pin_moment)

    def test_interval_edges_against_pin_moment(self):
        """Четыре положения интервала старта относительно сдвига.

        Начало интервала ровно в момент сдвига — «новый», не назван;
        конец ровно в момент сдвига (ответ `ps` + 2 с не раньше сдвига) —
        «пограничный»; конец раньше сдвига — «старый» без пометки,
        в строке время старта — начало интервала.

        Ловит мутацию: «новым» считается цикл, у которого раньше сдвига
        лишь конец интервала (пограничный выпадает молча); либо граница
        `>=` перевёрнута в `>` и цикл, начавшийся ровно в момент сдвига,
        назван; либо «старый» цикл получает пометку.
        """
        pin = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
        sec = timedelta(seconds=1)

        self.assertEqual(self.classify(pin, pin + 2 * sec, pin), [])

        border, = self.classify(pin - 2 * sec, pin, pin)
        self.assertTrue(border["borderline"])

        old, = self.classify(pin - 3 * sec, pin - sec, pin)
        self.assertFalse(old["borderline"])
        self.assertEqual(old["started"], pin - 3 * sec)
        line, = doctor.stale_cycle_lines([old])
        self.assertNotIn(selection.START_BORDERLINE, line)
        self.assertIn("2026-10-02 11:59:57Z", line)


if __name__ == "__main__":
    unittest.main()
