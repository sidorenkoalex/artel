"""AC-11 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME (часть про состав) — состав и
порядок условий `fsm_autogate._autogate_conditions` не изменились.

Зелёный с рождения: тест сохранения существующего поведения — шесть
условий автогейта в сегодняшнем порядке; задача меняет detail ОТКАЗА
автогейта и текст записи «что проверит approve», но не то, какие условия
автогейт проверяет и в каком порядке (SPEC «Не входит»).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FullSuiteSandbox  # noqa: E402
from orchestrator import fsm_autogate, store  # noqa: E402

# Условия автогейта acceptance в сегодняшнем порядке — по опознавательному
# куску каждой строки перечня выполненных условий (полный текст несёт
# ветку/sha/суммы, он не предмет этого критерия). Планка песочницы без
# критериев `ci`, поэтому условия «критерии ci» в перечне нет.
CONDITIONS_IN_ORDER = (
    "каталог приёмочных тестов",
    "приёмочные тесты задачи зелёные",
    "источник планки",
    "полный набор tests/",
    "бюджет задачи",
    "вердикт REVIEW approved",
)


class ConditionsCompositionTest(FullSuiteSandbox):

    def test_ac11_autogate_conditions_keep_their_composition_and_order(self):
        """Полностью проходимый автогейт перечисляет ровно шесть условий
        ровно в сегодняшнем порядке: планка без manual/skip, зелёные
        приёмочные тесты задачи, источник планки, зелёный полный набор
        tests/, непревышенный бюджет, вердикт REVIEW approved.

        Ловит мутацию: разбор вывода прогона вставлен в автогейт лишним
        условием (или условие про полный набор переставлено к бюджету) —
        число и порядок записей перечня разойдутся с сегодняшними, а
        политика автогейта поменяется молча, мимо ADR.
        """
        self.set_green_run()
        self.set_state("acceptance")
        conn = store.db()

        ok, reason = fsm_autogate._autogate_conditions(
            conn, self.TASK, self.task_row(), self.tdir, 1)

        self.assertIsNone(reason,
                          f"автогейт песочницы обязан проходить целиком, "
                          f"отказал: {reason!r}")
        self.assertEqual(
            len(ok), len(CONDITIONS_IN_ORDER),
            f"число условий автогейта изменилось: {ok}")
        for got, expected in zip(ok, CONDITIONS_IN_ORDER):
            self.assertIn(expected, got,
                          f"условие не на своём месте: ожидался "
                          f"{expected!r}, стоит {got!r}")


if __name__ == "__main__":
    unittest.main()
