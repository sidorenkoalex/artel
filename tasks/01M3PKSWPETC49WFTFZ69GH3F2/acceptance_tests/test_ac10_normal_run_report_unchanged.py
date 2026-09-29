"""AC-10 — 01M3PKSWPETC49WFTFZ69GH3F2: штатный прогон через процесс клона
даёт прежние вердикт, сводку и сравнение с базовой линией.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Выбор шаблонов и наборов, локальный слой моделей клона, вход
Codex клона, сравнение с базовой линией, вердикт штатного прогона и
формат сводки для штатного прогона не меняются: существующие тесты этих
частей проходят без ослабления.

Этот файл — сквозная половина критерия: два штатных прогона одного
шаблона через процесс клона. Первый заводит базовую линию, второй
сравнивается с ней без предупреждения (метрики те же); оба — вердикт
`green`, первая строка вывода и строка сводки задачи — в сегодняшнем
формате `canary._run_one_task`/`cmd_canary` байт-в-байт по структуре.
Вторая половина — прогон существующих наборов этих частей —
`test_ac10_existing_canary_suites_pass.py`.

Красен до реализации: ведение в процессе пульта упирается в растяжку
песочницы — строки сводки и строки `canary_runs` нет.
"""
import re
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402
from orchestrator import config  # noqa: E402


class NormalRunReportTest(_clone_drive.CloneDriveSandbox):

    def setUp(self):
        super().setUp()
        self.target = self.commit_code(_clone_drive.SCENARIO_GREEN,
                                       self.new_marker("метка"))

    def summary_re(self, task_id: str, tail: str) -> str:
        return (rf"^  {re.escape(task_id)}: шагов=\d+  \$\d+\.\d\d  "
                rf"ревью-итераций=0  эскалаций=0  повторов developer=0  "
                rf"исход=killed \(штатно\)  sha={self.target} \([^)]*\)  "
                rf"набор={re.escape(config.CANARY_DEFAULT_SET)}  "
                rf"test_author=нет{tail}$")

    def test_ac10_green_verdict_summary_format_and_baseline(self):
        """Два штатных прогона: оба пишут `canary_runs` с вердиктом `green`;
        первая строка вывода называет шаблон и проверяемый sha в прежнем
        формате; строка сводки первого прогона кончается «[бейзлайн
        создан]» и заводит строку `canary_baseline`, второго — без
        приписок (метрики совпали с базовой линией).

        Ловит мутацию: пульт после перехода на процесс клона пишет сводку
        по своим полям (меняется порядок/имена полей строки сводки), не
        заводит базовую линию по результату клона (нет «[бейзлайн создан]»
        и строки `canary_baseline`) или сравнивает второй прогон с пустыми
        метриками (предупреждение об отклонении на неизменном шаблоне).
        """
        self.run_canary(self.target)
        self.assert_no_crash()
        first_out = self.output
        self.run_canary(self.target)
        self.assert_no_crash()
        second_out = self.output

        rows = self.canary_rows()
        self.assertEqual(len(rows), 2, f"(зерно {self.seed})\n{first_out}\n{second_out}")
        self.assertEqual([r["verdict"] for r in rows], ["green", "green"])

        head_re = (rf"^\[canary\] прогон \d{{8}}T\d{{6}}Z: 1 задач из пула .+ в "
                   rf"порядке прогона: {_clone_drive.TEMPLATE_TITLE}; целевой sha "
                   rf"{self.target} \([^)]*\), набор "
                   rf"{re.escape(config.CANARY_DEFAULT_SET)}$")
        self.assertRegex(first_out.splitlines()[0], head_re)

        for out, row, tail in ((first_out, rows[0], r"  \[бейзлайн создан\]"),
                               (second_out, rows[1], "")):
            self.assertIn(f"[canary] {row['task_id']} заведена из "
                          f"{_clone_drive.TEMPLATE_TITLE}.md", out)
            self.output = out
            self.assertRegex(self.summary_line(row["task_id"]),
                             self.summary_re(row["task_id"], tail))
        self.assertNotIn("ВНИМАНИЕ", second_out)

        conn = sqlite3.connect(str(config.DB))
        try:
            baseline = conn.execute(
                "SELECT steps FROM canary_baseline WHERE title=? AND set_name=?",
                (_clone_drive.TEMPLATE_TITLE, config.CANARY_DEFAULT_SET)).fetchall()
        finally:
            conn.close()
        self.assertEqual(baseline, [(rows[0]["steps"],)])


if __name__ == "__main__":
    unittest.main()
