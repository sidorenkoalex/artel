"""Разбор строк doctor по компонентам и суммы отслеживаемых файлов блокировки в ключе итога (SPEC 01M58PG72PG64GS790XM2EWS61)."""
import dataclasses
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from orchestrator import acceptance, config, project_profile, store, targets
from orchestrator.doctor import project_checks
from tests.sandbox import ARTEL_TEST_PROFILE


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

    def test_unclosed_class_at_zero_depth_is_unparseable(self):
        """Незакрытый класс `[` при сбалансированных `()` — тоже неразбираемая строка.

        Ловит мутацию: по концу строки проверяется только глубина `()`, без
        признака незакрытого класса — `a|[b` даёт множество `{a, [b}`.
        """
        for text in ("a|[b", "^(a)|[b"):
            got, reason = project_checks.regex_alternatives(text)
            self.assertIsNone(got, text)
            self.assertTrue(reason, text)


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


class LockKeySandbox(unittest.TestCase):
    """Учебный git-репозиторий с `workdir` `w` и профилями без и с `tools`."""

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


class TrackedLockKeyTest(LockKeySandbox):

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


class ToolsKeyTest(LockKeySandbox):
    """Ключ рабочего дерева видит `tools` и игнорируемый файл блокировки,
    ключ базы — нет (требования 10-11)."""

    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text("w/package-lock.json\n",
                                              encoding="utf-8")
        self.ignored = self.root / "w" / "package-lock.json"
        self.ignored.write_text("a\n", encoding="utf-8")

    def test_declared_tools_change_work_tree_key(self):
        """Смена объявленной версии инструмента при том же дереве меняет ключ рабочего дерева.

        Ловит мутацию: элемент `tools` не попадает в данные ключа (или в нём
        нет объявленных версий) — `node: 22` и `node: 20` дают один ключ.
        """
        tree = self.tree()
        other = dataclasses.replace(
            self.profile, tools=MappingProxyType({"node": "20"}))
        self.assertNotEqual(
            acceptance.suite_result_key(tree, self.with_tools, root=self.root),
            acceptance.suite_result_key(tree, other, root=self.root))

    def test_ignored_lock_change_changes_work_tree_key(self):
        """Смена игнорируемого git файла блокировки при том же дереве меняет ключ рабочего дерева.

        Ловит мутацию: игнорируемый файл в суммы не входит (берутся только
        блобы дерева) — правка `package-lock.json` ключ не меняет.
        """
        tree = self.tree()
        self.assertEqual(self.git("ls-files", "w/package-lock.json"), "")
        key = acceptance.suite_result_key(tree, self.with_tools, root=self.root)
        self.assertIsNotNone(key)
        self.ignored.write_text("b\n", encoding="utf-8")
        self.assertNotEqual(acceptance.suite_result_key(
            tree, self.with_tools, root=self.root), key)

    def test_base_key_ignores_tools_and_locks(self):
        """Ключ базы одинаков при любых `tools` и не зависит от игнорируемого файла блокировки.

        Ловит мутацию: элемент `tools` добавляется и в ключ базы — ключ
        базы профиля с `tools` отличается от ключа без них либо меняется
        при правке `package-lock.json`.
        """
        tree = self.tree()
        plain = acceptance.suite_result_key(tree, self.profile, base=True)
        self.assertIsNotNone(plain)
        self.assertEqual(acceptance.suite_result_key(
            tree, self.with_tools, root=self.root, base=True), plain)
        self.ignored.write_text("b\n", encoding="utf-8")
        self.assertEqual(acceptance.suite_result_key(
            tree, self.with_tools, root=self.root, base=True), plain)


TARGET_HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

SINGLE_COMPONENT = """    components:
      front:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [tests/**/*.py]
        mutation_claim_scope: [tests/test_*.py]
        runner: pytest-own
        workdir: w
        tools:
          node: "22 (из .nvmrc)"
"""


class DecideToolsTest(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "targets.yaml"
        path.write_text(
            "targets:\n" + TARGET_HEAD.format(name=config.DEFAULT_TARGET)
            + ARTEL_TEST_PROFILE + TARGET_HEAD.format(name="single")
            + SINGLE_COMPONENT, encoding="utf-8")
        patcher = mock.patch.object(config, "TARGETS", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_decide_carries_single_component_tools(self):
        """`decide` записи с одним компонентом даёт `Profile` с его `tools`, записи с `test_profile` — с пустыми.

        Ловит мутацию: `decide` не зовёт `with_tools` (или помощник не берёт
        `tools` единственного компонента) — у `Profile` пустые `tools`, и
        ключ рабочего дерева не видит инструментов.
        """
        decision = project_profile.decide("single")
        self.assertEqual(decision.refusal, "")
        self.assertEqual(dict(decision.profile.tools),
                         {"node": "22 (из .nvmrc)"})
        self.assertEqual(
            dict(project_profile.decide(config.DEFAULT_TARGET).profile.tools), {})


OWN_TEST_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      runner: pytest-own
      workdir: w
"""


class TaskOwnProfileToolsTest(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "targets.yaml"
        path.write_text(
            "targets:\n" + TARGET_HEAD.format(name=config.DEFAULT_TARGET)
            + ARTEL_TEST_PROFILE + TARGET_HEAD.format(name="single")
            + SINGLE_COMPONENT + TARGET_HEAD.format(name="own")
            + OWN_TEST_PROFILE, encoding="utf-8")
        patcher = mock.patch.object(config, "TARGETS", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        self.conn = conn

    def own_profile(self, target: str):
        with mock.patch.object(store, "task_target", return_value=target):
            return acceptance._task_own_profile(self.conn, "T1")

    def test_task_own_profile_carries_single_component_tools(self):
        """Профиль автогейта приёмки записи с одним компонентом несёт его `tools`, записи с `test_profile` — пустые.

        Ловит мутацию: `_task_own_profile` не зовёт `with_tools` — `tools`
        профиля автогейта пусты, и ключ рабочего дерева автогейта не видит
        смены инструментов и игнорируемого файла блокировки.
        """
        single = self.own_profile("single")
        self.assertIsNotNone(single)
        self.assertEqual(dict(single.tools), {"node": "22 (из .nvmrc)"})
        own = self.own_profile("own")
        self.assertIsNotNone(own)
        self.assertEqual(dict(own.tools), {})


if __name__ == "__main__":
    unittest.main()
