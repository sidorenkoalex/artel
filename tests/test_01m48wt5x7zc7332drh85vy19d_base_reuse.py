"""Итоги базы suite-run по содержимому дерева.

Группа: долгоживущий
Красен до реализации: suite-run ищет итог базы по sha коммита и не получает результат после смены документного коммита.
"""

import contextlib
import io
import json
import os
import random
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, idgen, store, suite_run, workspace
from tests.sandbox import RealGitSandbox


RED_BASE = ("========== short test summary info ==========\n"
            "FAILED tests/test_base.py::test_base - AssertionError: base\n"
            "========== 1 failed, 2 passed in 0.10s ==========\n")
RED_BRANCH = ("========== short test summary info ==========\n"
              "FAILED tests/test_base.py::test_base - AssertionError: base\n"
              "FAILED tests/test_new.py::test_new - AssertionError: new\n"
              "========== 2 failed, 2 passed in 0.10s ==========\n")


class BaseReuseTest(RealGitSandbox):
    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.add_synced_origin()
        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-reuse"
        store.insert_task(store.db(), self.task, "Проверка базы", "in_dev",
                          self.branch, config.DEFAULT_TARGET, 25.0)
        self.wt, error = workspace.ensure(self.task, self.branch)
        self.assertIsNone(error, f"зерно {self.seed}: {error}")
        self.wt = Path(self.wt)
        (self.wt / "branch.txt").write_text("branch\n", encoding="utf-8")
        self.git("-C", str(self.wt), "add", "branch.txt")
        self.git("-C", str(self.wt), "commit", "-q", "-m", "branch")

    def test_ac14_finished_base_has_result_file(self):
        """Завершённый прогон базы оставляет запись в каталоге итогов.

        Ловит мутацию: сохранение базы пропущено или получает пустой ключ — каталог итогов остаётся без записи базы.
        """
        with mock.patch.object(acceptance, "run_full_suite",
                               side_effect=[(False, RED_BRANCH), (False, RED_BASE)]) as run:
            with mock.patch.object(suite_run.subprocess, "Popen") as process:
                process.return_value.pid = os.getpid()
                self.capture(lambda: suite_run.cmd_suite_run([self.task]))
            suite_run.background(self.task, "1", suite_run.MODE_FULL)
        self.assertEqual(run.call_count, 2, f"зерно {self.seed}: база не прогнана")
        files = list(acceptance.suite_results_dir().glob("*.json"))
        self.assertTrue(files, f"зерно {self.seed}: итог базы не записан")
        records = [json.loads(p.read_text(encoding="utf-8")) for p in files]
        self.assertTrue(any("tests/test_base.py::test_base" in str(r) for r in records),
                        f"зерно {self.seed}: {records}")

    def test_ac15_document_only_commit_reuses_base_but_other_document_does_not(self):
        """Новый коммит с копилкой или RETRO оставляет базу прежней; другой документ меняет её.

        Ловит мутацию: ключ базы остаётся sha коммита либо исключает весь docs — число прогонов базы после двух коммитов неверно.
        """
        with mock.patch.object(acceptance, "run_full_suite", side_effect=[
                (False, RED_BRANCH), (False, RED_BASE),
                (False, RED_BRANCH), (False, RED_BRANCH), (False, RED_BASE)]) as run:
            with mock.patch.object(suite_run.subprocess, "Popen") as process:
                process.return_value.pid = os.getpid()
                self.capture(lambda: suite_run.cmd_suite_run([self.task]))
            suite_run.background(self.task, "1", suite_run.MODE_FULL)
            self.assertEqual(run.call_count, 2, f"зерно {self.seed}: исходная база")

            choice = random.Random(self.seed).choice(("backlog", "retro"))
            if choice == "backlog":
                path = self.root / "docs" / "backlog.md"
            else:
                path = self.root / "docs" / "retro" / "sample.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("документ пульта\n", encoding="utf-8")
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "служебный документ")
            self.git("push", "-q", "origin", config.MAIN_BRANCH)
            second = idgen.new_task_id()
            branch = f"task/{second.lower()}-reuse"
            store.insert_task(store.db(), second, "Новая база", "in_dev", branch,
                              config.DEFAULT_TARGET, 25.0)
            wt, error = workspace.ensure(second, branch)
            self.assertIsNone(error, f"зерно {self.seed}: {error}")
            self.assertTrue(Path(wt).is_dir())
            with mock.patch.object(suite_run.subprocess, "Popen") as process:
                process.return_value.pid = os.getpid()
                self.capture(lambda: suite_run.cmd_suite_run([second]))
            suite_run.background(second, "1", suite_run.MODE_FULL)
            self.assertEqual(run.call_count, 3,
                             f"зерно {self.seed}: {choice} ошибочно запустил базу")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                suite_run.cmd_suite_run([second, "--wait", "0"])
            report = output.getvalue()
            self.assertRegex(report, r"(?:падают и на базе\W*1|1\W*падают и на базе)")

            other = self.root / "docs" / "stack.md"
            other.write_text("другой документ\n", encoding="utf-8")
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "другой документ")
            self.git("push", "-q", "origin", config.MAIN_BRANCH)
            third = idgen.new_task_id()
            branch = f"task/{third.lower()}-reuse"
            store.insert_task(store.db(), third, "Изменённая база", "in_dev", branch,
                              config.DEFAULT_TARGET, 25.0)
            wt, error = workspace.ensure(third, branch)
            self.assertIsNone(error, f"зерно {self.seed}: {error}")
            self.assertTrue(Path(wt).is_dir())
            with mock.patch.object(suite_run.subprocess, "Popen") as process:
                process.return_value.pid = os.getpid()
                self.capture(lambda: suite_run.cmd_suite_run([third]))
            suite_run.background(third, "1", suite_run.MODE_FULL)
        self.assertEqual(run.call_count, 5,
                         f"зерно {self.seed}: изменение docs/stack.md не прогнало базу")

    def test_ac16_gate_result_on_uncommitted_tree_serves_later_base(self):
        """Незакоммиченное дерево гейта становится базой после коммита приложения и RETRO.

        Ловит мутацию: гейт сохраняет только sha HEAD или не пишет ключ базы — suite-run заново гоняет совпадающую базу.
        """
        scratch = self.root.parent / f"scratch-{self.seed}"
        self.git("worktree", "add", "-q", "--detach", str(scratch), config.MAIN_BRANCH)
        self.addCleanup(lambda: self.git("worktree", "remove", "--force", str(scratch)))
        (scratch / "marker.txt").write_text("приложение\n", encoding="utf-8")
        with mock.patch.object(acceptance, "run_full_suite", side_effect=[
                (False, RED_BASE), (False, RED_BRANCH), (False, RED_BASE)]) as run:
            gate = acceptance.full_suite(scratch, self.task)
            self.assertFalse(gate.green)
            (self.root / "marker.txt").write_text("приложение\n", encoding="utf-8")
            self.git("add", "marker.txt")
            self.git("commit", "-q", "-m", "приложение Оператора")
            retro = self.root / "docs" / "retro" / "sample.md"
            retro.parent.mkdir(parents=True, exist_ok=True)
            retro.write_text("ретро\n", encoding="utf-8")
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "снимок")
            self.git("push", "-q", "origin", config.MAIN_BRANCH)
            next_task = idgen.new_task_id()
            branch = f"task/{next_task.lower()}-reuse"
            store.insert_task(store.db(), next_task, "После гейта", "in_dev", branch,
                              config.DEFAULT_TARGET, 25.0)
            wt, error = workspace.ensure(next_task, branch)
            self.assertIsNone(error, f"зерно {self.seed}: {error}")
            self.assertTrue(Path(wt).is_dir())
            with mock.patch.object(suite_run.subprocess, "Popen") as process:
                process.return_value.pid = os.getpid()
                self.capture(lambda: suite_run.cmd_suite_run([next_task]))
            suite_run.background(next_task, "1", suite_run.MODE_FULL)
        self.assertEqual(run.call_count, 2,
                         f"зерно {self.seed}: suite-run запустил базу после итога гейта")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            suite_run.cmd_suite_run([next_task, "--wait", "0"])
        report = output.getvalue()
        self.assertRegex(report, r"(?:падают и на базе\W*1|1\W*падают и на базе)")
