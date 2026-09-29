"""Юнит-тесты `amend-tests` для долгоживущих файлов задачи в `tests/`
(SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV, требования 1-2; ADR-0020, задача 3) —
свойства, которых не касается планка задачи: допуск красной планки рядом
с зелёным долгоживущим файлом, отказ при непрочитанном перечне лока,
перечень в обход команды без иной правки, незакоммиченная правка worktree
при `--from-branch`.

Песочница — `_TransitionSandbox` задачи 2 (настоящий git: пульт с веткой
документов, bare `origin`, worktree кодовой ветки); задача залочена
настоящим выходом из `tests_writing` с непустым перечнем.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import amend, artifact_branch, gitcmd, store  # noqa: E402
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_long_lived_transitions import (  # noqa: E402
    _TransitionSandbox, capture_call, long_lived_source)

RED_MARKED_PLANK = '''"""Фикстура разового файла планки, ещё без кода под собой.

Группа: разовый
Красен до реализации: фикстура песочницы — кода ещё нет.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_plank_fixture(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 3)
'''


class _LockedSandbox(_TransitionSandbox):

    def setUp(self):
        super().setUp()
        self.lock_with_own()
        self.docs_branch = artifact_branch.branch_name(self.TASK)
        self.plank_rel = f"tasks/{self.TASK}/acceptance_tests/test_ac1_plank.py"

    def heads(self) -> tuple:
        return (gitcmd.branch_head_sha(self.branch),
                gitcmd.branch_head_sha(self.docs_branch),
                self.row()["tests_locked_sha"])

    def amend_events(self) -> int:
        return sum(1 for s in store.task_steps(store.db(), self.TASK)
                   if amend.AMEND_ACTION in s["action"])

    def write_wt(self, rel: str, text: str) -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def amend(self, **kwargs) -> str:
        return capture_call(amend.cmd_amend_tests, self.TASK, "правка",
                            **kwargs)


class WorktreeModeTest(_LockedSandbox):

    def test_green_long_lived_next_to_red_marked_plank_passes(self):
        """Оператор правит долгоживущий файл (зелёный, без маркера
        красноты) и одновременно кладёт в планку файл «Красен до
        реализации», который падает: правка проходит, лок сдвинут.

        Ловит мутацию: маркер красноты требуется от каждого долгоживущего
        файла красного прогона, а не только от упавшего — зелёный
        долгоживущий файл без маркера отклоняет правку.
        """
        before = self.heads()
        self.write_wt(self.plank_rel, RED_MARKED_PLANK)
        self.write_wt(self.own, long_lived_source(tag="правка Оператора"))

        out = self.amend()

        self.assertNotIn("SystemExit", out)
        self.assertNotEqual(self.heads()[2], before[2], out)
        self.assertEqual(self.amend_events(), 1)

    def test_unreadable_manifest_refuses_long_lived_edit(self):
        """Перечень в дереве лока испорчен; Оператор правит долгоживущий
        файл — отказ, называющий непрочитанный перечень, без записей и без
        события правки планки.

        Ловит мутацию: ветка «перечень не прочитан» снята — непрочитанный
        перечень трактуется как «долгоживущих файлов нет», и отказ
        приходит как «изменения за пределами», не называя причину.
        """
        artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        "мусор\n"}, "испорченный перечень")
        self.set_row(tests_locked_sha=gitcmd.branch_head_sha(self.docs_branch))
        before = self.heads()
        self.write_wt(self.own, long_lived_source(tag="правка Оператора"))

        out = self.amend()

        self.assertIn("SystemExit", out)
        self.assertIn("перечень долгоживущих файлов лока не прочитан", out)
        self.assertEqual(self.heads(), before)
        self.assertEqual(self.amend_events(), 0)


class FromBranchModeTest(_LockedSandbox):

    def test_bypass_manifest_alone_is_no_divergence(self):
        """В ветку документов в обход команды закоммичен перечень с чужой
        суммой, а кодовая ветка и планка не менялись: `--from-branch` —
        отказ «нет расхождения», лок прежний, события правки нет.

        Ловит мутацию: файл перечня входит в сравнение планки лока и
        головы ветки документов — перечень в обход команды сам по себе
        засчитывается правкой, и лок сдвигается с событием правки планки.
        """
        artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        guard.render_long_lived_manifest({self.own: "0" * 64})},
            "перечень в обход команды")
        before = self.heads()

        out = self.amend(from_branch=True)

        self.assertIn("нет расхождения", out)
        self.assertEqual(self.heads(), before)
        self.assertEqual(self.amend_events(), 0)

    def test_dirty_worktree_long_lived_refused(self):
        """Кодовая ветка несёт закоммиченную годную правку долгоживущего
        файла, а в worktree поверх неё — ещё одна, незакоммиченная:
        `--from-branch` — отказ с путём файла, лок прежний.

        Ловит мутацию: проверка незакоммиченной правки снята — прогон
        `--from-branch` исполняет файл с диска worktree вместо головы
        кодовой ветки, и лок сдвигается по непроверенному содержимому.
        """
        self.wt_commit({self.own: long_lived_source(tag="годная правка")})
        self.write_wt(self.own, long_lived_source(tag="незакоммиченная правка"))
        before = self.heads()

        out = self.amend(from_branch=True)

        self.assertIn("SystemExit", out)
        self.assertIn(self.own, out)
        self.assertEqual(self.heads(), before)
        self.assertEqual(self.amend_events(), 0)


if __name__ == "__main__":
    unittest.main()
