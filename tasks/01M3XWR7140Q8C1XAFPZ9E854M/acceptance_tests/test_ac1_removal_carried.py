"""AC-1 — удаление файла планки на диске worktree переносится в
артефактную ветку в обоих режимах `amend-tests`.

Группа: разовый
Красен до реализации: коммит правки не передаёт `remove` в `artifact_branch.commit_files` — README.md остаётся в дереве нового лока в обоих режимах.

Разовый: планка исполняется до мержа; после мержа это свойство держит
`tests/test_amend_remove.py` (SPEC, требование 6 и AC-5).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (README_NAME, LongLivedLockedSandbox,  # noqa: E402
                      PlainLockedSandbox, artifact_branch, gitcmd)


class PlainModeRemovalTest(PlainLockedSandbox):

    def test_ac1_plain_mode_removal_reaches_artifact_branch(self):
        """Задача без перечня: README.md удалён на диске worktree, вызван
        `amend-tests`.

        Команда проходит, `tests_locked_sha` сдвинут на голову
        артефактной ветки, в дереве этого коммита README.md нет, а
        `test_ac.py` на месте.

        Ловит мутацию: `remove` не передан — файл остаётся, коммит пустой
        (README.md в дереве нового лока).
        """
        before = self.locked()
        self.delete_on_disk(README_NAME)

        out = self.run_amend()

        self.assertNotIn("SystemExit", out, out)
        lock = self.locked()
        self.assertNotEqual(lock, before, out)
        self.assertEqual(
            lock, gitcmd.branch_head_sha(artifact_branch.branch_name(self.TASK)))
        names = self.plank_names_at(lock)
        self.assertNotIn(README_NAME, names, f"README.md остался в локе: {names}")
        self.assertIn("test_ac.py", names)


class LongLivedModeRemovalTest(LongLivedLockedSandbox):

    def test_ac1_long_lived_mode_removal_keeps_manifest(self):
        """Задача с перечнем долгоживущих файлов: README.md удалён на диске
        worktree, вызван `amend-tests`.

        Команда проходит, `tests_locked_sha` сдвинут на голову
        артефактной ветки, в дереве этого коммита README.md нет, а
        `long_lived.sha256.txt` остаётся.

        Ловит мутацию: удаление перенесено только в одном из двух режимов
        (`_amend_with_long_lived` по-прежнему коммитит без `remove`) —
        README.md в дереве нового лока; либо удаление задевает перечень —
        `long_lived.sha256.txt` пропадает из лока.
        """
        before = self.locked()
        self.delete_on_disk(README_NAME)

        out = self.run_amend()

        self.assertNotIn("SystemExit", out, out)
        lock = self.locked()
        self.assertNotEqual(lock, before, out)
        self.assertEqual(lock, gitcmd.branch_head_sha(self.docs_branch))
        names = self.plank_names_at(lock)
        self.assertNotIn(README_NAME, names, f"README.md остался в локе: {names}")
        self.assertIn(self.manifest_name, names,
                      f"перечень удалён из артефактной ветки: {names}")

    def test_ac1_manifest_absent_on_disk_is_not_removed(self):
        """Задача с перечнем: на диске нет ни README.md, ни
        `long_lived.sha256.txt`; вызван `amend-tests`.

        README.md уходит из лока, а перечень в дереве нового лока
        остаётся — его пишет только команда.

        Ловит мутацию: файл перечня не исключён из удаляемых путей —
        отсутствие перечня на диске worktree удаляет его из артефактной
        ветки (или команда вовсе пишет лок без перечня).
        """
        self.delete_on_disk(README_NAME)
        self.delete_on_disk(self.manifest_name)

        out = self.run_amend()

        self.assertNotIn("SystemExit", out, out)
        names = self.plank_names_at(self.locked())
        self.assertNotIn(README_NAME, names, f"README.md остался в локе: {names}")
        self.assertIn(self.manifest_name, names,
                      f"перечень удалён из артефактной ветки: {names}")


if __name__ == "__main__":
    unittest.main()
