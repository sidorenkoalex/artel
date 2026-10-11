"""Приёмочные тесты T040 — учёт стоимости шага при таймауте/обрыве потока.

Источник — tasks/T040/SPEC.md, «Критерии приёмки» (AC-1..AC-4). Песочница —
тот же приём, что `tests/test_step_cost.py::CmdRunCostTest`: БД, задачи и
логи во временном каталоге (`tests.sandbox.TmpRootTest`), `runner.spawn_agent`
подменён заготовленным процессом, `gitcmd.git` — заглушкой `fake_git`
(идентичность роли), `doctor.preflight_checks` — пустым списком (pre-flight
не про эту задачу).

Финальное событие потока `type: result` в обеих ветках SPEC (AC-1 —
таймаут, AC-2 — обрыв stdout-пайпа) физически ОТСУТСТВУЕТ — это
определение обоих сценариев, не деталь реализации. Различие между ними —
КАК процесс перестаёт отдавать события:

- AC-1 (таймаут): `proc.wait()` не укладывается в `config.AGENT_TIMEOUT_SEC`
  и бросает `subprocess.TimeoutExpired` — тот же приём, что уже кодирует
  `tests/test_agent_log.py::CmdRunLoggingTest.test_timeout_kills_process_and_journals`.
- AC-2 (обрыв stdout-пайпа): сам поток обрывается посреди чтения —
  `BrokenPipeStream` кидает `OSError` вместо чистого `StopIteration`,
  `proc.wait()` при этом возвращает код процесса как обычно (пайп
  порвался — не сам процесс завис). Это ловит `agent_log.OutputPump.run`
  (`except Exception: self.error = exc`) — уже существующий путь для
  сбоя перекачки, T040 меняет лишь то, что происходит со стоимостью шага
  после него.

Критерий даёт РАЗВИЛКУ («либо частичная сумма с пометкой «частичная»,
либо событие «стоимость шага неизвестна» + алерт») — какая ветка сработает,
зависит от того, есть ли в потоке что восстанавливать. Тесты ниже гоняют
сценарий, где в потоке до обрыва НЕТ ни одного usage-события (только
обычный текст) — тогда восстановить нечего, и по формулировке критерия
(«если восстановить стоимость нельзя») однозначно обязана сработать
ветка «неизвестна» + алерт; это не предположение о реализации, а прямое
следствие входных данных теста. Ветка «частичная сумма» в SPEC не
определяет формулу (курс токена в доллары нигде в кодовой базе сегодня
не задан), поэтому тестом на конкретное число не фиксируется — тест
пишется по критерию, а не по домыслу о непрописанной механике.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, doctor, gitcmd, runner, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402


def event(**fields) -> str:
    """Строка потока `--output-format stream-json`."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def result_event(usd=0.5, **fields) -> str:
    """Финальное событие запуска: в нём стоимость и usage."""
    return event(type="result", subtype="success", is_error=False,
                 result="готово", total_cost_usd=usd, **fields)


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, чисто заканчивается EOF."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class BrokenPipeStream(FakeStream):
    """Пайп, обрывающийся посреди чтения (AC-2): после заготовленных строк
    вместо чистого EOF (`StopIteration`) — `OSError`, как при реальном
    обрыве stdout-пайпа агента."""

    def __next__(self) -> str:
        try:
            return next(self.lines)
        except StopIteration:
            raise OSError("обрыв stdout-пайпа шага") from None


class FakeProc:
    """Процесс агента: отдаёт заготовленный поток, `wait()` — сразу rc."""

    def __init__(self, stream, returncode: int = 0):
        self.stdout = stream
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode

    def kill(self) -> None:
        pass


def timeout_then_killed_proc(lines) -> mock.Mock:
    """Процесс, чей `wait()` сперва бросает TimeoutExpired (AC-1), как в
    `tests/test_agent_log.py::test_timeout_kills_process_and_journals`."""
    proc = mock.Mock(stdout=FakeStream(lines))
    proc.wait.side_effect = [
        runner.subprocess.TimeoutExpired(cmd="claude",
                                         timeout=config.AGENT_TIMEOUT_SEC),
        -9,
    ]
    return proc


class _T040TmpRootTest(TmpRootTest):
    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR")


TmpRootTest = _T040TmpRootTest


