"""Юнит-тесты переноса удаления файла планки командой `amend-tests`
(tasks/01M3XWR7140Q8C1XAFPZ9E854M/SPEC.md, требования 1-6).

Случай 101965d0: Оператор удалил в worktree `acceptance_tests/README.md`,
`amend-tests` сдвинул `tests_locked_sha` на коммит без единого изменения,
README остался в артефактной ветке. Здесь — оба режима worktree-пути (без
перечня долгоживущих файлов и с ним): удаление доходит до ветки, перечень
не удаляется, пустой коммит правки отклоняется, удаление `test_*.py`
проходит трассируемость, журнал называет удалённые пути.

Песочницы — настоящий git: предмет проверки — дерево коммита правки, его
родитель и сдвиг лока. Режим без перечня — рецепт `tests/test_amend.py`
(`SPEC_V2`/`AC_TEST_BOTH_COVERED` из `tests/test_acceptance_tests_flow.py`),
режим с перечнем — `tests/test_amend_long_lived.py::_LockedSandbox`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (amend, artifact_branch, catalog, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import (  # noqa: E402
    AC_TEST_BOTH_COVERED, SPEC_V2)
from tests.test_amend_long_lived import _LockedSandbox  # noqa: E402
from tests.test_long_lived_transitions import capture_call  # noqa: E402

README = "README.md"
README_TEXT = "Пояснение к планке — без заголовочного блока.\n"

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
    """Запись коммита, не применяющая удалений: коммит правки, в которой
    кроме удаления ничего нет, получает дерево родителя."""
    real = artifact_branch.write_commit

    def no_remove(repo, files, *args, **kwargs):
        kwargs.pop("remove", None)
        return real(repo, files, *args, **kwargs)

    return mock.patch.object(artifact_branch, "write_commit", no_remove)


class _RemovalMixin:
    """README в лок, планка на диск worktree, снимки лока и журнала.
    Подкласс задаёт `self.TASK` и `self.wt_root`."""

    def prefix(self) -> str:
        return f"tasks/{self.TASK}/acceptance_tests/"

    def put_readme_into_lock(self) -> None:
        sha = artifact_branch.commit_files(
            self.TASK, {self.prefix() + README: README_TEXT},
            f"{self.TASK}: README планки")
        self.assertTrue(sha, "README в артефактную ветку не закоммичен")
        store.update_task(store.db(), self.TASK, tests_locked_sha=sha)

    def plank_to_disk(self) -> None:
        for rel, text in artifact_branch.read_tree(self.TASK).items():
            if rel.startswith(self.prefix()):
                dest = self.wt_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")

    def delete_on_disk(self, name: str) -> None:
        (self.wt_root / (self.prefix() + name)).unlink()

    def locked(self) -> str:
        return store.get_task(store.db(), self.TASK)["tests_locked_sha"]

    def docs_head(self) -> str:
        return gitcmd.branch_head_sha(artifact_branch.branch_name(self.TASK))

    def names_at(self, rev: str) -> set[str]:
        prefix = self.prefix()
        return {p[len(prefix):]
                for p in gitcmd.ls_tree_files(rev, prefix.rstrip("/")) or []}

    def amend_details(self) -> list[str]:
        return [s["detail"] or "" for s in store.task_steps(store.db(), self.TASK)
                if s["action"] == amend.AMEND_ACTION]

    def run_amend(self) -> str:
        return capture_call(amend.cmd_amend_tests, self.TASK, "удалён README")


class _PlainSandbox(_RemovalMixin, RealGitSandbox):
    """Задача без перечня долгоживущих файлов, залоченная настоящим
    выходом из `tests_writing`; затем в лок доложен README."""

    PLANK = {"test_ac.py": AC_TEST_BOTH_COVERED}

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "удаление планки")
        self.docs_commit({f"tasks/{self.TASK}/SPEC.md":
                          SPEC_V2.format(task=self.TASK, extra="")}, "SPEC")
        capture(fsm.cmd_advance, self.TASK)
        capture(fsm.cmd_approve, self.TASK,
                artifact_branch.ref_head(self.TASK))
        self.docs_commit({self.prefix() + name: text
                          for name, text in self.PLANK.items()}, "планка")
        capture(fsm.cmd_advance, self.TASK)
        row = store.get_task(store.db(), self.TASK)
        self.assertEqual(row["state"], "in_dev", "предпосылка: лок не взят")
        manifest, _reason = acceptance_gates.long_lived_manifest(
            self.TASK, row, store.task_target(store.db(), self.TASK))
        self.assertFalse(manifest, "предпосылка: у задачи есть перечень")
        self.put_readme_into_lock()
        self.wt_root, error = workspace.ensure(self.TASK, row["branch"])
        self.assertIsNone(error)
        self.plank_to_disk()

    def docs_commit(self, files: dict, message: str) -> None:
        self.assertTrue(artifact_branch.commit_files(
            self.TASK, files, f"{self.TASK}: {message}"))


class _LongLivedSandbox(_RemovalMixin, _LockedSandbox):
    """Задача с непустым перечнем лока; затем в лок доложен README."""

    def setUp(self):
        super().setUp()
        self.wt_root = self.wt
        self.manifest_name = acceptance_gates.long_lived_manifest_rel(
            self.TASK).rsplit("/", 1)[-1]
        self.assertIn(self.manifest_name, self.names_at(self.locked()),
                      "предпосылка: перечня в дереве лока нет")
        self.put_readme_into_lock()
        self.plank_to_disk()


class _Scenarios:
    """Сценарии, общие обоим режимам."""

    def assert_removal_carried(self) -> str:
        before = self.locked()
        self.delete_on_disk(README)

        out = self.run_amend()

        self.assertNotIn("SystemExit", out, out)
        lock = self.locked()
        self.assertNotEqual(lock, before, out)
        self.assertEqual(lock, self.docs_head())
        self.assertNotIn(README, self.names_at(lock), out)
        return lock

    def assert_empty_commit_refused(self) -> None:
        before_lock, before_head = self.locked(), self.docs_head()
        self.delete_on_disk(README)

        with write_commit_ignoring_remove():
            out = self.run_amend()

        self.assertIn("SystemExit", out, f"пустой коммит принят: {out}")
        self.assertIn("пустой коммит правки", out)
        self.assertEqual(self.locked(), before_lock, out)
        self.assertEqual(self.docs_head(), before_head,
                         "пустой коммит остался головой артефактной ветки")
        self.assertEqual(self.amend_details(), [])

    def assert_journal_names_removed(self) -> None:
        self.delete_on_disk(README)

        out = self.run_amend()

        self.assertNotIn("SystemExit", out, out)
        details = self.amend_details()
        self.assertEqual(len(details), 1, details)
        self.assertIn(f"удалены: acceptance_tests/{README}", details[0])


class PlainModeRemovalTest(_Scenarios, _PlainSandbox):

    def test_removal_reaches_artifact_branch(self):
        """Задача без перечня: README удалён на диске worktree — после
        `amend-tests` лок указывает на голову артефактной ветки, в её
        дереве README нет, `test_ac.py` на месте.

        Ловит мутацию: `remove` не передан в `artifact_branch.commit_files`
        — файл остаётся, коммит пустой (README в дереве нового лока).
        """
        lock = self.assert_removal_carried()
        self.assertIn("test_ac.py", self.names_at(lock))

    def test_empty_commit_refused(self):
        """Задача без перечня: запись коммита подменена так, что удаление
        не применилось, — дерево коммита правки равно дереву родителя.
        Именованный отказ, лок и голова артефактной ветки прежние, записи
        «правка планки» нет.

        Ловит мутацию: проверка пустого коммита убрана — повтор случая
        101965d0 (лок сдвинут на коммит без изменений, «правка планки» в
        журнале); либо ветка не возвращена на родителя — пустой коммит
        остаётся её головой.
        """
        self.assert_empty_commit_refused()

    def test_journal_names_removed_path(self):
        """Задача без перечня: деталь записи «правка планки» после удаления
        называет `acceptance_tests/README.md`.

        Ловит мутацию: удалённые пути не добавлены в деталь записи
        журнала — удаление происходит молча.
        """
        self.assert_journal_names_removed()


class RemovedSoleTestTraceabilityTest(_PlainSandbox):

    PLANK = {"test_ac1_only.py": ONLY_AC1, "test_ac2_only.py": ONLY_AC2}

    def test_removed_sole_test_refused_by_traceability(self):
        """Лок несёт два файла планки, AC-2 песочницы покрыт только
        `test_ac2_only.py`; он удалён на диске worktree — отказ по
        трассируемости, называющий AC-2, лок прежний, записи «правка
        планки» нет.

        Ловит мутацию: удалённые файлы исключены из проверок —
        трассируемость считается по планке артефактной ветки, и лок
        сдвигается на планку без покрытия AC-2.
        """
        before = self.locked()
        self.delete_on_disk("test_ac2_only.py")

        out = self.run_amend()

        self.assertIn("SystemExit", out, out)
        self.assertIn("трассируемость", out)
        self.assertIn("AC-2", out)
        self.assertEqual(self.locked(), before)
        self.assertEqual(self.amend_details(), [])


class LongLivedModeRemovalTest(_Scenarios, _LongLivedSandbox):

    def test_removal_reaches_artifact_branch_keeping_manifest(self):
        """Задача с перечнем: README удалён на диске — после `amend-tests`
        в дереве нового лока README нет, а `long_lived.sha256.txt` есть.

        Ловит мутацию: удаление перенесено только в одном из двух режимов
        (`_amend_with_long_lived` коммитит без `remove`) — README в дереве
        нового лока.
        """
        lock = self.assert_removal_carried()
        self.assertIn(self.manifest_name, self.names_at(lock))

    def test_manifest_absent_on_disk_is_not_removed(self):
        """Задача с перечнем: на диске нет ни README, ни перечня — README
        уходит из лока, перечень в дереве нового лока остаётся.

        Ловит мутацию: файл перечня не исключён из удаляемых путей —
        его отсутствие на диске удаляет перечень из артефактной ветки.
        """
        self.delete_on_disk(self.manifest_name)
        lock = self.assert_removal_carried()
        self.assertIn(self.manifest_name, self.names_at(lock))

    def test_empty_commit_refused(self):
        """Задача с перечнем: перечень пересчитан в те же байты, удаление
        не применилось — дерево коммита равно дереву родителя. Именованный
        отказ, лок и голова артефактной ветки прежние, записи «правка
        планки» нет.

        Ловит мутацию: проверка пустого коммита есть только в режиме без
        перечня — режим с перечнем сдвигает лок на коммит без изменений.
        """
        self.assert_empty_commit_refused()

    def test_journal_names_removed_path(self):
        """Задача с перечнем: деталь записи «правка планки» после удаления
        называет `acceptance_tests/README.md`.

        Ловит мутацию: удалённые пути добавлены в журнал только режима без
        перечня — запись режима с перечнем путь не называет.
        """
        self.assert_journal_names_removed()


if __name__ == "__main__":
    unittest.main()
