"""AC-3/AC-4 (tasks/01M290PVYG2VJK6442H5BAX9MA/SPEC.md): чекпоинт перед
подтяжкой main (`commit_pull_checkpoint`, вызывается на входе в
`verifying` и в `merge_gate`) отказывает переходу целиком при постороннем
файле в worktree — подтяжка (`git merge`) не начинается, задача остаётся
в прежнем состоянии, отказ несёт тот же перечень посторонних файлов, что
запись журнала AC-2, и именованную причину «посторонние файлы в worktree
— решение Оператора».

Красен до реализации: `pull._clean_worktree_before_merge`/`checkpoint.
commit_pull_checkpoint` сегодня коммитят ЛЮБОЙ WIP worktree (кроме
`tasks/<id>/`) без сверки с зонами и безусловно продолжают подтяжку —
посторонний файл проезжает в кодовый коммит, а `git merge` стартует как
обычно (`grep -rn "посторонние файлы в worktree" orchestrator/pull.py
orchestrator/checkpoint.py` пуст).

Песочница — `_WorktreeCheckpointTest` (tests/test_timeout_checkpoint.py,
импорт, не копия): реальный git-репозиторий пульта + реальный worktree
ветки задачи. `pull.evaluate` вызывается напрямую с `origin_main_source`/
`origin_main_sha`, вычисленными тестом БЕЗ настоящего remote origin — sha
нового коммита main уже достижим в объектной базе `config.ROOT` (тот же
репозиторий, что и worktree задачи через `git worktree add`), фетч не
нужен — тот же приём инъекции параметров, что документирует
`orchestrator/pull.py::evaluate`.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, pull, store  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402


class PullCheckpointStrayFileRefusalTest(_WorktreeCheckpointTest):

    ZONE = "orchestrator/allowed_module.py"

    def enter_in_dev(self):
        # `zones` объявляется ПОСЛЕ `enter_in_dev()` — см. докстринг
        # того же приёма в test_ac1_ac2_checkpoint_zone_filter.py.
        sha = super().enter_in_dev()
        store.update_task(store.db(), self.TASK, zones=self.ZONE)
        return sha

    def advance_main(self, rel: str = "docs/ac3_marker.txt",
                     text: str = "прогресс main\n") -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "прогресс main"],
                       cwd=self.root, check=True)
        return subprocess.run(
            ["git", "rev-parse", config.MAIN_BRANCH], cwd=self.root,
            capture_output=True, text=True, check=True).stdout.strip()

    def evaluate(self, state: str = "in_dev"):
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        main_sha = self.advance_main()
        return pull.evaluate(
            conn, self.TASK, t, state,
            origin_main_source=lambda name: ("origin", config.MAIN_BRANCH),
            origin_main_sha=lambda name: main_sha,
            read_branch_text_or_refuse=fsm._read_branch_text_or_refuse)

    def test_ac3_stray_file_refuses_the_transition_before_merge_starts(self):
        """Ветка задачи отстала от main (behind > 0) и worktree несёт
        посторонний файл вне заявленной зоны — подтяжка обязана
        отказать ДО `git merge`: HEAD worktree и состояние задачи не
        меняются.

        Ловит мутацию: `commit_pull_checkpoint`/её вызыватель
        по-прежнему безусловно коммитят WIP и запускают `git merge` —
        HEAD worktree сдвинется (WIP-коммит стрей-файла и/или
        merge-коммит main), и `assertEqual(after_head, before_head)`
        покраснеет."""
        self.enter_in_dev()
        (self.wt / "docs").mkdir(parents=True, exist_ok=True)
        (self.wt / "docs" / "stray_pull_file.md").write_text(
            "рабочая заметка вне зоны\n", encoding="utf-8")
        before_head = self.worktree_head()

        self.evaluate()

        after_head = self.worktree_head()
        self.assertEqual(after_head, before_head,
                         "ни WIP-коммит стрей-файла, ни merge не имеют "
                         "права состояться")
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev",
                         "задача обязана остаться в прежнем состоянии")
        rows = store.task_steps(store.db(), self.TASK)
        details = [r["detail"] for r in rows]
        self.assertTrue(any(
            "посторонние файлы в worktree" in d and "stray_pull_file.md" in d
            for d in details))

    def test_ac4_refusal_carries_the_named_operator_decision_reason(self):
        """Отказ AC-3 несёт именованную причину «посторонние файлы в
        worktree — решение Оператора» — не общий текст отказа merge —
        ровно ту, которой обязан остановиться `auto` вместо повторной
        попытки той же безнадёжной подтяжки.

        Ловит мутацию: причина отказа журналируется общим текстом (без
        именованной пометки) — `assertTrue(any(...))` ниже не найдёт
        литеральную строку и покраснеет."""
        self.enter_in_dev()
        (self.wt / "docs").mkdir(parents=True, exist_ok=True)
        (self.wt / "docs" / "stray_pull_file.md").write_text(
            "рабочая заметка вне зоны\n", encoding="utf-8")

        self.evaluate()

        rows = store.task_steps(store.db(), self.TASK)
        combined = [f"{r['action']} {r['detail']}" for r in rows]
        self.assertTrue(any(
            "посторонние файлы в worktree — решение Оператора" in c
            for c in combined))


if __name__ == "__main__":
    unittest.main()
