"""Юнит-тесты `orchestrator.catalog._pin_divergence_warning_text`/
`_pin_divergence_journal_detail` (SPEC 01M297HFSKV3GVZJ9YF20FZEZE,
требование 3, AC-7): чистое форматирование предупреждения `cmd_new` о
непушенных коммитах главной копии — без git, тем же приёмом, что
`tests/test_catalog_tz_zones_parsing.py` для соседней подсказки
калибровки. Сама сверка с origin (fetch, предковость) — на настоящем
git, покрыта acceptance_tests этой задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog  # noqa: E402

COMMITS = [
    ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "документный коммит один"),
    ("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "документный коммит два"),
]


class PinDivergenceWarningTextTest(unittest.TestCase):

    def test_lists_the_seven_char_sha_and_message_of_each_commit(self):
        text = catalog._pin_divergence_warning_text(COMMITS)

        self.assertIn("пин расходится с origin", text)
        for sha, msg in COMMITS:
            self.assertIn(sha[:7], text)
            self.assertIn(msg, text)

    def test_counts_the_commits(self):
        text = catalog._pin_divergence_warning_text(COMMITS)

        self.assertIn(f"{len(COMMITS)}", text)


class PinDivergenceJournalDetailTest(unittest.TestCase):

    def test_names_the_count(self):
        detail = catalog._pin_divergence_journal_detail(COMMITS)

        self.assertIn("пин расходится с origin", detail)
        self.assertIn(f"{len(COMMITS)} коммит", detail)


if __name__ == "__main__":
    unittest.main()
