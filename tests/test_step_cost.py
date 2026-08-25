"""Тесты учёта стоимости шага и потолка бюджета (см. tasks/T007/SPEC.md).

Реального `claude` CLI тут нет: `subprocess.Popen` подменяется фейковым
процессом, в поток которого подкладывается финальное событие
`--output-format stream-json` со стоимостью. Так проверяются и разбор
события, и деньги в БД, и реакция на потолок.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): кодируют инвариант
«потолок задачи = её денежный бюджет, жёсткий, с алертом на 70%»
(README «Инварианты» 5, docs/design.md §6, §10). Ослабить, заскипать или
удалить их может только Оператор отдельным ADR; перечень «инвариант →
тест → откуда» — docs/invariants.md.
"""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (agent_log, budget, catalog, config,  # noqa: E402
                          fsm, gitcmd, runner, spend, store)


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: пустой ответ вместо обращения к репозиторию.

    Исключение — `config --get user.*`: за ним `runner.role_env` ходит
    за авторством коммита шага, и пустой ответ означал бы «идентичность
    не задана», то есть предупреждение в выводе каждого прогона.
    """
    identity = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
    value = identity.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


def event(**fields) -> str:
    """Строка потока `--output-format stream-json`."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def result_event(usd=0.5, **fields) -> str:
    """Финальное событие запуска: в нём стоимость и usage."""
    return event(type="result", subtype="success", is_error=False,
                 result="готово", total_cost_usd=usd, **fields)


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class TmpRootTest(unittest.TestCase):
    """Общая песочница: DB, TASKS и LOGS уводятся во временный каталог."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()


class ParseCostEventTest(unittest.TestCase):
    """Разбор финального события потока: цена шага и токены."""

    def test_cost_and_tokens_are_taken_from_result_event(self):
        cost = spend.parse_cost_event(result_event(
            usd=0.1234, usage={"input_tokens": 10, "output_tokens": 90,
                               "cache_creation_input_tokens": 400,
                               "cache_read_input_tokens": 500}))

        self.assertEqual(cost, {"usd": 0.1234, "tokens": 1000})

    def test_tokens_are_optional(self):
        cost = spend.parse_cost_event(result_event(usd=0.5))

        self.assertEqual(cost, {"usd": 0.5, "tokens": None})

    def test_known_usage_counters_are_summed(self):
        cost = spend.parse_cost_event(result_event(
            usd=0.5, usage={"input_tokens": 7, "server_tool_use": {"a": 1}}))

        self.assertEqual(cost["tokens"], 7, "чужие поля usage не считаются")

    def test_failed_run_still_costs_money(self):
        cost = spend.parse_cost_event(event(
            type="result", subtype="error_during_execution", is_error=True,
            result="лимит контекста", total_cost_usd=0.7))

        self.assertEqual(cost["usd"], 0.7)

    def test_free_run_is_zero_not_unknown(self):
        self.assertEqual(spend.parse_cost_event(result_event(usd=0))["usd"], 0.0)

    def test_events_without_cost_are_unknown(self):
        for raw in (event(type="system", subtype="init"),
                    event(type="assistant", message={"content": []}),
                    event(type="result", subtype="success"),
                    event(type="result", total_cost_usd=None),
                    event(type="result", total_cost_usd="0.5"),
                    event(type="result", total_cost_usd=True),
                    event(type="result", total_cost_usd=-1),
                    event(type="result", total_cost_usd=float("nan")),
                    '{"type": "result", "total_cost_usd": NaN}\n',
                    '{"type":"result","total_cost_usd":\n',
                    "Traceback (most recent call last):\n",
                    "[1, 2]\n"):
            with self.subTest(raw=raw[:45]):
                self.assertIsNone(spend.parse_cost_event(raw))

    def test_unknown_cost_renders_as_nothing(self):
        self.assertEqual(spend.cost_note(None), "")

    def test_cost_note_shows_dollars_and_tokens(self):
        note = spend.cost_note({"usd": 0.1234, "tokens": 1000})

        self.assertIn("$0.1234", note)
        self.assertIn("1000", note)


class PumpCostTest(TmpRootTest):
    """Перекачка снимает стоимость с потока — в файл лога она не попадает."""

    def pump(self, lines, log_path=None) -> agent_log.OutputPump:
        pump = agent_log.OutputPump(iter(lines),
                                log_path or agent_log.new_agent_log("T007", "developer"))
        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)
        return pump

    def test_cost_is_caught_from_the_stream(self):
        pump = self.pump(["работаю\n", result_event(usd=0.25)])

        self.assertEqual(pump.cost["usd"], 0.25)

    def test_cost_event_does_not_reach_the_log(self):
        log = agent_log.new_agent_log("T007", "developer")

        self.pump(["работаю\n", result_event(usd=0.25)], log)

        self.assertEqual(log.read_text(encoding="utf-8"), "работаю\n",
                         "служебное событие Оператору в логе не нужно")

    def test_last_result_wins(self):
        pump = self.pump([result_event(usd=0.1), result_event(usd=0.9)])

        self.assertEqual(pump.cost["usd"], 0.9, "итог запуска — последний")

    def test_cost_is_caught_even_when_log_is_not_writable(self):
        unreachable = config.LOGS / "нет-такого-каталога" / "шаг.log"

        pump = self.pump([result_event(usd=0.25)], unreachable)

        self.assertIsInstance(pump.error, OSError)
        self.assertEqual(pump.cost["usd"], 0.25,
                         "деньги потрачены независимо от того, записан ли лог")

    def test_stream_without_cost_leaves_none(self):
        self.assertIsNone(self.pump(["просто вывод\n"]).cost)


class CmdRunCostTest(TmpRootTest):
    """`run` считает деньги: журнал шага, spent_usd, реакция на потолок."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Учёт стоимости шага")
        self.set_task(state="in_dev")

        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        # Шаг ревью собирает пакет настоящим git (T011); в песочнице
        # репозитория нет, а этому модулю важны деньги шага, не diff.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()

    def run_agent(self, *attempts) -> str:
        """attempts: (rc, строки вывода) — по одной паре на попытку."""
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        with mock.patch.object(runner.subprocess, "Popen", side_effect=procs) as popen:
            out = self.capture(runner.cmd_run, self.TASK)
        self.popen = popen
        return out

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def test_step_cost_lands_in_spent_and_journal(self):
        out = self.run_agent((0, [result_event(
            usd=0.25, usage={"input_tokens": 100, "output_tokens": 20})]))

        self.assertAlmostEqual(self.task_row()["spent_usd"], 0.25)
        detail = self.journal_details("agent run finished")[0]
        self.assertIn("стоимость $0.2500", detail)
        self.assertIn("токенов 120", detail)
        self.assertIn("стоимость $0.2500", out, "цена шага видна Оператору сразу")

    def test_costs_accumulate_over_steps(self):
        self.run_agent((0, [result_event(usd=0.25)]))
        self.run_agent((0, [result_event(usd=0.5)]))

        self.assertAlmostEqual(self.task_row()["spent_usd"], 0.75)

    def test_failed_attempts_are_paid_for_too(self):
        """Ретраи после T006 стоят денег — иначе потолок обходится провалами."""
        self.set_task(budget_usd=10.0)

        self.run_agent(*[(1, [result_event(usd=0.2)])] * config.AGENT_ATTEMPTS)

        self.assertAlmostEqual(self.task_row()["spent_usd"],
                               0.2 * config.AGENT_ATTEMPTS)
        self.assertIn("стоимость $0.2000", self.journal_details("agent run FAILED")[0])

    def test_missing_cost_is_warned_but_step_survives(self):
        out = self.run_agent((0, ["агент отработал без события стоимости\n"]))

        self.assertEqual(self.task_row()["spent_usd"], 0.0, "нечего прибавлять")
        self.assertEqual(self.task_row()["state"], "in_dev", "шаг не провален")
        self.assertIn("developer завершил (rc=0)", out)
        self.assertEqual(self.journal_details("agent cost UNKNOWN"),
                         [f"попытка 1/{config.AGENT_ATTEMPTS}: в выводе нет "
                          f"события со стоимостью — spent_usd не изменён"])
        self.assertEqual(self.journal_details("agent run finished"),
                         [f"rc=0, попытка 1/{config.AGENT_ATTEMPTS}"])

    def test_status_and_log_show_the_money(self):
        """Критерий приёмки 1: ненулевой spent_usd в status, цена шага в log."""
        self.set_task(budget_usd=5.0)

        self.run_agent((0, [result_event(usd=0.25)]))

        self.assertIn("$0.25/5.00", self.capture(catalog.cmd_status))
        self.assertIn("стоимость $0.2500", self.capture(catalog.cmd_log, self.TASK))

    def test_warning_at_seventy_percent(self):
        self.set_task(budget_usd=1.0)

        out = self.run_agent((0, [result_event(usd=0.7)]))

        self.assertIn("ВНИМАНИЕ", out)
        self.assertIn("больше 70% бюджета",
                      self.journal_details("бюджет: предупреждение")[0])
        self.assertEqual(self.task_row()["state"], "in_dev", "70% — не блокировка")

    def test_no_warning_below_the_threshold(self):
        self.set_task(budget_usd=1.0)

        out = self.run_agent((0, [result_event(usd=0.69)]))

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertEqual(self.journal_details("бюджет: предупреждение"), [])

    def test_exhausted_budget_escalates_the_task(self):
        self.set_task(budget_usd=0.3)

        out = self.run_agent((0, [result_event(usd=0.5)]))

        row = self.task_row()
        self.assertEqual(row["state"], "escalated")
        self.assertEqual(row["escalated_from"], "in_dev", "вернуться надо в шаг")
        self.assertIn("бюджет исчерпан",
                      self.journal_details("state -> escalated")[0])
        self.assertIn(f"artel.py budget {self.TASK}", out, "видно, чем разблокировать")

    def test_exhausted_budget_stops_the_retries(self):
        """Потолок пробит первой же попыткой — остальные не запускаются."""
        self.set_task(budget_usd=0.3)

        self.run_agent((1, [result_event(usd=0.5)]))

        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.task_row()["state"], "escalated")

    def test_exhausted_review_step_remembers_its_state(self):
        self.set_task(state="review", budget_usd=0.3)

        self.run_agent((0, [result_event(usd=0.5)]))

        self.assertEqual(self.task_row()["escalated_from"], "review")

    def test_run_refuses_to_start_over_budget(self):
        """Критерий приёмки 2: повторный run не стартует и объясняет, почему."""
        self.set_task(budget_usd=0.3)
        self.run_agent((0, [result_event(usd=0.5)]))
        self.capture(fsm.cmd_approve, self.TASK)  # Оператор снял эскалацию

        with mock.patch.object(runner.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit) as exit_:
                self.capture(runner.cmd_run, self.TASK)

        self.assertEqual(popen.call_count, 0, "агент не запускается")
        self.assertIn("бюджет исчерпан", str(exit_.exception))
        self.assertIn(f"artel.py budget {self.TASK}", str(exit_.exception))

    def test_task_without_budget_is_not_blocked(self):
        """БД прошлых версий: budget_usd NULL — потолка нет, а не потолок 0."""
        self.set_task(budget_usd=None)

        out = self.run_agent((0, [result_event(usd=0.5)]))

        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertNotIn("бюджет исчерпан", out)


