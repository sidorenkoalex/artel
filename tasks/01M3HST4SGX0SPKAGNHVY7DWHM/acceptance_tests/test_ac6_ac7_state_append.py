"""AC-6, AC-7 — 01M3HST4SGX0SPKAGNHVY7DWHM: дописка состояния отделяется
разделителем с датой; у пустой ячейки ведущего разделителя нет.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Дописка состояния к непустой ячейке даёт
`<прежний текст> — <ДД.ММ>: <новый текст>`: прежний текст присутствует
целиком, новый отделён разделителем с текущей датой.

AC-7. Дописка состояния к пустой ячейке (пробелы либо «—») даёт
`<ДД.ММ>: <новый текст>` без ведущего разделителя.

Дата сверяется с текущей датой пульта в обеих раскладках (местная и UTC,
`_sandbox.today_stamps`): часовой пояс критерий не фиксирует, а прогон
около полуночи не должен красить залоченную планку.

Красен до реализации: `_apply_append` (:228) склеивает прежний текст с
новым одним пробелом (`f"{cells[-1]} {text}".strip()`) — ни разделителя,
ни даты в ячейке нет, поэтому оба теста падают на разборе ячейки.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

FILLED = re.compile(r"(?P<old>.*) — (?P<stamp>\d\d\.\d\d): (?P<new>.*)")
EMPTY = re.compile(r"(?P<stamp>\d\d\.\d\d): (?P<new>.*)")


class StateAppendTest(_sandbox.NoteSandbox):

    def test_ac6_append_to_filled_cell_keeps_old_text_and_dated_separator(self):
        """Дописка к строке, чья колонка «Состояние» несёт «прежнее
        состояние»: ячейка в документе origin становится
        `прежнее состояние — <ДД.ММ>: ДОПИСКАОДИН` — прежний текст цел,
        новый отделён разделителем с текущей датой пульта.

        Ловит мутацию: разделитель поставлен, но прежний текст ячейки
        затёрт (дописка реализована через путь `--set-state`, заменяющий
        ячейку целиком) — тест красен на несовпадении группы «old».
        """
        self.note("--append", "СОСТОЯНИЕЕСТЬ", "--text", "ДОПИСКАОДИН")

        row = self.backlog_row("СОСТОЯНИЕЕСТЬ")
        cell = _sandbox.cells(row)[-1]
        match = FILLED.fullmatch(cell)
        self.assertIsNotNone(match, f"ячейка «{cell}» строки {row}")
        self.assertEqual(match.group("old"), "прежнее состояние", cell)
        self.assertEqual(match.group("new"), "ДОПИСКАОДИН", cell)
        self.assertIn(match.group("stamp"), _sandbox.today_stamps(), cell)

    def test_ac7_append_to_empty_cell_has_no_leading_separator(self):
        """Дописка к строке с пробельной колонкой «Состояние» и к строке с
        прочерком «—»: в обоих случаях ячейка становится
        `<ДД.ММ>: <новый текст>` — ни ведущего разделителя, ни прежнего
        прочерка.

        Ловит мутацию: пустой признан только пробельный случай, прочерк
        «—» трактуется как обычный текст — вторая ячейка получает
        `— — <ДД.ММ>: …`, и `fullmatch` без ведущего разделителя её не
        принимает.
        """
        for key in ("СОСТОЯНИЕПУСТО", "СОСТОЯНИЕПРОЧЕРК"):
            with self.subTest(key=key):
                self.note("--append", key, "--text", f"ДОПИСКА{key}")

                row = self.backlog_row(key)
                cell = _sandbox.cells(row)[-1]
                match = EMPTY.fullmatch(cell)
                self.assertIsNotNone(match, f"ячейка «{cell}» строки {row}")
                self.assertEqual(match.group("new"), f"ДОПИСКА{key}", cell)
                self.assertIn(match.group("stamp"), _sandbox.today_stamps(),
                              cell)


if __name__ == "__main__":
    unittest.main()
