"""Юнит-тесты условия «а» `fsm_autogate._autogate_conditions` — чтение
планки `acceptance_tests/` и её AC-пометок через источник артефактов
задачи, не с диска рабочей копии (SPEC 01M1NBWWPJMHKJMYXRDCM0W0C5).

Приёмочные тесты задачи (`tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/`,
`AutogateBranchSandbox`) уже покрывают сценарий целиком через настоящий
git. Эти тесты дополняют их на уровне юнита самой функции — чистые моки
`artifact_source.resolve`/`gitcmd.*`, без реального репозитория — для
углов, которые приёмочные тесты не бьют напрямую: разбор ВСЕХ `*.py`
каталога (не только `test_*.py`, расхождение с дисковым
`guard.scan_acceptance_tests`, прецедент `fsm._tests_writing_ac_state`),
вырожденный ответ `gitcmd.ls_tree_files` (`None` — git не ответил) и
точный текст пометки источника (ветка+sha).
"""
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, artifact_source, budget, fsm_autogate, gitcmd, workspace
from scripts import guard

BRANCH = "artifact/T001"
SHA = "a" * 40


class _AutogateConditionsUnitTest(unittest.TestCase):
    """Условия б/в/г/д заглушены на «выполнено» — тем же приёмом, что
    `AutogateBranchSandbox.conditions` приёмочных тестов задачи; предмет
    этих тестов — только условие «а»."""

    TASK = "T001"

    def call(self, *, ls_tree_files=None, show_map=None, acc_tdir=None,
             iteration=1):
        acc_tdir = acc_tdir if acc_tdir is not None else Path("/no/such/dir")
        show_map = show_map or {}
        t = {"branch": "task/t001-x", "spent_usd": 0.0, "budget_usd": 5.0}

        def fake_show(branch, rel):
            self.assertEqual(branch, BRANCH)
            return (show_map[rel], "") if rel in show_map else (None, "нет файла")

        with mock.patch.object(artifact_source, "resolve",
                               return_value=(BRANCH, True)), \
             mock.patch.object(gitcmd, "branch_head_sha", return_value=SHA), \
             mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=ls_tree_files), \
             mock.patch.object(gitcmd, "show", side_effect=fake_show), \
             mock.patch.object(workspace, "on_task_branch",
                               return_value=True), \
             mock.patch.object(workspace, "path",
                               return_value=Path("/wt")), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, "")), \
             mock.patch.object(budget, "budget_block", return_value=None):
            return fsm_autogate._autogate_conditions(object(), self.TASK, t,
                                                      acc_tdir, iteration)


