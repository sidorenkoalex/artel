"""AC-10, AC-11 — 01M3HST4SGX0SPKAGNHVY7DWHM: `--apply` отказывает, когда
документ в origin ушёл от базы и когда заготовка нарушила форму.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. `--apply`, когда `docs/backlog.md` в `origin/main` изменился между
чтением заготовки и коммитом, — именованный отказ: коммита в `origin`
нет, содержимое файла в `origin` прежнее.

AC-11. `--apply` с заготовкой, потерявшей раздел («## Бэклог») либо
изменившей число колонок шапки раздела, — именованный отказ до коммита;
содержимое файла в `origin` прежнее.

Прочтение AC-10: воспроизводимое проявление «документ изменился» —
расхождение `docs/backlog.md` в `origin/main` с базой главной копии, та
самая сверка, на которую требование 10 ссылается словами «те же сверки,
что `doc-commit`: база — свежий `origin/main`» (`_build_doc_commit`, :373
— blob-sha в origin против blob-sha пина). Гонку внутри одного вызова
команды детерминированным тестом не поставить, а сверка базы ловит ровно
тот класс, ради которого критерий написан: заготовка готовилась от одной
версии документа, а коммит лёг бы поверх другой.

Красен до реализации: флага `--apply` у `note` нет (`_parse_args`, :573) —
argparse отказывает кодом выхода 2, а `assert_named_refusal` именно этот
случай называет отдельно: «argparse не разобрал аргументы вместо отказа по
существу».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import notes  # noqa: E402

FOREIGN_BACKLOG = _sandbox.BACKLOG_TEXT + "\n<!-- чужая правка в origin -->\n"


class ApplyBaseCheckTest(_sandbox.NoteSandbox):

    def test_ac10_document_changed_in_origin_past_the_base_refuses(self):
        """Чужая правка `docs/backlog.md` уехала в origin позже базы
        главной копии; `--apply` корректной заготовки — именованный отказ:
        коммита в origin нет, в origin по-прежнему чужой текст, удержанной
        записи не появилось.

        Ловит мутацию: `--apply` берёт содержимое из свежего origin и
        коммитит заготовку поверх, не сверяя базу (сверка доехала только до
        `doc-commit`) — чужая правка молча затирается, и тест красен на
        содержимом origin.
        """
        self.push_foreign_backlog_change(FOREIGN_BACKLOG)
        draft = _sandbox.draft_with_extra_row()
        before = self.origin_head()

        message = self.refusal(
            notes.cmd_note, "--apply",
            str(self.source_file(draft, "draft-backlog.md")),
            "--message", "мой разнос")

        self.assert_named_refusal(message, notes.BACKLOG_REL, "origin",
                                  "изменил", "устарел", "база")
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), FOREIGN_BACKLOG)
        self.assertEqual(notes.pending_notes(), [])


class ApplyDraftShapeTest(_sandbox.NoteSandbox):

    def test_ac11_draft_without_section_or_with_widened_header_refuses(self):
        """Две негодные заготовки по очереди: без раздела «## Бэклог»
        целиком и с шапкой «Копилки» на одну колонку шире, чем в origin.
        Каждая — именованный отказ до коммита; документ в origin после обеих
        попыток байт-в-байт прежний, удержанной записи нет.

        Ловит мутацию: проверяется только наличие заголовков разделов, а
        число колонок шапки — нет (или наоборот) — одна из двух заготовок
        доезжает до коммита, и тест красен на содержимом origin в её
        итерации.
        """
        for name, draft in (("без раздела",
                             _sandbox.draft_without_backlog_section()),
                            ("шапка шире",
                             _sandbox.draft_with_widened_kopilka_header())):
            with self.subTest(draft=name):
                before = self.origin_head()

                message = self.refusal(
                    notes.cmd_note, "--apply",
                    str(self.source_file(draft, "draft-backlog.md")),
                    "--message", "разнос")

                self.assert_named_refusal(message, "раздел", "колон", "шапк",
                                          "заготов")
                self.assertEqual(before, self.origin_head())
                self.assertEqual(self.origin_backlog(), _sandbox.BACKLOG_TEXT)
                self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
