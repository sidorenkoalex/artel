"""Приёмочный тест T094 — AC-10 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-10: «Запись фиксации гейта содержит оба sha — головы кодовой ветки
целевого и головы артефактной ветки пульта — на момент перехода.»

«Запись фиксации гейта» — существующая, стабильно именованная точка:
журнальная запись `"sha зафиксирован"`, которую на КАЖДОМ переходе FSM
пишет `store.record_fixation` (`store.set_state` → `record_fixation` →
`fixation.fix`, `orchestrator/store.py`). Сегодня её `detail` несёт
РОВНО один sha (`f"target={target}, sha={sha or '—'}, чисто={clean}"`)
— критерий требует два. Тест не предполагает НИКАКОГО конкретного
формата этой строки (имена полей — решение разработчика, требование 1
SPEC отдаёт реестр точек фиксации PLAN.md): достаточно, что оба
40-символьных hex sha — головы кодовой ветки целевого
(`self.target_workspace`, реальный git) и головы артефактной ветки
пульта (`self.root`) — присутствуют в тексте детали КАК ПОДСТРОКИ и
РАЗЛИЧНЫ между собой.

Красен до реализации: сегодняшняя фиксация внешнего target
(`fixation._fix_external`) вообще не читает `self.target_workspace` —
она коммитит `config.PROJECTS/<target>/` (легаси-адрес, требование 2
SPEC меняет его на артефактную ветку пульта); sha кода целевого в
detail сегодня нет ни в каком виде.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, gitcmd, config, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


class Ac10GateFixationTwoShasTest(ExternalTargetGitSandbox):

    def test_ac10_fixation_record_carries_both_code_and_artifact_shas(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)

        # Код целевого сдвигается вперёд реальным коммитом в клоне.
        self.commit_workspace_file(
            "app/feature.py", "print('готово')\n",
            f"{task_id}: код фичи (роль developer)")
        code_sha = self.wgit("rev-parse", "HEAD").strip()

        pult_branches = [b for b in (gitcmd.list_branches() or [])
                         if b != config.MAIN_BRANCH]
        hosting = [b for b in pult_branches
                  if gitcmd.ls_tree_files(b, f"tasks/{task_id}")]
        self.assertTrue(hosting, f"нет артефактной ветки для {task_id}")
        artifact_sha = gitcmd.branch_head_sha(hosting[0])
        self.assertTrue(artifact_sha, "не удалось прочитать sha артефактной ветки")
        self.assertNotEqual(
            code_sha, artifact_sha,
            "код и артефакты в этой песочнице обязаны иметь РАЗНЫЕ sha "
            "— иначе тест не различил бы «один sha» от «два sha»")

        conn = store.db()
        state = store.get_task(conn, task_id)["state"]
        store.set_state(conn, task_id, "spec_gate", "operator",
                        expected_state=state)

        steps = store.task_steps(conn, task_id)
        fixations = [s for s in steps if s["action"] == "sha зафиксирован"]
        self.assertTrue(fixations, "нет ни одной записи «sha зафиксирован»")
        detail = fixations[-1]["detail"] or ""
        found = set(SHA_RE.findall(detail))

        self.assertIn(
            code_sha, found,
            f"запись фиксации не несёт sha головы кодовой ветки целевого "
            f"(AC-10): detail={detail!r}")
        self.assertIn(
            artifact_sha, found,
            f"запись фиксации не несёт sha головы артефактной ветки "
            f"пульта (AC-10): detail={detail!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
