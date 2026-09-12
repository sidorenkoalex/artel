"""Приёмочные тесты AC-4, AC-8 задачи 01M2B6K76EAFDF5X1B3Z9XK30Q.

Красен до реализации: `fsm_autogate._maybe_autogate_acceptance` сегодня
не журналирует запись «приёмка: что проверит approve» вовсе — оба теста
падают внутри `entry_report()` (записей действия 0), не доходя до
собственных assert'ов.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AcceptanceEntryReportSandbox  # noqa: E402

_CLEAN_PLANKA = '''"""Маркер: заведомо чистая планка (без manual/skip/escalate)."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''


class NoMarkerReportTest(AcceptanceEntryReportSandbox):
    """Планка без единой пометки manual/skip/escalate."""

    def setUp(self):
        super().setUp()
        self.seed_planka(_CLEAN_PLANKA)
        self.checkout_code_branch()
        self.commit_on_code_branch("dev.txt", "работа\n", "работа по задаче")

    def test_ac4_clean_planka_still_autogates_to_merge_gate(self):
        """Планка не несёт ни одного manual/skip/escalate-критерия — запись
        несёт «автогейт пройдёт сам» вместо группы «остаётся человеку», а
        переход `acceptance -> merge_gate` автогейтом при выполнении
        прочих условий по-прежнему проходит без участия Оператора, как и
        до этой задачи (SPEC AC-4).

        Ловит мутацию: новая печать/журнал случайно блокирует сам
        автогейт (например, ранний `return` внутри новой ветки кода до
        вызова `store.set_state` в `merge_gate`) — `self.state()` ниже
        останется `"acceptance"` вместо `"merge_gate"`.
        """
        out, detail = self.entry_report(iteration=1)

        self.assertIn("автогейт пройдёт сам", detail)
        self.assertNotIn("остаётся человеку", detail,
                         "без manual/skip/escalate вторая группа заменена "
                         "целиком, а не дополнена")
        self.assertEqual(self.state(), "merge_gate",
                         "AC-4: поведение автогейта не меняется — переход "
                         "по-прежнему проходит сам, без Оператора")

    def test_ac8_clean_planka_report_says_autogate_will_pass_itself(self):
        """Планка без пометок: запись (и печать) несут именно фразу
        «автогейт пройдёт сам» (SPEC AC-8) — точный текст, не любое
        описание отсутствия ручных пунктов.

        Ловит мутацию: код, печатающий пустую вторую группу (например,
        `"остаётся человеку: "` без единого пункта) вместо литеральной
        фразы «автогейт пройдёт сам» — `assertIn` ниже не найдёт точную
        подстроку ни в `detail`, ни в `out`.
        """
        out, detail = self.entry_report(iteration=1)

        self.assertIn("автогейт пройдёт сам", detail)
        self.assertIn("автогейт пройдёт сам", out)


if __name__ == "__main__":
    unittest.main()
