"""AC-9 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md), сценарий (в): main
изменил документный файл (например `docs/backlog.md`), который ветка
задачи тоже правит, — `pull.evaluate` возвращает `Pulled` (подтяжка
выполняется, несмотря на документность).

Зелёный с рождения: пересекающийся документный файл обязан подтягиваться
уже СЕГОДНЯШНИМ, нереализованным ещё правилом кодом — `pull.evaluate`
безусловно мержит main при `behind > 0`, а новое правило AC-1 (когда оно
появится) явно требует непересечение с диффом ветки, так что этот
сценарий остаётся `Pulled` и до, и после реализации — лок «пересечение
не даёт ложного Fresh» для документного случая.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import acceptance, pull  # noqa: E402


class ScenarioCOverlappingDocFileStillPullsTest(PullFreshnessSandbox):

    def test_ac9_scenario_c_overlapping_doc_file_still_pulls(self):
        """Общий документный файл `docs/shared.md` существует уже в точке
        расхождения; main и ветка задачи правят РАЗНЫЕ строки этого же
        файла (чистый 3-way merge, без конфликта содержимого) — несмотря
        на то, что диффа main целиком документный, пересечение путей с
        диффом ветки обязано откатить `evaluate` к настоящей подтяжке:
        `Pulled` со sha main, оба коммита — предки новой головы.

        Ловит мутацию: `evaluate` проверяет условие (б) требования 1
        (непересечение с диффом ветки) неверно — например, только для
        НЕдокументных файлов, теряя его для документных — вернул бы
        `Fresh()` вместо `Pulled`; `assertIsInstance` и проверки предков
        поймают и подмену типа, и отсутствие настоящего merge."""
        base_content = "line1\nline2\nline3\nline4\nline5\n"
        self.add_main_commit({"docs/shared.md": base_content},
                             "docs: общий файл (база)")
        self.branch_off_main()
        branch_sha = self.commit_on_branch(
            {"docs/shared.md": base_content.replace("line5", "line5-branch")},
            f"{self.TASK}: правка ветки в общем файле")
        main_sha = self.add_main_commit(
            {"docs/shared.md": base_content.replace("line1", "line1-main")},
            "оператор: правка main в общем файле")
        self.write_acceptance_plank()

        with mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertEqual(outcome.sha, main_sha)
        new_head = self.worktree_head()
        self.assertTrue(self.is_ancestor(branch_sha, new_head),
                        "существующий коммит ветки обязан остаться предком")
        self.assertTrue(self.is_ancestor(main_sha, new_head),
                        "main обязан быть подтянут в ветку задачи")


if __name__ == "__main__":
    unittest.main()
