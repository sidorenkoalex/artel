"""AC-4 (tasks/01M2B6JNFD381MZT70CVB5NJQC/SPEC.md): после исхода `Pulled`
(подтяжка main через `pull.evaluate` на стенде с bare origin) каталог
`tasks/<task_id>/acceptance_tests/` в worktree отсутствует, при этом
прогон приёмочных тестов на материализованной планке фактически
состоялся.

Красен до реализации: `pull._materialize_and_run_plank` сегодня не
убирает материализованный каталог планки — после реального `pull.
evaluate` на этом стенде каталог остаётся в worktree, и проверка его
отсутствия падает.

НАСТОЯЩИЙ git на всём протяжении (`tests.sandbox.RealGitSandbox`,
образец `tests/test_pull.py::DocOnlyMainAdvanceTest` того же файла) — с
локальным bare `origin`, тем же приёмом, что `add_synced_origin` уже
применяет `tests/test_branch_freshness_gate.py`/`_WorktreeCheckpointTest`:
материализация планки читает АРТЕФАКТНУЮ ветку задачи через настоящий
git (`gitcmd.ls_tree_files`/`gitcmd.show`), заглушкой это не изобразить
осмысленно. Планка пишет маркер-файл СНАРУЖИ `acceptance_tests/` (в
`tasks/<task_id>/` — путь, который уборка AC-3 не трогает) — единственный
способ отличить «прогон реально состоялся» от «переход вернул `Pulled`
случайно/по другой причине», не полагаясь на мок `acceptance.run`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, config, pull, store, workspace  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

SPEC_WITH_AC_MARKUP = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура планки (стенд bare origin, AC-4)

## Критерии приёмки

AC-1. Фикстура.
"""

# Пишет маркер-файл ВНЕ `acceptance_tests/` (родитель — `tasks/<id>/`,
# который уборка AC-3 не трогает) — доказательство, что pytest реально
# исполнил ЭТОТ файл планки, а не просто удачно вернул `Pulled`.
PLANK_RAN_MARKER_TEST = '''"""Зелёный с рождения: фикстура — реальный прогон на настоящем git,
пишет маркер СНАРУЖИ acceptance_tests/, чтобы факт прогона пережил
последующую уборку каталога планки (AC-3/AC-4 задачи
01M2B6JNFD381MZT70CVB5NJQC)."""
import unittest
from pathlib import Path


class RanMarkerTest(unittest.TestCase):

    def test_writes_ran_marker(self):
        marker = Path(__file__).resolve().parents[1] / "PLANK_RAN.marker"
        marker.write_text("ran\\n", encoding="utf-8")
'''


class PullEvaluateBareOriginCleansPlankTest(RealGitSandbox):

    TASK = "01PULLBAREORIGINCLEAN1"

    def setUp(self):
        super().setUp()
        self.add_synced_origin()

        self.branch = f"task/{self.TASK.lower()}-x"
        self.checkout(self.branch, create=True)

        store.insert_task(store.db(), self.TASK,
                          "Стенд bare origin (AC-4, уборка планки)",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # main уходит вперёд ПОСЛЕ ответвления ветки задачи — иначе
        # `pull.evaluate` вернёт `Fresh()`, и подтяжки не случится вовсе
        # (тот же приём, что `tests/test_pull.py::DocOnlyMainAdvanceTest`
        # и залоченная планка 01M1RNZ6V7TTTTYAHBMF8JBQQS/
        # acceptance_tests/_sandbox.py::MarkerPullSandbox).
        self.checkout(config.MAIN_BRANCH)
        (self.root / "main-advance.txt").write_text(
            "main ушёл вперёд после ответвления\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "main ушёл вперёд")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.checkout(self.branch)

        sha = artifact_branch.commit_files(
            self.TASK,
            {
                f"tasks/{self.TASK}/SPEC.md":
                    SPEC_WITH_AC_MARKUP.format(task=self.TASK),
                f"tasks/{self.TASK}/acceptance_tests/test_ran_marker.py":
                    PLANK_RAN_MARKER_TEST,
            },
            f"{self.TASK}: фикстура планки")
        self.assertTrue(sha, "artifact_branch.commit_files не сработал")

        # `pull.evaluate` (self-target) заводит worktree через `workspace.
        # ensure` — здесь им служит сам `self.root` (тот же приём, что
        # `DocOnlyMainAdvanceTest`/`MarkerPullSandbox`): ветка задачи уже
        # стоит checked out в нём.
        self.ensure_mock = mock.Mock(return_value=(self.root, None))
        ensure_patcher = mock.patch.object(workspace, "ensure",
                                           self.ensure_mock)
        ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)

        self.origin_main_source = mock.Mock(
            return_value=("origin", config.MAIN_BRANCH))
        self.read_branch_text_or_refuse = mock.Mock(return_value=None)

    def evaluate(self):
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        main_sha = self.git("rev-parse", config.MAIN_BRANCH).strip()
        return pull.evaluate(
            conn, self.TASK, t, "in_dev",
            origin_main_source=self.origin_main_source,
            origin_main_sha=mock.Mock(return_value=main_sha),
            read_branch_text_or_refuse=self.read_branch_text_or_refuse)

    def journal_details(self) -> list:
        return [r["detail"] for r in
               store.task_steps(store.db(), self.TASK)]

    def test_ac4_pulled_leaves_no_materialized_plank_but_acceptance_ran(self):
        """Подтяжка main через `pull.evaluate` на настоящем git с bare
        `origin` завершается `Pulled` (чистый merge, зелёная планка) —
        каталог `tasks/<task_id>/acceptance_tests/`, материализованный
        НА МЕСТЕ в worktree, отсутствует после возврата, а маркер-файл,
        который пишет сама планка при исполнении, реально появился —
        приёмочные тесты не просто вернули «зелено», а фактически
        прогнались.

        Ловит мутацию: уборка каталога планки после подтяжки не
        добавлена вовсе (сегодняшнее поведение) — `acc_dir.exists()`
        остался бы `True` после `Pulled`. Отдельно: если бы прогон
        вообще не состоялся (например, каталог убирался бы ДО прогона,
        а не после), маркер-файл не появился бы — `marker.is_file()`
        поймал бы и такую мутацию.
        """
        outcome = self.evaluate()

        self.assertIsInstance(
            outcome, pull.Pulled,
            f"журнал: {self.journal_details()}")

        acc_dir = self.root / "tasks" / self.TASK / "acceptance_tests"
        self.assertFalse(
            acc_dir.exists(),
            "материализованный каталог планки обязан быть убран из "
            "worktree после подтяжки (AC-3)")

        marker = self.root / "tasks" / self.TASK / "PLANK_RAN.marker"
        self.assertTrue(
            marker.is_file(),
            "приёмочные тесты на материализованной планке обязаны "
            "фактически прогнаться — маркер, который пишет тест планки "
            "при исполнении, не появился")


if __name__ == "__main__":
    unittest.main()
