"""Приёмочные тесты T083 — AC-1 (SPEC.md, «Критерии приёмки»):

Уборка временных git-песочниц с настоящим git (`TemporaryDirectory.
cleanup()`) устойчива к `OSError: [Errno 39] Directory not empty` при
удалении `.git` — правка в одном общем месте (`tests/sandbox.py`), не
дублируется по копиям тестовых файлов.

Красен до реализации: сегодня `tests.sandbox.TmpRootTest.setUp` регистрирует
голый `tmp.cleanup()` без какой-либо защиты, и минимум три файла
(`tests/test_git_fixation.py::RealPultGitTest`,
`tests/test_multitarget_invariants.py::PultArtifactIsolationTest`, и через
них — их дочерние сценарные классы) держат СВОИ независимые копии того же
`tempfile.TemporaryDirectory()` + `self.addCleanup(tmp.cleanup)`. Оба теста
ниже воспроизводят фактуру ран post-merge T038 напрямую: подменяют
`os.rmdir` так, чтобы ОДИН РАЗ на каждый реальный каталог `.git` вернуть
`OSError(39, "Directory not empty")` — ровно то исключение из инцидента —
и проверяют, что уборка тестового класса всё равно не падает. Подход
провалидирован: с голым `tmp.cleanup()` оба теста красны с тем же текстом
ошибки, что в инциденте; с временным стабом (ретрай/`ignore_errors` в
`setUp`, не закоммичен) — зелены.

Метод 1 бьёт по классам, названным в SPEC.md/«Контекст» напрямую
(`ExternalTransitionCommitsTest`, `ExternalApproveDoesNotCommitOthersWorkInProgressTest`
— оба идут через `tests.sandbox.TmpRootTest`, «общее место»). Метод 2 бьёт
по классам, которые СЕГОДНЯ это общее место не используют вовсе (свои
копии `tempfile.TemporaryDirectory()` в обход `tests/sandbox.py`) — это и
есть проверка требования «не дублируется по копиям»: если исправление
уйдёт только в `TmpRootTest.setUp` и не заберёт эти копии под общий
хелпер, метод 2 останется красным.
"""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def _flaky_rmdir_once_per_git_dir():
    """`os.rmdir`, который на КАЖДЫЙ уникальный каталог `.git` (различается
    по `dir_fd` родителя — так реально вызывает `shutil.rmtree` при
    удалении вложенной директории через файловый дескриптор) падает
    ровно один раз с `OSError(39, ...)`, а на повтор/прочие пути отвечает
    настоящим `os.rmdir`. Эмпирически проверено: `shutil.rmtree` на
    настоящем git-репо зовёт `os.rmdir(".git", dir_fd=<fd>)` — не
    абсолютным путём, поэтому матчим по basename, не по полному пути."""
    real_rmdir = os.rmdir
    failed_once = set()

    def flaky(path, *args, **kwargs):
        key = (str(path), kwargs.get("dir_fd"))
        if os.path.basename(str(path)) == ".git" and key not in failed_once:
            failed_once.add(key)
            raise OSError(39, "Directory not empty: '.git'")
        return real_rmdir(path, *args, **kwargs)

    return flaky


class NamedFlakyClassesCleanupSurvivesTest(unittest.TestCase):
    """AC-1, метод 1: классы из «Контекста» SPEC (ран post-merge T038,
    26.08) — через общее `tests.sandbox.TmpRootTest`."""

    def test_ac1_external_transition_and_approve_classes_survive_git_cleanup_flake(self):
        test_git_fixation = importlib.import_module("tests.test_git_fixation")

        loader = unittest.defaultTestLoader
        suite = unittest.TestSuite()
        for name in ("ExternalTransitionCommitsTest",
                     "ExternalApproveDoesNotCommitOthersWorkInProgressTest"):
            suite.addTests(loader.loadTestsFromTestCase(
                getattr(test_git_fixation, name)))

        result = unittest.TestResult()
        with mock.patch("os.rmdir", side_effect=_flaky_rmdir_once_per_git_dir()):
            suite.run(result)

        self.assertTrue(
            result.wasSuccessful(),
            "уборка временной git-песочницы не пережила "
            "OSError: [Errno 39] Directory not empty (AC-1): "
            f"errors={result.errors}\nfailures={result.failures}")


class StandaloneRealGitSandboxesCleanupSurvivesTest(unittest.TestCase):
    """AC-1, метод 2: классы, у которых СЕГОДНЯ нет `tests.sandbox.
    TmpRootTest` вовсе — своя копия `tempfile.TemporaryDirectory()`.
    Зелёный результат тут возможен только если правка добралась и до них
    (переиспользованием общего хелпера или эквивалентной защитой), а не
    осела исключительно в `TmpRootTest.setUp`."""

    def _probe_setup_and_teardown(self, base_cls):
        """Прогоняет ТОЛЬКО setUp/tearDown/addCleanup класса — тем же
        приёмом `_Probe`, что и `tasks/T037/acceptance_tests/test_sandbox.py`
        и `tasks/T061/acceptance_tests/test_tmproottest_adoption.py`: тело
        сценария не нужно, предмет проверки — уборка."""
        class _Probe(base_cls):
            def test_probe(self):
                pass

        case = _Probe("test_probe")
        result = unittest.TestResult()
        with mock.patch("os.rmdir", side_effect=_flaky_rmdir_once_per_git_dir()):
            case.run(result)
        return result

    def test_ac1_real_pult_git_test_survives_git_cleanup_flake(self):
        test_git_fixation = importlib.import_module("tests.test_git_fixation")
        result = self._probe_setup_and_teardown(test_git_fixation.RealPultGitTest)

        self.assertTrue(
            result.wasSuccessful(),
            "tests/test_git_fixation.py::RealPultGitTest держит свою "
            "копию tempfile.TemporaryDirectory() в обход tests/sandbox.py "
            f"и не пережила OSError 39 (AC-1): {result.errors}")

    def test_ac1_pult_artifact_isolation_test_survives_git_cleanup_flake(self):
        test_multitarget_invariants = importlib.import_module(
            "tests.test_multitarget_invariants")
        result = self._probe_setup_and_teardown(
            test_multitarget_invariants.PultArtifactIsolationTest)

        self.assertTrue(
            result.wasSuccessful(),
            "tests/test_multitarget_invariants.py::PultArtifactIsolationTest "
            "держит свою копию tempfile.TemporaryDirectory() в обход "
            f"tests/sandbox.py и не пережила OSError 39 (AC-1): {result.errors}")


if __name__ == "__main__":
    unittest.main()
