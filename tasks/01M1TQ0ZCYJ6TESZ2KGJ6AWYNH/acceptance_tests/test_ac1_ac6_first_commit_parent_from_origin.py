"""Приёмочные тесты AC-1/AC-6 задачи 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH:
родитель ПЕРВОГО коммита артефактной ветки новой задачи — голова
`origin/main` после `git fetch origin main`, не голова локального
пина главной копии (`config.MAIN_BRANCH`), когда origin ушёл вперёд от
пина (инцидент 06.09).

Красен до реализации: `artifact_branch.commit_files`
(`orchestrator/artifact_branch.py:118-119`) сегодня вычисляет родителя
ТОЛЬКО через `gitcmd.branch_head_sha(config.MAIN_BRANCH)` — локальный
пин, ни разу не опрашивая origin. В песочнице этого файла origin
специально уведён на один коммит вперёд от пина (`advance_origin_main`)
— сегодняшний код вернёт родителем sha пина, тест ждёт sha origin/main:
несовпадение красит оба теста файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch  # noqa: E402
from _sandbox import ArtifactBranchOriginSandbox  # noqa: E402

TASK = "01ACORIGINPARENT01"
ORIGIN_ONLY_MARKER = "tasks/01ACORIGINPARENT_OTHER/marker.txt"


class FirstCommitParentFromOriginTest(ArtifactBranchOriginSandbox):

    def setUp(self):
        super().setUp()
        self.add_origin()
        self.pin_head = self.local_main_head()
        self.origin_ahead_sha = self.advance_origin_main(
            {ORIGIN_ONLY_MARKER: "маркер существует только в origin\n"})

    def test_ac1_first_commit_parent_is_origin_main_head(self):
        """Origin ушёл на один коммит вперёд от локального пина main;
        первый коммит новой артефактной ветки задачи `TASK` берёт
        родителя из головы `origin/main` (после `git fetch origin
        main`), а не из отставшего пина.

        Ловит мутацию: родитель по-прежнему читается из
        `gitcmd.branch_head_sha(config.MAIN_BRANCH)` — sha родителя
        совпадёт с пином, а не с головой origin/main, тест это ловит
        прямым сравнением sha.
        """
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек"}, f"{TASK}: тест")

        self.assertTrue(sha, "коммит артефактной ветки не создан")
        parent = self.commit_parent_sha(sha)
        self.assertEqual(parent, self.origin_ahead_sha,
                         "родитель первого коммита обязан быть головой "
                         "origin/main после fetch")
        self.assertNotEqual(parent, self.pin_head,
                            "родитель не должен остаться отставшим пином")

    def test_ac6_tasks_dir_reflects_origin_state_not_pin(self):
        """Дерево первого коммита новой артефактной ветки несёт файл,
        добавленный ТОЛЬКО в origin/main (`ORIGIN_ONLY_MARKER`),
        которого нет в дереве локального пина — прямое подтверждение,
        что унаследованное содержимое `tasks/` взято из состояния
        origin, а не из состояния отставшего пина главной копии.

        Ловит мутацию: родитель коммита продолжает читаться от
        локального пина (`config.MAIN_BRANCH`) — маркерный файл origin
        отсутствует в результирующем дереве, хотя сам коммит формально
        создаётся успешно.
        """
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек"}, f"{TASK}: тест")

        self.assertTrue(sha, "коммит артефактной ветки не создан")
        content = self.git("show", f"{sha}:{ORIGIN_ONLY_MARKER}")
        self.assertEqual(content, "маркер существует только в origin\n")


if __name__ == "__main__":
    unittest.main()
