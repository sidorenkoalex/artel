"""AC-2 — коммит правки с деревом родителя: именованный отказ, лок не
сдвинут, записи журнала «правка планки» нет.

Группа: разовый
Красен до реализации: проверки «дерево коммита правки равно дереву родителя» ещё нет — команда сдвигает tests_locked_sha на пустой коммит и пишет «правка планки».

Разовый: планка исполняется до мержа; после мержа это свойство держит
`tests/test_amend_remove.py` (SPEC, требование 6 и AC-5).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (README_NAME, LongLivedLockedSandbox,  # noqa: E402
                      PlainLockedSandbox, write_commit_ignoring_remove)


class _EmptyCommitScenario:

    def assert_empty_commit_refused(self) -> None:
        before = self.locked()
        self.delete_on_disk(README_NAME)

        with write_commit_ignoring_remove():
            out = self.run_amend()

        self.assertIn("SystemExit", out, f"пустой коммит правки принят: {out}")
        message = out.split("SystemExit:", 1)[1].strip()
        self.assertTrue(message, "отказ без текста")
        self.assertEqual(self.locked(), before,
                         f"tests_locked_sha сдвинут на пустой коммит: {out}")
        self.assertEqual(self.amend_details(), [],
                         "запись «правка планки» при отказе")


class PlainModeEmptyCommitTest(_EmptyCommitScenario, PlainLockedSandbox):

    def test_ac2_plain_mode_empty_commit_refused(self):
        """Задача без перечня: README.md удалён на диске, запись коммита
        подменена так, что удаление не применилось, — дерево коммита
        правки равно дереву родителя.

        `amend-tests` завершается отказом с текстом, `tests_locked_sha`
        прежний, записи «правка планки» в журнале нет.

        Ловит мутацию: проверка пустого коммита убрана — повтор случая
        101965d0 (лок сдвинут на коммит без изменений, журнал пишет
        «правка планки»).
        """
        self.assert_empty_commit_refused()


class LongLivedModeEmptyCommitTest(_EmptyCommitScenario, LongLivedLockedSandbox):

    def test_ac2_long_lived_mode_empty_commit_refused(self):
        """Задача с перечнем: тот же сценарий в режиме
        `_amend_with_long_lived` — перечень пересчитан в те же байты,
        удаление не применилось, дерево коммита равно дереву родителя.

        Отказ с текстом, `tests_locked_sha` прежний, записи «правка
        планки» нет.

        Ловит мутацию: проверка пустого коммита добавлена только в режим
        без перечня — режим с перечнем сдвигает лок на коммит без
        изменений и пишет «правка планки».
        """
        self.assert_empty_commit_refused()


if __name__ == "__main__":
    unittest.main()
