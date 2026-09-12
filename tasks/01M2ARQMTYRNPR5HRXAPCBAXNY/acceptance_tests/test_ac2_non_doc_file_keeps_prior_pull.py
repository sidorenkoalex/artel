"""AC-2 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md): если хотя бы один
файл диффа main из AC-1 не документный либо пересекается с файлами диффа
ветки — `pull.evaluate` ведёт себя прежним образом (выполняет подтяжку)
байт-в-байт.

Зелёный с рождения: сценарий описывает поведение, которое `pull.evaluate`
УЖЕ несёт сегодня (безусловная подтяжка при `behind > 0`) — новое правило
AC-1 его не меняет, только добавляет РЕДКОЕ исключение для другого случая
(AC-1). Проверка сохранена как лок «прежнее поведение не сломано».
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import acceptance, pull  # noqa: E402


class NonDocMainFileKeepsPriorPullBehaviorTest(PullFreshnessSandbox):

    def test_ac2_single_non_doc_main_file_keeps_prior_pull_behavior(self):
        """main продвигается РОВНО ОДНИМ недокументным файлом
        (`orchestrator/ac2_main_marker.py`), который даже не пересекается
        с диффом ветки — единственное условие AC-1 (документность),
        нарушенное этим файлом, обязано откатить `evaluate` к прежнему
        поведению: настоящая подтяжка (`Pulled`), не `Fresh`.

        Ловит мутацию: `evaluate` смотрит только на ПЕРЕСЕЧЕНИЕ файлов, не
        на их документность (или классифицирует `.py` как документный) —
        вернул бы `Fresh()` вместо `Pulled`; `assertIsInstance` и
        `assertEqual(outcome.sha, main_sha)` поймают подмену исхода."""
        self.branch_off_main()
        self.commit_on_branch({"orchestrator/ac2_branch_marker.py": "# ветка\n"},
                              f"{self.TASK}: правка ветки")
        main_sha = self.add_main_commit(
            {"orchestrator/ac2_main_marker.py": "# код main\n"},
            "оператор: правка кода main")
        self.write_acceptance_plank()

        with mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertEqual(outcome.sha, main_sha)
        self.assertTrue(self.is_ancestor(main_sha, self.worktree_head()),
                        "main обязан быть подтянут в ветку задачи")


if __name__ == "__main__":
    unittest.main()
