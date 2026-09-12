"""AC-8 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md), сценарий (б): main
продвинулся коммитом, затрагивающим `docs/x.md` и `orchestrator/a.py`, —
`pull.evaluate` возвращает `Pulled` (прежняя подтяжка).

Зелёный с рождения: смешанный дифф (документ + код) обязан подтягиваться
уже СЕГОДНЯШНИМ, нереализованным ещё правилом кодом — `pull.evaluate`
безусловно мержит main при `behind > 0`, а новое правило AC-1 (когда оно
появится) явно требует «ВСЕ файлы документные», так что этот сценарий
остаётся `Pulled` и до, и после реализации — лок «прежнее поведение
сохранено» для смешанного случая.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import acceptance, pull  # noqa: E402


class ScenarioBMixedDocAndCodeMainDiffPullsTest(PullFreshnessSandbox):

    def test_ac8_scenario_b_mixed_doc_and_code_main_diff_pulls(self):
        """main продвигается ОДНИМ коммитом, затрагивающим одновременно
        документный `docs/x.md` и кодовый `orchestrator/a.py` — смешанный
        дифф не проходит условие «ВСЕ файлы документные» (AC-1), поэтому
        `evaluate` обязан выполнить настоящую подтяжку: `Pulled` со sha
        main, голова ветки задачи содержит и её собственный коммит, и
        коммит main как предков.

        Ловит мутацию: `evaluate` признаёт дифф документным, если ХОТЯ БЫ
        ОДИН файл документный (вместо «ВСЕ файлы») — вернул бы `Fresh()`
        вместо `Pulled`; `assertIsInstance`/`assertTrue(is_ancestor(...))`
        поймают и подмену типа исхода, и отсутствие настоящего merge."""
        self.branch_off_main()
        branch_sha = self.commit_on_branch(
            {"orchestrator/ac8_marker.py": "# ветка\n"},
            f"{self.TASK}: правка ветки")
        main_sha = self.add_main_commit(
            {"docs/x.md": "документ\n", "orchestrator/a.py": "# код\n"},
            "main: документ + код")
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
