"""Приёмочный тест AC-6 задачи 01M2XMCG167615YS9EZD9TYJWV: удержанные
записи обоих видов лежат в одном каталоге `.artel/notes-pending/` в
общем JSON-формате с полем `kind`, и любой из двух флашей (`note
--flush`, `doc-commit --flush`) отправляет их обе.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — под открытым окном удерживается только запись `note`, второго
вида в каталоге не появляется, и тест красен на длине
`pending_records()`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import DOC_REL, DocCommitSandbox  # noqa: E402

NOTE_MARKER = "наблюдение из окна тишины"
NOTE_ROW = f"9 | 09.09 | {NOTE_MARKER} | orchestrator/n.py"
NEW_TEXT = "# Роадмап\n\nПравка, ушедшая общим флашем.\n"
BACKLOG_REL = "docs/backlog.md"


class FlushSendsBothKindsTest(DocCommitSandbox):

    def _hold_both_kinds(self) -> None:
        """Обе записи удерживаются штатным путём — открытым окном
        тишины, не подделкой файлов в каталоге: формат удержанной
        записи `doc-commit` тест не знает и знать не должен."""
        source = self.source_file(NEW_TEXT)
        self.open_silence_window()
        self.run_allowing_exit("note", "копилка", "--text", NOTE_ROW)
        self.run_allowing_exit("doc-commit", DOC_REL, "--from", str(source),
                               "--message", "правка под окном тишины")
        records = self.pending_records()
        self.assertEqual(len(records), 2, records)
        kinds = [r.get("kind") for r in records]
        self.assertNotIn(None, kinds,
                         f"запись без поля kind: {records}")
        self.assertEqual(len(set(kinds)), 2,
                         f"виды записей не различимы по kind: {kinds}")
        self.close_silence_window()

    def _assert_both_arrived(self) -> None:
        self.assertIn(NOTE_MARKER, self.origin_show(BACKLOG_REL))
        self.assertEqual(self.origin_show(DOC_REL), NEW_TEXT)
        self.assertEqual(self.pending_files(), [])

    def test_ac6_note_flush_sends_note_and_doc_commit_records(self):
        """Обе записи удержаны, флаш вызывается командой `note --flush` —
        в origin приезжают обе: строка копилки и новое содержимое
        `docs/roadmap.md`.

        Ловит мутацию: флаш разбирает каждую запись старым путём
        (`_build_for` по разделам бэклога) и на записи с чужим `kind`
        молча спотыкается, оставляя её висеть — тест красен на
        непустом `pending_files()` и старом содержимом роадмапа в
        origin.
        """
        self._hold_both_kinds()

        self.run_artel("note", "--flush")

        self._assert_both_arrived()

    def test_ac6_doc_commit_flush_sends_note_and_doc_commit_records(self):
        """Тот же расклад, но флаш вызывается командой `doc-commit
        --flush`: каталог удержанных записей один на два вида, и
        симметрично отправляет обе.

        Ловит мутацию: `doc-commit --flush` фильтрует каталог по своему
        виду записи и отправляет только записи `doc-commit`, бросая
        записи `note` висеть — тест красен на непустом `pending_files()`
        и отсутствии строки копилки в origin.
        """
        self._hold_both_kinds()

        self.run_artel("doc-commit", "--flush")

        self._assert_both_arrived()


if __name__ == "__main__":
    unittest.main()
