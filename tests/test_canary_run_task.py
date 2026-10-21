"""Внутренняя подкоманда `canary run-task` (SPEC 01M5FZ9G7ME2F1T5TYEWSVNA1R,
требования 1-3): разбор флагов в `artel._cmd_canary` и тело
`canary.cmd_canary_run_task` — отказы до записи реестра, сверка метки
родителя и сводки набора, запись дочернего в реестр и её снятие при любом
исходе, строка «оборвана сигналом» и код 128 + номер сигнала.

Песочница — `tests.sandbox.InitializedTmpRootTest`: каталог реестра
(`config.ROOT/.artel/canary-live`) и БД — во временном каталоге. План набора
(`_set_plan`) и ведение задачи (`_run_one_task`) подменены; клон и обращение
к origin не подменяются, а запрещаются — их вызов роняет тест. Родитель
подкоманды — `os.getppid()` процесса теста, его метку тест кладёт файлом.
Сигнал шлёт подменённое ведение самому процессу только после проверки, что
обработчик поставлен подкомандой. Входы — фиксированные значения.
"""
import contextlib
import itertools
import json
import os
import signal
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, gitcmd, runner, store
from tests.sandbox import InitializedTmpRootTest, TmpRootTest

STAMP = "20310305T101500Z"
SHA = "3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93"
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
TEMPLATE_NAME = "uchebnaya-sosna"


class RunTaskArgumentOrderTest(TmpRootTest):
    def test_flags_in_any_order_reach_subcommand(self):
        """Пять флагов во всех перестановках; значения фиксированы.

        Наблюдение: подкоманда вызвана один раз с run_stamp, путём шаблона,
        sha, набором и сводкой из своих флагов, независимо от порядка.

        Ловит мутацию: разбор берёт значения по позиции (`rest[1]` — всегда
        `--stamp` и т. д.) либо путает значения соседних флагов — при
        перестановке подкоманда получает чужое значение.
        """
        values = {"--stamp": STAMP,
                  "--template": f"/pul/{TEMPLATE_NAME}.md",
                  "--sha": SHA, "--set": SET_NAME, "--summary": SUMMARY}
        for order in itertools.permutations(artel._RUN_TASK_FLAGS):
            argv = [item for flag in order for item in (flag, values[flag])]
            with self.subTest(порядок=order), mock.patch.object(
                    canary, "cmd_canary_run_task") as run_task:
                artel._cmd_canary(["run-task", *argv])
                run_task.assert_called_once_with(
                    run_stamp=values["--stamp"],
                    template_path=Path(values["--template"]),
                    target_sha=values["--sha"], set_name=values["--set"],
                    summary=values["--summary"])


class RunTaskSandboxTest(InitializedTmpRootTest):
    """Общие фикстуры: шаблон, реестр, запреты клона и origin."""

    def setUp(self):
        super().setUp()
        handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
        self.addCleanup(lambda: [signal.signal(s, h) for s, h in handlers.items()])
        self.template = Path(config.ROOT) / "pool" / f"{TEMPLATE_NAME}.md"
        self.template.parent.mkdir(parents=True, exist_ok=True)
        self.template.write_text("# учебная задача\n", encoding="utf-8")
        self.registry = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        self.record_name = f"{STAMP}-{os.getpid()}.json"
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for name in ("_resolve_target_sha", "_ephemeral_clone",
                     "_locked_canary_profile", "_canary_profile_auth",
                     "_codex_clone_auth", "_live_run_record"):
            stack.enter_context(mock.patch.object(
                canary, name, side_effect=AssertionError(f"{name} вызван")))
        stack.enter_context(mock.patch.object(
            gitcmd, "fetch_ref_sha",
            side_effect=AssertionError("gitcmd.fetch_ref_sha вызван")))

    def plan(self, summary=SUMMARY, codex_roles=()):
        return canary.CanarySetPlan(SET_NAME, {}, None, summary, tuple(codex_roles))

    def put_mark(self, pid) -> Path:
        self.registry.mkdir(parents=True, exist_ok=True)
        mark = self.registry / f"{STAMP}.lock"
        mark.write_text(f"{pid}\n", encoding="utf-8")
        return mark

    def listing(self) -> list:
        if not self.registry.is_dir():
            return []
        return sorted(p.name for p in self.registry.iterdir())

    def rows(self) -> list:
        return [dict(r) for r in store.all_canary_runs(store.db())]

    def run_task(self, *, plan=None, task=None, summary=SUMMARY):
        """Тело подкоманды; (исключение или None, подменённое ведение)."""
        with mock.patch.object(canary, "_set_plan",
                               return_value=plan or self.plan()), \
                mock.patch.object(canary, "_run_one_task",
                                  side_effect=task) as drive:
            try:
                canary.cmd_canary_run_task(
                    run_stamp=STAMP, template_path=self.template,
                    target_sha=SHA, set_name=SET_NAME, summary=summary)
            except BaseException as exc:  # noqa: BLE001 — исход сценария
                return exc, drive
        return None, drive

    def assert_own_files_gone(self):
        self.assertEqual([n for n in self.listing()
                          if n.startswith(self.record_name)], [])

    def send_signal(self, signum, before):
        if signal.getsignal(signum) == before:
            raise AssertionError(f"обработчик {signal.Signals(signum).name} "
                                 f"не поставлен подкомандой — сигнал не отправлен")
        os.kill(os.getpid(), signum)


