"""AC-3 (SPEC): та же задача (планка только в артефактной ветке), но с
хотя бы одним manual-критерием в планке (прочитанной из артефактной
ветки), не проходит автогейт: состояние остаётся `acceptance`, причина
в журнале и выводе — «автогейт: критерии manual — AC-<номера>» (та же
формулировка, что до этой правки).

Красен до реализации: строка «автогейт: критерии manual — AC-...» уже
существует в `orchestrator/fsm_autogate.py` сегодня и эта задача её
текст не меняет (SPEC требование 2), но СЕГОДНЯ manual-маркер
артефактной ветки вообще не достигает этой строки — функция отказывает
раньше, на пустом `acc_tdir` (диск), с ДРУГОЙ причиной («каталог...
пуст или отсутствует»); тест красный именно по этому расхождению, до
переключения чтения на ветку.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateBranchSandbox, MANUAL_PLANKA  # noqa: E402


class ManualCriteriaBlocksAutogateTest(AutogateBranchSandbox):

    def test_ac3_manual_marker_on_branch_blocks_autogate_with_named_reason(self):
        """Планка артефактной ветки несёт один manual-критерий —
        автогейт не проходит, состояние остаётся `acceptance`, причина
        в журнале и в выводе — «автогейт: критерии manual — AC-2»
        (номер — из фикстуры планки песочницы).

        Ловит мутацию: если реализация перестанет отличать manual от
        skip (например, объединит обе пометки в одну причину без слова
        "manual") или перестанет распознавать manual-маркер ветки
        вовсе (пропустит переход дальше), `assertIn` на точную
        формулировку и `assertEqual` на состояние поймают это.
        """
        self.seed_planka(MANUAL_PLANKA)

        out = self.autogate()

        self.assertEqual(self.state(), "acceptance")
        self.assertIn("автогейт: критерии manual — AC-2", out)
        detail = "\n".join(r[2] for r in self.journal_rows())
        self.assertIn("автогейт: критерии manual — AC-2", detail)


if __name__ == "__main__":
    unittest.main()
