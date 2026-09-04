"""AC-6 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «artel report показывает суммарную верхнюю оценку
(spent_estimate_usd) отдельной строкой/метрикой от точной суммы
(spent_usd).»

Красен до реализации: колонки `tasks.spent_estimate_usd` в схеме нет
(появится миграцией требования 1) — сценарий падает уже на
`conn.execute("UPDATE tasks SET spent_estimate_usd=...")`
(`sqlite3.OperationalError: no such column`); после появления колонки
`orchestrator/report.py` (`_metrics_html`/`_render`) сегодня вообще не
читает её и не печатает — `self.assertIn("$7.00", html)` не находит
подстроку.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, report  # noqa: E402
from _sandbox import CostTmpRootTest  # noqa: E402


class ReportShowsEstimateSeparatelyTest(CostTmpRootTest):

    def test_ac6_report_shows_the_estimate_and_the_exact_spend_as_distinct_figures(self):
        """`.artel/report.html` несёт и точную сумму, и верхнюю оценку —
        двумя РАЗЛИЧИМЫМИ числами, не слитыми в одно.

        Ловит мутацию: отчёт складывает `spent_usd + spent_estimate_usd`
        в единую метрику «расход» вместо отдельной строки оценки —
        `$7.00` (сама оценка) нигде в HTML не появится, тест
        покраснеет.
        """
        conn = self.conn
        conn.execute("UPDATE tasks SET spent_usd=?, spent_estimate_usd=? "
                     "WHERE id=?", (3.0, 7.0, self.TASK))
        conn.commit()

        report.cmd_report()

        html = (config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")
        self.assertIn("$3.00", html, "точная сумма видна")
        self.assertIn("$7.00", html, "верхняя оценка видна отдельной цифрой")
