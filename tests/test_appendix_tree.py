"""Юнит-тесты `orchestrator/appendix_tree.py` (SPEC 01M46C776SZEMYPBQGPNJN1TXY)
на свойства, которых нет в долгоживущих файлах задачи: перенос удалённого
и неотслеживаемого файла рабочей копии во временное дерево `suite-run` и
приложение, уже наложенное в дереве (подтянутый main его несёт).

Настоящий git во временном каталоге, без песочницы `config`: узел
подготовки дерева (`_prepared`) зовёт только git и файловую систему.
"""
import subprocess
from pathlib import Path

from orchestrator import appendix_tree
from scripts import guard
from tests.sandbox import TmpDirTest

BASE = "".join(f"строка {n}\n" for n in range(1, 11))


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


class PreparedTreeTest(TmpDirTest):

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