class RunTaskParseRefusalTest(RunTaskSandboxTest):
    def test_parse_refusals_exit_nonzero_with_empty_registry(self):
        """Пропуск флага, повтор, флаг без значения (последним и перед
        `--…`), лишний аргумент и `--stamp` вне формы — ненулевой выход до
        плана набора, каталог реестра пуст.

        Ловит мутацию: разбор пропускает один из отказов (например,
        принимает `--detach` или берёт `--set` следующим значением) — тело
        подкоманды зовёт `_set_plan` и пишет запись.
        """
        full = ["--stamp", STAMP, "--template", str(self.template),
                "--sha", SHA, "--set", SET_NAME, "--summary", SUMMARY]
        cases = {"повтор": full + ["--sha", SHA],
                 "флаг последним": full[:-1],
                 "флаг перед --": ["--stamp", "--template", str(self.template),
                                   "--sha", SHA, "--set", SET_NAME,
                                   "--summary", SUMMARY],
                 "лишний --detach": full + ["--detach"],
                 "лишний --k": full + ["--k", "1"],
                 "лишний --result-file": full + ["--result-file", "x.json"],
                 "stamp вне формы": ["--stamp", "2031-03-05"] + full[2:]}
        for index in range(0, len(full), 2):
            cases[f"нет {full[index]}"] = full[:index] + full[index + 2:]
        for name, argv in cases.items():
            with self.subTest(name), mock.patch.object(
                    canary, "_set_plan",
                    side_effect=AssertionError("_set_plan вызван")):
                with self.assertRaises(SystemExit) as caught:
                    artel._cmd_canary(["run-task", *argv])
                self.assertNotIn(caught.exception.code, (0, None))
                self.assertEqual(self.listing(), [])

    def test_empty_summary_value_accepted(self):
        """`--summary ""` — законное значение, отказа разбора нет.

        Ловит мутацию: «флаг без значения» проверяется по пустоте значения,
        а не по `--` в начале — пустая сводка отказывает.
        """
        with mock.patch.object(canary, "cmd_canary_run_task") as run_task:
            artel._cmd_canary(["run-task", "--stamp", STAMP, "--template",
                               str(self.template), "--sha", SHA, "--set",
                               SET_NAME, "--summary", ""])
        self.assertEqual(run_task.call_args.kwargs["summary"], "")

    def test_role_refused_and_not_in_help(self):
        """Под ролью подкоманда не разрешена; справка её не называет.

        Ловит мутацию: `canary run-task` внесён в белый список ролей или в
        текст справки `artel.py`.
        """
        self.assertFalse(artel._role_allowed_command("canary", ["run-task"]))
        with mock.patch.object(runner, "in_role_environment", return_value=True), \
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
            with self.assertRaises(SystemExit) as caught:
                artel._refuse_if_role_restricted("canary", ["run-task"])
        self.assertIn("artel.py canary run-task: команда недоступна процессу роли",
                      str(caught.exception.code))
        self.assertNotIn("run-task", artel.__doc__ or "")


