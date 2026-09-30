"""Автогейт читает обе группы файлов планки из веток задачи.

Группа: долгоживущий
Красен до реализации: автогейт не читает перечень долгоживущих файлов.
"""

import hashlib
import random
import unittest
from unittest import mock

from orchestrator import (acceptance, budget, ci, config, fixation, fsm, gates,
                          lease, store, workspace)
from tests.sandbox import RealGitSandbox


class LongLivedAutogateTest(RealGitSandbox):
    """Настоящие ветки в отдельном репозитории и переход через cmd_advance."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        self.task_id = f"T{rng.randrange(1 << 72):018X}"
        self.code_branch = f"task/{self.task_id.lower()}"
        self.docs_branch = f"artifact/{self.task_id.lower()}"
        self.code_rel = "tests/test_fixture_plank.py"
        self.acc_dir = config.TASKS / self.task_id / "acceptance_tests"
        self.acc_dir.mkdir(parents=True, exist_ok=True)
        self.git("checkout", "-q", "-b", self.code_branch)
        self.code_text = self._source("")
        code_path = self.root / self.code_rel
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(self.code_text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "кодовая планка")
        self.git("checkout", "-q", "-b", self.docs_branch)
        review = config.TASKS / self.task_id / "REVIEW.md"
        review.write_text(
            "---\n" + f"task: {self.task_id}\n" +
            "type: review\nauthor_role: reviewer\nstatus: approved\n"
            "iteration: 1\nschema_version: 2\n---\n\n# REVIEW\n",
            encoding="utf-8")
        self._write_manifest()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "вердикт и перечень")
        self.lock_sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", self.code_branch)
        self.conn = store.db()
        store.insert_task(self.conn, self.task_id, "Проверка автогейта",
                          "review", self.code_branch, config.DEFAULT_TARGET,
                          10.0)
        store.update_task(self.conn, self.task_id, tests_locked_sha=self.lock_sha)

        self.patches = [
            mock.patch.object(fsm, "guard_refuses", return_value=False),
            mock.patch.object(fixation, "read", return_value=("", True)),
            mock.patch.object(fixation, "approve_sha_hint", return_value=""),
            mock.patch.object(store, "record_fixation", return_value=None),
            mock.patch.object(gates, "policy", return_value=gates.AUTO),
            mock.patch.object(workspace, "on_task_branch", return_value=True),
            mock.patch.object(workspace, "path", return_value=self.root),
            mock.patch.object(acceptance, "full_suite", return_value=
                              acceptance.FullSuiteRun(True,
                                  acceptance.FULL_SUITE_GREEN, "зелёный",
                                  None, "зелёный прогон")),
            mock.patch.object(budget, "budget_block", return_value=None),
            mock.patch.object(lease, "run_locked",
                              side_effect=lambda conn, task, sid, fn,
                                                 **kwargs: fn("test-session")),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _source(self, marker: str) -> str:
        return ('"""Зелёная долгоживущая планка фикстуры."""\n'
                'import unittest\n\n'
                'class Plank(unittest.TestCase):\n'
                '    def test_ac1_fixture(self):\n'
                '        self.assertEqual(2 + 2, 4)\n'
                + marker)

    def _write_manifest(self):
        digest = hashlib.sha256(self.code_text.encode("utf-8")).hexdigest()
        (self.acc_dir / "long_lived.sha256.txt").write_text(
            f"{digest}  {self.code_rel}\n", encoding="utf-8")

    def _replace_code(self, marker: str):
        self.code_text = self._source(marker)
        (self.root / self.code_rel).write_text(self.code_text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "вариант кодовой планки")
        self.git("checkout", "-q", self.docs_branch)
        self._write_manifest()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "обновлён перечень")
        self.lock_sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", self.code_branch)
        store.update_task(self.conn, self.task_id, state="review",
                          reviewed_iter=0, tests_locked_sha=self.lock_sha)

    def _advance(self) -> tuple[str, str]:
        out = self.capture(fsm.cmd_advance, self.task_id)
        state = store.get_task(self.conn, self.task_id)["state"]
        return state, out

    def test_ac1_combined_sources_and_markers(self):
        """Разовый и долгоживущий источники вместе дают пометки автогейту.

        Ловит мутацию: каталог собирается лишь из разовых файлов —
        долгоживущая manual-пометка не отклоняет переход и не попадает
        в запись для Оператора.
        """
        self._replace_code("# AC-27: manual — осмотр результата.\n")
        self.git("checkout", "-q", self.docs_branch)
        (self.acc_dir / "test_once.py").write_text(
            "# AC-28: skip — нет контура.\n"
            "# AC-29: escalate — нужен ответ.\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "разовая пометка")
        self.git("checkout", "-q", self.code_branch)
        (self.root / self.code_rel).write_text(
            self._source("# AC-99: manual — только рабочее дерево.\n"),
            encoding="utf-8")
        state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn("AC-27", out, f"зерно: {self.seed}; {out}")
        self.assertIn("AC-28", out, f"зерно: {self.seed}; {out}")
        self.assertIn("AC-29", out, f"зерно: {self.seed}; {out}")
        self.assertNotIn("AC-99", out, f"зерно: {self.seed}; {out}")
        checklist = [row["detail"] for row in store.task_steps(
            self.conn, self.task_id)
            if row["action"] == "приёмка: что проверит approve"]
        self.assertTrue(checklist, f"зерно: {self.seed}; записи нет")
        self.assertIn("AC-27: manual", checklist[-1],
                      f"зерно: {self.seed}; {checklist[-1]}")
        self.assertIn("AC-28: skip", checklist[-1],
                      f"зерно: {self.seed}; {checklist[-1]}")
        self.assertIn("AC-29: escalate", checklist[-1],
                      f"зерно: {self.seed}; {checklist[-1]}")

        (self.root / self.code_rel).write_text(self.code_text, encoding="utf-8")
        self._replace_code("# AC-30: ci — статус ветки.\n")
        self.git("checkout", "-q", self.docs_branch)
        self.git("rm", "-q", str(self.acc_dir / "test_once.py"))
        self.git("commit", "-q", "-m", "без разовой пометки")
        self.git("checkout", "-q", self.code_branch)
        with mock.patch.object(ci, "verifying_status",
                               return_value=(ci.VERIFYING_RED, "красный CI")):
            state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn("AC-30", out, f"зерно: {self.seed}; {out}")

    def test_ac2_empty_and_unreadable_manifest_entry(self):
        """Пустой набор отказывает как пустой, потерянный файл называется.

        Ловит мутацию: непустой перечень принимается за пустой каталог —
        после удаления его файла отказ теряет путь файла.
        """
        original_set_state = store.set_state
        def lose_file(conn, task, state, actor, **kwargs):
            original_set_state(conn, task, state, actor, **kwargs)
            if state == "acceptance":
                self.git("rm", "-q", self.code_rel)
                self.git("commit", "-q", "-m", "файл исчез после сверки")
        with mock.patch.object(store, "set_state", side_effect=lose_file):
            state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn(self.code_rel, out, f"зерно: {self.seed}; {out}")
        self.assertNotIn("каталог приёмочных тестов пуст", out,
                         f"зерно: {self.seed}; {out}")
        store.update_task(self.conn, self.task_id, state="review",
                          reviewed_iter=0, tests_locked_sha=None)
        state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn("каталог приёмочных тестов пуст", out,
                      f"зерно: {self.seed}; {out}")

    def test_ac3_without_manifest_keeps_empty_refusal(self):
        """Старая задача без перечня сохраняет отказ пустому каталогу.

        Ловит мутацию: отсутствие перечня ошибочно считается ошибкой
        чтения файла — старый отказ пустому каталогу меняет текст.
        """
        store.update_task(self.conn, self.task_id, tests_locked_sha=None)
        state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn("каталог приёмочных тестов пуст", out,
                      f"зерно: {self.seed}; {out}")

    def test_ac4_four_long_lived_scenarios(self):
        """Зелёная планка проходит, пометки и ошибки видны в журнале.

        Ловит мутацию: каталог только из acceptance_tests/ — полностью
        долгоживущая зелёная планка получает отказ о пустом каталоге.
        """
        state, out = self._advance()
        self.assertEqual(state, "merge_gate", f"зерно: {self.seed}; {out}")
        self._replace_code("# AC-37: manual — осмотр результата.\n")
        state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn("manual", out, f"зерно: {self.seed}; {out}")
        self.assertIn("AC-37", out, f"зерно: {self.seed}; {out}")
        self.assertIn("приёмка: что проверит approve", out,
                      f"зерно: {self.seed}; {out}")
        self.assertIn("AC-37: manual", out, f"зерно: {self.seed}; {out}")
        checklist = [row["detail"] for row in store.task_steps(
            self.conn, self.task_id)
            if row["action"] == "приёмка: что проверит approve"]
        self.assertIn("AC-37: manual", checklist[-1],
                      f"зерно: {self.seed}; {checklist[-1]}")
        original_set_state = store.set_state
        def lose_file(conn, task, state, actor, **kwargs):
            original_set_state(conn, task, state, actor, **kwargs)
            if state == "acceptance":
                self.git("rm", "-q", self.code_rel)
                self.git("commit", "-q", "-m", "файл исчез после сверки")
        self._replace_code("")
        with mock.patch.object(store, "set_state", side_effect=lose_file):
            state, out = self._advance()
        self.assertEqual(state, "acceptance", f"зерно: {self.seed}; {out}")
        self.assertIn(self.code_rel, out, f"зерно: {self.seed}; {out}")
