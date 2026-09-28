"""Приёмочный тест AC-8 (порядок: push снимка раньше уборки веток) —
tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Порядок вызовов наблюдается подменой зависимости: `gitcmd.in_repo`
оборачивается шпионом, который в МОМЕНТ push в `refs/artifacts/<id>`
снимает, живы ли ещё ветки задачи. Иначе порядок не наблюдаем вовсе —
после закрытия обе картины («push раньше уборки» и «уборка раньше push»)
выглядят на диске одинаково, если не считать пустого дерева снимка.

Кодовая ветка наблюдается на пути `kill`: там её убирает
`cleanup.cleanup_killed_task` в локальном репозитории пульта. На пути
мержа кодовая ветка задачи ВНЕШНЕГО target живёт в клоне целевого, и
`cleanup.drop_merged_task_branch` (репозиторий пульта) её не трогает —
наблюдать там нечего, поэтому проверяется артефактная ветка, та самая,
чьё содержимое снимок и читает.

Зелёный с рождения: требование 8 прямо велит СОХРАНИТЬ сегодняшний
порядок (`orchestrator/cleanup.py:393-394`,
`orchestrator/fsm_merge_gate.py:950-952`) и сегодняшний отказ от уборки
при неудавшемся push — тест стережёт его от перестановки при правке
исхода и источника чтения.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, cleanup, gitcmd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ClosingSnapshotSandbox  # noqa: E402

MERGED_TASK = "01PLANKORDERMERGEDTASK0001"
KILLED_TASK = "01PLANKORDERKILLEDTASK0001"


class SnapshotPushOrderTest(ClosingSnapshotSandbox):

    def spy_on_snapshot_push(self, task_id: str):
        """Подменяет `gitcmd.in_repo` обёрткой, снимающей живость веток
        задачи в момент push снимка; возвращает словарь-приёмник снимка
        (пустой, если push так и не случился)."""
        seen: dict = {}
        real_in_repo = gitcmd.in_repo
        ref = self.snapshot_ref(task_id)

        def spy(repo, *args, **kwargs):
            if args and args[0] == "push" and any(
                    isinstance(a, str) and a.endswith(ref) for a in args):
                seen["artifact_branch"] = gitcmd.branch_exists(
                    artifact_branch.branch_name(task_id))
                seen["code_branch"] = gitcmd.branch_exists(
                    self.code_branch(task_id))
            return real_in_repo(repo, *args, **kwargs)

        patcher = mock.patch.object(gitcmd, "in_repo", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return seen

    def test_ac8_merge_pushes_snapshot_before_dropping_the_artifact_branch(self):
        """Закрытие мержем: в момент push снимка артефактная ветка ещё
        жива, а после закрытия её уже нет.

        Ловит мутацию: публикация снимка на пути мержа переставлена ПОСЛЕ
        уборки (`_cleanup_merged_task` раньше
        `_publish_closing_snapshot_or_wait`) — шпион увидит артефактную
        ветку уже удалённой в момент push, и снимок при этом соберётся
        пустым, потому что читать её дерево будет неоткуда.
        """
        self.seed_merge_gate_task(MERGED_TASK)
        seen = self.spy_on_snapshot_push(MERGED_TASK)

        self.approve_merge(MERGED_TASK)

        self.assertTrue(
            seen, f"push снимка в {self.snapshot_ref(MERGED_TASK)} не "
                  f"наблюдался вовсе — снимок обязан публиковаться при "
                  f"закрытии мержем (AC-8)")
        self.assertTrue(
            seen["artifact_branch"],
            "в момент push снимка артефактная ветка задачи обязана быть "
            "ещё жива (AC-8: push раньше удаления веток)")
        self.assertFalse(
            gitcmd.branch_exists(artifact_branch.branch_name(MERGED_TASK)),
            "после подтверждённого push снимка артефактная ветка обязана "
            "быть убрана (AC-8)")

    def test_ac8_kill_pushes_snapshot_before_dropping_branches(self):
        """Закрытие через `kill`: в момент push снимка живы обе ветки
        задачи — кодовая и артефактная, — а после закрытия нет ни одной.

        Ловит мутацию: `cleanup._cmd_kill` зовёт `cleanup_killed_task`
        раньше `_publish_snapshot_if_pending` — шпион увидит в момент push
        обе ветки уже удалёнными.
        """
        branch = self.seed_task(KILLED_TASK, "in_dev")
        # Кодовая ветка задачи в репозитории пульта — именно её убирает
        # `cleanup_killed_task`; без неё уборка кодовой ветки не наблюдаема.
        self.git("branch", branch)
        seen = self.spy_on_snapshot_push(KILLED_TASK)

        self.capture(cleanup.cmd_kill, KILLED_TASK)

        self.assertTrue(
            seen, f"push снимка в {self.snapshot_ref(KILLED_TASK)} не "
                  f"наблюдался вовсе — снимок обязан публиковаться при "
                  f"закрытии через kill (AC-8)")
        self.assertTrue(
            seen["artifact_branch"],
            "в момент push снимка артефактная ветка задачи обязана быть "
            "ещё жива (AC-8)")
        self.assertTrue(
            seen["code_branch"],
            "в момент push снимка кодовая ветка задачи обязана быть ещё "
            "жива (AC-8)")
        self.assertFalse(
            gitcmd.branch_exists(artifact_branch.branch_name(KILLED_TASK)),
            "после подтверждённого push снимка артефактная ветка обязана "
            "быть убрана (AC-8)")
        self.assertFalse(
            gitcmd.branch_exists(branch),
            "после подтверждённого push снимка кодовая ветка обязана быть "
            "убрана (AC-8)")

    def test_ac8_failed_push_on_merge_keeps_the_artifact_branch(self):
        """Закрытие мержем при недоступном origin целевого: снимок не
        доставлен — артефактная ветка остаётся.

        Ловит мутацию: уборка веток перестаёт зависеть от исхода push
        (например, `snapshot.publish_and_cleanup` начинает звать
        `artifact_branch.drop` безусловно, а не только после
        подтверждённого push) — ветка исчезнет вместе с единственным
        экземпляром артефактов задачи.
        """
        self.seed_merge_gate_task(MERGED_TASK)
        self.break_target_origin()

        self.approve_merge(MERGED_TASK)

        self.assertFalse(
            self.snapshot_ref_exists(MERGED_TASK),
            "снимок не мог доставиться в недостижимый origin целевого — "
            "предпосылка теста нарушена")
        self.assertTrue(
            gitcmd.branch_exists(artifact_branch.branch_name(MERGED_TASK)),
            "при неудавшемся push снимка артефактная ветка удаляться не "
            "вправе (AC-8)")

    def test_ac8_failed_push_on_kill_keeps_the_artifact_branch(self):
        """То же на пути `kill`: недоставленный снимок не даёт убрать
        артефактную ветку.

        Ловит мутацию: отказ от уборки при неудавшемся push оставлен
        только на пути мержа (там он живёт отдельной веткой
        `_publish_closing_snapshot_or_wait`), а путь `kill` начинает
        убирать ветку безусловно — единственный экземпляр артефактов
        убитой задачи пропадёт.
        """
        self.seed_task(KILLED_TASK, "in_dev")
        self.break_target_origin()

        self.capture(cleanup.cmd_kill, KILLED_TASK)

        self.assertFalse(
            self.snapshot_ref_exists(KILLED_TASK),
            "снимок не мог доставиться в недостижимый origin целевого — "
            "предпосылка теста нарушена")
        self.assertTrue(
            gitcmd.branch_exists(artifact_branch.branch_name(KILLED_TASK)),
            "при неудавшемся push снимка артефактная ветка удаляться не "
            "вправе (AC-8)")


if __name__ == "__main__":
    unittest.main()
