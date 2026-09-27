"""AC-8, AC-9 — 01M3HST4SGX0SPKAGNHVY7DWHM: `note --apply` заменяет
документ заготовкой одним коммитом и перечисляет в журнале удалённые
строки.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. `note --apply <файл> --message "<основание>"` с корректной
заготовкой заменяет `docs/backlog.md` её содержимым одним коммитом в
`origin/main`; сообщение коммита несёт основание; HEAD и рабочее дерево
главной копии после команды те же, что до неё.

AC-9. После успешного `--apply` журнал пульта несёт запись с числом
удалённых строк и перечнем самих строк, которые были в прежнем
содержимом документа и отсутствуют в заготовке.

Красен до реализации: флага `--apply` у `note` нет — `_parse_args` (:573)
не знает такого аргумента, и argparse отказывает кодом 2 раньше любого
обращения к origin.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import notes  # noqa: E402

REASON = "разнос бэклога по решению Оператора"

# Отдельно стоящее число в тексте журнала: фрагменты sha (цифры внутри
# hex-строки) под образец не подпадают — соседний символ там буквенный.
STANDALONE_NUMBER = re.compile(r"(?<!\w)(\d+)(?!\w)")


class ApplyReplacesDocumentTest(_sandbox.NoteSandbox):

    def test_ac8_draft_becomes_document_in_one_commit(self):
        """Корректная заготовка (те же три раздела, в «Копилке» на строку
        больше) приезжает в `origin/main` целиком: содержимое пути
        совпадает с заготовкой байт-в-байт, добавлен РОВНО один коммит,
        сообщение коммита несёт основание `--message`, а HEAD, ветка и
        рабочее дерево главной копии остались прежними.

        Ловит мутацию: `--apply` правит и коммитит документ в рабочей копии
        пульта (`config.ROOT`), а не в изолированном рабочем репозитории —
        снимок главной копии меняется, и тест красен на нём даже при
        верном содержимом в origin.
        """
        draft = _sandbox.draft_with_extra_row()
        before_commits = self.origin_commit_count()
        before_main = self.main_copy_snapshot()

        self.apply_draft(draft, REASON)

        self.assertEqual(self.origin_backlog(), draft)
        self.assertEqual(self.origin_commit_count(), before_commits + 1)
        self.assertIn(REASON, self.origin_message())
        self.assertEqual(before_main, self.main_copy_snapshot())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac9_journal_names_dropped_row_count_and_rows(self):
        """Заготовка без двух строк «Копилки»: журнал пульта после
        успешного `--apply` несёт число удалённых строк (2 — отдельно
        стоящим числом) и сами строки, причём длинная усечена — маркер за
        границей 80 знаков в журнал не попадает.

        Ловит мутацию: перечисляются не удалённые, а ДОБАВЛЕННЫЕ строки
        (стороны сравнения прежнего содержимого и заготовки перепутаны) —
        ни одного маркера СНЯТАЯ* в журнале нет, и тест красен на первом
        же `assertIn`.
        """
        draft = _sandbox.draft_without_dropped_rows()

        self.apply_draft(draft, REASON)
        self.assertEqual(self.origin_backlog(), draft)

        journal = self.journal_text()
        self.assertIn("2", set(STANDALONE_NUMBER.findall(journal)), journal)
        self.assertIn("СНЯТАЯОДИН", journal)
        self.assertIn("СНЯТАЯДВА", journal)
        self.assertNotIn("ХВОСТОДИН", journal)


if __name__ == "__main__":
    unittest.main()
