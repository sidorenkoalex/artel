"""Юнит-тесты `orchestrator/appendix_tree.py` (SPEC 01M46C776SZEMYPBQGPNJN1TXY)
на свойства, которых нет в долгоживущих файлах задачи: перенос удалённого
и неотслеживаемого файла рабочей копии во временное дерево `suite-run` и
приложение, уже наложенное в дереве (подтянутый main его несёт); класс
отказа `suite_tree` (SPEC 01M4JD3SRN66SD6BM63XAGHB11): по содержимому PLAN
либо по сбою git.

Настоящий git во временном каталоге, без песочницы `config`: узел
подготовки дерева (`_prepared`) зовёт только git и файловую систему.
"""
import contextlib
import subprocess
from pathlib import Path
from unittest import mock

from orchestrator import appendix_tree
from scripts import guard
from tests.sandbox import TmpDirTest

BASE = "".join(f"строка {n}\n" for n in range(1, 11))


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


class GitTreeCase(TmpDirTest):
    """Рабочая копия `self.wt` на настоящем git и место временного дерева
    `self.tree`."""

    def setUp(self):
        super().setUp()
        self.wt = self.tdir / "wt"
        self.wt.mkdir()
        git(self.wt, "init", "-q", "-b", "main")
        git(self.wt, "config", "user.email", "t@example.invalid")
        git(self.wt, "config", "user.name", "t")
        for name in ("doc.md", "gone.txt", "kept.txt"):
            (self.wt / name).write_text(BASE, encoding="utf-8")
        git(self.wt, "add", "-A")
        git(self.wt, "commit", "-q", "-m", "база")
        self.tree = self.tdir / "holder" / "tree"
        self.tree.parent.mkdir()

    def appendix(self, old: str, new: str) -> guard.PlanAppendix:
        """Дифф правки `doc.md` настоящим `git diff`; рабочая копия затем
        возвращается к HEAD."""
        path = self.wt / "doc.md"
        path.write_text(path.read_text(encoding="utf-8").replace(old, new),
                        encoding="utf-8")
        diff = git(self.wt, "diff", "--", "doc.md")
        git(self.wt, "checkout", "-q", "--", "doc.md")
        return guard.PlanAppendix(("doc.md",), diff)


class PreparedTreeTest(GitTreeCase):

    def test_uncommitted_deletion_and_untracked_file_reach_the_tree(self):
        """Удалённый без коммита файл во временном дереве отсутствует,
        неотслеживаемый — есть, изменённый — с правкой; рабочая копия цела.

        Ловит мутацию: перенос берёт только `git diff --name-only` без
        `ls-files --others` — неотслеживаемого файла в дереве нет; удаление
        не переносится (`continue` до снятия файла в дереве) — удалённый
        файл остаётся и тест ветки видел бы его.
        """
        (self.wt / "gone.txt").unlink()
        (self.wt / "kept.txt").write_text("правка\n", encoding="utf-8")
        (self.wt / "new" / "fresh.txt").parent.mkdir()
        (self.wt / "new" / "fresh.txt").write_text("новый\n", encoding="utf-8")
        status = git(self.wt, "status", "--porcelain", "--untracked-files=all")

        note, refusal = appendix_tree._prepared(
            self.wt, None, [self.appendix("строка 3\n", "правка 3\n")],
            self.tree)

        self.assertEqual(refusal, "")
        self.assertIn(appendix_tree.WITH_APPENDICES, note)
        self.assertFalse((self.tree / "gone.txt").exists())
        self.assertEqual((self.tree / "kept.txt").read_text(encoding="utf-8"),
                         "правка\n")
        self.assertEqual((self.tree / "new" / "fresh.txt").read_text(
            encoding="utf-8"), "новый\n")
        self.assertIn("правка 3", (self.tree / "doc.md").read_text(
            encoding="utf-8"))
        self.assertEqual(git(self.wt, "status", "--porcelain",
                             "--untracked-files=all"), status)

    def test_appendix_already_in_tree_is_skipped_and_named(self):
        """Приложение, правка которого уже в дереве ветки, не отказ: оно
        пропускается и названо в признаке прогона номером.

        Ловит мутацию: `already_applied` не передан в `apply_in_order` —
        уже наложенное приложение не ложится повторно, и прогон ветки,
        подтянувшей main с этой правкой, отказывает «приложение 1 не
        накладывается».
        """
        first = self.appendix("строка 2\n", "правка 2\n")
        second = self.appendix("строка 7\n", "правка 7\n")
        (self.wt / "doc.md").write_text(BASE.replace("строка 2\n", "правка 2\n"),
                                        encoding="utf-8")
        git(self.wt, "commit", "-q", "-am", "main с приложением 1")

        note, refusal = appendix_tree._prepared(
            self.wt, "main", [first, second], self.tree)

        self.assertEqual(refusal, "")
        self.assertIn("уже в дереве: приложения 1", note)
        text = (self.tree / "doc.md").read_text(encoding="utf-8")
        self.assertIn("правка 2", text)
        self.assertIn("правка 7", text)


