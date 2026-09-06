"""AC-5: если для критерия с пометкой `ci` данных CI нет, либо CI
красный или незавершённый, автогейт НЕ засчитывает критерий исполненным
— задача идёт на ручной гейт приёмки (остаётся в `acceptance`), причина
(какой критерий, какой статус CI) записывается в журнал задачи.

Красен до реализации: сегодня `_autogate_conditions` не знает про
пометку `ci` (недостающая ветвь AC-4/AC-5) — планка с единственной
пометкой `ci` читается как планка БЕЗ единой пометки, условие «а»
проходит пусто, и при заглушенных условиях б/в/г/д (`autogate()`)
автогейт целиком проходит в `merge_gate` НЕЗАВИСИМО от статуса CI —
`self.assertEqual(self.state(), "acceptance")` ниже красит оба теста
до реализации: задача сегодня уезжает в `merge_gate` при красном/
отсутствующем CI, хотя обязана остаться на ручном гейте.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateCiMarkerSandbox, ci_only_planka  # noqa: E402


class Ac5CiMarkerMissingOrRedCiBlocksAutogateTest(AutogateCiMarkerSandbox):

    def test_ac5_red_ci_of_code_branch_keeps_task_on_manual_gate(self):
        """Планка несёт единственную пометку `# AC-2: ci`, CI головного
        коммита кодовой ветки красный (одна проверка с
        `conclusion=failure`) — автогейт не проходит, задача остаётся
        в `acceptance`, а причина в журнале называет критерий (AC-2).

        Ловит мутацию: реализация, читающая только факт «данные CI
        есть» без разбора заключения проверок (`conclusion`) — приняла
        бы красный CI за исполненный критерий, тест поймает переход в
        `merge_gate` там, где он не должен случиться.
        """
        self.seed_planka(ci_only_planka(2))

        with self.gh_check_runs(conclusion="failure"):
            self.autogate()

        self.assertEqual(self.state(), "acceptance",
                         "красный CI не должен пропускать критерий ci")
        reasons = "; ".join(detail for _, _, detail in self.journal_rows()
                            if detail)
        self.assertIn("AC-2", reasons,
                      "журнал обязан называть критерий с непройденным ci")

    def test_ac5_missing_ci_data_of_code_branch_keeps_task_on_manual_gate(self):
        """Планка несёт единственную пометку `# AC-2: ci`, а `gh` не
        отвечает вовсе (данных о CI нет) — автогейт не проходит
        (fail-closed: отсутствие данных — не зелёный), задача остаётся
        в `acceptance`.

        Ловит мутацию: реализация, трактующая отсутствие ответа `gh`
        как «нечего проверять — считаем исполненным» (не fail-closed,
        обратная требованию 2 полярность) — тест поймает переход в
        `merge_gate` там, где ожидается отказ.
        """
        self.seed_planka(ci_only_planka(2))

        with self.gh_no_data():
            self.autogate()

        self.assertEqual(self.state(), "acceptance",
                         "отсутствие данных CI не должно пропускать "
                         "критерий ci (fail-closed)")


if __name__ == "__main__":
    unittest.main()
