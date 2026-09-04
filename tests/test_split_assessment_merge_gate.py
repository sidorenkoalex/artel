"""Юнит-тесты `orchestrator.fsm._snapshot_split_assessment`
(tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6; ANSWER-1, ANSWER-2).

Единственная часть задачи, которую приёмочная планка (`tasks/
01M1KS8K9RXWHX2PW3ZKB0P903/acceptance_tests/
test_ac_manual_and_escalate_markers.py`) НЕ проверяет: `test_ac12_
report_diff_bytes_column.py`/`test_ac12_report_split_assessment_
column.py` фиксируют только схему БД и рендер отчёта, читая уже
заполненные колонки напрямую через `store.update_task` — саму
переходную механику (заполнение на входе в `merge_gate` реальным
git diff/git show) планка не трогает вовсе. Регресс этой механики без
юнит-теста не поймать никаким гейтом (см. PLAN.md, шаг 3).

Тот же лёгкий приём песочницы, что и `tests/test_capacity_gate.py`:
`TmpRootTest` + прямой мок `gitcmd.git`, без настоящего репозитория.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

SPEC_WITH_SECTION = (
    "---\ntask: T900\ntype: spec\nauthor_role: analyst\nstatus: ready\n---\n\n"
    "# SPEC: фикстура\n\n"
    "## Оценка объёма и деление\nДеление на 2 части.\n")

SPEC_WITHOUT_SIGNALS = (
    "---\ntask: T900\ntype: spec\nauthor_role: analyst\nstatus: ready\n---\n\n"
    "# SPEC: фикстура\n\n## Не входит\n- x\n")


class SnapshotSplitAssessmentTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T900"
        store.insert_task(self.conn, self.task_id, "Тест снимка", "acceptance",
                          "task/t900-x", config.DEFAULT_TARGET, 25.0)
        self.t = {"title": "Тест снимка", "branch": "task/t900-x"}
        self.artifact_branch = artifact_branch.branch_name(self.task_id)
        self.spec_target = f"{self.artifact_branch}:tasks/{self.task_id}/SPEC.md"

    def _fake_git(self, diff_result, spec_text):
        """`diff_result` — `(returncode, stdout, stderr)` для `git diff`;
        `spec_text` — `None` симулирует «файла на ветке нет» для `git show`."""
        code, out, err = diff_result

        def git(*args):
            if args and args[0] == "diff":
                return subprocess.CompletedProcess(list(args), code, out, err)
            if args and args[0] == "show":
                if args[1] == self.spec_target and spec_text is not None:
                    return subprocess.CompletedProcess(list(args), 0, spec_text, "")
                return subprocess.CompletedProcess(
                    list(args), 128, "", "fatal: path not in tree")
            return subprocess.CompletedProcess(list(args), 0, "", "")
        return git

    def test_fills_diff_bytes_and_split_assessment_for_self_target(self):
        """Ловит мутацию: снимок не вызывает `git diff`/`git show` вовсе,
        либо пишет не то поле (перепутаны местами `diff_bytes` и
        `split_assessment`) — обе колонки остались бы `NULL` или несли
        значение друг друга."""
        diff_text = "diff --git a b\n+код"
        with mock.patch.object(
                gitcmd, "git", self._fake_git((0, diff_text, ""), SPEC_WITH_SECTION)):
            fsm._snapshot_split_assessment(self.conn, self.task_id, self.t)

        row = store.get_task(self.conn, self.task_id)
        self.assertEqual(row["diff_bytes"], len(diff_text.encode("utf-8")))
        self.assertEqual(row["split_assessment"], "Деление на 2 части.")

    def test_empty_or_missing_section_becomes_literal_no_signals(self):
        """Ловит мутацию: пустая/отсутствующая секция «Оценка объёма и
        деление» пишется в БД как есть (пустая строка или `NULL`) вместо
        читаемого литерала «сигналов нет» — отчёт (AC-12) показывал бы
        пустую ячейку неотличимо от «колонка не заполнена вовсе»."""
        with mock.patch.object(
                gitcmd, "git",
                self._fake_git((0, "diff --git a b", ""), SPEC_WITHOUT_SIGNALS)):
            fsm._snapshot_split_assessment(self.conn, self.task_id, self.t)

        row = store.get_task(self.conn, self.task_id)
        self.assertEqual(row["split_assessment"], "сигналов нет")

    def test_git_diff_failure_leaves_diff_bytes_null_but_does_not_raise(self):
        """Ловит мутацию: сбой `git diff` не перехвачен (исключение
        всплывает и роняет гейт `merge_gate`) либо ошибочно останавливает
        чтение секции — сбой одной команды git не должен ронять гейт и не
        должен мешать заполнению независимого поля."""
        with mock.patch.object(
                gitcmd, "git",
                self._fake_git((128, "", "fatal: bad revision"), SPEC_WITH_SECTION)):
            fsm._snapshot_split_assessment(self.conn, self.task_id, self.t)

        row = store.get_task(self.conn, self.task_id)
        self.assertIsNone(row["diff_bytes"])
        self.assertEqual(row["split_assessment"], "Деление на 2 части.",
                         "сбой diff не обязан мешать чтению секции")

    def test_git_show_failure_leaves_split_assessment_null_but_does_not_raise(self):
        """Ловит мутацию: сбой `git show` (файла на артефактной ветке нет)
        не перехвачен и роняет гейт, либо ошибочно затирает уже
        посчитанный `diff_bytes` — независимость двух полей должна
        сохраняться и при сбое второй команды."""
        with mock.patch.object(
                gitcmd, "git",
                self._fake_git((0, "diff --git a b", ""), None)):
            fsm._snapshot_split_assessment(self.conn, self.task_id, self.t)

        row = store.get_task(self.conn, self.task_id)
        self.assertIsNotNone(row["diff_bytes"])
        self.assertIsNone(row["split_assessment"])

    def test_external_target_skips_diff_but_still_reads_split_assessment(self):
        """Ловит мутацию: диф внешнего target'а считается наравне с self
        (пропуск `_capacity_gate_refuses`-довода потерян) — `diff_bytes`
        внешней задачи заполнился бы по коду `config.ROOT`, который её не
        видит, и нёс бы неверное (нулевое или чужое) число."""
        store.update_task(self.conn, self.task_id, target="sled")
        with mock.patch.object(
                gitcmd, "git",
                self._fake_git((0, "diff --git a b", ""), SPEC_WITH_SECTION)):
            fsm._snapshot_split_assessment(self.conn, self.task_id, self.t)

        row = store.get_task(self.conn, self.task_id)
        self.assertIsNone(
            row["diff_bytes"],
            "diff в config.ROOT не видит код внешнего target — тот же "
            "довод, что и fsm_advance._capacity_gate_refuses")
        self.assertEqual(row["split_assessment"], "Деление на 2 части.")


if __name__ == "__main__":
    unittest.main()
