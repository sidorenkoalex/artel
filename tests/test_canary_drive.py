"""Юнит-тесты ведения учебной задачи канарейки кодом проверяемого коммита
(SPEC 01M3PKSWPETC49WFTFZ69GH3F2; ADR-0021, этап 0).

Фаза 1 прогона (`canary._run_task_in_ephemeral_clone`) запускает процесс
интерпретатора из эфемерного клона и читает его результат; здесь клон —
настоящий `git clone` крошечного репозитория, чей
`orchestrator/canary_drive.py` в каждом коммите — сценарий теста с
собственной меткой, а не код пульта. Так «чьим кодом велась задача»
наблюдаемо без единого шага роли: метка в результате есть только у кода
клона.
"""
import contextlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, canary_drive, config, store
from orchestrator.providers import codex as codex_provider

#: `subprocess.run` до любых подмен песочниц — клон теста делается им.
_REAL_RUN = subprocess.run

_METRICS = {
    "steps": 2, "cost_usd": 0.0, "review_iterations": 0, "escalations": [],
    "dev_retries": 0, "outcome": "killed", "kill_note": "штатно",
    "test_author_visited": False, "ceiling_exhausted": False,
    "ceiling_raise": None,
}

#: Вход клона для сценариев. `{mark}`, `{head}`, `{rc}`, `{sleep}`,
#: `{flush}` — подстановки коммита сценария.
_ENTRY = '''
import argparse, json, subprocess, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("--result")
args, _ = parser.parse_known_args()
print("вывод процесса клона {mark}", flush={flush})
time.sleep({sleep})
head = {head!r} or subprocess.run(["git", "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
result = {{"task_id": "01CLONETASK", "head": head, "outcome": "killed",
          "escalated": False, "metrics": {metrics!r},
          "steps": [{{"ts": "t", "actor": "clone", "action": "state -> merge_gate",
                     "detail": "{mark}"}}]}}
with open(args.result, "w", encoding="utf-8") as fh:
    json.dump(result, fh)
sys.exit({rc})
'''


