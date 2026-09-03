"""Юнит-тесты `checkpoint.commit_step_artifacts` (tasks/T059/SPEC.md).

Приёмочные тесты (tasks/T059/acceptance_tests) проверяют критерии
приёмки целиком через `cmd_run` с подложным процессом агента; здесь —
изолированные случаи самой функции автокоммита: пустое дерево, отказ
плотницкой записи, повторная фиксация sha (`store.record_fixation`) и
чтение результата `fixation.check_integrity` сразу после коммита.

A7 (генерализация, требование 2) переводит `commit_step_artifacts` на
ЕДИНЫЙ путь для любого target — `checkpoint._commit_external_step_
artifacts`: роль пишет `tasks/<id>/` в свой рабочий каталог
(`config.PROJECTS/<target>/workspace/tasks/<id>/`), функция плотницки
(`orchestrator/artifact_branch.py`) переносит это в артефактную ветку
ПУЛЬТА и убирает из рабочего каталога. Три РАЗНЫХ физических места:
рабочий каталог роли (откуда автокоммит ЧИТАЕТ), артефактная ветка
пульта (куда коммитит) и репо фиксации self/артели
`config.PROJECTS/artel/tasks/<id>/` (`RealPultGitTest.task_dir()`,
`fixation._fix_external`, читает/пишет ИСКЛЮЧИТЕЛЬНО `store.
record_fixation` после автокоммита — своя отдельная, не связанная с
первыми двумя, фиксация sha, PLAN «Предложения системе»). Песочница —
`RealPultGitTest` (tests/test_git_fixation.py): настоящий git, заглушкой
эту механику не проверить (тот же довод, что в acceptance_tests T059).

Пересмотр планки решением Оператора 03.09 (вариант A, блокер R1-F1
ревью итерации 1 задачи A7; канал ADR-0012) вернул `runner.role_cwd`
для self/артели на git-worktree КОДОВОЙ ветки задачи — НЕ на
`config.PROJECTS/artel/workspace/`, использованный ниже как источник
для изолированных случаев самой функции автокоммита. С этого момента
`workspace_task_dir()` ниже — УЖЕ НЕ то же самое место, что реальный
`runner.role_cwd()` вернёт для self/артели; `RoleCwdVsCommitSourceGapTest`
в конце файла документирует и доказывает исполнением расхождение
(tasks/01M1H224X5A8W159MKF1Q24R5Y/PLAN.md, «Эскалация», Вопрос 2).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, checkpoint, config, fixation,  # noqa: E402
                          gitcmd, runner, store)
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class CommitStepArtifactsTest(RealPultGitTest):

    def workspace_task_dir(self) -> Path:
        """Источник для изолированных случаев самой функции автокоммита —
        `config.PROJECTS/artel/workspace/tasks/<id>/`, ОТДЕЛЬНО от репо
        фиксации `self.task_dir()` (`config.PROJECTS/artel/tasks/<id>/`).

        НЕ путать с реальным `runner.role_cwd()` для self/артели — с
        03.09 (вариант A по R1-F1) он возвращает git-worktree кодовой
        ветки задачи, не этот путь (см. докстринг модуля,
        `RoleCwdVsCommitSourceGapTest`)."""
        d = config.PROJECTS / config.DEFAULT_TARGET / "workspace" / "tasks" / self.TASK
        d.mkdir(parents=True, exist_ok=True)
        return d

    def orchestrator_steps(self) -> list:
        """Записи журнала САМОГО автокоммита — не любые действия actor=
        'orchestrator': generic-approve self/артели (A7) теперь пытается
        Draft-MR (github forge, AC-1) и при отказе (нет origin в
        песочнице) журналит `actor='orchestrator'` под именем «Draft MR
        FAILED», тот же actor, но другой предмет (см. `tests/
        test_timeout_checkpoint.py`, тот же фильтр)."""
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"
               and r["action"] == "автокоммит артефактов шага (артефактная ветка)"]

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.head()

        detail = checkpoint.commit_step_artifacts(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_to_artifact_branch_and_journals(self):
        self.enter_in_dev()
        (self.workspace_task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")

        detail = checkpoint.commit_step_artifacts(
            store.db(), self.TASK, "developer")

        # Коммит автокоммита — в артефактную ветку ПУЛЬТА (M1), не в репо
        # фиксации и не в рабочий каталог роли (SPEC T094, требование 8).
        tree = artifact_branch.read_tree(self.TASK)
        self.assertEqual(tree.get(f"tasks/{self.TASK}/wip.md"),
                         "недописанный артефакт роли\n")
        self.assertIn(f"{self.TASK}: артефакты шага developer "
                      f"(автокоммит оркестратора)", detail)
        self.assertIn("артефактная ветка", detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("автокоммит", entries[0]["action"].lower())
        # Рабочий каталог роли убран после переноса (требование 8: кодовая
        # ветка/рабочий каталог целевого свободны от артефактов задачи).
        # `workspace_task_dir()` сама создаёт каталог (`mkdir`) — здесь
        # путь вычислен напрямую, чтобы не воссоздать убранное.
        raw_dir = (config.PROJECTS / config.DEFAULT_TARGET / "workspace"
                  / "tasks" / self.TASK)
        self.assertFalse(raw_dir.exists())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        """`store.record_fixation`, вызванная автокоммитом, фиксирует РЕПО
        ФИКСАЦИИ (`self.repo()`/`self.head()`), не артефактную ветку и не
        рабочий каталог роли — те два коммита автокоммита её не касаются
        (PLAN «Предложения системе»: несвязанные механизмы)."""
        self.enter_in_dev()
        (self.workspace_task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_write_commit_failure_commits_nothing_and_journals_nothing(self):
        """Отказ плотницкой записи (`artifact_branch.write_commit`,
        любой из её шагов hash-object/write-tree/commit-tree) — тихая
        деградация: ничего не коммитится, рабочий каталог роли не
        убирается (он и не был перенесён), журнал не пишется."""
        self.enter_in_dev()
        (self.workspace_task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.head()

        with mock.patch.object(artifact_branch, "write_commit",
                               return_value=""):
            detail = checkpoint.commit_step_artifacts(
                store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])
        self.assertTrue((self.workspace_task_dir() / "wip.md").exists(),
                        "неудачный перенос не должен стирать WIP роли")

    def test_update_ref_failure_commits_nothing_and_journals_nothing(self):
        """Отказ на последнем шаге `commit_files` (`git update-ref`,
        artifact_branch.py) — тот же класс тихой деградации, отдельная
        точка отказа от самой плотницкой записи."""
        self.enter_in_dev()
        (self.workspace_task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.head()

        with mock.patch.object(artifact_branch, "commit_files",
                               return_value=""):
            detail = checkpoint.commit_step_artifacts(
                store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])
        self.assertTrue((self.workspace_task_dir() / "wip.md").exists())

class RoleCwdVsCommitSourceGapTest(RealPultGitTest):
    """Регресс-тест по рекомендации REVIEW.md T-A7 итерации 1, R1-F2
    («после исправления R1-F1 — добавить хотя бы один тест/сценарий,
    который заводит код через настоящий `role_cwd()`, не через ручной
    `git checkout -b`»): пишет артефакт РОВНО туда, куда указывает
    настоящий `runner.role_cwd()`, а не в захардкоженный
    `workspace_task_dir()` выше (тот же класс слепого пятна, что R1-F2
    поставил в вину `test_ac7_full_scenario_no_pult_writes.py`).

    Пересмотр планки решением Оператора 03.09 (вариант A по R1-F1;
    `orchestrator/runner.py::role_cwd`, коммит этой же сессии) вернул
    self/артели git-worktree кодовой ветки задачи. `checkpoint._commit_
    external_step_artifacts` при этом НЕ тронут — источник для self
    остался захардкожен на `config.PROJECTS/artel/workspace/tasks/<id>/`
    (см. `workspace_task_dir()` выше и REVIEW.md AC-6 `Checkpoint
    CommitsToArtifactBranchForArtelTest`, залоченный acceptance-тест,
    пишущий ИМЕННО туда). Эти два места разошлись: артефакт, реально
    написанный ролью в её настоящем `role_cwd()` (worktree кодовой
    ветки), `commit_step_artifacts` там не ищет — тест ниже
    воспроизводит это исполнением и красен (`skip`), пока конфликт не
    разрешён Оператором (PLAN.md, «Эскалация», Вопрос 2): починка кода
    без правки залоченного `CheckpointCommitsToArtifactBranchForArtelTest`
    (право только Оператора, tasks/T023) невозможна — обе стороны
    конфликта вне мандата разработчика.
    """

    @unittest.skip(
        "R1-F1×R1-F2 follow-up — tasks/01M1H224X5A8W159MKF1Q24R5Y/"
        "PLAN.md, «Эскалация», Вопрос 2: чинить требует правки залоченного "
        "AC-6 CheckpointCommitsToArtifactBranchForArtelTest — решение за "
        "Оператором.")
    def test_artifact_written_via_real_role_cwd_reaches_artifact_branch(self):
        self.enter_in_dev()
        cwd = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)
        task_dir = cwd / "tasks" / self.TASK
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "PLAN.md").write_text("план\n", encoding="utf-8")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        files = gitcmd.ls_tree_files(artifact_branch.branch_name(self.TASK),
                                     f"tasks/{self.TASK}") or []
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files,
                      "артефакт, написанный в настоящий role_cwd(), обязан "
                      "дойти до артефактной ветки пульта")


if __name__ == "__main__":
    unittest.main()