class SuiteTreeRefusalClassTest(GitTreeCase):
    """`suite_tree` на рабочей копии `self.wt` с подменённым разбором PLAN:
    контекст проекта и чтение PLAN — без пульта."""

    def suite_tree(self, appendices: list, branch: str | None):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for patcher in (
                mock.patch.object(appendix_tree.workspace, "task_target",
                                  lambda task_id: "artel"),
                mock.patch.object(appendix_tree.repo_context, "resolve",
                                  lambda target: object()),
                mock.patch.object(appendix_tree.repo_context, "is_artel",
                                  lambda ctx: True),
                mock.patch.object(appendix_tree.repo_context,
                                  "protected_paths", lambda ctx: ()),
                mock.patch.object(appendix_tree, "read_plan",
                                  lambda conn, task_id, protected:
                                  (appendices, [], ""))):
            stack.enter_context(patcher)
        return stack.enter_context(appendix_tree.suite_tree(
            None, "T1", self.wt, branch, not_run="планка не запускалась"))

    def test_inapplicable_appendix_is_role_fixable_and_names_what_did_not_run(self):
        """Неприменимое приложение — отказ по содержимому PLAN (`fixable`),
        с номером приложения и хвостом `not_run` вызывающего.

        Ловит мутацию: `fixable` не выставлен на отказе наложения — рубеж
        `in_dev -> verifying` пишет его действием сбоя гейта, и цикл `auto`
        не отдаёт починку роли; хвост отказа прибит к «полный набор не
        запускался» — рубеж называет не тот прогон."""
        bad = guard.PlanAppendix(("doc.md",), (
            "diff --git a/doc.md b/doc.md\n--- a/doc.md\n+++ b/doc.md\n"
            "@@ -1,3 +1,3 @@\n нет такой\n-и такой\n+новая\n и этой\n"))

        tree = self.suite_tree([self.appendix("строка 3\n", "правка 3\n"),
                                bad], None)

        self.assertIsNone(tree.root)
        self.assertTrue(tree.fixable, tree.refusal)
        self.assertIn("приложение 2 PLAN (doc.md)", tree.refusal)
        self.assertTrue(tree.refusal.endswith("— планка не запускалась"),
                        tree.refusal)

    def test_git_failure_is_not_role_fixable(self):
        """Дерево не развернулось (головы ветки нет) — отказ без прогона, но
        не по содержимому PLAN: `fixable` ложен.

        Ловит мутацию: `fixable` выставлен на любой отказ дерева — сбой git
        на рубеже `in_dev -> verifying` уходит роли подсказкой «почини
        приложение», которую нечем исполнить."""
        tree = self.suite_tree([self.appendix("строка 3\n", "правка 3\n")],
                               "нет-такой-ветки")

        self.assertIsNone(tree.root)
        self.assertFalse(tree.fixable, tree.refusal)
        self.assertIn("планка не запускалась", tree.refusal)
