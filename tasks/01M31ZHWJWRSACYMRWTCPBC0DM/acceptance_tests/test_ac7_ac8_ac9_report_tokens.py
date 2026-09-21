"""AC-7, AC-8, AC-9 — 01M31ZHWJWRSACYMRWTCPBC0DM: `report` показывает
токены по видам рядом с долларами в разрезе задач и в разрезе ролей, а
строка без записей токенов — прочерк вместо нуля.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. `report` показывает токены по видам рядом с долларами в разрезе
задач.

AC-8. `report` показывает токены по видам рядом с долларами в разрезе
ролей.

AC-9. Строка `report` без записей токенов показывает прочерк, а не ноль.

Разметку строки отчёта критерии не фиксируют, поэтому планка не знает ни
тегов, ни классов: она разбирает готовый HTML на ЭЛЕМЕНТЫ
(`_tokens.rows`) и спрашивает, нашёлся ли элемент, несущий одновременно
адрес разреза (идентификатор задачи или имя роли), доллары и все четыре
вида со СВОИМИ числами. Числа у задачи (34/42/48/56) и у ролей
(11/13/17/19 и 23/29/31/37) разные — разрез, которого нет, не может
случайно совпасть с соседним.

Красен до реализации: `orchestrator/report.py` не печатает ни одного
числа токенов — ни в плитке борда, ни в строке закрытой задачи
(`_tile_html`/`_closed_tasks_html` знают только `_usd`), а разреза по
ролям в отчёте нет вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import config, report  # noqa: E402
from tests.sandbox import capture  # noqa: E402

REPORT_REL = (".artel", "report.html")


class ReportTokensTest(_tokens.TokensSandbox):

    def setUp(self):
        super().setUp()
        self.charge_two_roles()
        self.charge_without_tokens(self.SILENT, _tokens.DEV_ROLE,
                                   _tokens.SILENT_USD)
        capture(report.cmd_report)
        self.html = config.ROOT.joinpath(*REPORT_REL).read_text(
            encoding="utf-8")

    def rows_of(self, marker: str, *forbidden: str) -> list:
        found = _tokens.rows(self.html, marker, *forbidden)
        self.assertTrue(found, f"в отчёте нет ни одной строки, несущей "
                               f"«{marker}» рядом с долларами")
        return found

    def test_ac7_task_row_carries_the_four_kinds_next_to_dollars(self):
        """В отчёте есть строка задачи `T001`, где рядом с её деньгами
        стоят все четыре вида токенов со СВОИМИ суммами по задаче
        (input=34, output=42, cache_write=48, cache_read=56) — и это
        строка задачи, а не документ целиком: чужого идентификатора
        `T002` в ней нет.

        Ловит мутацию: разрез задач берёт числа последнего шага задачи
        (или первой строки «agent cost KNOWN») вместо суммы по всем её
        шагам — в строке окажется `input=11` или `input=23`, а не 34, и
        `missing_kinds` назовёт все четыре вида непоказанными.
        """
        candidates = self.rows_of(self.TASK, self.SILENT)

        missing = [_tokens.missing_kinds(row, _tokens.TASK_TOKENS)
                   for row in candidates]
        self.assertTrue(
            any(not gap for gap in missing),
            f"ни одна строка задачи {self.TASK} не несёт разбивку по видам "
            f"{_tokens.TASK_TOKENS} рядом с долларами; не хватает: "
            f"{missing}")

    def test_ac8_role_row_carries_the_four_kinds_next_to_dollars(self):
        """В отчёте есть строка роли `developer` со своими деньгами и
        своей разбивкой (11/13/17/19) и строка роли `reviewer` со своими
        (23/29/31/37); имени соседней роли в строке нет.

        Ловит мутацию: разрез ролей считает одну общую разбивку на все
        роли (складывает строки «agent cost KNOWN» без группировки по
        actor) — обе роли получат 34/42/48/56, и ни у одной из них
        собственные числа не найдутся.
        """
        cases = ((_tokens.DEV_ROLE, _tokens.DEV_TOKENS, _tokens.REV_ROLE),
                 (_tokens.REV_ROLE, _tokens.REV_TOKENS, _tokens.DEV_ROLE))
        for role, tokens, alien in cases:
            with self.subTest(role=role):
                candidates = self.rows_of(role, alien)
                missing = [_tokens.missing_kinds(row, tokens)
                           for row in candidates]
                self.assertTrue(
                    any(not gap for gap in missing),
                    f"ни одна строка роли {role} не несёт её разбивку "
                    f"{tokens} рядом с долларами; не хватает: {missing}")

    def test_ac9_row_without_token_records_shows_a_dash_not_zero(self):
        """Строка задачи `T002`, у которой шаг завершился без разбивки
        usage, показывает прочерк; ни в одной её строке нет ни вида,
        показанного нулём, ни голого нуля.

        Ловит мутацию: отсутствующая разбивка подставляется
        `.get(kind, 0)` — в строке появятся `input=0 … cache_read=0`
        («шаг прошёл бесплатно») вместо честного «данных нет», и обе
        проверки ниже покраснеют.
        """
        candidates = self.rows_of(self.SILENT, self.TASK)

        self.assertTrue(
            any(_tokens.has_dash(row) for row in candidates),
            f"ни одна строка задачи {self.SILENT} не показывает прочерк "
            f"вместо отсутствующих токенов: {candidates}")
        for row in candidates:
            self.assertEqual([], _tokens.zeroed_kinds(row),
                             f"вид токенов показан нулём вместо прочерка: "
                             f"{row}")
            self.assertEqual([], _tokens.bare_zeros(row),
                             f"голый ноль вместо прочерка в строке отчёта: "
                             f"{row}")


if __name__ == "__main__":
    unittest.main()
