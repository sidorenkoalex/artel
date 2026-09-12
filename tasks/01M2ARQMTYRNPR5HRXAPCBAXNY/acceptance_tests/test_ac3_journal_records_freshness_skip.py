"""AC-3 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md): пропуск подтяжки по
AC-1 журналируется (`store.journal`) записью с действием «свежесть: N
документных коммитов main без подтяжки», где N — число таких файлов, и
`detail`, перечисляющим первые 10 путей.

Красен до реализации: правило AC-1 (условие пропуска подтяжки) ещё не
реализовано в `pull.evaluate` — при `behind > 0` она безусловно идёт в
`git merge` и никогда не журналирует запись «свежесть: …»
(`grep -n "свежесть:" orchestrator/pull.py` пуст).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import pull  # noqa: E402


class FreshnessSkipJournalRecordTest(PullFreshnessSandbox):

    def test_ac3_skip_pull_journals_freshness_record_with_paths(self):
        """Пропуск подтяжки по двум документным коммитам main
        (`docs/backlog.md`, `docs/other.md`) обязан оставить РОВНО одну
        запись журнала с действием «свежесть: 2 документных коммитов main
        без подтяжки», чей `detail` называет оба пути.

        Ловит мутацию: `evaluate` признаёт ветку `Fresh` по новому
        правилу, но не журналирует запись (или журналирует без списка
        путей) — `assertEqual(len(details), 1)`/`assertIn` по каждому
        пути поймают отсутствие записи или её пустой `detail`."""
        self.branch_off_main()
        self.commit_on_branch({"orchestrator/ac3_marker.py": "# ветка\n"},
                              f"{self.TASK}: правка ветки")
        self.add_main_commit({"docs/backlog.md": "строка 1\n"},
                             "оператор: копилка 1")
        self.add_main_commit({"docs/other.md": "строка 2\n"},
                             "оператор: копилка 2")

        outcome = self.evaluate()

        self.assertEqual(outcome, pull.Fresh())
        matching = [
            r["detail"] for r in self.journal_rows()
            if r["action"] == "свежесть: 2 документных коммитов main без подтяжки"
        ]
        self.assertEqual(len(matching), 1,
                         "запись журнала обязана появиться ровно один раз")
        self.assertIn("docs/backlog.md", matching[0])
        self.assertIn("docs/other.md", matching[0])


if __name__ == "__main__":
    unittest.main()
