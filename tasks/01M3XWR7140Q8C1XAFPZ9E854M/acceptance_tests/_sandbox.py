"""Песочница планки задачи 01M3XWR7140Q8C1XAFPZ9E854M: вложенная задача
на НАСТОЯЩЕМ git, залоченная настоящим выходом из `tests_writing`, затем
в артефактную ветку докладывается `acceptance_tests/README.md` (без
заголовочного блока, как в случае 101965d0) и `tests_locked_sha` ставится
на голову ветки с ним — лок, в котором README есть.

Два режима `amend-tests` (SPEC, требование 1):

- `PlainLockedSandbox` — задача без перечня долгоживущих файлов; рецепт
  `tests/test_amend.py::AmendGroupLineRefusalTest` (SPEC_V2 песочницы с
  AC-1/AC-2, фикстуры `tests/test_acceptance_tests_flow.py`);
- `LongLivedLockedSandbox` — задача с непустым перечнем лока
  (`_amend_with_long_lived`); основа —
  `tests/test_amend_long_lived.py::_LockedSandbox` (лок с долгоживущим
  файлом `tests/test_<id>_alpha.py`, перечень в дереве лока).

Почему настоящий git: предмет критериев — дерево коммита правки в
артефактной ветке, его родитель и сдвиг `tests_locked_sha`; заглушка git
отвечала бы на это вымыслом.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (amend, artifact_branch, catalog, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import (  # noqa: E402
    AC_TEST_BOTH_COVERED, SPEC_V2)
from tests.test_amend_long_lived import _LockedSandbox  # noqa: E402
from tests.test_long_lived_transitions import capture_call  # noqa: E402

README_NAME = "README.md"
README_TEXT = "Пояснение к планке — без заголовочного блока.\n"

# Две половины покрытия SPEC_V2 песочницы — каждая в своём файле: удаление
# одного из них оставляет свой критерий без теста (AC-3).
ONLY_AC1 = '''"""Фикстура планки: покрывает только AC-1 песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixtureAc1Test(unittest.TestCase):

    def test_ac1_first_criterion(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''

ONLY_AC2 = '''"""Фикстура планки: покрывает только AC-2 песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixtureAc2Test(unittest.TestCase):

    def test_ac2_second_criterion(self):
        """Фикстурный метод."""
        self.assertEqual(2 + 2, 4)
'''


def write_commit_ignoring_remove():
    """Подмена записи коммита: удаления не применяются — коммит правки
    получает дерево родителя, если кроме удаления ничего не менялось
    (сценарий AC-2, повтор 101965d0)."""
    real = artifact_branch.write_commit

    def no_remove(repo, files, *args, **kwargs):
        kwargs.pop("remove", None)
        return real(repo, files, *args[:4], **kwargs)

    return mock.patch.object(artifact_branch, "write_commit", no_remove)


class _ReadmeLockMixin:
    """Общее обоим режимам: README в лок, планка на диск worktree, снимки
    лока и журнала. Подкласс задаёт `self.TASK`, `self.wt_root` и
    `lock_head()`."""

    def plank_prefix(self) -> str:
        return f"tasks/{self.TASK}/acceptance_tests/"

    def readme_rel(self) -> str:
        return self.plank_prefix() + README_NAME

    def put_readme_into_lock(self) -> None:
        sha = artifact_branch.commit_files(
            self.TASK, {self.readme_rel(): README_TEXT},
            f"{self.TASK}: README планки")
        assert sha, "README в артефактную ветку не закоммичен"
        store.update_task(store.db(), self.TASK, tests_locked_sha=sha)

    def materialize_plank_on_disk(self) -> None:
        for rel, text in artifact_branch.read_tree(self.TASK).items():
            if rel.startswith(self.plank_prefix()):
                dest = self.wt_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")

    def delete_on_disk(self, name: str) -> None:
        (self.wt_root / (self.plank_prefix() + name)).unlink()

    def locked(self) -> str:
        return store.get_task(store.db(), self.TASK)["tests_locked_sha"]

    def plank_names_at(self, rev: str) -> set[str]:
        prefix = self.plank_prefix()
        return {p[len(prefix):]
                for p in gitcmd.ls_tree_files(rev, prefix.rstrip("/")) or []}

    def amend_details(self) -> list[str]:
        return [s["detail"] or "" for s in store.task_steps(store.db(), self.TASK)
                if s["action"] == amend.AMEND_ACTION]

    def run_amend(self) -> str:
        return capture_call(amend.cmd_amend_tests, self.TASK,
                            "удалён README без заголовочного блока")


class PlainLockedSandbox(_ReadmeLockMixin, RealGitSandbox):
    """Задача без перечня долгоживущих файлов. `PLANK` — файлы планки на
    момент выхода из `tests_writing` (имя -> текст)."""

    PLANK = {"test_ac.py": AC_TEST_BOTH_COVERED}

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new,
                                           "amend-tests, удаление файла планки")
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK,
                                                          extra="")}, "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.artifact_commit(
            {self.plank_prefix() + name: text for name, text in self.PLANK.items()},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        row = store.get_task(store.db(), self.TASK)
        self.assertEqual(row["state"], "in_dev", "предпосылка: лок не взят")
        manifest, _reason = acceptance_gates.long_lived_manifest(
            self.TASK, row, store.task_target(store.db(), self.TASK))
        self.assertFalse(manifest, "предпосылка: у задачи нет перечня")
        self.put_readme_into_lock()
        self.wt_root, error = workspace.ensure(self.TASK, row["branch"])
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.materialize_plank_on_disk()

    def artifact_commit(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} не удался")
        return sha


class LongLivedLockedSandbox(_ReadmeLockMixin, _LockedSandbox):
    """Задача с непустым перечнем лока: `_LockedSandbox` уже залочил её с
    долгоживущим файлом и перечнем в дереве лока."""

    def setUp(self):
        super().setUp()
        self.wt_root = self.wt
        manifest_rel = acceptance_gates.long_lived_manifest_rel(self.TASK)
        self.manifest_name = manifest_rel.rsplit("/", 1)[-1]
        self.assertIn(self.manifest_name, self.plank_names_at(self.locked()),
                      "предпосылка: перечня в дереве лока нет")
        self.put_readme_into_lock()
        self.materialize_plank_on_disk()