class RunTaskBodyTest(RunTaskSandboxTest):
    def test_codex_set_refused_before_record(self):
        """Набор с ролью на Codex — отказ именованным текстом, реестр пуст,
        задача не ведётся.

        Ловит мутацию: проверка `codex_roles` стоит после записи реестра или
        снята — в реестре остаётся след либо ведение задачи вызвано.
        """
        self.put_mark(os.getppid())
        exc, drive = self.run_task(plan=self.plan(codex_roles=("developer",)))
        self.assertIsInstance(exc, SystemExit)
        self.assertIn(f"canary run-task: набор {SET_NAME} с ролями на провайдере "
                      f"codex не ведётся отдельным процессом — профиль Codex "
                      f"канарейки один на машину", str(exc.code))
        drive.assert_not_called()
        self.assertEqual(self.listing(), [f"{STAMP}.lock"])
        self.assertEqual(self.rows(), [])

    def test_mark_missing_or_foreign_refused_and_record_dropped(self):
        """Метки нет либо в ней чужой pid — ненулевой выход, запись снята,
        задача не ведётся, строки нет; чужая метка не тронута.

        Ловит мутацию: сверка метки не сравнивает pid с `os.getppid()` либо
        отказ (б) не снимает свою запись в `finally`.
        """
        for owner in (None, os.getppid() + 1):
            with self.subTest(метка=owner):
                if owner is not None:
                    self.put_mark(owner)
                exc, drive = self.run_task()
                self.assertIsInstance(exc, SystemExit)
                self.assertIn(f"canary run-task: метка прогона {STAMP} не "
                              f"принадлежит родителю {os.getppid()}", str(exc.code))
                drive.assert_not_called()
                self.assert_own_files_gone()
                self.assertEqual(self.rows(), [])
                if owner is not None:
                    self.assertEqual((self.registry / f"{STAMP}.lock").read_text(),
                                     f"{owner}\n")

    def test_summary_mismatch_writes_red_row_without_task(self):
        """Сводка плана не равна `--summary` — одна красная строка с полями
        `_report_drive_failure`, ненулевой выход, задача не ведётся; при
        пустой `--summary` `models_summary` равен None.

        Ловит мутацию: сверка сводки снята (задача ведётся) либо строка
        пишет сводку плана вместо переданной / пустую строку вместо None.
        """
        self.put_mark(os.getppid())
        for passed, expected in (("developer → другая", "developer → другая"),
                                 ("", None)):
            with self.subTest(сводка=passed):
                before = len(self.rows())
                exc, drive = self.run_task(summary=passed)
                self.assertIsInstance(exc, SystemExit)
                self.assertNotIn(exc.code, (0, None))
                self.assertIn("набор изменился во время прогона", str(exc.code))
                drive.assert_not_called()
                rows = self.rows()[before:]
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(
                    (row["run_stamp"], row["title"], row["task_id"],
                     row["outcome"], row["main_sha"], row["verdict"],
                     row["set_name"], row["models_summary"],
                     row["expected_escalation"]),
                    (STAMP, TEMPLATE_NAME, None, canary._DRIVE_FAILED_OUTCOME,
                     None, "red", SET_NAME, expected, None))
                self.assert_own_files_gone()

    def test_empty_summary_matches_empty_plan_summary(self):
        """Пустая `--summary` при пустой сводке плана — сверка проходит.

        Ловит мутацию: пустая сводка трактуется как расхождение.
        """
        self.put_mark(os.getppid())
        exc, drive = self.run_task(plan=self.plan(summary=""), summary="")
        self.assertIsNone(exc)
        drive.assert_called_once()
        self.assertEqual(self.rows(), [])

    def test_record_fields_during_task_and_cleanup_after(self):
        """Во время задачи запись `<stamp>-<pid>.json` несёт поля требования 3;
        ведение получает план и аргументы подкоманды; после штатного конца
        записи и `.tmp` нет, метка цела, выход без исключения.

        Ловит мутацию: в записи нет `parent_pid`/`template` или `tasks` не 1;
        `_run_one_task` получает не план (0) либо `sha_label`/`codex_auth`
        не None; `finally` не снимает запись — она остаётся и держит окно.
        """
        mark = self.put_mark(os.getppid())
        seen = {}

        def task(*args, **kwargs):
            seen["listing"] = self.listing()
            seen["record"] = json.loads(
                (self.registry / self.record_name).read_text(encoding="utf-8"))

        plan = self.plan()
        exc, drive = self.run_task(plan=plan, task=task)
        self.assertIsNone(exc)
        drive.assert_called_once_with(self.template, STAMP,
                                      config.CANARY_DEVIATION_RATIO, SHA,
                                      None, plan, None)
        self.assertEqual(seen["listing"], sorted([f"{STAMP}.lock", self.record_name]))
        record = seen["record"]
        self.assertEqual(
            {k: record[k] for k in ("run_stamp", "sha", "set_name", "pid",
                                    "tasks", "parent_pid", "template")},
            {"run_stamp": STAMP, "sha": SHA, "set_name": SET_NAME,
             "pid": os.getpid(), "tasks": 1, "parent_pid": os.getppid(),
             "template": TEMPLATE_NAME})
        self.assertTrue(record["started_at"])
        self.assertIn("process_start", record)
        self.assertEqual(self.listing(), [f"{STAMP}.lock"])
        self.assertEqual(mark.read_text(), f"{os.getppid()}\n")

    def test_task_exception_propagates_and_record_dropped(self):
        """Исключение из ведения — выходит наружу, строки нет, записи нет.

        Ловит мутацию: исключение глотается (код 0) либо запись не снимается.
        """
        self.put_mark(os.getppid())
        exc, _drive = self.run_task(task=RuntimeError("ведение упало"))
        self.assertIsInstance(exc, RuntimeError)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.listing(), [f"{STAMP}.lock"])

    def test_signal_during_task_writes_interrupted_row(self):
        """SIGTERM и SIGHUP во время задачи — строка «оборвана сигналом
        <имя>» с полями `cmd_canary`, код 128 + номер, записи нет.

        Ловит мутацию: `CanaryInterrupted` в ведении уходит во внешний
        `except` без строки либо строка без `main_sha`/с не тем кодом.
        """
        self.put_mark(os.getppid())
        for signum in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal.Signals(signum).name):
                before_rows = len(self.rows())
                before = signal.getsignal(signum)
                exc, _drive = self.run_task(
                    task=lambda *a, **k: self.send_signal(signum, before))
                self.assertIsInstance(exc, SystemExit)
                self.assertEqual(exc.code, 128 + signum)
                rows = self.rows()[before_rows:]
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(
                    (row["title"], row["task_id"], row["outcome"],
                     row["main_sha"], row["verdict"], row["set_name"],
                     row["models_summary"]),
                    (TEMPLATE_NAME, None,
                     f"оборвана сигналом {signal.Signals(signum).name}",
                     SHA, "red", SET_NAME, SUMMARY))
                self.assertEqual(self.listing(), [f"{STAMP}.lock"])
                self.assertEqual(signal.getsignal(signum), before)

    def test_signal_before_task_exits_without_row(self):
        """Сигнал во время записи реестра (до ведения) — код 128 + номер,
        строки нет, ни записи, ни `.tmp`.

        Ловит мутацию: `_interrupt_on_signal` поставлен после записи реестра
        либо `finally` не убирает `.tmp`.
        """
        self.put_mark(os.getppid())
        real_replace = os.replace
        before = signal.getsignal(signal.SIGTERM)

        def replace(src, dst, *args, **kwargs):
            if Path(os.fsdecode(dst)).name == self.record_name:
                self.send_signal(signal.SIGTERM, before)
            return real_replace(src, dst, *args, **kwargs)

        with mock.patch.object(os, "replace", replace):
            exc, drive = self.run_task()
        self.assertIsInstance(exc, SystemExit)
        self.assertEqual(exc.code, 128 + signal.SIGTERM)
        drive.assert_not_called()
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.listing(), [f"{STAMP}.lock"])

    def test_replace_failure_drops_tmp_and_keeps_mark(self):
        """Сбой атомарной замены — исключение наружу, `.tmp` убран, метка цела.

        Ловит мутацию: временный файл пишется сразу под маской `*.json` либо
        не убирается в `finally`.
        """
        mark = self.put_mark(os.getppid())
        with mock.patch.object(os, "replace", side_effect=OSError("диск")):
            exc, drive = self.run_task()
        self.assertIsInstance(exc, OSError)
        drive.assert_not_called()
        self.assertEqual(self.listing(), [f"{STAMP}.lock"])
        self.assertEqual(mark.read_text(), f"{os.getppid()}\n")

    def test_set_plan_refusal_exits_without_record(self):
        """Отказ `_set_plan` — ненулевой выход, ни записи, ни строки.

        Ловит мутацию: запись реестра пишется до построения плана.
        """
        self.put_mark(os.getppid())
        with mock.patch.object(canary, "_set_plan",
                               side_effect=SystemExit("canary: набор не найден")), \
                mock.patch.object(canary, "_run_one_task") as drive:
            with self.assertRaises(SystemExit):
                canary.cmd_canary_run_task(
                    run_stamp=STAMP, template_path=self.template,
                    target_sha=SHA, set_name=SET_NAME, summary=SUMMARY)
        drive.assert_not_called()
        self.assertEqual(self.listing(), [f"{STAMP}.lock"])
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