class AllPyFilesScannedTest(_AutogateConditionsUnitTest):

    def test_manual_marker_in_non_test_prefixed_file_is_seen(self):
        """`guard.scan_ac_content` (ветко-корректное чтение) разбирает
        ВСЕ `*.py` каталога, не только `test_*.py` — тот же приём, что
        `fsm._tests_writing_ac_state` (SPEC T031), сознательно
        расходящийся с дисковым `guard.scan_acceptance_tests`.

        Ловит мутацию: фильтр на `Path(p).name.startswith("test_")`
        перед сбором `sources` пропустил бы этот файл — manual-маркер
        остался бы невидим, условие «а» прошло бы автогейтом вместо
        отказа.
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/helper.py"
        content = (
            '"""Не test_*, обычный помощник планки."""\n'
            "# AC-3: manual — маркер юнит-теста в файле без префикса test_.\n"
        )

        ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertEqual(reason, "автогейт: критерии manual — AC-3 "
                         f"(источник планки: ветка {BRANCH}, sha {SHA})")


class MissingLsTreeAnswerTest(_AutogateConditionsUnitTest):

    def test_git_not_answering_ls_tree_is_treated_as_empty_planka(self):
        """`gitcmd.ls_tree_files` возвращает `None` (git не ответил на
        сам запрос дерева, не «каталога нет») — условие «а» отказывает
        тем же fail-closed приёмом, что и для действительно пустого
        каталога, не проходит автогейтом молча.

        Ловит мутацию: код, различающий `None` и `[]` через `is None`
        без общего `or []`/эквивалента, уронил бы саму функцию
        `TypeError` на последующей итерации по `None`, а не вернул бы
        причину отказа.
        """
        ok, reason = self.call(ls_tree_files=None)

        self.assertEqual(
            reason,
            "автогейт: каталог приёмочных тестов пуст или отсутствует "
            f"(источник планки: ветка {BRANCH}, sha {SHA})")


class NonPyFilesIgnoredTest(_AutogateConditionsUnitTest):

    def test_directory_with_only_non_py_files_is_treated_as_empty(self):
        """Каталог в дереве ветки существует, но несёт только не-`.py`
        файл — тот же отказ, что и для полностью отсутствующего
        каталога (фильтр на `.py`, не голое «список путей непуст»).

        Ловит мутацию: код, убравший фильтр `p.endswith(".py")` перед
        `py_paths` (голая проверка «список путей из дерева непуст»),
        принял бы README.md за непустую планку — `sources` остался бы
        пуст (`gitcmd.show` для него не замокан), markers пуст, и
        условие «а» прошло бы автогейтом вместо ожидаемого отказа
        «каталог приёмочных тестов пуст или отсутствует».
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/README.md"

        ok, reason = self.call(ls_tree_files=[rel], show_map={})

        self.assertIn("автогейт: каталог приёмочных тестов пуст или "
                      "отсутствует", reason)


class SourceNoteOnPassTest(_AutogateConditionsUnitTest):

    def test_ok_list_names_branch_and_sha_on_clean_planka(self):
        """Условие «а» пройдено (чистая планка) — перечень `ok` несёт
        точную пометку источника (ветка + полный sha), которую
        `_maybe_autogate_acceptance` кладёт в `detail` перехода
        `acceptance -> merge_gate` (SPEC AC-6).

        Ловит мутацию: код, забывший `ok.append(source_note)` на пути
        пройденного условия «а» (называть источник — не только на
        отказе, но и на успехе, того требует SPEC AC-6), — тест уронил
        бы `assertIn`; тесты на путях отказа (`reason`) такой пропуск
        не поймали бы, поэтому нужен отдельный тест именно ветки успеха.
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/test_marker.py"
        content = (
            '"""Чистая планка юнит-теста."""\n'
            "import unittest\n\n\n"
            "class MarkerTest(unittest.TestCase):\n"
            "    def test_ac1_marker(self):\n"
            "        self.assertTrue(True)\n"
        )

        ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertIsNone(reason)
        self.assertIn(f"источник планки: ветка {BRANCH}, sha {SHA}", ok)


class DiskAccTdirIgnoredForConditionATest(_AutogateConditionsUnitTest):

    def test_disk_scan_helper_is_never_called(self):
        """Условие «а» не читает диск рабочей копии вовсе — старое ядро
        `guard.scan_acceptance_tests` (принимает `Path`, читает диск) не
        имеет права быть вызванным реализацией.

        Ловит мутацию: частичный откат правки (например, оставленный по
        ошибке вызов дискового пути как запасного варианта) — мок
        роняет тест немедленно вместо того, чтобы молча совпасть по
        результату, как совпал бы AC-1 приёмочный тест только по
        отсутствию manual-маркера.
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/test_marker.py"
        content = (
            '"""Чистая планка юнит-теста."""\n'
            "import unittest\n\n\n"
            "class MarkerTest(unittest.TestCase):\n"
            "    def test_ac1_marker(self):\n"
            "        self.assertTrue(True)\n"
        )

        with mock.patch.object(
                guard, "scan_acceptance_tests",
                side_effect=AssertionError(
                    "condition A must not touch the disk-based scan")):
            ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
