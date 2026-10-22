"""Разбор добавленных строк `git diff -M -U0` гейта исходов (SPEC
01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 7): края, которых не касаются
долгоживущие файлы задачи — путь, который git берёт в кавычки, текст не в
utf-8 и строка без перевода строки в конце файла.

Стенд — настоящий git во временном каталоге (`tests.sandbox.TmpDirTest`).
"""
import subprocess

from orchestrator.advance_gates import outcome_integrity
from tests.sandbox import TmpDirTest


class AddedLinesTest(TmpDirTest):

    def git(self, *args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=t",
             "-c", "user.email=t@example.invalid", *args],
            capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def setUp(self):
        super().setUp()
        self.repo = self.tdir / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "app.js").write_text("const a = 1;\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.base = self.git("rev-parse", "HEAD")

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        return self.git("rev-parse", "HEAD")

    def test_quoted_path_latin1_text_and_no_final_newline(self):
        """Путь с табуляцией и кавычкой разобран из кавычек git, строка не в utf-8 не роняет разбор, последняя строка без перевода строки засчитана со своим номером.

        Ловит мутацию: путь `+++ "b/…"` не снимается с кавычек — ключ с
        кавычками и экранами; вывод декодируется строго — исключение
        `UnicodeDecodeError` вместо разбора; строка «\\ No newline at end of
        file» сбрасывает счёт ханка или считается добавленной — номер или
        состав строк иной.
        """
        odd = 'lib/odd\tna"me.js'
        (self.repo / "lib").mkdir()
        (self.repo / odd).write_text("const x = 1;\nconst m = 'NODE_ENV';",
                                     encoding="utf-8")
        (self.repo / "app.js").write_bytes(
            "const a = 1;\n// caf\xe9 eslint-disable\n".encode("latin-1"))
        head = self.commit()
        added = outcome_integrity._added_lines(self.repo, self.base, head)
        self.assertEqual(added[odd], [(1, "const x = 1;"),
                                      (2, "const m = 'NODE_ENV';")])
        self.assertEqual(len(added["app.js"]), 1)
        number, text = added["app.js"][0]
        self.assertEqual(number, 2)
        self.assertIn("eslint-disable", text)
