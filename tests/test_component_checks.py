"""Разбор строк doctor по компонентам и суммы отслеживаемых файлов блокировки в ключе итога (SPEC 01M58PG72PG64GS790XM2EWS61)."""
import dataclasses
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from orchestrator import acceptance, project_profile, targets
from orchestrator.doctor import project_checks


class RegexAlternativesTest(unittest.TestCase):

    def test_bar_inside_class_or_escaped_does_not_split(self):
        """`|` внутри `[]` и после `\\` альтернативы не делит (требование 5).

        Ловит мутацию: сканер не знает классов символов или экранирования —
        `[c|d]` и `a\\|b` делятся, множество выходит из четырёх частей.
        """
        got, reason = project_checks.regex_alternatives(r"^(a\|b|[c|d]|e/)")
        self.assertEqual(got, {r"a\|b", "[c|d]", "e/"}, reason)

    def test_unclosed_class_is_unparseable(self):
        """Незакрытый класс `[` — неразбираемая строка, а не одна альтернатива.

        Ловит мутацию: по концу строки проверяется только глубина `()` —
        `^(a|[b)` даёт множество вместо причины.
        """
        got, reason = project_checks.regex_alternatives("^(a|[b)")
        self.assertIsNone(got)
        self.assertTrue(reason)


class FindVariableTest(unittest.TestCase):

    def test_literal_block_single_line_and_double_quotes(self):
        """Блок `|` из одной строки — значение; `"…"` снимаются; ключ с иным хвостом имени не совпадает.

        Ловит мутацию: блок читается только для `>-` — у `|` значение
        `|`; поиск ключа префиксом — `KEY_OTHER` принят за `KEY`.
        """
        text = ("env:\n  A_RE_OTHER: 'x/'\n  A_RE: |\n    ^(p/|q/)\n"
                '  B_RE: "^(r/)"\n')
        self.assertEqual(project_checks.find_variable(text, "A_RE"),
                         ("^(p/|q/)", ""))
        self.assertEqual(project_checks.find_variable(text, "B_RE"),
                         ("^(r/)", ""))


class TrackedLockKeyTest(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.git("init", "-q")
        (self.root / "w").mkdir()
        self.lock = self.root / "w" / "uv.lock"
        self.lock.write_text("one\n", encoding="utf-8")
        self.profile = project_profile.Profile(
            command=("python3", "-m", "pytest"), long_lived_dir="tests",
            long_lived_name="test_<id>_<name>.py", weakening_scope=("tests/**",),
            mutation_claim_scope=("tests/test_*.py",),
            runner=targets.PROFILE_RUNNER_OWN, workdir="w")
        self.with_tools = dataclasses.replace(
            self.profile, tools=MappingProxyType({"node": "22"}))

    def git(self, *args) -> str:
        res = subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t",
                              "-c", "user.email=t@t", *args],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def tree(self) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c", "--allow-empty")
        return self.git("rev-parse", "HEAD^{tree}")

    def test_tracked_lock_sum_comes_from_tree_object(self):
        """Отслеживаемый файл блокировки входит в ключ суммой блоба дерева, не рабочей копии.

        Сценарий: `uv.lock` закоммичен; правка рабочей копии без нового
        дерева ключ не меняет, новое дерево с другим содержимым — меняет.

        Ловит мутацию: сумма отслеживаемого файла берётся из рабочей копии —
        правка файла при прежнем дереве меняет ключ.
        """
        first = self.tree()
        key = acceptance.suite_result_key(first, self.with_tools, root=self.root)
        self.assertIsNotNone(key)
        self.lock.write_text("two\n", encoding="utf-8")
        self.assertEqual(acceptance.suite_result_key(
            first, self.with_tools, root=self.root), key)
        second = self.tree()
        self.assertNotEqual(acceptance.suite_result_key(
            second, self.with_tools, root=self.root), key)

    def test_tools_without_root_give_no_key_and_empty_tools_ignore_root(self):
        """Ключ рабочего дерева с `tools` без рабочей копии не считается; без `tools` от `root` не зависит.

        Ловит мутацию: без `root` суммы молча пропускаются — ключ есть и
        не видит файлов блокировки; при пустых `tools` суммы всё же
        добавляются — ключ с `root` отличается от ключа без него.
        """
        tree = self.tree()
        self.assertIsNone(acceptance.suite_result_key(tree, self.with_tools))
        self.assertEqual(
            acceptance.suite_result_key(tree, self.profile, root=self.root),
            acceptance.suite_result_key(tree, self.profile))


if __name__ == "__main__":
    unittest.main()
