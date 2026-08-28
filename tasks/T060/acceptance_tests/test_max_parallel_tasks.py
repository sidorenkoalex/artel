"""Приёмочные тесты T060 — лимитер параллельных задач: AC-1..AC-7 (SPEC.md).

## Допущения интерфейса, которые вводит этот файл

Ничего из перечисленного ниже ещё не существует в коде — прогон ДО
реализации падает по этой причине (`AttributeError: module
'orchestrator.config' has no attribute 'MAX_PARALLEL_TASKS'` и т.п.),
ожидаемо (скил test-authoring: «падать на отсутствующей пока реализации —
нормально»), не брак теста.

- `orchestrator/config.MAX_PARALLEL_TASKS` — новая константа (SPEC
  требование 1). Тесты читают её значение из `config`, а не хардкодят
  число `2` — критерий сформулирован через сравнение с этой константой
  (требование 3: «посчитанное число >= config.MAX_PARALLEL_TASKS»).
- Сам лимитер — не отдельная публичная функция с зафиксированным именем:
  тесты бьют по наблюдаемому поведению команд `run`/`auto` (система
  снаружи), а не по внутренней точке входа, которую ещё не выбрал
  разработчик — тем же приёмом, что и T044/T053.
- Песочница — `tests.test_invariants.FsmTest` (T001, git и preflight
  заглушены, `spawn_agent` подменяется по месту вызова) — переиспользуется
  (skills/test-authoring, conventions-core). «Занятые» другие задачи
  заводятся напрямую в БД (`store.insert_task` + строка `leases`), без
  собственных worktree/веток — лимитер читает только `store.all_leases`
  (SPEC требование 2), полноценный FSM-цикл этим задачам не нужен.
- Held-хост фиксируется как `socket.gethostname()` (свой host) во всех
  сценариях — SPEC требование 2 явно решает вопрос адресуемости pid
  только для «своего host»; поведение на чужом host критерии (AC-1..AC-7)
  не описывают, тестировать нечего (эта развилка — только в разделе
  «Требования», не в «Критериях приёмки»).
"""
import io
import os
import socket
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, catalog, cleanup, config, fsm, runner, store  # noqa: E402
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402


def _invoke(call) -> str:
    """Стдаут вызова + текст SystemExit (если он был) — отказ лимитера мог
    уйти любым из двух путей (`sys.exit`, как `budget_block`, или
    печать+`return`, как отказ по чужой ветке worktree — оба уже
    существуют в `_cmd_run`), для теста это один и тот же наблюдаемый
    текст."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        return buf.getvalue() + str(exc)
    return buf.getvalue()


def _dead_pid() -> int:
    """Гарантированно мёртвый pid: дочерний процесс, дождавшийся своего
    завершения (тот же приём, что и tasks/T044/acceptance_tests/
    test_lease_readonly_and_doctor.py::Ac6DoctorDetectsDeadPidLeaseTest)."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    proc.wait()
    return proc.pid


def _stale_heartbeat() -> str:
    dt = datetime.now(timezone.utc) - timedelta(
        seconds=config.LEASE_STALE_AFTER_SEC + 5)
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


