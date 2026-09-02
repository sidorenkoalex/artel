"""AC-9: `doctor`, проверка lease: если первый снимок живости pid —
«мёртв», а повторный снимок после короткого интервала — «жив», FAIL по
этому lease не выставляется (анти-race между pid'ами соседних шагов
одной сессии).

AC-10: FAIL-строка `doctor` по мёртвому lease называет держателя
(`session_id`), роль, номер шага, время старта шага и последнее
журнальное событие задачи.

AC-9 проверяется подменой `liveness._pid_alive` управляемой
последовательностью ответов (первый вызов — False, все следующие —
True): реальный гоняющийся pid двух соседних шагов одной сессии
детерминированно не воспроизвести в юнит-тесте, тот же приём, которым
уже приходится тестировать другие race-условия этой кодовой базы.

Красный до реализации:
- AC-9 — сегодня `doctor.check_leases` решает "мёртв" по ОДНОМУ снимку
  `liveness._pid_alive` (`orchestrator/doctor.py:685`); повторной
  сверки нет вовсе, так что первый ответ False сразу становится FAIL.
- AC-10 — сегодняшняя FAIL-строка называет только `session_id`, `pid` и
  `hostname` (`f"{row['task_id']}: lease сессии {row['session_id']} "
  f"мёртв (pid {row['pid']} на {row['hostname']})"`) — ни роли, ни
  номера шага, ни времени его старта, ни последнего журнального события
  она не несёт.
"""
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import doctor, liveness, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest  # noqa: E402

HOLDER_SESSION = "sess-holder-antirace"


class AntiRaceTest(LeaseTaskTest):

    def test_ac9_dead_then_alive_recheck_does_not_fail(self):
        self.insert_lease(self.TASK, HOLDER_SESSION, 555555,
                          socket.gethostname(), store.now())
        seen = {"n": 0}

        def flaky_alive(pid):
            seen["n"] += 1
            # Первый снимок — «мёртв» (гонка: pid соседнего, уже
            # завершившегося шага); повторный, после короткого
            # интервала, — «жив» (шаг B уже стартовал под другим pid,
            # либо тот же pid просто ещё жив).
            return seen["n"] > 1

        with mock.patch.object(liveness, "_pid_alive", side_effect=flaky_alive):
            checks = doctor.check_leases(store.db())

        failed = [c for c in checks if c.status == "fail"]
        self.assertEqual(
            failed, [],
            f"FAIL выставлен по единственному снимку живости pid, хотя "
            f"повторная сверка после короткого интервала показала «жив» "
            f"(AC-9, анти-race): {checks}")


class FailLineFieldsTest(LeaseTaskTest):
    """`self.TASK` заведена `_sandbox.LeaseTaskTest` в состоянии `in_dev`
    -> роль `developer` (`config.STATE_ROLE`)."""

    STEP_START_TS = "2026-01-02 03:04:05Z"
    LAST_EVENT_ACTION = "agent env WARNING"
    LAST_EVENT_TS = "2026-01-02 03:10:00Z"

    def setUp(self):
        super().setUp()
        self.insert_step(self.TASK, "developer", "pre-flight ok", "",
                         ts="2026-01-02 03:00:00Z")
        self.insert_step(self.TASK, "developer", "agent run started",
                         "попытка 1/3, лог: /dev/null",
                         ts=self.STEP_START_TS)
        self.insert_step(self.TASK, "developer", self.LAST_EVENT_ACTION,
                         "git-идентичность роли не задана",
                         ts=self.LAST_EVENT_TS)
        self.insert_lease(self.TASK, HOLDER_SESSION, 555555,
                          socket.gethostname(), store.now())

    def test_ac10_fail_line_names_holder_role_step_start_and_last_event(self):
        with mock.patch.object(liveness, "_pid_alive", return_value=False):
            checks = doctor.check_leases(store.db())

        failed = [c for c in checks if c.status == "fail"]
        self.assertEqual(len(failed), 1, checks)
        msg = failed[0].detail

        self.assertIn(HOLDER_SESSION, msg,
                     f"FAIL-строка не называет держателя: {msg!r}")
        self.assertIn("developer", msg,
                     f"FAIL-строка не называет роль держателя: {msg!r}")
        self.assertRegex(
            msg, r"шаг\D{0,20}\d",
            f"FAIL-строка не называет номер шага (AC-10): {msg!r}")
        self.assertIn(self.STEP_START_TS, msg,
                     f"FAIL-строка не называет время старта шага (AC-10): "
                     f"{msg!r}")
        self.assertIn(
            self.LAST_EVENT_ACTION, msg,
            f"FAIL-строка не называет последнее журнальное событие "
            f"задачи (AC-10): {msg!r}")


if __name__ == "__main__":
    unittest.main()