class MissingFinalEventCostTest(TmpRootTest):
    """`run` на шаге без финального события потока: журнал и алерты."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Учёт стоимости шага при таймауте")
        self.set_task(state="in_dev")

        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch.object(doctor, "preflight_checks",
                                       lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal_text(self) -> str:
        """Все записи журнала шага одной строкой — фраза-маркер ищется по
        содержимому, а не по конкретному имени `action`, которое SPEC не
        называет."""
        rows = store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (self.TASK,)).fetchall()
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in rows)

    def unknown_cost_alerts(self) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source LIKE 'spend.unknown_cost%'").fetchall()

    def run_with_proc(self, proc) -> str:
        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            return self.capture(runner.cmd_run, self.TASK)

    def test_ac1_timeout_without_recoverable_data_does_not_stay_silent(self):
        """AC-1: таймаут шага без единого usage-события в потоке —
        восстановить стоимость нечем, значит журнал обязан нести событие
        «стоимость шага неизвестна» и открыть алерт `spend.unknown_cost`."""
        self.run_with_proc(
            timeout_then_killed_proc(["агент работает, потом молчит\n"]))

        self.assertEqual(
            self.task_row()["spent_usd"], 0.0,
            "восстановить нечего — прибавлять фиктивную сумму нельзя")

        text = self.journal_text()
        self.assertIn(
            "стоимость шага неизвестна", text,
            "AC-1: при таймауте без данных для восстановления в журнал "
            "обязано попасть событие «стоимость шага неизвестна» — "
            f"фактический журнал:\n{text}")

        found = self.unknown_cost_alerts()
        self.assertEqual(
            len(found), 1,
            f"AC-1: во второй ветке критерия обязан открыться ровно один "
            f"алерт `alerts` с kind=incident, source вида "
            f"spend.unknown_cost — найдено {len(found)}")
        self.assertEqual(found[0]["kind"], "incident")
        self.assertTrue(found[0]["source"].startswith("spend.unknown_cost"))

    def test_ac2_broken_pipe_without_recoverable_data_does_not_stay_silent(self):
        """AC-2: обрыв stdout-пайпа (без единого usage-события в потоке до
        обрыва) обрабатывается так же, как AC-1 — событие «стоимость шага
        неизвестна» и алерт `spend.unknown_cost`."""
        self.run_with_proc(
            FakeProc(BrokenPipeStream(["агент начал работу\n"]), 0))

        self.assertEqual(
            self.task_row()["spent_usd"], 0.0,
            "восстановить нечего — прибавлять фиктивную сумму нельзя")

        text = self.journal_text()
        self.assertIn(
            "стоимость шага неизвестна", text,
            "AC-2: при обрыве stdout-пайпа без данных для восстановления "
            "в журнал обязано попасть событие «стоимость шага неизвестна» "
            f"— фактический журнал:\n{text}")

        found = self.unknown_cost_alerts()
        self.assertEqual(
            len(found), 1,
            f"AC-2: во второй ветке критерия обязан открыться ровно один "
            f"алерт `alerts` с kind=incident, source вида "
            f"spend.unknown_cost — найдено {len(found)}")
        self.assertEqual(found[0]["kind"], "incident")
        self.assertTrue(found[0]["source"].startswith("spend.unknown_cost"))

    def test_ac3_normal_step_with_result_event_is_charged_as_before(self):
        """AC-3: шаг с финальным событием потока учитывается как раньше —
        деньги списаны, новых записей «неизвестна» и новых алертов
        `spend.unknown_cost` нет."""
        out = self.run_with_proc(FakeProc(FakeStream([
            "работаю\n",
            result_event(usd=0.42, usage={"input_tokens": 10,
                                          "output_tokens": 5}),
        ]), 0))

        self.assertAlmostEqual(self.task_row()["spent_usd"], 0.42)
        self.assertIn("стоимость $0.4200", out,
                      "цена шага видна Оператору сразу, как и раньше")

        text = self.journal_text()
        self.assertNotIn(
            "стоимость шага неизвестна", text,
            "AC-3: нормальный шаг не должен заводить новую запись "
            "«стоимость шага неизвестна»")
        self.assertNotIn(
            "частичная", text,
            "AC-3: нормальный шаг не должен заводить пометку «частичная»")
        self.assertEqual(
            self.unknown_cost_alerts(), [],
            "AC-3: нормальный шаг не должен заводить алерт "
            "spend.unknown_cost")

    def test_ac3_normal_step_survives_a_timed_out_predecessor(self):
        """AC-3 (продолжение): деньги и журнал таймаутнувшегося шага (AC-1)
        не портят учёт следующего нормального шага той же задачи."""
        self.run_with_proc(
            timeout_then_killed_proc(["первая попытка молчит\n"]))
        self.set_task(state="in_dev")  # таймаут не ретраится — запуск заново

        out = self.run_with_proc(
            FakeProc(FakeStream([result_event(usd=0.3)]), 0))

        self.assertAlmostEqual(self.task_row()["spent_usd"], 0.3)
        self.assertIn("стоимость $0.3000", out)


# AC-4: manual — CI (`.github/workflows/ci.yml`, шаг `unittest discover -s
# tests -v`) уже гоняет полный набор `tests/` на каждый пуш; дублировать
# прогон подпроцессом внутри acceptance_tests того же смысла не добавляет
# и рискует ложным красным из-за окружения этой машины (см. тот же довод
# в tasks/T037/acceptance_tests/test_manual_criteria.py, AC-5). Число
# тестов «до этой задачи» — 605 (`python3 -c "import unittest;
# print(unittest.TestLoader().discover('tests').countTestCases())"`,
# ветка task/t040-uchyot-stoimosti-shaga-pri-tay от свежего main) —
# планка для сверки Оператором/ревьювером на приёмке, что набор не
# уменьшился и не покраснел, без повторного авто-подсчёта здесь.


if __name__ == "__main__":
    unittest.main()
