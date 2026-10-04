"""AC-6: `apply_check(diff, reverse=False)` — применимость к дереву HEAD.

Применимый к HEAD дифф — пустая строка, неприменимый — непустой ответ git,
`reverse=True` для диффа, уже наложенного в HEAD, — пустая строка; ни
прямой, ни обратный вызов не меняют файлы рабочей копии и индекс.

Группа: разовый
Красен до реализации: выкладка не кладёт `_pult.py` — `apply_check` помощника нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import PlankHelperSandbox  # noqa: E402

TASK_FILE = "feature/task_change.py"

# Применим к HEAD (`marker.txt` = "main"), но не к рабочему дереву, где
# `marker.txt` правлен и не закоммичен.
APPLICABLE_TO_HEAD = """diff --git a/marker.txt b/marker.txt
--- a/marker.txt
+++ b/marker.txt
@@ -1 +1 @@
-main
+main, правка приложения
"""

INAPPLICABLE = """diff --git a/marker.txt b/marker.txt
--- a/marker.txt
+++ b/marker.txt
@@ -1 +1 @@
-строки, которой в дереве нет
+правка приложения
"""

DIRTY_MARKER = "грязная правка рабочей копии\n"


class ApplyCheckTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.commit_code(TASK_FILE, "TASK_CHANGE = 1\n")
        # Дифф, уже наложенный в HEAD: коммит правки задачи.
        self.applied = self.wt_git("diff", "HEAD~1", "HEAD")
        self.assertIn(TASK_FILE, self.applied)
        (self.wt / "marker.txt").write_text(DIRTY_MARKER, encoding="utf-8")
        self.helper = self.materialize()

    def snapshot(self) -> tuple:
        """Состояние рабочей копии и индекса: статус, записи индекса,
        застейдженный дифф и содержимое затронутых файлов."""
        return (self.wt_git("status", "--porcelain=v1", "--untracked-files=all"),
                self.wt_git("ls-files", "-s"),
                self.wt_git("diff", "--cached"),
                (self.wt / "marker.txt").read_text(encoding="utf-8"),
                (self.wt / TASK_FILE).read_text(encoding="utf-8"))

    def test_ac6_applicable_to_head_is_empty_string(self):
        """Дифф, применимый к HEAD, — пустая строка, даже при грязном дереве.

        Сценарий: `marker.txt` в HEAD = "main", в рабочем дереве правлен и
        не закоммичен; дифф `main` -> правка приложения применим к HEAD —
        `apply_check` отдаёт `""`.

        Ловит мутацию: проверка идёт `git apply --check` по рабочему
        дереву, а не по дереву HEAD — git отказывает на грязном
        `marker.txt`, ответ непустой."""
        self.assertEqual(self.helper.apply_check(APPLICABLE_TO_HEAD), "")

    def test_ac6_inapplicable_returns_git_answer(self):
        """Неприменимый дифф — непустой ответ git.

        Сценарий: дифф ждёт в `marker.txt` строку, которой нет ни в HEAD,
        ни в рабочем дереве; `apply_check` отдаёт непустую строку.

        Ловит мутацию: ответ строится по stdout git (пустому при отказе
        `--check`) либо код возврата не проверяется — на отказе git
        помощник отдаёт `""`, как на согласии."""
        answer = self.helper.apply_check(INAPPLICABLE)

        self.assertIsInstance(answer, str)
        self.assertNotEqual(answer.strip(), "")

    def test_ac6_reverse_for_diff_already_in_head_is_empty_string(self):
        """`reverse=True` для диффа, уже наложенного в HEAD, — пустая строка.

        Сценарий: дифф коммита правки задачи (`HEAD~1..HEAD`) уже в HEAD;
        `apply_check(diff, reverse=True)` отдаёт `""`.

        Ловит мутацию: `reverse` не передаётся git (`--reverse` потерян) —
        обратная проверка отвечает как прямая, отказом «already exists»."""
        self.assertEqual(self.helper.apply_check(self.applied, reverse=True), "")

    def test_ac6_calls_leave_worktree_and_index_intact(self):
        """Прямой и обратный вызовы не меняют рабочую копию и индекс.

        Сценарий: снимок статуса, записей индекса, застейдженного диффа и
        содержимого `marker.txt`/файла задачи до вызовов совпадает со
        снимком после применимой, неприменимой и обратной проверок.

        Ловит мутацию: проверка накладывает дифф по-настоящему в рабочую
        копию (`git apply` без `--check`) или через `--index`/`--cached`
        общего индекса — меняется `marker.txt` либо индекс."""
        before = self.snapshot()

        self.helper.apply_check(APPLICABLE_TO_HEAD)
        self.helper.apply_check(INAPPLICABLE)
        self.helper.apply_check(self.applied, reverse=True)

        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
