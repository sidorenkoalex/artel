"""AC-2: порядок подкоманды `canary run-task` — сверка метки родителя, сверка сводки набора, ведение одной задачи, сигналы и исходы.

Группа: разовый
Красен до реализации: подкоманды `run-task` нет — вызов уходит в ветку прогона `cmd_canary` и отказывает «нужен параметр --k»: ни отказа «метка прогона … не принадлежит родителю», ни красной строки расхождения сводки, ни вызова ведения задачи, ни кода 128 + номер сигнала.

Почему разовый: критерий требует подменить закрытые `_run_one_task` и
`_set_plan` (и фазу 1 `_run_task_in_ephemeral_clone` для красной строки
`_report_drive_failure`) — правила долгоживущего файла `tests/` такие
подмены запрещают.

Песочница — `tests.sandbox.InitializedTmpRootTest`. Подкоманда —
диспетчером `artel.main()` в главном потоке процесса теста. Сигнал во время
задачи шлёт подменённое ведение самому процессу (`os.kill(os.getpid(), …)`)
только после проверки, что `signal.getsignal` уже не равен обработчику до
вызова (`_runtask.RunTaskMixin.send_signal`); сигнал до ведения — тем же
приёмом из подменённого `_set_plan` и из подменённой атомарной замены записи
реестра. Значения порождаются от зерна; зерно печатается и входит в текст
провала.
"""
import contextlib
import inspect
import os
import signal
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runtask import RunTaskMixin, invoke, plan  # noqa: E402

from orchestrator import canary, config  # noqa: E402
from tests.sandbox import InitializedTmpRootTest  # noqa: E402

SIGNALS = (signal.SIGTERM, signal.SIGHUP)
REAL_RUN_ONE_TASK = canary._run_one_task


