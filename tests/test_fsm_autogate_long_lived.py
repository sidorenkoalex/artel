"""Пометки и ошибки долгоживущей планки в записи приёмки."""
import unittest
from unittest import mock

from orchestrator import artifact_source, fsm_autogate, gitcmd, store
from orchestrator.advance_gates import acceptance as acceptance_gates


class LongLivedChecklistTest(unittest.TestCase):
    TASK = "T001"
    ARTIFACT_BRANCH = "artifact/T001"
    CODE_BRANCH = "task/t001-x"
    PATH = "tests/test_t001_plank.py"

    def detail(self, source: str | None) -> str:
        task = {"branch": self.CODE_BRANCH, "tests_locked_sha": "a" * 40,
                "budget_usd": 5.0}

        def show(branch, path, repo=None):
            self.assertEqual((branch, path), (self.CODE_BRANCH, self.PATH))
            return (source, "") if source is not None else (None, "нет файла")

        with mock.patch.object(artifact_source, "resolve",
                               return_value=(self.ARTIFACT_BRANCH, True)), \
             mock.patch.object(gitcmd, "branch_head_sha",
                               return_value="b" * 40), \
             mock.patch.object(gitcmd, "ls_tree_files", return_value=[]), \
             mock.patch.object(gitcmd, "show", side_effect=show), \
             mock.patch.object(store, "task_target", return_value="artel"), \
             mock.patch.object(acceptance_gates, "long_lived_manifest",
                               return_value=({self.PATH: "c" * 64}, "")), \
             mock.patch.object(gitcmd, "git",
                               return_value=mock.Mock(returncode=0, stdout="")):
            return fsm_autogate._acceptance_checklist_detail(
                object(), self.TASK, task, 1)

    def test_skip_and_escalate_from_code_branch_are_listed(self):
        """Ловит мутацию: тексты файлов перечня перестали входить в
        сканирование пометок — запись скрывает оба оставшихся критерия.
        """
        detail = self.detail(
            "# AC-4: skip — нет контура.\n"
            "# AC-5: escalate — нужен ответ.\n"
            "# AC-6: ci — статус ветки.\n")

        self.assertIn("AC-4: skip", detail)
        self.assertIn("AC-5: escalate", detail)
        self.assertNotIn("AC-6: ci", detail)

    def test_unreadable_code_branch_file_is_named_in_checklist(self):
        """Ловит мутацию: непрочитанный файл перечня молча пропущен —
        запись ошибочно обещает автоматический проход без его пометок.
        """
        detail = self.detail(None)

        self.assertIn(self.PATH, detail)
        self.assertIn("не прочитан", detail)
        self.assertNotIn("автогейт пройдёт сам", detail)
