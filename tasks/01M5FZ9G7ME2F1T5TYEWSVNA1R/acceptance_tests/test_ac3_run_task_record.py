"""AC-3: запись дочернего процесса в реестре живого прогона — поля на время задачи и уборка на любом исходе.

Группа: разовый
Красен до реализации: подкоманды `run-task` нет — вызов отказывает в ветке прогона `cmd_canary` («нужен параметр --k»), во время задачи записи `<run_stamp>-<pid>.json` в каталоге реестра нет.

Почему разовый: критерий требует подменённой задачи (закрытый
`_run_one_task`) и подменённого плана (`_set_plan`) — правила
долгоживущего файла `tests/` такие подмены запрещают.

Песочница — `tests.sandbox.InitializedTmpRootTest`; родитель — запись и
метка прогона с pid `os.getppid()` процесса теста, разложенные файлами.
Подкоманда — диспетчером `artel.main()` в процессе теста. Время старта
процесса для сверки — `doctor.process_start_time`, тот же помощник, что
пишет `_live_run_record`. Значения порождаются от зерна; зерно печатается и
входит в текст провала.
"""
import contextlib
import json
import os
import signal
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runtask import RunTaskMixin, invoke, plan  # noqa: E402

from orchestrator import canary, doctor  # noqa: E402
from tests.sandbox import InitializedTmpRootTest  # noqa: E402

FIELDS = ("run_stamp", "sha", "set_name", "pid", "process_start", "started_at",
          "tasks", "parent_pid", "template")


