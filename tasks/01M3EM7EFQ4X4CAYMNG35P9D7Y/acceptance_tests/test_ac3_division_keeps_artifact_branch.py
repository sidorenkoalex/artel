"""AC-3 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): после перехода
деления артефактная ветка родителя существует, её голова — тот же sha,
что до перехода, и SPEC.md в ней по-прежнему несёт раздел «## Деление».

Артефакты читаются с артефактной ветки (`gitcmd.show`/
`gitcmd.branch_head_sha`), не с диска: рабочая копия шага — не источник.

Зелёный с рождения: критерий охраняет ГРАНИЦУ будущей уборки — сегодня
уборки при делении нет вовсе, `approve` артефактную ветку родителя не
трогает, и свойство уже держится. Тест краснеет ровно на той
реализации, ради которой написан: уборка, сделанная не `cleanup.
cleanup_killed_task`, а полным `cleanup._cmd_kill` (самый естественный
для разработчика способ «убрать тем же механизмом, что kill»), по пути
зовёт `_publish_snapshot_if_pending` -> `snapshot.publish_and_cleanup`,
который УДАЛЯЕТ локальную артефактную ветку задачи (`artifact_branch.
drop`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import DivisionApproveSandbox  # noqa: E402


class DivisionKeepsArtifactBranchTest(DivisionApproveSandbox):

    def test_ac3_artifact_branch_head_and_division_section_survive(self):
        """Деление не двигает и не удаляет артефактную ветку родителя:
        голова та же, SPEC.md в ней всё ещё несёт «## Деление».

        Ловит мутацию: уборка родителя сделана полным путём kill
        (`cleanup._cmd_kill`) вместо `cleanup_killed_task` — снапшот
        закрытия публикуется и локальная артефактная ветка удаляется
        (`snapshot.publish_and_cleanup`), хотя SPEC деления оставляет её
        нетронутой; `branch_head_sha` вернёт пустую строку.
        """
        sha = self.enter_spec_gate()
        head_before = self.artifact_head()
        self.assertTrue(
            head_before,
            "предусловие AC-3: артефактная ветка родителя заведена")
        self.assertIn(
            "## Деление", self.artifact_spec_text() or "",
            "предусловие AC-3: SPEC родителя несёт раздел «## Деление»")

        self.approve(sha)

        head_after = self.artifact_head()
        self.assertTrue(
            head_after,
            "артефактная ветка родителя исчезла после деления (AC-3)")
        self.assertEqual(
            head_before, head_after,
            f"голова артефактной ветки родителя сдвинулась при делении "
            f"(AC-3): было {head_before}, стало {head_after}")
        self.assertIn(
            "## Деление", self.artifact_spec_text() or "",
            "SPEC родителя в артефактной ветке потерял раздел "
            "«## Деление» после деления (AC-3)")


if __name__ == "__main__":
    unittest.main()
