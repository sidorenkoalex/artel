"""Юнит-тесты сигнала «длительность близка к пределу» (SPEC
01M4K2767FXKZ8EW7AME81SZ9N).

Гейт, `suite-run` и `notes` у предела, один открытый алерт на проект и
константу порога держит долгоживущий файл задачи
`tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`. Здесь — углы,
которых он не бьёт: задача держателя замка (по ней сигнал находит журнал),
повтор упавших `suite-run --failed` — не полный прогон, нечитаемый профиль
у `notes`.
"""
import contextlib
import io
import itertools
import json
import os
import unittest
from unittest import mock

from orchestrator import acceptance, config, notes, project_profile, suite_lock, targets
from tests.sandbox import TmpRootTest


class MyTaskIdTest(TmpRootTest):

    def write_lock(self, task_id, pid: int) -> None:
        path = suite_lock.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"task_id": task_id, "pid": pid,
                                    "run": None}), encoding="utf-8")

    def test_task_only_for_lock_held_by_this_process(self):
        """Задача держателя — только у замка текущего процесса.

        Ловит мутацию: `my_task_id` не сверяет pid держателя — прогон
        `notes` рядом с чужим прогоном гейта пишет сигнал в журнал чужой
        задачи; либо прогон `notes` (задачи нет) получает не `None`.
        """
        self.assertIsNone(suite_lock.my_task_id())
        self.write_lock("T001", os.getppid())
        self.assertIsNone(suite_lock.my_task_id())
        self.write_lock("T001", os.getpid())
        self.assertEqual(suite_lock.my_task_id(), "T001")
        self.write_lock(None, os.getpid())
        self.assertIsNone(suite_lock.my_task_id())


class FailedRerunTest(TmpRootTest):

    def run_at_limit(self, run_targets: tuple) -> str:
        """Прогон, «длящийся» ровно свой предел: каждый вызов часов
        сдвигает их на предел."""
        (self.root / "tests").mkdir(exist_ok=True)
        buf = io.StringIO()
        with mock.patch.object(acceptance, "_run_full_suite_now",
                               return_value=(True, "1 passed in 0.1s")), \
                mock.patch.object(acceptance.time, "monotonic",
                                  side_effect=itertools.count(0, 1000)), \
                contextlib.redirect_stdout(buf):
            acceptance.run_full_suite(self.root, targets=run_targets,
                                      limit=(1000, "профиль"))
        return buf.getvalue()

    def test_failed_rerun_gives_no_signal_full_run_does(self):
        """Повтор упавших у предела сигнала не даёт, полный прогон — даёт.

        Ловит мутацию: сигнал не различает полный прогон и повтор упавших
        (`targets` — id тестов) — длительность нескольких тестов
        сравнивается с пределом полного набора и сигналит ложно; либо
        условие перевёрнуто и полный прогон у предела молчит.
        """
        self.assertNotIn(acceptance.SUITE_NEAR_LIMIT_ACTION,
                         self.run_at_limit(("tests/test_x.py::T::test_a",)))
        self.assertIn(acceptance.SUITE_NEAR_LIMIT_ACTION,
                      self.run_at_limit(("tests",)))


class NotesUnreadProfileTest(unittest.TestCase):

    def test_unread_profile_falls_back_to_config_limit(self):
        """Нечитаемый профиль: `notes` гоняет набор с запасным пределом.

        Ловит мутацию: ошибка чтения профиля пробрасывается из
        `notes` — команда падает вместо прогона; либо запасной предел
        передаётся без источника «config» в выводе.
        """
        buf = io.StringIO()
        with mock.patch.object(project_profile, "full_suite_limit",
                               side_effect=targets.TargetsError("сломан")), \
                contextlib.redirect_stdout(buf):
            kwargs = notes._suite_limit_kwargs()
        self.assertEqual(kwargs, {})
        out = buf.getvalue()
        self.assertIn("сломан", out)
        self.assertIn(f"предел {config.FULL_SUITE_TIMEOUT_SEC} с "
                      f"(источник: config)", out)


if __name__ == "__main__":
    unittest.main()