class RunTaskRecordTest(RunTaskMixin, InitializedTmpRootTest):
    """Подкоманда в процессе теста; ведение задачи и план набора подменены."""

    def setUp(self):
        super().setUp()
        self.setup_runtask()

    def parent(self, stamp: str, set_name: str) -> dict:
        """Запись и метка родителя; снимок каталога реестра."""
        self.put_record(stamp, self.ppid, self.sha, set_name)
        self.put_mark(stamp, self.ppid)
        return self.snapshot()

    def call_task(self, stamp, set_name, summary, plan_value, task=None):
        with contextlib.ExitStack() as stack:
            self.guards(stack)
            self.spy_replace(stack)
            stack.enter_context(mock.patch.object(canary, "_set_plan",
                                                  return_value=plan_value))
            stack.enter_context(mock.patch.object(canary, "_run_one_task",
                                                  side_effect=task))
            return invoke(self.argv(stamp, set_name, summary))

    # -------------------------------------------------------------- AC-3

    def test_ac3_record_fields_during_task(self):
        """Во время подменённой задачи каталог реестра несёт запись `<run_stamp>-<свой pid>.json`.

        Наблюдение: поля `run_stamp`, `sha`, `set_name` — из аргументов;
        `pid` — pid процесса подкоманды; `process_start` — время старта
        процесса тем же помощником `process_start_time`; `started_at` —
        момент внутри вызова; `tasks` = 1; `parent_pid` = `os.getppid()`;
        `template` — имя шаблона без `.md`. Временного `.json.tmp` нет.

        Ловит мутацию: запись пишется прежним `_live_run_record` (нет
        `parent_pid`/`template`, `tasks` = число шаблонов), `template` несёт
        путь или имя с `.md`, `parent_pid` — свой pid вместо `os.getppid()`.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        summary = "сводка " + self.token(6)
        self.parent(stamp, set_name)
        seen = {}

        def task(*args, **kwargs):
            seen["listing"] = self.listing()
            path = self.registry() / self.own_record_name(stamp)
            seen["record"] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

        before = datetime.now(timezone.utc)
        outcome = self.call_task(stamp, set_name, summary, plan(set_name, summary), task)
        after = datetime.now(timezone.utc)
        ctx = self.msg(f"{outcome!r}; {seen}")
        self.assertEqual(outcome.code, 0, ctx)
        record = seen.get("record")
        self.assertIsInstance(record, dict, ctx)
        for field in FIELDS:
            self.assertIn(field, record, ctx)
        self.assertEqual(record["run_stamp"], stamp, ctx)
        self.assertEqual(record["sha"], self.sha, ctx)
        self.assertEqual(record["set_name"], set_name, ctx)
        self.assertEqual(record["pid"], os.getpid(), ctx)
        self.assertEqual(record["tasks"], 1, ctx)
        self.assertEqual(record["parent_pid"], self.ppid, ctx)
        self.assertEqual(record["template"], self.template_name, ctx)
        started = doctor.process_start_time(os.getpid())
        if started is None:
            self.assertIsNone(record["process_start"], ctx)
        else:
            self.assertIsNotNone(record["process_start"], ctx)
            self.assertEqual(datetime.fromisoformat(record["process_start"]), started, ctx)
        moment = datetime.fromisoformat(record["started_at"])
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        self.assertTrue(before - timedelta(seconds=1) <= moment <= after + timedelta(seconds=1),
                        self.msg(f"started_at {moment} вне [{before}, {after}]"))
        self.assertFalse([n for n in seen["listing"] if n.endswith(".tmp")], ctx)

    def test_ac3_no_record_left_after_every_outcome(self):
        """Штатный конец, исключение в задаче, SIGTERM и SIGHUP в задаче, отказ сверки метки (б), отказ сверки сводки (в).

        Наблюдение после каждого исхода: ни своей записи, ни её временного
        файла; метка родителя и запись родителя — те же файлы с тем же
        содержимым (в случае (б) метка несёт чужой pid и тоже цела).

        Ловит мутацию: снятие записи — строкой после задачи, а не в
        `finally` (исключение и сигнал оставляют запись), отказ (б)/(в)
        выходит до снятия, либо снятие записи заодно снимает метку
        `<run_stamp>.lock`, как это делает `_live_run_record`.
        """
        for case in ("штатно", "исключение", "SIGTERM", "SIGHUP", "(б)", "(в)"):
            with self.subTest(исход=case):
                stamp, set_name = self.stamp(), "nabor-" + self.token(5)
                summary = "сводка " + self.token(6)
                self.put_record(stamp, self.ppid, self.sha, set_name)
                self.put_mark(stamp, os.getpid() if case == "(б)" else self.ppid)
                shot = self.snapshot()
                passed = summary + " иная" if case == "(в)" else summary
                seen = {}

                def task(*args, _case=case, _stamp=stamp, **kwargs):
                    seen["record"] = (self.registry() / self.own_record_name(_stamp)).exists()
                    if _case == "исключение":
                        raise RuntimeError("подменённое ведение упало")
                    if _case.startswith("SIG"):
                        signum = getattr(signal, _case)
                        self.send_signal(signum, self.before[signum])

                self.before = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
                outcome = self.call_task(stamp, set_name, passed, plan(set_name, summary), task)
                ctx = self.msg(f"{case}: {outcome!r}")
                if case in ("штатно", "исключение") or case.startswith("SIG"):
                    self.assertTrue(seen.get("record"), self.msg(f"{case}: записи не было во время задачи"))
                self.assertEqual(self.snapshot(), shot, ctx)

    def test_ac3_failed_replace_leaves_no_tmp_and_mark_intact(self):
        """Атомарная замена `os.replace` своей записи бросает `OSError`.

        Наблюдение: в момент сбоя временный файл лежит, а `live_runs()` не
        возвращает записи с pid подкоманды (временный файл не попадает под
        маску `*.json`); после вызова временного файла нет, своей записи нет,
        метка родителя та же (содержимое, inode).

        Ловит мутацию: временный файл назван с суффиксом `.json` (его читает
        `live_runs`), либо уборка в `finally` снимает только запись, но не
        `<имя>.json.tmp`.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        summary = "сводка " + self.token(6)
        self.put_mark(stamp, self.ppid)
        shot = self.snapshot()
        seen = {}

        def hook(src, dst):
            if dst.name == self.own_record_name(stamp):
                seen["tmp_exists"] = src.exists()
                seen["tmp"] = src.name
                seen["live"] = [e.get("pid") for e in canary.live_runs()]
                raise OSError("подменённая замена отказала")

        with contextlib.ExitStack() as stack:
            self.guards(stack)
            self.spy_replace(stack, hook)
            stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan(set_name, summary)))
            runs = stack.enter_context(mock.patch.object(canary, "_run_one_task"))
            outcome = invoke(self.argv(stamp, set_name, summary))
        ctx = self.msg(f"{outcome!r}; {seen}")
        self.assertTrue(seen.get("tmp_exists"), ctx)
        self.assertFalse(seen["tmp"].endswith(".json"), ctx)
        self.assertNotIn(os.getpid(), seen["live"], ctx)
        self.assertFalse(runs.called, ctx)
        self.assertEqual(self.snapshot(), shot, ctx)


if __name__ == "__main__":
    unittest.main()
