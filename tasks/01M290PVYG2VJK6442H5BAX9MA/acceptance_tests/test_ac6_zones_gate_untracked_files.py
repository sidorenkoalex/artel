"""AC-6 (tasks/01M290PVYG2VJK6442H5BAX9MA/SPEC.md): гейт зон перехода
`in_dev -> verifying` (`fsm_advance._zones_gate`) сверяет с зонами не
только дифф коммитов (`git diff`), но и неотслеживаемые файлы рабочего
дерева (`git status --porcelain`); неотслеживаемый файл вне заявленных
зон отказывает переходу тем же отказом «дифф трогает файлы вне
заявленных zones…», что и закоммиченный файл вне зон.

Красен до реализации: `fsm_advance._zones_gate` сегодня сверяет с зонами
только `gitcmd.diff_names(base, t["branch"])` (committed-дифф) — файл,
оставленный в worktree НЕОТСЛЕЖИВАЕМЫМ (не закоммиченным и даже не
застейдженным), гейтом не виден вовсе.

Песочница — `_WorktreeCheckpointTest` (tests/test_timeout_checkpoint.py,
импорт, не копия): реальный git-репозиторий пульта + реальный worktree
ветки задачи, `_zones_gate_refuses` вызывается напрямую тем же приёмом,
что и `tests/test_zones_gate.py` (публичная обёртка гейта).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm_advance, store  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402


class ZonesGateUntrackedFileTest(_WorktreeCheckpointTest):

    ZONE = "orchestrator/allowed_module.py"

    def enter_in_dev(self):
        # `zones` объявляется ПОСЛЕ `enter_in_dev()` — см. докстринг
        # того же приёма в test_ac1_ac2_checkpoint_zone_filter.py.
        sha = super().enter_in_dev()
        store.update_task(store.db(), self.TASK, zones=self.ZONE)
        return sha

    def test_ac6_untracked_file_outside_zones_refuses_the_gate(self):
        """Committed-дифф пуст (никаких коммитов сверх точки расхождения
        с main), но рабочее дерево worktree несёт НЕОТСЛЕЖИВАЕМЫЙ файл
        вне заявленной зоны — гейт обязан отказать переходу тем же
        текстом, что и для закоммиченного файла вне зон, назвав сам
        путь.

        Ловит мутацию: гейт по-прежнему сверяет с зонами только
        `gitcmd.diff_names` (committed-дифф), не читает `git status
        --porcelain` рабочего дерева — нетрекенный `docs/stray_note.md`
        остаётся незамеченным, `refuses` вернула бы `False` вместо
        `True`."""
        self.enter_in_dev()
        (self.wt / "docs").mkdir(parents=True, exist_ok=True)
        (self.wt / "docs" / "stray_note.md").write_text(
            "рабочая заметка вне зоны\n", encoding="utf-8")

        conn = store.db()
        t = store.get_task(conn, self.TASK)
        branch = t["branch"]

        refuses = fsm_advance._zones_gate_refuses(conn, self.TASK, t, branch,
                                                   "PLAN\n")

        self.assertTrue(refuses)
        rows = store.task_steps(conn, self.TASK)
        details = [r["detail"] for r in rows]
        self.assertTrue(any(
            "дифф трогает файлы вне заявленных zones" in d
            and "stray_note.md" in d for d in details))


if __name__ == "__main__":
    unittest.main()
