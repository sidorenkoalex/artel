"""Приёмочный тест AC-3 — 01M1NBWTSXEJB24PXR417YF1VA: журнал отката по
AC-2.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-3. Откат по AC-2 отражается записью в журнал, называющей отброшенные
пути и число отброшенных строк.

Число строк контролируется тестом буквально: правка добавляет РОВНО 3
строки в единственный изменённый файл — журнал обязан назвать и путь
(`CLAUDE.md`), и это число (3), иначе критерий «число отброшенных строк»
не проверен, а изображён.

Красен до реализации: до этой задачи откат вне мандата роли вообще не
существует как отдельное действие (см. AC-2) — значит, и записи журнала
о нём нет. `orchestrator_checkpoint_steps()` — записи actor=orchestrator
с действием, начинающимся на «WIP-чекпоинт» (тот же префикс, что журналит
существующий `commit_timeout_checkpoint`, `tests/test_timeout_checkpoint.
py`) — сегодня для этого сценария пуст, тест ниже ловит именно это.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import checkpoint, store  # noqa: E402


class DiscardJournalNamesPathsAndLineCountTest(MandateCheckpointTest):

    def test_ac3_discarded_path_and_line_count_are_journaled(self):
        """Таймаут шага `test_author` с правкой ровно из 3 добавленных
        строк в `CLAUDE.md` — запись журнала об откате называет и путь
        `CLAUDE.md`, и число 3.

        Ловит мутацию: откат путей реализован (AC-2 зелёный), но без
        журналирования — тогда `orchestrator_checkpoint_steps()` для
        этого сценария остался бы пуст, либо запись не называла бы ни
        путь, ни число строк.
        """
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        claude_md.write_text(
            claude_md.read_text(encoding="utf-8")
            + "строка 1\nстрока 2\nстрока 3\n", encoding="utf-8")

        checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "test_author")

        entries = self.orchestrator_checkpoint_steps()
        self.assertTrue(
            entries,
            "AC-3: откат вне мандата роли обязан оставить запись в "
            "журнале actor=orchestrator, действие «WIP-чекпоинт…»")
        marker = " ".join(f"{r['action']} {r['detail']}" for r in entries)
        self.assertIn(
            "CLAUDE.md", marker,
            f"AC-3: запись журнала обязана называть отброшенный путь — "
            f"фактические записи: {marker!r}")
        self.assertTrue(
            re.search(r"\b3\b", marker),
            f"AC-3: запись журнала обязана называть число отброшенных "
            f"строк (3) — фактические записи: {marker!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
