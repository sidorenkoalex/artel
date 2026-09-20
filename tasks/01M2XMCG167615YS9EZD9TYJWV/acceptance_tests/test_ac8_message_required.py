"""Приёмочный тест AC-8 задачи 01M2XMCG167615YS9EZD9TYJWV: вызов без
`--message` отказывает — основание правки обязательно; коммита в origin
нет, удержанной записи нет.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — отказ приходит от диспетчера («Неизвестная команда»), и
`assert_refused` красен на этом маркере, а не на отсутствии коммита.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import DOC_REL, ROADMAP_TEXT, DocCommitSandbox  # noqa: E402


class MessageRequiredTest(DocCommitSandbox):

    def test_ac8_missing_message_refuses_without_commit_or_hold(self):
        """Допустимый путь, существующий `--from`, но `--message` не
        передан: вызов отказывает, origin остаётся на прежнем коммите с
        прежним текстом, `.artel/notes-pending/` пуст.

        Ловит мутацию: `--message` объявлен необязательным и при
        отсутствии подставляется дефолт («правка Оператора») — тогда
        коммит создаётся, и тест красен и на сдвинувшемся origin, и на
        подменённом содержимом.
        """
        source = self.source_file("# Роадмап\n\nбез основания правки\n")
        before = self.origin_head()

        self.assert_refused(["doc-commit", DOC_REL, "--from", str(source)])

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(DOC_REL), ROADMAP_TEXT)
        self.assertEqual(self.pending_files(), [])


if __name__ == "__main__":
    unittest.main()
