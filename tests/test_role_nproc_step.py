"""Предел процессов на шаге роли: отказ при исчерпанном запасе, передача
предела в `spawn_agent`, однократные предупреждения, снятие оставшейся
группы на обычном исходе (SPEC 01M6KB0FS809DG55K9A20CYKJE, требования
1-3, 5).

Агент — `FakeProc` подменённого `runner.spawn_agent`; источники предела
и счёта подменены точками SPEC (`_read_maxprocperuid`,
`_user_process_count`), настоящих процессов тесты не порождают."""
import os
import signal
import unittest
from unittest import mock

from orchestrator import (artifact_branch, catalog, config, gitcmd, liveness,
                          runner, store, zone_lock)
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc,
                           capture_new_task_id, fake_git,
                           sync_spec_from_worktree)

MAXPROC = config.ROLE_NPROC_RESERVE + 3000


class _StepSandbox(DeveloperBriefTmpRootTest):
    """Задача в `in_dev` с PLAN.md — `cmd_run` доходит до запуска агента."""

    def setUp(self):
        super().setUp()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        for patcher in (
                mock.patch.object(gitcmd, "git", fake_git),
                mock.patch.object(runner.keychain, "token",
                                  lambda slot: "tok-test"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda role, target: []),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Предел процессов")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()
        tdir = artifact_branch.docs_dir(self.TASK, config.DEFAULT_TARGET)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

    def patch(self, name: str, **kwargs) -> None:
        patcher = mock.patch.object(runner, name, **kwargs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def sources(self, maxproc=(MAXPROC, "ok"), **count):
        """Подмены `kern.maxprocperuid` и счёта процессов (`return_value=`
        или `side_effect=`); по умолчанию счёт — 1."""
        self.patch("_read_maxprocperuid", return_value=maxproc)
        self.patch("_user_process_count", **(count or {"return_value": 1}))

    def actions(self, action: str) -> list[str]:
        return [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                if r["action"] == action]

    def run_failing_step(self) -> int:
        """Шаг, каждая попытка которого падает rc=1, — все попытки; число
        порождений агента."""
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=lambda cmd, **kw:
                               FakeProc(["сбой\n"], 1)) as spawn:
            self.capture(runner.cmd_run, self.TASK)
        return spawn.call_count


class RoleNprocStepTest(_StepSandbox):

    def test_exhausted_reserve_refuses_without_agent_and_zone_claim(self):
        """N = M — `cmd_run` выходит SystemExit с причиной, агент не
        порождён, захвата зоны у задачи нет.

        Ловит мутацию: сравнение запаса строгое (`count > limit`) либо
        отказ снят — при N = M шаг стартует и агент порождается; либо
        отказ вынесен из `try/finally` `_cmd_run` — задача держит зону.
        """
        self.patch("_read_maxprocperuid", return_value=(MAXPROC, "ok"))
        limit = runner.role_nproc_limit()
        self.patch("_user_process_count", return_value=limit)
        with mock.patch.object(runner, "spawn_agent") as spawn, \
                self.assertRaises(SystemExit) as exc:
            self.capture(runner.cmd_run, self.TASK)
        self.assertIn(f"запас процессов пользователя исчерпан: {limit} из "
                      f"{limit}", str(exc.exception.code))
        spawn.assert_not_called()
        self.assertFalse(zone_lock._occupies(store.db(), self.TASK))
        self.assertEqual(len(self.actions(runner.NPROC_REFUSAL_ACTION)), 1)

    def test_step_passes_role_limit_to_every_attempt(self):
        """Каждая попытка шага зовёт `spawn_agent` с `nproc_limit`, равным
        `role_nproc_limit()`.

        Ловит мутацию: `_run_attempts` (или `run_agent_once`) не передаёт
        предел дальше — в вызове `spawn_agent` нет `nproc_limit`.
        """
        self.sources()
        expected = runner.role_nproc_limit()
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=lambda cmd, **kw:
                               FakeProc(["сбой\n"], 1)) as spawn:
            self.capture(runner.cmd_run, self.TASK)
        self.assertGreater(spawn.call_count, 1)
        self.assertEqual([c.kwargs.get("nproc_limit")
                          for c in spawn.call_args_list],
                         [expected] * spawn.call_count)

    def test_failed_read_warns_once_per_step(self):
        """Сбой чтения `kern.maxprocperuid` — одна запись-предупреждение на
        шаг из нескольких попыток.

        Ловит мутацию: предупреждение пишется в каждой попытке (расчёт
        перенесён в цикл попыток) — записей столько же, сколько попыток;
        либо не пишется вовсе.
        """
        self.sources(maxproc=(None, "failed"))
        self.assertGreater(self.run_failing_step(), 1)
        self.assertEqual(len(self.actions(runner.NPROC_WARNING_ACTION)), 1)

    def test_absent_maxproc_writes_no_warning(self):
        """Платформа без `kern.maxprocperuid` — предупреждений нет.

        Ловит мутацию: запись выбирается по «значение не прочитано», а не
        по исходу "failed" — у "absent" появляется предупреждение.
        """
        self.sources(maxproc=(None, "absent"))
        self.assertGreater(self.run_failing_step(), 1)
        self.assertEqual(self.actions(runner.NPROC_WARNING_ACTION), [])

    def test_count_failure_warns_once_and_step_runs(self):
        """Сбой счёта процессов — шаг идёт, одна запись с причиной.

        Ловит мутацию: исключение счёта не ловится — шаг падает, агент не
        порождён; либо запись пишется на каждую попытку.
        """
        self.sources(side_effect=RuntimeError("ps-метка"))
        self.assertGreater(self.run_failing_step(), 1)
        warnings = self.actions(runner.NPROC_WARNING_ACTION)
        self.assertEqual(len(warnings), 1)
        self.assertIn("счёт процессов пользователя недоступен: ps-метка",
                      warnings[0])


