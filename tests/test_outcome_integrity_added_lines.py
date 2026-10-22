"""Разбор добавленных строк `git diff -M -U0` гейта исходов (SPEC
01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 7): края, которых не касаются
долгоживущие файлы задачи — путь, который git берёт в кавычки, текст не в
utf-8, строка без перевода строки в конце файла, конфиг git процесса пульта
с `diff.noprefix` и переименование из тестового пути в путь кода.

Стенд — настоящий git во временном каталоге (`tests.sandbox.TmpDirTest`).
"""
import os
import subprocess
import unittest
from unittest import mock

from orchestrator import project_profile
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

    def test_noprefix_config_does_not_hide_added_lines(self):
        """`diff.noprefix=true` и `diff.mnemonicPrefix=true` в конфиге git процесса пульта не меняют разбор: добавленная строка с подстрокой исключения найдена с номером по голове.

        Ловит мутацию: префиксы `--src-prefix=a/ --dst-prefix=b/` убраны из
        argv — при `diff.noprefix=true` заголовок `+++ app.js` без `b/`, и
        разбор либо молча теряет строки файла (fail-open требования 8),
        либо отказывает подготовкой.
        """
        (self.repo / "app.js").write_text(
            "const a = 1;\nconst m = process.env.NODE_ENV;\n",
            encoding="utf-8")
        head = self.commit()
        for key in ("diff.noprefix", "diff.mnemonicPrefix"):
            env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": key,
                   "GIT_CONFIG_VALUE_0": "true"}
            with self.subTest(key=key), mock.patch.dict(os.environ, env):
                added = outcome_integrity._added_lines(self.repo, self.base,
                                                       head)
                self.assertEqual(added, {"app.js": [
                    (2, "const m = process.env.NODE_ENV;")]})

    def test_unexpected_header_is_prepare_refusal(self):
        """Заголовок `+++ ` без префикса `b/` (и не `/dev/null`) — отказ подготовки `_Prepare`, а не пропуск строк файла.

        Ловит мутацию: заголовок неожиданной формы снова ставит путь `None`
        — гейт молча получает ноль добавленных строк вместо отказа.
        """
        out = (b"diff --git x/app.js y/app.js\n--- x/app.js\n+++ y/app.js\n"
               b"@@ -1,0 +2 @@\n+NODE_ENV\n")
        done = subprocess.CompletedProcess([], 0, stdout=out, stderr=b"")
        with mock.patch.object(outcome_integrity.subprocess, "run",
                               return_value=done):
            with self.assertRaises(outcome_integrity._Prepare):
                outcome_integrity._added_lines(self.repo, self.base, "f" * 40)

    def test_deleted_file_header_dev_null_is_not_refusal(self):
        """Удалённый файл (`+++ /dev/null`) не отказ подготовки и добавленных строк не даёт.

        Ловит мутацию: `/dev/null` попадает под проверку префикса `b/` —
        любое удаление файла веткой роняет гейт отказом подготовки.
        """
        (self.repo / "app.js").unlink()
        head = self.commit()
        self.assertEqual(
            outcome_integrity._added_lines(self.repo, self.base, head), {})


class CodeExceptionRenameTest(unittest.TestCase):

    @staticmethod
    def files(tests=()):
        profile = project_profile.Profile(
            command=("npx", "vitest"), long_lived_dir="tests",
            long_lived_name="test_{id}_{slug}.py",
            weakening_scope=("tests/**/*.py",), mutation_claim_scope=(),
            tests=tests)
        return outcome_integrity._Files(profile, {"tests/test_util.py"},
                                        {"tests/test_util.py"})

    def test_rename_from_test_path_to_code_path_is_checked(self):
        """Файл, переименованный из тестового пути в путь кода, проверяется как файл кода: подстрока исключения в добавленной строке даёт находку «исключение в коде» по пути головы — у компонента с полем `tests` и без него.

        Ловит мутацию: вид файла решается и по старому пути переименования
        (`for p in (path, old)`) — у переименования тест→код находки нет.
        """
        added = {"lib/util.py": [(3, 'if os.environ["NODE_ENV"]:')]}
        for tests in ((), ("tests/**/*.py",)):
            with self.subTest(tests=tests):
                found = outcome_integrity._code_exception_findings(
                    self.files(tests),
                    [("R090", "tests/test_util.py", "lib/util.py")], added)
                self.assertEqual(
                    [(f.kind, f.id, f.runs) for f in found],
                    [(outcome_integrity.CODE_EXCEPTION, "lib/util.py",
                      "строка 3: NODE_ENV")])

    def test_rename_between_test_paths_is_not_checked(self):
        """Переименование тестового файла в тестовый путь с записями в отчёте головы у компонента без `tests` находки «исключение в коде» не даёт — новый путь тестовый по правилу файла `A`.

        Ловит мутацию: правило файла `A` под `weakening_scope` с записями в
        отчёте головы не распространено на новый путь `R` — ложная находка
        на переименованный тест.
        """
        profile = self.files().profile
        files = outcome_integrity._Files(profile, {"tests/test_util.py"},
                                         {"tests/test_tools.py"})
        found = outcome_integrity._code_exception_findings(
            files, [("R090", "tests/test_util.py", "tests/test_tools.py")],
            {"tests/test_tools.py": [(1, 'os.environ["NODE_ENV"] = "x"')]})
        self.assertEqual(found, [])