class LimiterSandbox(FsmTest):
    """`FsmTest` (T001, git/агент заглушены) + прямые операции над
    `leases`/`tasks` для симуляции ДРУГИХ занятых задач."""

    CALLER_SESSION = "session-caller"

    def seed_busy_task(self, task_id: str, session_id: str, pid: int,
                       hostname: str, heartbeat_ts: str) -> None:
        """Заводит строку `tasks` (id должен существовать — лимитер обязан
        суметь назвать задачу по id) и её lease — «другая занятая задача»."""
        store.insert_task(store.db(), task_id, f"Другая задача {task_id}",
                          "in_dev", f"task/{task_id.lower()}-fake",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def seed_self_lease(self, session_id: str, pid: int, hostname: str,
                        heartbeat_ts: str) -> None:
        """Собственный lease СТАРТУЮЩЕЙ задачи (`self.TASK`) — симулирует
        продолжение уже идущего цикла (`auto`, повторный `run`)."""
        conn = store.db()
        conn.execute("DELETE FROM leases WHERE task_id=?", (self.TASK,))
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def reset_task(self) -> None:
        """Возвращает T001 к нейтральному in_dev и чистит чужие задачи/lease
        перед очередным подшагом свипа."""
        self.set_state("in_dev", budget_usd=config.DEFAULT_BUDGET_USD,
                       spent_usd=0.0, escalated_from=None)
        conn = store.db()
        conn.execute("DELETE FROM leases")
        conn.execute("DELETE FROM tasks WHERE id != ?", (self.TASK,))
        conn.commit()

    def journal_tail(self, since: int) -> str:
        rows = store.task_steps(store.db(), self.TASK)[since:]
        return "\n".join(f"{r['actor']} {r['action']} {r['detail']}"
                         for r in rows).lower()

    def journal_len(self) -> int:
        return len(store.task_steps(store.db(), self.TASK))

    def run_with_fake_agent(self, call) -> tuple[str, mock.Mock]:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = _invoke(call)
        return out, popen


class Ac1TwoForeignBusyTasksRefuseThirdTest(LimiterSandbox):
    """AC-1: две другие задачи держат живые lease — `run` и `auto` третьей
    задачи отказывают именованным отказом (id обеих занятых задач,
    session_id держателей, значение MAX_PARALLEL_TASKS), запись — в
    журнале третьей задачи."""

    HOLDERS = (
        ("T901", "session-busy-1"),
        ("T902", "session-busy-2"),
    )

    def _seed_two_busy(self) -> None:
        self.assertEqual(
            len(self.HOLDERS), config.MAX_PARALLEL_TASKS,
            "AC-1 буквально говорит о «двух» занятых задачах — фикстура "
            "должна давать ровно config.MAX_PARALLEL_TASKS")
        for task_id, session_id in self.HOLDERS:
            self.seed_busy_task(task_id, session_id, os.getpid(),
                               socket.gethostname(), store.now())

    def test_ac1_run_is_refused_by_name_and_journalled(self):
        self.reset_task()
        self._seed_two_busy()
        before_state = self.state()
        journalled_before = self.journal_len()

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertEqual(self.state(), before_state,
                         "run отказался стартовать, но состояние сдвинулось")
        journal = self.journal_tail(journalled_before)
        self.assertTrue(journal,
                        "отказ лимитера не записан в журнал третьей задачи")
        combined = f"{out}\n{journal}".lower()
        for task_id, session_id in self.HOLDERS:
            self.assertIn(task_id.lower(), combined,
                          f"отказ не назвал занятую задачу {task_id}")
            self.assertIn(session_id, combined,
                          f"отказ не назвал session_id держателя {session_id}")
        self.assertRegex(
            combined, rf"\b{config.MAX_PARALLEL_TASKS}\b",
            "отказ не назвал значение MAX_PARALLEL_TASKS")

    def test_ac1_auto_is_refused_the_same_way_on_first_step(self):
        self.reset_task()
        self._seed_two_busy()
        before_state = self.state()
        journalled_before = self.journal_len()

        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertEqual(self.state(), before_state,
                         "auto не должен был сдвинуть состояние на первом же "
                         "отказавшем шаге")
        combined = f"{out}\n{self.journal_tail(journalled_before)}".lower()
        for task_id, session_id in self.HOLDERS:
            self.assertIn(task_id.lower(), combined,
                          f"auto: отказ не назвал занятую задачу {task_id}")
            self.assertIn(session_id, combined,
                          f"auto: отказ не назвал session_id {session_id}")
        self.assertRegex(combined, rf"\b{config.MAX_PARALLEL_TASKS}\b",
                         "auto: отказ не назвал значение MAX_PARALLEL_TASKS")


class Ac2OneForeignBusyTaskPassesTest(LimiterSandbox):
    """AC-2: только одна другая задача занята — запуск второй задачи
    проходит без отказа лимитера."""

    def test_ac2_single_busy_task_does_not_block_run(self):
        self.reset_task()
        self.seed_busy_task("T901", "session-busy-1", os.getpid(),
                           socket.gethostname(), store.now())

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"run отказал при единственной другой занятой задаче: {out!r}")


class Ac3StaleOrDeadLeaseNotCountedTest(LimiterSandbox):
    """AC-3: чужой протухший lease или lease с мёртвым pid не засчитывается
    против потолка — запуск второй задачи проходит, даже если таких
    «формально занятых» задач ровно MAX_PARALLEL_TASKS."""

    def test_ac3_stale_heartbeat_leases_are_not_counted(self):
        self.reset_task()
        stale = _stale_heartbeat()
        for i in range(config.MAX_PARALLEL_TASKS):
            self.seed_busy_task(f"T90{i}", f"session-stale-{i}", os.getpid(),
                               socket.gethostname(), stale)

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(popen.called,
                        f"run отказал, хотя все другие lease протухли: {out!r}")

    def test_ac3_dead_pid_leases_are_not_counted(self):
        self.reset_task()
        dead_pid = _dead_pid()
        for i in range(config.MAX_PARALLEL_TASKS):
            self.seed_busy_task(f"T91{i}", f"session-dead-{i}", dead_pid,
                               socket.gethostname(), store.now())

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(popen.called,
                        f"run отказал, хотя все другие pid мертвы: {out!r}")


