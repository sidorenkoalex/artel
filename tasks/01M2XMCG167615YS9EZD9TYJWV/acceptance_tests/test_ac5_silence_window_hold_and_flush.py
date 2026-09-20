"""Приёмочный тест AC-5 задачи 01M2XMCG167615YS9EZD9TYJWV: при открытом
окне тишины `doc-commit` не пушит, а удерживает запись в
`.artel/notes-pending/`; `doc-commit --flush` после закрытия окна её
отправляет.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — вызов под открытым окном отказывает «Неизвестная команда»
(`run_allowing_exit` красит тест прямо на этом маркере), удержанной
записи не появляется.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import DOC_REL, ROADMAP_TEXT, DocCommitSandbox  # noqa: E402

NEW_TEXT = "# Роадмап\n\nПравка, дождавшаяся закрытия окна тишины.\n"


class SilenceWindowHoldAndFlushTest(DocCommitSandbox):

    def test_ac5_open_window_holds_record_and_flush_after_close_pushes_it(self):
        """Окно тишины открыто задачей в состоянии из
        `config.NOTE_SILENCE_WINDOW_STATES`: вызов `doc-commit` не
        сдвигает origin и оставляет ровно одну запись в
        `.artel/notes-pending/`. После закрытия окна `doc-commit --flush`
        доводит её до origin — файл там равен содержимому `--from`.

        Ловит мутацию: `doc-commit` не спрашивает `_silence_window_reason`
        вовсе и пушит немедленно (механика `note` перенесена без ветки
        удержания) — тест красен на сдвинувшемся origin и пустом
        `pending_files()` ещё до закрытия окна.
        """
        source = self.source_file(NEW_TEXT)
        self.open_silence_window()
        self.assertIsNotNone(notes._silence_window_reason(),
                             "предусловие: окно тишины должно быть открыто")
        before = self.origin_head()

        self.run_allowing_exit("doc-commit", DOC_REL, "--from", str(source),
                               "--message", "правка под окном тишины")

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(DOC_REL), ROADMAP_TEXT)
        self.assertEqual(len(self.pending_files()), 1, self.pending_files())

        self.close_silence_window()
        self.assertIsNone(notes._silence_window_reason(),
                          "предусловие: окно тишины должно закрыться")

        self.run_artel("doc-commit", "--flush")

        self.assertEqual(self.origin_show(DOC_REL), NEW_TEXT)
        self.assertEqual(self.pending_files(), [])


if __name__ == "__main__":
    unittest.main()
