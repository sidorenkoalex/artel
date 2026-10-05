"""AC-5: база диффа помощника — `gitcmd.diff_base`, список — правило гейта зон.

Сценарий 13.09: `refs/remotes/origin/<main>` ушла вперёд локальной
основной ветки, ветка задачи подтянула `origin/<main>`. База в помощнике
равна `gitcmd.diff_base`, источник — `gitcmd.diff_base_source` той же
ветки; `changed_paths()` совпадает со списком гейта зон (закоммиченный
дифф от базы плюс неотслеживаемые файлы вне `tasks/<id>/`), `branch_diff()`
— закоммиченный дифф от той же базы до HEAD.

Изменённые, но не закоммиченные отслеживаемые файлы сценарий не заводит:
SPEC («Контекст») прямо исключает их из правила, а критерий сверяет
список с гейтом зон — их случай вне предмета сверки.

Группа: разовый
Красен до реализации: выкладка не кладёт `_pult.py` — базы, `changed_paths` и `branch_diff` помощника нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import (BRANCH, TASK, PlankHelperSandbox,  # noqa: E402
                       constant_values, git)

from orchestrator import config, gitcmd  # noqa: E402

TASK_FILE = "feature/task_change.py"
TASK_LINE = "TASK_CHANGE = 1"
MAIN_ONLY = "main_only.txt"
UNTRACKED = "scratch/notes.txt"


class OriginAheadOfLocalMainTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        main = config.MAIN_BRANCH
        # Чужая задача влита в origin/<main>; локальная <main> остаётся пином.
        self.checkout("upstream", create=True)
        (self.root / MAIN_ONLY).write_text("из origin/main\n", encoding="utf-8")
        self.git("add", MAIN_ONLY)
        self.git("commit", "-q", "-m", "чужая задача в origin/main")
        self.git("push", "-q", "origin", f"upstream:{main}")
        self.checkout(main)
        self.git("fetch", "-q", "origin")
        # Ветка задачи подтягивает origin/<main>, затем несёт свою правку.
        self.wt_git("merge", "-q", "--no-edit", f"origin/{main}")
        self.commit_code(TASK_FILE, f"{TASK_LINE}\n")
        self.write_untracked(UNTRACKED)
        local_base = git(self.root, "merge-base", main, BRANCH).strip()
        self.assertNotEqual(local_base, self.expected_base(),
                            "сценарий не воспроизводит origin впереди main")
        self.helper = self.materialize()

    def test_ac5_base_and_source_equal_gitcmd(self):
        """База и источник помощника — `gitcmd.diff_base`/`diff_base_source`.

        Сценарий: origin/<main> впереди локальной <main>; среди констант
        помощника — merge-base с `origin/<main>` и строка
        `origin/<main>`, а merge-base с локальной <main> среди них нет.

        Ловит мутацию: выкладка считает базу собственным `git merge-base
        <main> HEAD` от локальной ветки — подставлен sha пина, а не
        `gitcmd.diff_base`."""
        values = constant_values(self.helper)
        base = gitcmd.diff_base(BRANCH, repo=self.task_repo())
        source = gitcmd.diff_base_source(BRANCH, repo=self.task_repo())

        self.assertEqual(source, f"origin/{config.MAIN_BRANCH}")
        self.assertIn(base, values)
        self.assertIn(source, values)
        local_base = git(self.root, "merge-base", config.MAIN_BRANCH,
                         BRANCH).strip()
        self.assertNotIn(local_base, values)

    def test_ac5_changed_paths_equal_zones_gate_list(self):
        """`changed_paths()` — закоммиченный дифф от базы плюс неотслеживаемые.

        Сценарий: ожидаемый список строится по правилу гейта зон —
        `gitcmd.diff_names(база, ветка)` плюс неотслеживаемый
        `scratch/notes.txt`; выложенная планка (`tasks/<id>/…`,
        неотслеживаемая) в список не входит, `main_only.txt` из
        `origin/<main>` — тоже.

        Ловит мутацию: помощник берёт базу от локальной <main> (в списке
        появляется `main_only.txt`), не исключает `tasks/<id>/` (в списке
        файлы выложенной планки) или читает неотслеживаемые без
        `--untracked-files=all` (вместо `scratch/notes.txt` — `scratch/`)."""
        base = self.expected_base()
        committed = gitcmd.diff_names(base, BRANCH, repo=self.task_repo())
        self.assertIsNotNone(committed)
        expected = sorted(set(committed) | {UNTRACKED})

        paths = list(self.helper.changed_paths())

        self.assertEqual(sorted(paths), expected)
        self.assertNotIn(MAIN_ONLY, paths)
        self.assertFalse([p for p in paths if p.startswith(f"tasks/{TASK}/")])

    def test_ac5_branch_diff_is_committed_diff_from_same_base(self):
        """`branch_diff()` — закоммиченный дифф от той же базы до HEAD.

        Сценарий: дифф несёт файл и строку правки задачи, но не
        `main_only.txt` (он ниже базы) и не неотслеживаемый
        `scratch/notes.txt` (не закоммичен).

        Ловит мутацию: дифф считается от локальной <main> (в нём
        `main_only.txt`) или против рабочего дерева, а не HEAD (в нём
        файлы выложенной планки)."""
        diff = self.helper.branch_diff()

        self.assertIn(f"diff --git a/{TASK_FILE} b/{TASK_FILE}", diff)
        self.assertIn(f"+{TASK_LINE}", diff)
        self.assertNotIn(MAIN_ONLY, diff)
        self.assertNotIn(UNTRACKED, diff)
        self.assertNotIn(f"tasks/{TASK}/", diff)


if __name__ == "__main__":
    unittest.main()