class CmdBudgetTest(TmpRootTest):
    """`budget <id> <usd>`: поднятие потолка и снятие блокировки."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Потолок бюджета")

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def exhausted(self) -> None:
        """Задача, вставшая на исчерпанном бюджете."""
        self.set_task(state="escalated", escalated_from="in_dev",
                      budget_usd=0.3, spent_usd=0.5)

    def test_new_ceiling_is_saved_and_journaled(self):
        self.set_task(state="in_dev", budget_usd=5.0, spent_usd=1.0)

        out = self.capture(budget.cmd_budget, self.TASK, "12.5")

        self.assertAlmostEqual(self.task_row()["budget_usd"], 12.5)
        self.assertIn(("operator", "бюджет изменён",
                       "$5.00 -> $12.50, израсходовано $1.00"), self.journal())
        self.assertIn("$5.00 -> $12.50", out)

    def test_raised_ceiling_unblocks_the_task(self):
        """Критерий приёмки 2: после `budget` шаг продолжается."""
        self.exhausted()

        out = self.capture(budget.cmd_budget, self.TASK, "5")

        row = self.task_row()
        self.assertEqual(row["state"], "in_dev")
        self.assertIsNone(row["escalated_from"], "точка возврата одноразовая")
        self.assertIn(f"дальше: artel.py run {self.TASK}", out)
        self.assertIsNone(budget.budget_block(row))

    def test_unblocked_review_step_returns_to_review(self):
        self.exhausted()
        self.set_task(escalated_from="review")

        self.capture(budget.cmd_budget, self.TASK, "5")

        self.assertEqual(self.task_row()["state"], "review")

    def test_too_small_ceiling_keeps_the_block(self):
        self.exhausted()

        out = self.capture(budget.cmd_budget, self.TASK, "0.4")

        self.assertEqual(self.task_row()["state"], "escalated", "денег всё ещё нет")
        self.assertIn("этого мало", out)
        self.assertIn(("operator", "бюджет изменён",
                       "$0.30 -> $0.40, израсходовано $0.50"), self.journal(),
                      "в журнал пишется и неудачная попытка поднять потолок")

    def test_other_escalation_is_not_resolved_by_budget(self):
        """Эскалацию по провалу агента снимает approve, а не деньги."""
        self.set_task(state="escalated", escalated_from="review",
                      budget_usd=5.0, spent_usd=1.0)

        self.capture(budget.cmd_budget, self.TASK, "10")

        row = self.task_row()
        self.assertEqual(row["state"], "escalated")
        self.assertEqual(row["escalated_from"], "review", "точка возврата цела")

    def test_working_task_keeps_its_state(self):
        self.set_task(state="in_dev", spent_usd=1.0)

        self.capture(budget.cmd_budget, self.TASK, "10")

        self.assertEqual(self.task_row()["state"], "in_dev")

    def test_bad_amount_is_refused(self):
        for raw in ("", "дорого", "-5", "0", "nan", "inf"):
            with self.subTest(raw=raw):
                with self.assertRaises(SystemExit) as exit_:
                    self.capture(budget.cmd_budget, self.TASK, raw)
                self.assertIn("не сумма в долларах", str(exit_.exception))
        self.assertAlmostEqual(self.task_row()["budget_usd"],
                               config.DEFAULT_BUDGET_USD)

    def test_comma_is_accepted_as_decimal_separator(self):
        self.capture(budget.cmd_budget, self.TASK, "7,5")

        self.assertAlmostEqual(self.task_row()["budget_usd"], 7.5)

    def test_unknown_task_is_reported(self):
        with self.assertRaises(SystemExit) as exit_:
            self.capture(budget.cmd_budget, "T404", "10")

        self.assertIn("не найдена", str(exit_.exception))


if __name__ == "__main__":
    unittest.main()
