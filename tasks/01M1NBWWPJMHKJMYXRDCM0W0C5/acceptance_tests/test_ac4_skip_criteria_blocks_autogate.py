"""AC-4 (SPEC): та же задача (планка только в артефактной ветке), но с
хотя бы одним skip-критерием — не проходит автогейт, причина — «автогейт:
критерии skip — AC-<номера>».

Красен до реализации: тем же расхождением, что AC-3 — сегодня
skip-маркер артефактной ветки не достигает этой строки, функция
отказывает раньше, на пустом `acc_tdir` (диск), с причиной «каталог...
пуст или отсутствует».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateBranchSandbox, SKIP_PLANKA  # noqa: E402


class SkipCriteriaBlocksAutogateTest(AutogateBranchSandbox):

    def test_ac4_skip_marker_on_branch_blocks_autogate_with_named_reason(self):
        """Планка артефактной ветки несёт один skip-критерий — автогейт
        не проходит, состояние остаётся `acceptance`, причина в журнале
        и в выводе — «автогейт: критерии skip — AC-2».

        Ловит мутацию: если реализация перепутает ветвление
        manual/skip (вернёт формулировку «manual» для skip-маркера или
        наоборот) либо перестанет распознавать skip-маркер ветки вовсе,
        `assertIn` на точную формулировку и `assertEqual` на состояние
        поймают это.
        """
        self.seed_planka(SKIP_PLANKA)

        out = self.autogate()

        self.assertEqual(self.state(), "acceptance")
        self.assertIn("автогейт: критерии skip — AC-2", out)
        detail = "\n".join(r[2] for r in self.journal_rows())
        self.assertIn("автогейт: критерии skip — AC-2", detail)


if __name__ == "__main__":
    unittest.main()
