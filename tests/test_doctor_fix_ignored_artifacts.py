"""Юнит-тесты `doctor._fix_ignored_artifact_files`/`doctor --fix` (SPEC
01M1KVG3KSCY47HWXWF5HM0E76, требование 4, AC-5): уборка файлов,
игнорируемых `.gitignore` пульта, из артефактных веток живых задач.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, config, doctor, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

GITIGNORE_TEXT = "__pycache__/\n*.pyc\n*.log\ndropme/\n.artel/\n"
PYC_REL = "acceptance_tests/__pycache__/x.cpython-311.pyc"


class FixIgnoredArtifactFilesTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore")

    def seed_task(self, task_id: str, state: str, files: dict) -> None:
        store.insert_task(store.db(), task_id, f"Задача {task_id}", state,
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        sha = artifact_branch.commit_files(
            task_id, files, f"{task_id}: артефакты шага developer "
            f"(автокоммит оркестратора)")
        self.assertTrue(sha)

    def branch_files(self, task_id: str) -> list:
        branch = artifact_branch.branch_name(task_id)
        return gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []

    def journal_entries(self, task_id: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id", (task_id,))]

    def test_ignored_file_removed_normal_file_kept(self):
        """Ловит мутацию: `_fix_ignored_artifact_files` собирает пути для
        `commit_files(..., remove=...)` без прогона через `check_ignore`
        (например, чистит вообще все пути задачи) — либо `.pyc` остался бы
        в ветке (фильтр не сработал), либо `PLAN.md` тоже был бы удалён
        (фильтр слишком широкий); оба провала ловятся парой assert'ов ниже.
        """
        task_id = "01FIXTASKPYCREMOVE01"
        self.seed_task(task_id, "in_dev", {
            f"tasks/{task_id}/PLAN.md": "план\n",
            f"tasks/{task_id}/{PYC_REL}": b"\x00\x01\xff"})

        doctor._fix_ignored_artifact_files(store.db())

        files = self.branch_files(task_id)
        self.assertNotIn(f"tasks/{task_id}/{PYC_REL}", files)
        self.assertIn(f"tasks/{task_id}/PLAN.md", files)
        self.assertTrue(self.journal_entries(task_id))

    def test_task_without_ignored_files_is_not_journaled(self):
        """Ловит мутацию: журналирование срабатывает безусловно для каждой
        живой задачи, а не только для реально изменённых (пропущено
        сравнение «нашли ли игнорируемые пути») — задача без единого
        игнорируемого файла получила бы шумную запись в `store.journal`,
        AC-5 требует запись только для затронутых задач.
        """
        task_id = "01FIXTASKNOJUNK00001"
        self.seed_task(task_id, "in_dev",
                       {f"tasks/{task_id}/PLAN.md": "план\n"})

        doctor._fix_ignored_artifact_files(store.db())

        self.assertIn(f"tasks/{task_id}/PLAN.md", self.branch_files(task_id))
        self.assertEqual(self.journal_entries(task_id), [])

    def test_done_task_is_not_touched(self):
        """Ловит мутацию: фильтр «живых» задач в `_fix_ignored_artifact_files`
        забывает исключить `done`/`killed` (например, копирует критерий из
        `check_orphans` неверно) — артефактная ветка закрытой задачи была бы
        переписана уборкой, хотя SPEC («Не входит») ограничивает действие
        живыми задачами.
        """
        task_id = "01FIXTASKDONESKIP001"
        self.seed_task(task_id, "done", {
            f"tasks/{task_id}/PLAN.md": "план\n",
            f"tasks/{task_id}/{PYC_REL}": b"\x00"})

        doctor._fix_ignored_artifact_files(store.db())

        self.assertIn(f"tasks/{task_id}/{PYC_REL}", self.branch_files(task_id),
                      "done/killed задачи вне уборки — не 'живые'")
        self.assertEqual(self.journal_entries(task_id), [])

    def test_main_is_never_touched(self):
        """Ловит мутацию: уборка по ошибке пишет через рабочее дерево пульта
        (`git rm`/checkout в `config.ROOT`) вместо плотницкой записи прямо
        в `refs/heads/artifact/<id>` — `main` сдвинулся бы или рабочее
        дерево испачкалось, что нарушает неприкосновенность `main` (AC-5).
        """
        task_id = "01FIXTASKMAINSAFE001"
        self.seed_task(task_id, "in_dev", {
            f"tasks/{task_id}/PLAN.md": "план\n",
            f"tasks/{task_id}/{PYC_REL}": b"\x00"})
        main_before = gitcmd.head_sha()

        doctor._fix_ignored_artifact_files(store.db())

        self.assertEqual(gitcmd.head_sha(), main_before)
        self.assertEqual(gitcmd.git("status", "--porcelain").stdout.strip(), "")

    def test_multiple_live_tasks_only_affected_ones_journaled(self):
        """Ловит мутацию: цикл по живым задачам обрывается на первой найденной
        или журналирует по общему флагу вместо задачи-за-задачей — при двух
        задачах, из которых игнорируемый файл есть только у одной, чистая
        задача либо тоже получила бы запись в журнал, либо у грязной задачи
        `.pyc` остался бы неубранным (цикл остановился на первой).
        """
        clean_id = "01FIXTASKMULTICLEAN1"
        dirty_id = "01FIXTASKMULTIDIRTY1"
        self.seed_task(clean_id, "in_dev",
                       {f"tasks/{clean_id}/PLAN.md": "план\n"})
        self.seed_task(dirty_id, "review", {
            f"tasks/{dirty_id}/REVIEW.md": "ревью\n",
            f"tasks/{dirty_id}/{PYC_REL}": b"\x00"})

        doctor._fix_ignored_artifact_files(store.db())

        self.assertEqual(self.journal_entries(clean_id), [])
        self.assertTrue(self.journal_entries(dirty_id))
        self.assertNotIn(f"tasks/{dirty_id}/{PYC_REL}",
                         self.branch_files(dirty_id))
        self.assertIn(f"tasks/{dirty_id}/REVIEW.md", self.branch_files(dirty_id))

if __name__ == "__main__":
    unittest.main()
