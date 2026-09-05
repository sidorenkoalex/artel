"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-7 (первая строка
stdout в режиме артефактной ветки — сводка «сдано N / черновиков M /
нарушений K» с фактическими числами по проверенному набору файлов).

Красен до реализации: сегодня такой строки не печатается вовсе ни при
каких обстоятельствах (`grep -n "сдано" scripts/guard.py` и `grep -n
"черновиков" scripts/guard.py` — без совпадений) — `_sandbox.
parse_summary` вернёт `None` на любом сегодняшнем выводе,
`assertIsNotNone` красен именно на этом, а не на конкретных числах.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import parse_summary, run_main, spec_zones_text  # noqa: E402


class SummaryLineReportsActualCountsTest(unittest.TestCase):
    """Три файла с заранее известными категориями: один валидный сданный
    (0 нарушений), один черновик с одним нарушением, один сданный с
    одним нарушением — сводка обязана назвать N=2, M=1, K=2 и стоять
    ПЕРВОЙ строкой вывода."""

    def test_ac7_summary_line_matches_the_documented_format_with_real_counts(self):
        """Ловит мутацию: разработчик считает `K` только по сданным файлам
        (забывая приплюсовать нарушения черновиков, хотя требование 5
        явно требует «и по сданным, и по черновикам») — тогда `K` вышло
        бы 1 вместо 2, при том что `N`/`M` совпали бы случайно.
        """
        files = {
            "tasks/T1/SPEC.md": spec_zones_text(status="ready", zones="tests/"),
            "tasks/T2/SPEC.md": spec_zones_text(status="draft", zones=None),
            "tasks/T3/SPEC.md": spec_zones_text(status="ready", zones=None),
        }

        code, out = run_main(files, artifact_branch=True)

        summary = parse_summary(out)
        self.assertIsNotNone(summary, out)
        sdano, chernovikov, narusheniy = summary
        self.assertEqual((sdano, chernovikov, narusheniy), (2, 1, 2), out)
        self.assertEqual(code, 1, out)

    def test_ac7_summary_line_is_the_first_line_of_stdout(self):
        """Ловит мутацию: разработчик печатает сводку ПОСЛЕ списка
        нарушений (например добавляет её в конец, а не в начало вывода)
        — `stdout.splitlines()[0]` перестал бы совпадать с форматом
        сводки, хотя сама строка где-то в выводе присутствовала бы.
        """
        files = {"tasks/T1/SPEC.md": spec_zones_text(status="ready", zones=None)}

        code, out = run_main(files, artifact_branch=True)

        self.assertIsNotNone(parse_summary(out), out)


if __name__ == "__main__":
    unittest.main()
