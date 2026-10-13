"""Команда `reference <проект>`, вход справочника без задачи и сводка `target-init`: края разбора.

Свойства вне долгоживущих тестов задачи 01M4TVBT9ZCRQDY669QV3S95MA:
лишние аргументы команды отказывают до чтения `targets.yaml`, вход без
задачи и без sha — `absent` без алертов, `target-init` с неузнанным
коммитом базы печатает причину и не падает. Песочница — подмены функций
модулей и временный каталог; настоящий `targets.yaml` не читается.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import alerts, projects, reference_cache, repo_context, store, targets, workspace

SETTING = {"modules": ["lib/core.py"]}
ENTRY = {"forge": "github", "url": "file:///nonexistent/proj", "base": "main",
         "token_slot": "proj-token", "no_paths": [], "project_skills": [],
         "merge_gate": "operator", "core_reference": SETTING}


class ReferenceArgsTest(unittest.TestCase):

    def test_extra_arguments_refused_before_targets_read(self):
        """Нераспознанные аргументы и пропущенный проект — отказ с формой команды до `targets.target`.

        Ловит мутацию: разбор `reference` молча отбрасывает лишние
        аргументы (опечатка `--shaa` собирает справочник на базе вместо
        отказа) или читает `targets.yaml` до разбора argv.
        """
        cases = (["proj", "--shaa", "a" * 40], ["proj", "--sha"],
                 ["proj", "--sha", "a" * 40, "x"], [], ["--sha", "a" * 40])
        with mock.patch.object(targets, "target",
                               side_effect=AssertionError("targets прочитан")) as read:
            for argv in cases:
                with self.subTest(argv=argv):
                    with self.assertRaises(SystemExit) as refused:
                        projects.cmd_reference(argv)
                    self.assertIn("--sha <sha>", str(refused.exception.code))
        read.assert_not_called()


class TargetEntryWithoutTaskTest(unittest.TestCase):

    def test_no_task_no_sha_is_absent_without_alert(self):
        """Вход без задачи и без sha — `absent` с причиной и записью журнала без задачи, без алерта.

        Ловит мутацию: при `task_id=None` и `sha=None` вход ищет голову
        ветки по пустой задаче или поднимает алерт повода `reference`
        (источник по умолчанию `brief.core_reference`), либо запись «сбой»
        уходит без явного `target`.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        journal = []
        with mock.patch.object(repo_context, "projects_root", return_value=Path(tmp.name)), \
                mock.patch.object(targets, "core_reference", return_value=dict(SETTING)), \
                mock.patch.object(alerts, "raise_alert",
                                  side_effect=AssertionError("алерт поднят")) as raised, \
                mock.patch.object(store, "journal",
                                  side_effect=lambda *a, **kw: journal.append((a, kw))):
            result = reference_cache.get_reference_for_target(
                None, "proj", reason=reference_cache.REFERENCE_REASON, sha=None)
        self.assertEqual("absent", result.state)
        self.assertIn(reference_cache.HEAD_UNKNOWN, result.note)
        raised.assert_not_called()
        self.assertEqual(1, len(journal))
        args, kwargs = journal[0]
        self.assertIsNone(args[1])
        self.assertEqual(reference_cache.FAILED_ACTION, args[3])
        self.assertEqual("proj", kwargs.get("target"))


class TargetInitBaseUnknownTest(unittest.TestCase):

    def test_target_init_prints_reason_when_base_commit_unknown(self):
        """`target-init`: коммит базы в клоне не узнан — строка причины, без выхода и без сборки.

        Ловит мутацию: неузнанный коммит базы роняет `target-init`
        (`sys.exit`/исключение) либо сборка зовётся с `sha=None`.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clone = Path(tmp.name) / "repo"
        out = io.StringIO()
        with mock.patch.object(targets, "target", return_value=dict(ENTRY)), \
                mock.patch.object(projects, "init_project", return_value=[]), \
                mock.patch.object(workspace, "ensure_clone", return_value=(clone, None)), \
                mock.patch.object(store, "db_usable", return_value=True), \
                mock.patch.object(reference_cache, "get_reference_for_target",
                                  side_effect=AssertionError("сборка без sha")) as build, \
                contextlib.redirect_stdout(out):
            projects.cmd_target_init("proj")
        build.assert_not_called()
        self.assertIn("справочник ядра: не собран — коммит базы main не узнан",
                      out.getvalue())


if __name__ == "__main__":
    unittest.main()