class Ac4OwnLeaseNotCountedAgainstItselfTest(LimiterSandbox):
    """AC-4: собственный lease стартующей задачи не считается против неё
    самой — при `MAX_PARALLEL_TASKS - 1` чужих занятых задачах и
    собственном (уже существующем) lease число «других» занятых остаётся
    `MAX_PARALLEL_TASKS - 1` — повторный `run`/внутренний `run` `auto` не
    блокируется."""

    def _seed(self) -> None:
        for i in range(config.MAX_PARALLEL_TASKS - 1):
            self.seed_busy_task(f"T92{i}", f"session-foreign-{i}", os.getpid(),
                               socket.gethostname(), store.now())
        # Собственный, уже существующий lease той же задачи и той же сессии
        # — как если бы это был внутренний повторный вызов (auto, второй run).
        self.seed_self_lease(self.CALLER_SESSION, os.getpid(),
                             socket.gethostname(), store.now())

    def test_ac4_repeated_run_of_the_same_task_is_not_blocked(self):
        self.reset_task()
        self._seed()

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"повторный run той же задачи заблокирован собственным lease: "
            f"{out!r}")

    def test_ac4_internal_run_inside_auto_is_not_blocked(self):
        self.reset_task()
        self._seed()

        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"внутренний run auto заблокирован собственным lease задачи: "
            f"{out!r}")


class Ac5GateAndReadonlyCommandsIgnoreLimiterTest(LimiterSandbox):
    """AC-5: `kill`, `status`, `approve`, `reject` выполняются без отказа
    лимитера, даже когда число других занятых задач >= MAX_PARALLEL_TASKS."""

    def _seed_at_cap(self) -> None:
        for i in range(config.MAX_PARALLEL_TASKS):
            self.seed_busy_task(f"T93{i}", f"session-cap-{i}", os.getpid(),
                               socket.gethostname(), store.now())

    def test_ac5_status_ignores_the_limiter(self):
        self.reset_task()
        self._seed_at_cap()

        out = _invoke(catalog.cmd_status)

        self.assertNotIn("max_parallel", out.lower())

    def test_ac5_kill_ignores_the_limiter(self):
        self.reset_task()
        self._seed_at_cap()

        _invoke(lambda: cleanup.cmd_kill(self.TASK))

        row = store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()
        self.assertIsNone(row, "kill не выполнился при занятых других задачах")

    def test_ac5_approve_ignores_the_limiter(self):
        self.reset_task()
        self.set_state("acceptance")
        self._seed_at_cap()

        _invoke(lambda: fsm.cmd_approve(self.TASK))

        self.assertEqual(self.state(), "merge_gate",
                         "approve не выполнился при занятых других задачах")

    def test_ac5_reject_ignores_the_limiter(self):
        self.reset_task()
        self.set_state("acceptance")
        self._seed_at_cap()

        _invoke(lambda: fsm.cmd_reject(self.TASK, "критерий не выполнен"))

        self.assertEqual(self.state(), "in_dev",
                         "reject не выполнился при занятых других задачах")


class Ac6RefusalNotBypassedByRetryOrAdvanceTest(LimiterSandbox):
    """AC-6: отказ лимитера на достигнутом потолке не обходится ни
    повторным `run`, ни следующим за отказавшим шагом `advance`.

    Требование 6 SPEC отдельно предписывает разработчику продублировать
    эту же проверку неослабляемым тестом в `tests/test_invariants.py` —
    это адрес РЕАЛИЗАЦИИ теста (файл, который правит только разработчик
    и который потом защищает ADR-0002), а не часть наблюдаемого поведения
    команд. Приёмочный тест здесь проверяет само поведение — то, что
    реально можно предъявить приёмке через CLI, — не факт существования
    файла по конкретному пути в дереве разработчика.
    """

    def _seed_at_cap(self) -> None:
        for i in range(config.MAX_PARALLEL_TASKS):
            self.seed_busy_task(f"T94{i}", f"session-lock-{i}", os.getpid(),
                               socket.gethostname(), store.now())

    def test_ac6_retry_and_advance_do_not_bypass_the_refusal(self):
        self.reset_task()
        self._seed_at_cap()
        before_state = self.state()

        # Первая попытка — отказ.
        out1, popen1 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        popen1.assert_not_called()
        self.assertEqual(self.state(), before_state)

        # Повторный run той же (отказанной) сессии — тот же отказ, не обход.
        out2, popen2 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        popen2.assert_not_called()
        self.assertEqual(self.state(), before_state,
                         "повторный run обошёл отказ лимитера")

        # advance следующим за отказавшим шагом — тоже не двигает задачу
        # вперёд (шаг фактически не выполнялся, обходить нечем).
        with mock.patch.object(runner, "spawn_agent") as popen3:
            popen3.return_value = FakeProc(["готово\n"])
            _invoke(lambda: fsm.cmd_advance(self.TASK,
                                            session_id=self.CALLER_SESSION))
        popen3.assert_not_called()
        self.assertEqual(self.state(), before_state,
                         "advance после отказавшего run продвинул задачу")


# AC-7: manual — «все существующие тесты пакета зелёные после изменения»
# уже покрыт `.github/workflows/ci.yml` (джоб «Синтаксис и тесты
# оркестратора», `unittest discover -s tests -v` на каждый пуш в чистом
# раннере; прецедент tasks/T044/acceptance_tests/
# test_lease_readonly_and_doctor.py): повтор всего набора подпроцессом
# внутри acceptance_tests ловил бы окружение машины разработчика, а не
# дефект этой задачи.


if __name__ == "__main__":
    import unittest
    unittest.main()