class RunTaskOrderTest(RunTaskMixin, InitializedTmpRootTest):
    """Подкоманда в процессе теста; ведение задачи и план набора подменены."""

    def setUp(self):
        super().setUp()
        self.setup_runtask()

    # ------------------------------------------------------------ фикстуры

    def set_name(self) -> str:
        return "nabor-" + self.token(5)

    def summary(self) -> str:
        return f"developer → model-{self.token(4)}; источник: набор"

    def call(self, stamp: str, set_name: str, summary: str, plan_value=None,
             task=None, set_plan=None, replace_hook=None) -> tuple:
        """Вызов подкоманды; (исход, шпионы). `plan_value=None` — настоящий `_set_plan`."""
        self.replaced.clear()
        with contextlib.ExitStack() as stack:
            spies = self.guards(stack)
            self.spy_replace(stack, replace_hook)
            if set_plan is not None:
                spies["_set_plan"] = stack.enter_context(mock.patch.object(
                    canary, "_set_plan", side_effect=set_plan))
            elif plan_value is not None:
                spies["_set_plan"] = stack.enter_context(mock.patch.object(
                    canary, "_set_plan", return_value=plan_value))
            spies["_run_one_task"] = stack.enter_context(mock.patch.object(
                canary, "_run_one_task", side_effect=task))
            outcome = invoke(self.argv(stamp, set_name, summary))
        return outcome, spies

    def own_written(self, stamp: str) -> bool:
        return any(dst == self.own_record_name(stamp) for _src, dst in self.replaced)

    def assert_no_own_files(self, stamp: str, ctx: str) -> None:
        own = self.own_record_name(stamp)
        self.assertEqual([n for n in self.listing() if n.startswith(own)], [], ctx)

    # -------------------------------------------------------- AC-2 (б)

    def test_ac2_mark_missing_or_foreign_refused_after_record(self):
        """Метки `<run_stamp>.lock` нет; метка несёт pid процесса теста; метка несёт pid завершённого процесса.

        Наблюдение в каждом: запись подкоманды была записана (замена в
        каталог реестра на `<run_stamp>-<pid>.json`) и снята, ненулевой код,
        текст «canary run-task: метка прогона <run_stamp> не принадлежит
        родителю <ppid>», ведение задачи и клон не звались, строк
        `canary_runs` нет.

        Ловит мутацию: сверка метки — «метка существует» без сравнения pid
        с `os.getppid()` (метка чужого pid проходит, задача ведётся), либо
        отказ сверки выходит, не сняв свою запись.
        """
        for case in ("нет метки", "pid не родителя", "мёртвый pid"):
            with self.subTest(случай=case):
                stamp, set_name, summary = self.stamp(), self.set_name(), self.summary()
                if case == "pid не родителя":
                    self.put_mark(stamp, os.getpid())
                elif case == "мёртвый pid":
                    self.put_mark(stamp, self.dead_pid())
                outcome, spies = self.call(stamp, set_name, summary,
                                           plan(set_name, summary))
                ctx = self.msg(f"{case}: {outcome!r}")
                self.assertNotEqual(outcome.code, 0, ctx)
                self.assertIn(f"canary run-task: метка прогона {stamp} не принадлежит "
                              f"родителю {self.ppid}", outcome.text, ctx)
                self.assertTrue(self.own_written(stamp), self.msg(
                    f"{case}: запись реестра не писалась до сверки метки; {self.replaced}"))
                self.assert_no_own_files(stamp, ctx)
                self.assertFalse(spies["_run_one_task"].called, ctx)
                self.assertFalse(spies["_ephemeral_clone"].called, ctx)
                self.assertEqual(self.rows(stamp), [], ctx)

    # -------------------------------------------------------- AC-2 (в)

    def test_ac2_summary_mismatch_red_row_without_clone(self):
        """Переданная `--summary` расходится со сводкой плана: настоящий `_set_plan` набора по умолчанию, подменённый план, пустая `--summary` при непустой сводке плана.

        Наблюдение: ровно одна строка `canary_runs` прогона — шаблон
        подкоманды, исход `_DRIVE_FAILED_OUTCOME`, `main_sha` пуст,
        `set_name` — имя набора, `models_summary` — переданная сводка
        (пустая — None), `task_id` и ожидание эскалации пусты, вердикт red;
        в выводе «набор изменился во время прогона»; ведение задачи и клон
        не звались; ненулевой код.

        Ловит мутацию: сверки сводки нет (задача ведётся на изменившемся
        наборе), либо красная строка пишет сводку плана вместо переданной,
        либо пустая `--summary` пишется пустой строкой вместо None.
        """
        real = canary._set_plan(config.CANARY_DEFAULT_SET)
        cases = [("настоящий план", config.CANARY_DEFAULT_SET, None,
                  real.summary + " " + self.token(4)),
                 ("подменённый план", self.set_name(), self.summary(), self.summary()),
                 ("пустая --summary", self.set_name(), self.summary(), "")]
        for case, set_name, plan_summary, passed in cases:
            with self.subTest(случай=case):
                stamp = self.stamp()
                self.put_mark(stamp, self.ppid)
                plan_value = None if plan_summary is None else plan(set_name, plan_summary)
                outcome, spies = self.call(stamp, set_name, passed, plan_value)
                ctx = self.msg(f"{case}: {outcome!r}")
                self.assertNotEqual(outcome.code, 0, ctx)
                self.assertIn("набор изменился во время прогона", outcome.text, ctx)
                self.assertFalse(spies["_run_one_task"].called, ctx)
                self.assertFalse(spies["_ephemeral_clone"].called, ctx)
                rows = self.rows(stamp)
                self.assertEqual(len(rows), 1, self.msg(f"{case}: {rows}"))
                row = rows[0]
                self.assertEqual(row["title"], self.template_name, ctx)
                self.assertEqual(row["outcome"], canary._DRIVE_FAILED_OUTCOME, ctx)
                self.assertFalse(row["main_sha"], ctx)
                self.assertEqual(row["set_name"], set_name, ctx)
                self.assertEqual(row["models_summary"], passed or None, ctx)
                self.assertFalse(row["task_id"], ctx)
                self.assertFalse(row["expected_escalation"], ctx)
                self.assertEqual(row["verdict"], "red", ctx)

    def test_ac2_empty_summary_matches_empty_plan_summary(self):
        """Подменённый `_set_plan` возвращает план с пустой сводкой; `--summary ""`.

        Наблюдение: сверка проходит — ведение задачи вызвано один раз,
        строк `canary_runs` нет, код 0.

        Ловит мутацию: пустая `--summary` сравнивается с `None` (или пустая
        сводка плана читается как «сводки нет» и отказывает) — красная
        строка расхождения вместо ведения.
        """
        stamp, set_name = self.stamp(), self.set_name()
        self.put_mark(stamp, self.ppid)
        outcome, spies = self.call(stamp, set_name, "", plan(set_name, ""))
        self.assertEqual(outcome.code, 0, self.msg(outcome))
        self.assertEqual(spies["_run_one_task"].call_count, 1, self.msg(outcome))
        self.assertEqual(self.rows(stamp), [], self.msg(outcome))

    # -------------------------------------------------------- AC-2 (г)

    def test_ac2_run_one_task_gets_plan_and_arguments(self):
        """Подменённое ведение задачи получает план из (0) и аргументы подкоманды: настоящий `_set_plan` набора по умолчанию и подменённый план другого набора.

        Наблюдение: ровно один вызов; `template_path` — путь `--template`,
        `run_stamp` и `target_sha` — из аргументов, `sha_label` None,
        `ratio` = `config.CANARY_DEVIATION_RATIO`, `codex_auth` None,
        `plan` — план `_set_plan(--set)` (`plan.name` = `--set`,
        `plan.summary` — сверенная сводка; для подменённого — тот же
        объект); профиль Codex не тронут; код 0.

        Ловит мутацию: подкоманда ведёт задачу без плана (`plan=None` —
        набор по умолчанию с пустой сводкой), передаёт пометку sha вместо
        None, берёт `ratio` литералом или передаёт вход Codex.
        """
        real = canary._set_plan(config.CANARY_DEFAULT_SET)
        self.assertEqual(real.codex_roles, (), self.msg("набор песочницы с Codex"))
        other = plan(self.set_name(), self.summary())
        for case, set_name, plan_value, expected in (
                ("настоящий план", config.CANARY_DEFAULT_SET, None, real),
                ("подменённый план", other.name, other, other)):
            with self.subTest(случай=case):
                stamp = self.stamp()
                self.put_mark(stamp, self.ppid)
                outcome, spies = self.call(stamp, set_name, expected.summary, plan_value)
                ctx = self.msg(f"{case}: {outcome!r}")
                self.assertEqual(outcome.code, 0, ctx)
                runs = spies["_run_one_task"]
                self.assertEqual(runs.call_count, 1, ctx)
                bound = inspect.signature(REAL_RUN_ONE_TASK).bind(
                    *runs.call_args.args, **runs.call_args.kwargs)
                bound.apply_defaults()
                got = bound.arguments
                self.assertEqual(Path(got["template_path"]), self.template, ctx)
                self.assertEqual(got["run_stamp"], stamp, ctx)
                self.assertEqual(got["target_sha"], self.sha, ctx)
                self.assertIsNone(got["sha_label"], ctx)
                self.assertEqual(got["ratio"], config.CANARY_DEVIATION_RATIO, ctx)
                self.assertIsNone(got["codex_auth"], ctx)
                self.assertIsNotNone(got["plan"], ctx)
                self.assertEqual(got["plan"].name, set_name, ctx)
                self.assertEqual(got["plan"].summary, expected.summary, ctx)
                self.assertEqual(tuple(got["plan"]), tuple(expected), ctx)
                if plan_value is not None:
                    self.assertIs(got["plan"], plan_value, ctx)
                for name in ("_locked_canary_profile", "_canary_profile_auth",
                             "_codex_clone_auth"):
                    self.assertFalse(spies[name].called, self.msg(f"{name}: {outcome!r}"))

    def test_ac2_signal_during_task_writes_interrupted_row(self):
        """SIGTERM, затем SIGHUP подменённому ведению задачи самим процессом; сводка плана непустая и пустая.

        Наблюдение: строка `canary_runs` прогона «оборвана сигналом SIGTERM»
        (SIGHUP) шаблона подкоманды: `task_id` пуст, `main_sha` — `--sha`,
        `set_name`, `models_summary` — `plan.summary or None`, вердикт red;
        код 128 + номер сигнала.

        Ловит мутацию: сигнал во время задачи не перехвачен подкомандой
        (процесс умирает без строки), строка пишет `main_sha` пустым, либо
        код выхода — 1 вместо 128 + номер сигнала.
        """
        for signum in SIGNALS:
            for plan_summary in (self.summary(), ""):
                name = signal.Signals(signum).name
                with self.subTest(сигнал=name, сводка=bool(plan_summary)):
                    stamp, set_name = self.stamp(), self.set_name()
                    self.put_mark(stamp, self.ppid)
                    before = signal.getsignal(signum)

                    def task(*args, **kwargs):
                        self.send_signal(signum, before)

                    outcome, _spies = self.call(stamp, set_name, plan_summary,
                                                plan(set_name, plan_summary), task)
                    ctx = self.msg(f"{name}: {outcome!r}")
                    self.assertEqual(outcome.code, 128 + signum, ctx)
                    rows = self.rows(stamp)
                    self.assertEqual(len(rows), 1, self.msg(f"{name}: {rows}"))
                    row = rows[0]
                    self.assertEqual(row["outcome"], f"оборвана сигналом {name}", ctx)
                    self.assertEqual(row["title"], self.template_name, ctx)
                    self.assertFalse(row["task_id"], ctx)
                    self.assertEqual(row["main_sha"], self.sha, ctx)
                    self.assertEqual(row["set_name"], set_name, ctx)
                    self.assertEqual(row["models_summary"], plan_summary or None, ctx)
                    self.assertEqual(row["verdict"], "red", ctx)

    def test_ac2_signal_before_task_exits_without_row(self):
        """SIGTERM и SIGHUP до ведения задачи: из подменённого `_set_plan` и из атомарной замены записи реестра.

        Наблюдение: код 128 + номер сигнала, строки `canary_runs` прогона
        нет, ни записи `<run_stamp>-<pid>.json`, ни её временного файла в
        каталоге реестра; ведение задачи не звалось.

        Ловит мутацию: перехват сигналов ставится только вокруг ведения
        задачи (сигнал на записи реестра или плане убивает процесс без
        уборки временного файла), либо сигнал до ведения пишет строку
        «оборвана сигналом».
        """
        for signum in SIGNALS:
            for place in ("_set_plan", "os.replace"):
                name = signal.Signals(signum).name
                with self.subTest(сигнал=name, место=place):
                    stamp, set_name, summary = self.stamp(), self.set_name(), self.summary()
                    self.put_mark(stamp, self.ppid)
                    before = signal.getsignal(signum)
                    value = plan(set_name, summary)
                    sent = []

                    def set_plan(_name):
                        sent.append(place)
                        self.send_signal(signum, before)
                        return value

                    def replace_hook(src, dst):
                        if dst.name == self.own_record_name(stamp) and not sent:
                            sent.append(place)
                            self.send_signal(signum, before)

                    if place == "_set_plan":
                        outcome, spies = self.call(stamp, set_name, summary,
                                                   set_plan=set_plan)
                    else:
                        outcome, spies = self.call(stamp, set_name, summary, value,
                                                   replace_hook=replace_hook)
                    ctx = self.msg(f"{name} в {place}: {outcome!r}")
                    self.assertEqual(sent, [place], ctx)
                    self.assertEqual(outcome.code, 128 + signum, ctx)
                    self.assertEqual(self.rows(stamp), [], ctx)
                    self.assert_no_own_files(stamp, ctx)
                    self.assertFalse(spies["_run_one_task"].called, ctx)

    def test_ac2_set_plan_refusal_exits_without_row_or_record(self):
        """Подменённый `_set_plan` отказывает именованным `sys.exit` (набора нет).

        Наблюдение: ненулевой код, текст отказа в выводе, строк
        `canary_runs` прогона нет, замен в каталог реестра не было, в
        каталоге только метка теста.

        Ловит мутацию: план строится после записи реестра (отказ плана
        оставляет след записи) или отказ плана проглатывается и задача
        ведётся набором по умолчанию.
        """
        stamp, set_name, summary = self.stamp(), self.set_name(), self.summary()
        self.put_mark(stamp, self.ppid)
        text = f"canary: набора {set_name} нет в canary_sets"

        def set_plan(_name):
            raise SystemExit(text)

        outcome, spies = self.call(stamp, set_name, summary, set_plan=set_plan)
        ctx = self.msg(outcome)
        self.assertNotEqual(outcome.code, 0, ctx)
        self.assertIn(text, outcome.text, ctx)
        self.assertEqual(self.rows(stamp), [], ctx)
        self.assertEqual(self.replaced, [], ctx)
        self.assertEqual(self.listing(), [f"{stamp}.lock"], ctx)
        self.assertFalse(spies["_run_one_task"].called, ctx)

    def test_ac2_drive_failure_exit_zero_and_exception_nonzero(self):
        """Настоящий `_run_one_task`, фаза 1 бросает `CanaryDriveFailed`; затем подменённое ведение бросает `RuntimeError`.

        Наблюдение: после красной строки `_report_drive_failure` (одна строка
        прогона с исходом `_DRIVE_FAILED_OUTCOME`, вердикт red) — код 0;
        исключение из ведения — ненулевой код, строк прогона нет.

        Ловит мутацию: код выхода подкоманды считается по строке прогона
        (красная — ненулевой), либо исключение ведения глотается с кодом 0
        или превращается в строку «оборвана».
        """
        stamp, set_name, summary = self.stamp(), self.set_name(), self.summary()
        self.put_mark(stamp, self.ppid)
        failure = canary.CanaryDriveFailed(self.template_name, None,
                                           "завершился с кодом 3",
                                           self.home / "diag", None)
        with mock.patch.object(canary, "_run_task_in_ephemeral_clone",
                               side_effect=failure):
            outcome, _spies = self.call(stamp, set_name, summary, plan(set_name, summary),
                                        task=REAL_RUN_ONE_TASK)
        ctx = self.msg(outcome)
        self.assertEqual(outcome.code, 0, ctx)
        rows = self.rows(stamp)
        self.assertEqual(len(rows), 1, self.msg(rows))
        self.assertEqual(rows[0]["outcome"], canary._DRIVE_FAILED_OUTCOME, ctx)
        self.assertEqual(rows[0]["verdict"], "red", ctx)

        stamp = self.stamp()
        self.put_mark(stamp, self.ppid)

        def boom(*args, **kwargs):
            raise RuntimeError("подменённое ведение упало")

        outcome, _spies = self.call(stamp, set_name, summary, plan(set_name, summary),
                                    task=boom)
        ctx = self.msg(outcome)
        self.assertNotEqual(outcome.code, 0, ctx)
        self.assertEqual(self.rows(stamp), [], ctx)


if __name__ == "__main__":
    unittest.main()
