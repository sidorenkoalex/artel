"""Юнит-тесты засчитывания «нового модуля» гейтом честного FAIL_TO_PASS
(`orchestrator/advance_gates/tests_writing.py`, SPEC
01M5EDW6KD1ESCEVRSV2WPNXAP, требование 2 (а)): элемент `zones:`, который на
деле каталог, — записанный без завершающего `/` или существующий в базе
каталогом, — новым модулем не засчитывается (замечание ревью R1-F1).
"""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import project_profile
from orchestrator.advance_gates import tests_writing


def _vitest_case(spec: str):
    record = SimpleNamespace(
        detail=f'Failed to resolve import "{spec}" from "frontend/src/x/t.test.jsx"')
    cfile = SimpleNamespace(
        rel="frontend/src/x/t.test.jsx",
        profile=SimpleNamespace(report=project_profile.REPORT_VITEST))
    return record, cfile


class DirectoryZoneNotCountedTest(unittest.TestCase):

    def test_vitest_zone_without_extension_is_not_new_module(self):
        """Vitest: спецификатор каталога `../comp` при зоне `frontend/src/comp` (без `/`) — не P.

        Ловит мутацию: зона без расширения снова сравнивается с R
        спецификатора каталога — `_missing_import_path` вернёт
        `frontend/src/comp`, и каталог засчитается «новым модулем».
        """
        record, cfile = _vitest_case("../comp")
        self.assertIsNone(tests_writing._missing_import_path(
            record, cfile, ["frontend/src/comp"]))
        # Модуль-файл той же формы по-прежнему P (случай без расширения).
        self.assertEqual(
            tests_writing._missing_import_path(record, cfile,
                                               ["frontend/src/comp.jsx"]),
            "frontend/src/comp.jsx")

    def test_path_present_in_base_as_directory_is_not_absent(self):
        """P, оказавшийся в дереве базы каталогом (рекурсивный `ls-tree` перечисляет `P/a.js`), — не «отсутствует».

        Ловит мутацию: отсутствие считается как `path not in listed` —
        каталог базы `frontend/src/comp` объявлен отсутствующим (`True`).
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "frontend/src/comp").mkdir(parents=True)
            (repo / "frontend/src/comp/a.js").write_text("x\n", encoding="utf-8")
            for args in (("init", "-q"), ("add", "-A"),
                         ("-c", "user.name=t", "-c", "user.email=t@t",
                          "commit", "-q", "-m", "base")):
                subprocess.run(["git", "-C", tmp, *args], check=True,
                               capture_output=True)
            with mock.patch.object(tests_writing.store, "get_task",
                                   return_value={"branch": "task/none"}), \
                    mock.patch.object(tests_writing.workspace, "task_repo",
                                      return_value=repo), \
                    mock.patch.object(tests_writing.gitcmd, "branch_exists",
                                      return_value=False):
                self.assertFalse(tests_writing._absent_in_base(
                    None, "T", tmp, "frontend/src/comp"))
                self.assertTrue(tests_writing._absent_in_base(
                    None, "T", tmp, "frontend/src/comp.js"))


if __name__ == "__main__":
    unittest.main()
