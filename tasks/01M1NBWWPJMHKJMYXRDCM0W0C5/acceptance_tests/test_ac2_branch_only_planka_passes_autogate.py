"""AC-2 (SPEC): задача, у которой планка (`acceptance_tests/` без
manual/skip-критериев) закоммичена только в артефактную ветку и
отсутствует на диске рабочей копии в момент входа в `acceptance`,
проходит автогейт (переход `acceptance -> merge_gate`, `actor=autogate`)
при выполнении остальных условий ADR-0007 п.3 (б-д) — без ручного
вмешательства Оператора.

Красен до реализации: сегодня `_autogate_conditions` глядит на пустой
`acc_tdir` (диск) и всегда отвечает «каталог приёмочных тестов пуст или
отсутствует» — переход остаётся в `acceptance` вместо `merge_gate`, и
записи `actor=autogate` в журнале не появляется. После правки (планка
читается из артефактной ветки) при всех остальных условиях
заглушенными на «выполнено» тест обязан позеленеть.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateBranchSandbox, CLEAN_PLANKA  # noqa: E402


class BranchOnlyPlankaPassesAutogateTest(AutogateBranchSandbox):

    def test_ac2_branch_only_clean_planka_advances_to_merge_gate_by_autogate(self):
        """Планка коммитится ТОЛЬКО в артефактную ветку; `acc_tdir`
        (диск) указывает на несуществующий каталог, воспроизводя
        состояние после A7 (SPEC «Контекст»). Автогейт обязан пройти
        `acceptance -> merge_gate` без вмешательства Оператора, с
        записью журнала `actor=autogate`.

        Ловит мутацию: если чтение планки останется завязано на
        `acc_tdir` (диск), функция увидит пустой/отсутствующий каталог
        и откажет условие «а» — состояние останется `acceptance`
        вместо `merge_gate`, записи `actor=autogate` не будет.
        """
        self.assertFalse(self.stale_disk_dir().exists(),
                         "предпосылка теста: диска не существует")
        self.seed_planka(CLEAN_PLANKA)

        out = self.autogate()

        self.assertEqual(
            self.state(), "merge_gate",
            f"все условия ADR-0007 п.3 выполнены (планка — только в "
            f"ветке) — автогейт обязан пройти без Оператора: {out}")
        autogate_rows = [r for r in self.journal_rows() if r[0] == "autogate"]
        self.assertTrue(
            autogate_rows,
            f"ожидалась хотя бы одна запись журнала с actor=autogate; "
            f"журнал: {self.journal_rows()}")


if __name__ == "__main__":
    unittest.main()