class GroupLeftoverTest(_StepSandbox):
    """Снятие группы шага на обычном исходе (требование 5): у `FakeProc`
    целочисленный pid, `liveness.terminate_process_group` подменён."""

    PID = 987654

    def run_step(self, leftover: int) -> list[str]:
        """Шаг одной успешной попытки; порядок вызовов снятия и `close_pump`."""
        self.sources()
        order = []
        proc = FakeProc(["шаг\n"], 0)
        proc.pid = self.PID
        real_close = runner.close_pump

        def close(*args, **kwargs):
            order.append("close_pump")
            return real_close(*args, **kwargs)

        def terminate(pgid, *args, **kwargs):
            order.append(f"terminate {pgid}")
            return leftover

        with mock.patch.object(runner, "spawn_agent", return_value=proc), \
                mock.patch.object(runner, "close_pump", close), \
                mock.patch.object(liveness, "terminate_process_group",
                                  terminate):
            self.capture(runner.cmd_run, self.TASK)
        return order

    def test_leftover_group_terminated_before_pump_and_journaled(self):
        """Оставшиеся в группе процессы сняты до `close_pump`, запись есть.

        Ловит мутацию: на обычном исходе группа не снимается (снятие
        только в ветке таймаута) — нет вызова и записи; либо снятие идёт
        после `close_pump` — перекачка ждёт потомка, держащего stdout.
        """
        order = self.run_step(leftover=2)
        self.assertEqual(order[:2], [f"terminate {self.PID}", "close_pump"])
        self.assertEqual(self.actions(runner.GROUP_LEFTOVER_ACTION),
                         [liveness.group_kill_detail(self.PID, 2)])

    def test_empty_group_writes_no_record(self):
        """Пустая группа — снятие вызвано, записи нет.

        Ловит мутацию: запись пишется без проверки числа снятых — в
        журнале «снята: 0 процесс(ов)».
        """
        order = self.run_step(leftover=0)
        self.assertIn(f"terminate {self.PID}", order)
        self.assertEqual(self.actions(runner.GROUP_LEFTOVER_ACTION), [])


if __name__ == "__main__":
    unittest.main()
