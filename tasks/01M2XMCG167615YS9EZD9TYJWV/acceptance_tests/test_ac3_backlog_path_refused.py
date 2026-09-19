"""Приёмочный тест AC-3 задачи 01M2XMCG167615YS9EZD9TYJWV:
`doc-commit docs/backlog.md` отказывает — для этого пути есть `note`;
коммит в origin не создаётся.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — отказ приходит от диспетчера («Неизвестная команда»), и
`assert_refused` красен на этом маркере.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import BACKLOG_TEXT, DocCommitSandbox  # noqa: E402

BACKLOG_REL = "docs/backlog.md"


class BacklogPathRefusedTest(DocCommitSandbox):

    def test_ac3_backlog_is_refused_and_origin_keeps_its_content(self):
        """`docs/backlog.md` — путь команды `note`, а не `doc-commit`:
        вызов отказывает, origin остаётся на прежнем коммите и несёт
        прежний текст бэклога.

        Ловит мутацию: проверка допустимых путей смотрит только на
        префикс `docs/` и не выделяет `docs/backlog.md` — тогда
        `doc-commit` затёр бы бэклог целиком содержимым `--from`,
        и тест красен и на сдвинувшемся origin, и на подменённом тексте.
        """
        source = self.source_file("# Бэклог\n\nцеликом переписанный файл\n")
        before = self.origin_head()

        self.assert_refused(["doc-commit", BACKLOG_REL, "--from", str(source),
                             "--message", "правка бэклога"])

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(BACKLOG_REL), BACKLOG_TEXT)


if __name__ == "__main__":
    unittest.main()