def _git(repo: Path, *args: str) -> str:
    res = _REAL_RUN(["git", *args], cwd=repo, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {res.stderr}")
    return res.stdout.strip()


class _CloneDriveTest(unittest.TestCase):
    """Репозиторий «пульта» теста и подмена `_ephemeral_clone` настоящим
    клоном на проверяемом коммите."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="drive-repo-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.outer = Path(tempfile.mkdtemp(prefix="drive-outer-")).resolve()
        self.addCleanup(shutil.rmtree, self.outer, ignore_errors=True)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.invalid")
        _git(self.repo, "config", "user.name", "t")
        (self.repo / "orchestrator").mkdir()
        (self.repo / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
        self.template = self.outer / "shablon.md"
        self.template.write_text("# ТЗ\n", encoding="utf-8")
        self.clones = []
        patcher = mock.patch.object(canary, "_ephemeral_clone", self._clone)
        patcher.start()
        self.addCleanup(patcher.stop)

    @contextlib.contextmanager
    def _clone(self, target_sha=None, layer_text=None, codex_auth=None):
        dest = Path(tempfile.mkdtemp(prefix="drive-clone-")).resolve()
        self.clones.append(dest)
        try:
            _git(dest, "clone", "-q", str(self.repo), str(dest))
            if target_sha is not None:
                _git(dest, "checkout", "-q", target_sha)
            yield dest
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def commit(self, mark: str, *, head: str = "", rc: int = 0,
               sleep: float = 0, entry: bool = True, flush: bool = True) -> str:
        path = self.repo / "orchestrator" / "canary_drive.py"
        if entry:
            path.write_text(_ENTRY.format(mark=mark, head=head, rc=rc,
                                          sleep=sleep, flush=flush,
                                          metrics=_METRICS),
                            encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        (self.repo / "mark.txt").write_text(mark, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", mark)
        return _git(self.repo, "rev-parse", "HEAD")

    def phase_one(self, target: str) -> tuple:
        return canary._run_task_in_ephemeral_clone(
            self.template, "20260929T000000Z", target, self.outer)


class CloneCodeDrivesTheTaskTest(_CloneDriveTest):

    def test_result_carries_the_mark_of_the_checked_commit_code(self):
        """Проверяемый коммит и следующий за ним несут разные метки во входе
        клона: результат фазы 1 несёт метку проверяемого коммита, HEAD клона
        — сам проверяемый коммит, исход штатный.

        Ловит мутацию: ведение учебной задачи в процессе пульта (код пульта
        метки клона не знает — её нет в шагах результата) либо процесс
        клона запускается не из клона на проверяемом коммите (метка
        следующего коммита).
        """
        target = self.commit("метка-проверяемого")
        self.commit("метка-следующего")

        (task_id, _title, _expected, steps, metrics, _actual, _mismatch,
         normal_outcome, diag_dir) = self.phase_one(target)

        self.assertEqual(task_id, "01CLONETASK")
        self.assertEqual([s["detail"] for s in steps], ["метка-проверяемого"])
        self.assertEqual(metrics["code_sha"], target)
        self.assertEqual(metrics["target_sha"], target)
        self.assertTrue(normal_outcome)
        self.assertIsNone(diag_dir)
        self.assertTrue(self.clones and not any(c.exists() for c in self.clones))

    def test_process_is_launched_from_the_clone_with_the_result_path(self):
        """Процесс — интерпретатор пульта, модуль входа, рабочий каталог —
        клон; путь файла результата передаётся аргументом `--result`.

        Ловит мутацию: процесс запускается с рабочим каталогом главной копии
        (код пульта вместо кода клона) либо файл результата ему не
        передаётся (обмен через разбор вывода).
        """
        target = self.commit("м")
        launches = []
        real_popen = subprocess.Popen

        def spy(args, *a, **kwargs):
            # `git` теста тоже идёт через `Popen` — считаются только
            # запуски интерпретатора.
            if list(args)[:1] == [sys.executable]:
                launches.append((list(args), Path(kwargs["cwd"])))
            return real_popen(args, *a, **kwargs)

        with mock.patch.object(canary.subprocess, "Popen", spy):
            self.phase_one(target)

        self.assertEqual(len(launches), 1)
        args, cwd = launches[0]
        self.assertEqual(args[:3], [sys.executable, "-m", canary.CANARY_DRIVE_MODULE])
        self.assertEqual(cwd, self.clones[0])
        self.assertIn("--result", args)


class CommitWithoutEntryTest(_CloneDriveTest):

    def test_refusal_names_adr_0021_stage_0_and_launches_nothing(self):
        """Коммит без `orchestrator/canary_drive.py`: именованный отказ со
        ссылкой на ADR-0021, этап 0, ни одного запуска процесса, клон убран.

        Ловит мутацию: отсутствие входа ведёт задачу кодом пина (процесс
        пульта или запуск чужого входа) либо отказ не именован.
        """
        target = self.commit("старый", entry=False)
        with mock.patch.object(canary, "_drive_in_clone") as launch, \
                self.assertRaises(SystemExit) as ctx:
            self.phase_one(target)

        self.assertIn("ADR-0021, этап 0", str(ctx.exception.code))
        self.assertIn(target, str(ctx.exception.code))
        launch.assert_not_called()
        self.assertFalse(any(c.exists() for c in self.clones))


class CloneProcessFailureTest(_CloneDriveTest):

    def assert_failed_with_saved_output(self, target: str, mark: str):
        with self.assertRaises(canary.CanaryDriveFailed) as ctx:
            self.phase_one(target)
        failure = ctx.exception
        saved = (failure.diag_dir / canary._DRIVE_LOG_NAME).read_text(encoding="utf-8")
        self.assertIn(mark, saved)
        self.assertTrue(failure.diag_dir.is_relative_to(self.outer))
        self.assertFalse(any(c.exists() for c in self.clones))
        return failure

    def test_nonzero_exit_fails_even_with_a_written_result(self):
        """Процесс записал результат и вышел кодом 3: сбой, код назван в
        причине, вывод процесса сохранён снаружи клона, клон убран.

        Ловит мутацию: код выхода процесса клона не проверяется (записанный
        результат принят как штатный).
        """
        failure = self.assert_failed_with_saved_output(
            self.commit("вывод-с-кодом-3", rc=3), "вывод-с-кодом-3")
        self.assertIn("кодом 3", failure.reason)
        self.assertEqual(failure.task_id, "01CLONETASK")

    def test_hanging_process_is_killed_after_the_limit(self):
        """Процесс не завершается: по истечении `CANARY_DRIVE_TIMEOUT_SEC`
        он снят, сбой называет предел, вывод сохранён, результата нет.

        Ловит мутацию: пульт ждёт процесс клона без предела (тест висит до
        своего таймаута) либо по таймауту бросает `TimeoutExpired` наружу
        вместо красного прогона.
        """
        target = self.commit("вывод-зависшего", sleep=60)
        started = time.monotonic()
        with mock.patch.object(canary, "CANARY_DRIVE_TIMEOUT_SEC", 2):
            failure = self.assert_failed_with_saved_output(target, "вывод-зависшего")
        self.assertLess(time.monotonic() - started, 30)
        self.assertIn("не завершился за 2 с", failure.reason)
        self.assertIsNone(failure.task_id)

    def test_output_of_a_killed_process_is_not_lost_in_its_buffer(self):
        """Зависший процесс печатает без `flush` и снимается по пределу:
        его вывод всё равно в сохранённой диагностике.

        Ловит мутацию: процесс клона запускается с блочной буферизацией
        вывода в файл — снятие сигналом теряет буфер, и диагностика
        зависания (AC-9) пуста.
        """
        target = self.commit("вывод-без-flush", sleep=60, flush=False)
        with mock.patch.object(canary, "CANARY_DRIVE_TIMEOUT_SEC", 2):
            self.assert_failed_with_saved_output(target, "вывод-без-flush")


class InterruptedPultTest(_CloneDriveTest):

    def test_interrupt_while_waiting_kills_the_clone_process_group(self):
        """Ожидание процесса клона прервано `KeyboardInterrupt` (Ctrl-C
        Оператора): прерывание уходит наружу, группа процесса клона снята
        (лидер мёртв, в группе никого), клон убран.

        Ловит мутацию: группа процесса клона снимается только по таймауту —
        после прерывания пульта агенты роли продолжают работать и тратить
        бюджет на удалённом клоне.
        """
        target = self.commit("прерванный", sleep=60)
        procs = []
        real_popen = subprocess.Popen

        class InterruptedPopen(real_popen):
            def wait(self, timeout=None):
                if timeout is None:
                    return super().wait()
                procs.append(self)
                time.sleep(0.5)
                raise KeyboardInterrupt

        def popen(args, *a, **kwargs):
            if list(args)[:1] == [sys.executable]:
                return InterruptedPopen(args, *a, **kwargs)
            return real_popen(args, *a, **kwargs)

        def reap():
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        self.addCleanup(reap)

        with mock.patch.object(canary.subprocess, "Popen", popen), \
                self.assertRaises(KeyboardInterrupt):
            self.phase_one(target)

        self.assertEqual(len(procs), 1)
        self.assertIsNotNone(procs[0].poll())
        with self.assertRaises(ProcessLookupError):
            os.killpg(procs[0].pid, 0)
        self.assertFalse(any(c.exists() for c in self.clones))


class ReportedCommitMismatchTest(_CloneDriveTest):

    def test_other_reported_head_is_not_a_normal_outcome(self):
        """Процесс сообщил HEAD, отличный от проверяемого коммита: исход не
        штатный (вердикт не `green`, базовая линия не трогается),
        диагностика сохранена, в метриках — оба коммита.

        Ловит мутацию: HEAD клона из результата не сверяется с проверяемым
        коммитом — прогон кода, которого не проверяли, стал бы зелёным.
        """
        target = self.commit("м", head="0" * 40)
        with mock.patch.object(canary, "_save_diagnostics",
                               return_value=self.outer / "diag") as save:
            (self.outer / "diag").mkdir()
            result = self.phase_one(target)

        metrics, normal_outcome, diag_dir = result[4], result[7], result[8]
        self.assertFalse(normal_outcome)
        self.assertEqual(metrics["code_sha"], "0" * 40)
        self.assertEqual(metrics["target_sha"], target)
        save.assert_called_once()
        self.assertEqual(diag_dir, self.outer / "diag")


class ReadDriveResultTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "result.json"

    def valid(self) -> dict:
        return {"task_id": "01X", "head": "a" * 40, "outcome": "killed",
                "escalated": False, "metrics": dict(_METRICS),
                "steps": [{"ts": "t", "actor": "a", "action": "b", "detail": None}]}

    def read(self, data=None, text=None):
        if text is None:
            text = json.dumps(data)
        self.path.write_text(text, encoding="utf-8")
        return canary._read_drive_result(self.path)

    def test_valid_object_is_returned_as_is(self):
        """Ловит мутацию: полный результат процесса клона отклоняется
        (проверка полей требует лишнего) — ни один прогон не прошёл бы."""
        data = self.valid()
        self.assertEqual(self.read(data), (data, None))

    def test_missing_and_garbage_and_non_object_results_are_refused(self):
        """Нет файла, не JSON, JSON не-объект — `(None, причина)`, без
        исключения.

        Ловит мутацию: `FileNotFoundError`/`JSONDecodeError` не перехвачены
        и роняют пульт после уборки клона — без диагностики и без строки
        прогона.
        """
        self.assertIsNone(canary._read_drive_result(self.path)[0])
        for text in ("{оборван", "[1, 2]"):
            with self.subTest(text=text):
                result, reason = self.read(text=text)
                self.assertIsNone(result)
                self.assertTrue(reason)

    def test_object_without_a_field_read_later_is_refused_naming_it(self):
        """Ловит мутацию: объект без HEAD клона или без поля метрик принят —
        фаза 3 упала бы `KeyError` либо записала прогон без коммита кода."""
        for drop in ("head", "metrics.kill_note"):
            with self.subTest(drop=drop):
                data = self.valid()
                if "." in drop:
                    del data["metrics"][drop.split(".", 1)[1]]
                else:
                    del data[drop]
                result, reason = self.read(data)
                self.assertIsNone(result)
                self.assertIn(drop, reason)


class RecordCanaryRunCodeShaTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(config, "DB", Path(tmp.name) / "state.db")
        patcher.start()
        self.addCleanup(patcher.stop)

    def record(self, metrics: dict) -> tuple:
        conn = store.db()
        out = canary._record_canary_run(
            conn, "20260929T000000Z", "shablon", "01X", metrics, None, False,
            False, True, "b" * 40, "b" * 40, "код bbb", canary._DEFAULT_SET_PLAN)
        conn.commit()
        row = sqlite3.connect(str(config.DB)).execute(
            "SELECT main_sha FROM canary_runs").fetchone()
        return out, row[0]

    def test_main_sha_is_the_commit_that_drove_the_task(self):
        """`canary_runs.main_sha` и sha сводки — коммит, сообщённый процессом
        клона, а не проверяемый.

        Ловит мутацию: пульт пишет в `main_sha` проверяемый sha, игнорируя
        HEAD клона — строка прогона утверждала бы код, которым задача не
        велась.
        """
        (sha, label), main_sha = self.record(dict(_METRICS, code_sha="c" * 40))
        self.assertEqual(main_sha, "c" * 40)
        self.assertEqual(sha, "c" * 40)
        self.assertIn("c" * 40, label)

    def test_without_a_reported_commit_the_checked_one_is_kept(self):
        """Ловит мутацию: метрики без `code_sha` (подмена фазы 1) дают пустой
        `main_sha` вместо проверяемого коммита."""
        (sha, label), main_sha = self.record(dict(_METRICS))
        self.assertEqual((sha, label, main_sha), ("b" * 40, "код bbb", "b" * 40))


class DriveFailureReportTest(unittest.TestCase):

    def test_failure_is_a_red_row_and_named_summary(self):
        """Сбой процесса клона: красная строка `canary_runs` без коммита кода
        и строка сводки с причиной и каталогом диагностики.

        Ловит мутацию: сбой пишется зелёным или не пишется вовсе (история
        прогонов молчала бы о нём) либо сводка не называет причину.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(config, "DB", Path(tmp.name) / "state.db"), \
                mock.patch("builtins.print") as printed:
            failure = canary.CanaryDriveFailed(
                "shablon", None, "завершился с кодом 3", Path(tmp.name) / "d")
            canary._report_drive_failure(failure, "20260929T000000Z",
                                         canary._DEFAULT_SET_PLAN)
            row = sqlite3.connect(str(config.DB)).execute(
                "SELECT verdict, main_sha, outcome FROM canary_runs").fetchone()
        self.assertEqual(row, ("red", None, canary._DRIVE_FAILED_OUTCOME))
        text = " ".join(str(c.args[0]) for c in printed.call_args_list)
        self.assertIn("завершился с кодом 3", text)
        self.assertIn(str(Path(tmp.name) / "d"), text)


class CommitMismatchSummaryTest(unittest.TestCase):

    def summary(self, code_sha: str) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = "b" * 40
        metrics = dict(_METRICS, code_sha=code_sha, target_sha=target)
        phase_one = ("01X", "shablon", None, [], metrics, False, False,
                     code_sha == target, None)
        with mock.patch.object(config, "DB", Path(tmp.name) / "state.db"), \
                mock.patch.object(canary, "_run_task_in_ephemeral_clone",
                                  return_value=phase_one), \
                mock.patch("builtins.print") as printed:
            canary._run_one_task(Path(tmp.name) / "shablon.md",
                                 "20260929T000000Z", 2.0, target_sha=target,
                                 sha_label="проверяемый")
        return "\n".join(str(c.args[0]) for c in printed.call_args_list)

    def test_summary_names_the_mismatch_and_both_commits(self):
        """HEAD клона не равен проверяемому коммиту: строка сводки называет
        причину расхождения и оба коммита; при равенстве пометки нет.

        Ловит мутацию: пометка `[РАСХОЖДЕНИЕ КОММИТА …]` не печатается
        (или без одного из коммитов) — Оператор видит красный прогон без
        причины (AC-6).
        """
        text = self.summary("c" * 40)
        line = next(l for l in text.splitlines() if "РАСХОЖДЕНИЕ КОММИТА" in l)
        self.assertIn("c" * 40, line)
        self.assertIn("b" * 40, line)
        self.assertNotIn("РАСХОЖДЕНИЕ КОММИТА", self.summary("b" * 40))


class CanaryDriveMainTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        saved_venv = config.VENV_DIR
        saved_home = codex_provider.codex_home_override()
        self.addCleanup(setattr, config, "VENV_DIR", saved_venv)
        self.addCleanup(codex_provider.set_codex_home_override, saved_home)

    def test_result_file_is_one_json_object_and_pult_state_is_applied(self):
        """`main` пишет в `--result` ровно один JSON-объект результата и
        применяет переданные пультом venv и `CODEX_HOME` до ведения.

        Ловит мутацию: результат уходит в вывод, а не в переданный файл,
        либо `--codex-home`/`--venv-dir` не применяются — шаги ролей клона
        шли бы с чужим домом Codex и без venv пульта.
        """
        seen = {}

        def fake_drive(template):
            seen["home"] = codex_provider.codex_home_override()
            seen["venv"] = config.VENV_DIR
            return {"task_id": "01X", "head": "a" * 40, "outcome": "killed"}

        result = self.dir / "r.json"
        with mock.patch.object(canary_drive, "drive", fake_drive), \
                mock.patch("builtins.print"):
            rc = canary_drive.main([
                "--template", str(self.dir / "t.md"), "--result", str(result),
                "--codex-home", str(self.dir / "codex"),
                "--venv-dir", str(self.dir / "venv")])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(result.read_text(encoding="utf-8"))["task_id"], "01X")
        self.assertEqual(seen, {"home": self.dir / "codex", "venv": self.dir / "venv"})
        self.assertEqual([p.name for p in self.dir.iterdir()], ["r.json"])

    def drive_with(self, wt_error=None) -> tuple:
        calls = self.calls = []

        def record(name, value=None):
            def fake(*args, **kwargs):
                calls.append(name)
                return value
            return fake

        with mock.patch.object(canary_drive.gitcmd, "head_sha",
                               record("head", "a" * 40)), \
                mock.patch.object(canary_drive.store, "db", record("db", "conn")), \
                mock.patch.object(canary_drive.catalog, "cmd_new",
                                  record("cmd_new", "01X")), \
                mock.patch.object(canary_drive.store, "get_task",
                                  record("get_task", {"branch": "task/01x"})), \
                mock.patch.object(canary_drive.workspace, "ensure",
                                  record("ensure", (self.dir, wt_error))), \
                mock.patch.object(canary_drive.canary, "_drive_task",
                                  record("_drive_task")), \
                mock.patch.object(canary_drive, "build_result",
                                  record("build_result", {"task_id": "01X"})):
            result = canary_drive.drive(self.dir / "shablon.md")
        return calls, result

    def test_drive_opens_the_task_then_worktree_then_drives_it(self):
        """`drive` заводит задачу, её worktree, ведёт её `_drive_task` и
        только потом собирает результат; HEAD снят до заведения.

        Ловит мутацию: вход не ведёт задачу (`_drive_task` не вызван) или
        не заводит worktree — канарейка сообщила бы «штатный» результат по
        недоведённой задаче.
        """
        calls, result = self.drive_with()
        self.assertEqual(result, {"task_id": "01X"})
        order = [c for c in calls if c in
                 ("head", "cmd_new", "ensure", "_drive_task", "build_result")]
        self.assertEqual(order, ["head", "cmd_new", "ensure", "_drive_task",
                                 "build_result"])

    def test_drive_refuses_without_a_worktree_and_does_not_drive(self):
        """Ловит мутацию: ошибка `workspace.ensure` проглочена — задача
        велась бы без рабочей копии и падала бы на первом шаге роли."""
        with self.assertRaises(RuntimeError) as ctx:
            self.drive_with(wt_error="занято")
        self.assertIn("занято", str(ctx.exception))
        self.assertNotIn("_drive_task", self.calls)

    def test_build_result_carries_head_steps_metrics_and_escalation(self):
        """Ловит мутацию: объект результата теряет HEAD клона, шаги или факт
        эскалации — пульт не смог бы ни сверить коммит, ни напечатать
        выдержку журнала, ни сверить маркер шаблона."""
        row = {"ts": "t", "actor": "a", "action": "state -> escalated",
               "detail": "d", "id": 1}
        metrics = dict(_METRICS, escalations=["d"])
        with mock.patch.object(canary_drive.store, "task_steps", return_value=[row]), \
                mock.patch.object(canary_drive.canary, "_task_metrics",
                                  return_value=metrics):
            result = canary_drive.build_result(None, "01X", "a" * 40)
        self.assertEqual(result["head"], "a" * 40)
        self.assertEqual(result["steps"], [{"ts": "t", "actor": "a",
                                            "action": "state -> escalated",
                                            "detail": "d"}])
        self.assertIs(result["escalated"], True)
        self.assertEqual(result["metrics"], metrics)


if __name__ == "__main__":
    unittest.main()
