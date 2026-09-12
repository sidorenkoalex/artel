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


class TaskDirZoneTest(unittest.TestCase):
    """`checkpoint.task_dir_zone` (SPEC 01M2B6JNFD381MZT70CVB5NJQC,
    требование 1): единый источник строки «собственный каталог задачи»,
    которым пользуются и `_zone_paths` ниже, и довесок неотслеживаемых
    файлов `fsm_advance._zones_gate`."""

    def test_formats_task_dir_with_trailing_slash(self):
        """Ловит мутацию: trailing `/` потерян — зона перестала бы
        матчить вложенные пути через `_touches_zone`/`_paths_overlap`
        (обе сверяют директорию по префиксу с trailing `/`)."""
        self.assertEqual(checkpoint.task_dir_zone("01M2B6JNFD381MZT70CVB5NJQC"),
                         "tasks/01M2B6JNFD381MZT70CVB5NJQC/")


class ZonePathsTest(_WorktreeCheckpointTest):

    def test_task_dir_zone_element_comes_from_shared_helper(self):
        """Ловит мутацию: `_zone_paths` перестаёт звать `task_dir_zone` и
        собирает строку `tasks/<id>/` заново инлайном — расхождение с
        `fsm_advance._zones_gate`, использующим тот же `task_dir_zone`,
        осталось бы незамеченным этим тестом, не будь прямой сверки с
        возвратом самой функции."""
        self.enter_in_dev()
        conn = store.db()
        store.update_task(conn, self.TASK, zones="orchestrator/a.py")

        zones = checkpoint._zone_paths(conn, self.TASK)

        self.assertIn(checkpoint.task_dir_zone(self.TASK), zones)

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


class CommitSuccessCheckpointSummaryTest(_WorktreeCheckpointTest):
    """Регресс на R1-F1 (REVIEW.md 01M290PVYG2VJK6442H5BAX9MA, итерация 1,
    major): `_staged_change_summary` считала список файлов/строк ДО того,
    как `_commit_worktree_change` снимает посторонний путь со стейджа —
    `detail`/журнал «код закоммичен пультом за роль» называли его
    закоммиченным, хотя реальный коммит его не содержал (противоречило
    соседней записи `STRAY_WORKTREE_FILES_ACTION` о том же файле).
    `_commit_summary` считает сводку ПОСЛЕ коммита, по `git show
    --numstat` над готовым `sha` — расхождение исключено по построению."""

    def test_stray_file_outside_zones_is_not_listed_as_committed(self):
        self.enter_in_dev()
        conn = store.db()
        store.update_task(conn, self.TASK,
                          zones="orchestrator/allowed_module.py")
        self.write_code_file("orchestrator/allowed_module.py",
                             "строка 1\nстрока 2\nстрока 3\n")
        self.write_code_file("docs/stray_note.md", "посторонний\n")

        detail = checkpoint.commit_success_checkpoint(
            conn, self.TASK, "developer")

        self.assertIn("orchestrator/allowed_module.py", detail)
        self.assertNotIn(
            "stray_note.md", detail,
            "R1-F1: посторонний файл не должен значиться закоммиченным")
        committed = self.worktree_git(
            "show", "--name-only", "--format=", self.worktree_head())
        committed_paths = [p for p in committed.splitlines() if p]
        self.assertNotIn("docs/stray_note.md", committed_paths)
        self.assertIn("orchestrator/allowed_module.py", committed_paths)


class CommitSummaryTest(_WorktreeCheckpointTest):

    def test_lists_paths_and_total_line_count_of_the_given_commit(self):
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "строка 1\nстрока 2\nстрока 3\nстрока 4\n")
        self.worktree_git("add", "-A")
        self.worktree_git("commit", "-q", "-m", "тестовый коммит")

        summary = checkpoint._commit_summary(self.wt, self.worktree_head())

        self.assertIn("orchestrator/new_module.py", summary)
        self.assertIn("4", summary)

    def test_git_failure_degrades_to_empty_string(self):
        self.enter_in_dev()

        with mock.patch.object(gitcmd, "git",
                               return_value=subprocess.CompletedProcess(
                                   [], 1, "", "boom")):
            summary = checkpoint._commit_summary(self.wt, "deadbeef")

        self.assertEqual(summary, "")


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
