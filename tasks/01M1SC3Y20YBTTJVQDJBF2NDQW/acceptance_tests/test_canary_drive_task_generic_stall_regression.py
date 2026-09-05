"""Приёмочный тест AC-7 (SPEC 01M1SC3Y20YBTTJVQDJBF2NDQW): стагнация
`canary._drive_task` БЕЗ записи `agent run SKIPPED` в журнале
по-прежнему упирается в полный `CANARY_MAX_STALL_ITERS` — та же гарантия,
что и существующий `tests/test_canary.py::DriveTaskStallCapTest`, здесь
воспроизведена отдельно как защита ИМЕННО от побочного эффекта AC-3/AC-6
(`test_canary_drive_task_skip_shortcircuit.py`): новая проверка
«последняя запись журнала — agent run SKIPPED с такой-то причиной» не
должна случайно сработать и на генуинной стагнации, где такой записи
попросту нет.

Зелёный с рождения: этот сценарий — то же самое свойство, что уже
проверяет `DriveTaskStallCapTest` на сегодняшнем коде (`_drive_task`
считает `stall_streak` и не убивает задачу раньше `CANARY_MAX_STALL_ITERS`
проходов) — реализация AC-3/AC-6 эту ветку не трогает по условию SPEC
(«Не входит»: «поведение канарейки для генуинного отсутствия прогресса
без записи agent run SKIPPED... не меняется»). Красным он станет только
если правка AC-3/AC-6 всё же случайно расширит короткое замыкание на
этот случай — тогда он и должен покраснеть.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config, store  # noqa: E402


class DriveTaskGenericStallStillWaitsForCapTest(unittest.TestCase):
    """Тот же сценарий, что `tests/test_canary.py::DriveTaskStallCapTest`
    (`auto.cmd_auto` — no-op, состояние не меняется, журнал пуст)."""

    TASK = "T921"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача",
                          "in_dev", "task/t921-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        patcher = mock.patch.object(canary.auto, "cmd_auto", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac7_generic_stall_without_skip_marker_still_needs_more_than_one_pass(self):
        """`auto.cmd_auto` не журналирует ничего и не двигает состояние —
        `_drive_task` обязан отработать больше одного прохода, прежде чем
        сдаться (полный `CANARY_MAX_STALL_ITERS`, как и сегодня).

        Ловит мутацию: если реализация AC-3/AC-6 проверяет «последняя
        запись журнала — agent run SKIPPED» так, что ПУСТОЙ журнал (нет
        записей вовсе) ошибочно засчитывается как совпадение, `cmd_auto`
        позовётся только один раз вместо полного цикла до
        `CANARY_MAX_STALL_ITERS` — `assertGreater` ниже покраснеет.
        """
        canary._drive_task(self.conn, self.TASK)

        self.assertGreater(canary.auto.cmd_auto.call_count, 1)
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)


if __name__ == "__main__":
    unittest.main()
