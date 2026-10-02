"""AC-4 — запись журнала «правка планки» после `amend-tests` с удалением
называет удалённый путь.

Группа: разовый
Красен до реализации: деталь записи «правка планки» не перечисляет удалённые пути — в ней нет acceptance_tests/README.md.

Разовый: планка исполняется до мержа; после мержа это свойство держит
`tests/test_amend_remove.py` (SPEC, требование 6 и AC-5).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (README_NAME, LongLivedLockedSandbox,  # noqa: E402
                      PlainLockedSandbox)

REMOVED = f"acceptance_tests/{README_NAME}"


class _JournalScenario:

    def assert_journal_names_removed(self) -> None:
        self.delete_on_disk(README_NAME)

        out = self.run_amend()

        self.assertNotIn("SystemExit", out, out)
        details = self.amend_details()
        self.assertEqual(len(details), 1, details)
        self.assertIn(REMOVED, details[0],
                      f"удалённый путь не назван в журнале: {details[0]}")


class PlainModeJournalTest(_JournalScenario, PlainLockedSandbox):

    def test_ac4_plain_mode_journal_names_removed_path(self):
        """Задача без перечня: README.md удалён на диске, `amend-tests`
        прошёл.

        Деталь единственной записи «правка планки» содержит
        `acceptance_tests/README.md`.

        Ловит мутацию: удалённые пути не добавлены в деталь записи
        журнала — удаление происходит молча, путь в записи не назван.
        """
        self.assert_journal_names_removed()


class LongLivedModeJournalTest(_JournalScenario, LongLivedLockedSandbox):

    def test_ac4_long_lived_mode_journal_names_removed_path(self):
        """Задача с перечнем: README.md удалён на диске, `amend-tests`
        прошёл в режиме `_amend_with_long_lived`.

        Деталь единственной записи «правка планки» содержит
        `acceptance_tests/README.md`.

        Ловит мутацию: перечень удалённых путей добавлен в журнал только
        режима без перечня — запись режима с перечнем путь не называет.
        """
        self.assert_journal_names_removed()


if __name__ == "__main__":
    unittest.main()
