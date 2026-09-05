"""AC-7 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «RETRO задачи (docs/retro/<id>.md) показывает верхнюю
оценку стоимости отдельной строкой от «Стоимость итого» (spent_usd),
когда у задачи spent_estimate_usd больше нуля.»

Красен до реализации: колонки `tasks.spent_estimate_usd` в схеме нет
(появится миграцией требования 1) — сценарий падает уже на прямом
`UPDATE tasks SET spent_estimate_usd=...`
(`sqlite3.OperationalError: no such column`); после появления колонки
`orchestrator/retro.py::_cost_block`/`build_done` сегодня печатают
только `f"Стоимость итого: ${spent_usd:.2f}"` и построчный расход по
actor — `self.assertIn("$7.00", text)` не находит подстроку.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import retro  # noqa: E402
from _sandbox import CostTmpRootTest  # noqa: E402


class RetroShowsEstimateSeparatelyTest(CostTmpRootTest):

    def test_ac7_retro_shows_the_estimate_as_a_line_separate_from_the_total(self):
        """RETRO задачи с ненулевой `spent_estimate_usd` несёт и
        «Стоимость итого» (`spent_usd`), и верхнюю оценку — двумя
        различимыми числами, не слитыми в одну сумму.

        Ловит мутацию: `build_done` продолжает печатать только
        `spent_usd` (оценка вовсе не выводится) — `$7.00` нигде в тексте
        RETRO не появится, тест покраснеет.
        """
        self.conn.execute(
            "UPDATE tasks SET spent_usd=?, spent_estimate_usd=? WHERE id=?",
            (3.0, 7.0, self.TASK))
        self.conn.commit()

        text = retro.build_done(self.conn, self.TASK, "cafe" * 10)

        self.assertIn("Стоимость итого: $3.00", text)
        self.assertIn("$7.00", text, "верхняя оценка — отдельной строкой")

    def test_ac7_retro_without_any_estimate_does_not_mention_it(self):
        """Требование 7 обусловлено: строка оценки появляется, ТОЛЬКО
        когда `spent_estimate_usd` больше нуля — задача без частичных
        шагов не обзаводится лишней строкой «$0.00 оценки».

        Ловит мутацию: строка оценки печатается безусловно (даже при
        нулевой `spent_estimate_usd`) — в тексте появится «$0.00»
        рядом со словом «оцен», которого требование 7 не предполагает
        для этого случая.
        """
        self.conn.execute(
            "UPDATE tasks SET spent_usd=?, spent_estimate_usd=? WHERE id=?",
            (3.0, 0.0, self.TASK))
        self.conn.commit()

        text = retro.build_done(self.conn, self.TASK, "cafe" * 10)

        self.assertIn("Стоимость итого: $3.00", text)
        self.assertNotIn("оцен", text.lower())
