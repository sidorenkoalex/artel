"""Юнит-тесты вспомогательных функций фильтра по зонам WIP-чекпоинтов
(`orchestrator/checkpoint.py::_zone_paths`/`_stray_staged_paths`, SPEC
01M290PVYG2VJK6442H5BAX9MA, AC-1) — изолированные случаи, которые
залоченная планка приёмки (tasks/01M290PVYG2VJK6442H5BAX9MA/
acceptance_tests/) не покрывает: пустой список зон задачи, ничего не
заявившей, и отказ git на самом `diff --cached --name-only`.

Песочница — `_WorktreeCheckpointTest` (tests/test_timeout_checkpoint.py,
импорт, не копия): `_zone_paths` читает `store.get_task`, `_stray_staged_
paths` — реальный `git diff --cached`, тем же доводом, что и соседние
классы того файла.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, gitcmd, store  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402


class IsExtraneousTaskRootFileTest(unittest.TestCase):
    """`checkpoint._is_extraneous_task_root_file` (SPEC
    01M290PVYG2VJK6442H5BAX9MA, AC-5): `RETRO.md` первого уровня —
    единственное исключение поверх `guard.is_extraneous_task_root_file`,
    сам список guard его не несёт (белый список планки — не зона этой
    задачи)."""

    def test_retro_md_is_never_extraneous(self):
        self.assertFalse(checkpoint._is_extraneous_task_root_file("RETRO.md"))

    def test_other_names_still_delegate_to_guard(self):
        """Ловит мутацию: исключение расширяется на ЛЮБОЙ `.md` первого
        уровня вместо буквально `RETRO.md` — посторонний `_draft.md`
        перестал бы отсекаться."""
        self.assertTrue(
            checkpoint._is_extraneous_task_root_file("_draft.md"))
        self.assertFalse(
            checkpoint._is_extraneous_task_root_file("SPEC.md"))


class ZonePathsTest(_WorktreeCheckpointTest):

    def test_no_declared_zone_yields_empty_list(self):
        """Задача, ни разу не заявившая зону (SPEC старой версии до
        `guard.requires_zones`, либо тестовая фикстура мимо гейта SPEC) —
        пустой список: фильтр `_stray_staged_paths` в этом случае не
        применяется вовсе (обратная совместимость с задачами без zones)."""
        self.enter_in_dev()
        self.assertEqual(checkpoint._zone_paths(store.db(), self.TASK), [])

    def test_declared_zone_combines_extension_common_zones_and_task_dir(self):
        self.enter_in_dev()
        conn = store.db()
        store.update_task(conn, self.TASK, zones="orchestrator/a.py",
                          zones_extension="docs/b.md")

        zones = checkpoint._zone_paths(conn, self.TASK)

        self.assertIn("orchestrator/a.py", zones)
        self.assertIn("docs/b.md", zones)
        self.assertIn("tests/", zones)  # config.COMMON_ZONES
        self.assertIn(f"tasks/{self.TASK}/", zones)


class StrayStagedPathsGitFailureTest(_WorktreeCheckpointTest):

    def test_git_diff_failure_degrades_to_none_not_empty_list(self):
        """Ловит мутацию: отказ `git diff --cached --name-only` трактуется
        как «посторонних нет» вместо «git не ответил» — WIP-чекпоинт
        закоммитил бы вслепую, не зная реального списка посторонних
        путей (тот же класс, что и остальные fail-closed проверки этого
        модуля на отказе git)."""
        self.enter_in_dev()
        conn = store.db()
        store.update_task(conn, self.TASK, zones="orchestrator/a.py")
        self.write_code_file("orchestrator/a.py", "# зона\n")
        self.worktree_git("add", "-A")

        real_git = gitcmd.git

        def side_effect(*args):
            if "diff" in args and "--name-only" in args:
                return subprocess.CompletedProcess(list(args), 2, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            result = checkpoint._stray_staged_paths(
                self.wt, checkpoint._zone_paths(conn, self.TASK))

        self.assertIsNone(result)

    def test_empty_zones_short_circuits_without_calling_git(self):
        """Пустой список зон (задача не заявляла) — `_stray_staged_paths`
        не обязан звать git вовсе (см. `_zone_paths`)."""
        self.enter_in_dev()

        def boom(*args, **kwargs):
            raise AssertionError("не обязан звать git без заявленных зон")

        with mock.patch.object(gitcmd, "git", boom):
            result = checkpoint._stray_staged_paths(self.wt, [])

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
