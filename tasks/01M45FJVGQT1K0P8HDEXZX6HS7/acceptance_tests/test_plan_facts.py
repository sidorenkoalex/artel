"""Факты этой задачи: снятые развилки по проекту в местах таблицы
требования 5, перечни PLAN (смены ожиданий, фикстуры) и приложения PLAN к
`targets.yaml` и `tests/test_invariants.py` (SPEC «Критерии приёмки»,
AC-10, AC-13, AC-14).

Группа: разовый

Источник артефактов — помощник пульта `_pult.py`: PLAN и SPEC —
`artifact_text`, дифф задачи — `branch_diff`/`DIFF_BASE`, применимость
приложений — `apply_check`. Код базы и головы читается из git рабочей копии
(`git show <база>:<путь>`). Наложение приложений и прогон
`tests/test_invariants.py` — во временной копии дерева HEAD (`git archive`),
рабочая копия не меняется; прогон инвариантов разбит на три метода, чтобы
каждый уложился в таймаут теста.

Красен до реализации: PLAN.md ещё не написан, развилки по
`config.DEFAULT_TARGET`/`repo_context.is_artel` в местах таблицы на месте,
приложений к `targets.yaml` и `tests/test_invariants.py` нет.

Валидация: PLAN и ссылку документов стабом не подменить, поэтому методы
AC-10 и AC-14 прогнаны с подставным `_pult` — образцовый PLAN с
приложениями к обоим файлам (профиль артели в `targets.yaml`, `TARGETS`
песочницы `FsmTest` с профилем), код — рабочее дерево со стабом
реализации. Зелены AC-14 (применимость, только блок `test_profile`,
неизменные методы, прогон инвариантов в копии дерева) и AC-10 по всем
модулям, кроме намеренно недоснятой в стабе развилки `fsm_advance.py`
(автогейт), — её метод поймал. AC-13 (дифф разработчика) так не
проверить — разбор диффа и разделов сверен чтением.
"""
import ast
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import (CODE_ROOT, DIFF_BASE, TASK_ID, apply_check,  # noqa: E402
                   artifact_text, branch_diff)

sys.path.insert(0, CODE_ROOT)

from orchestrator import yamlmini  # noqa: E402
from scripts import guard  # noqa: E402

# Места таблицы требования 5 по модулям: сколько сравнений с
# `config.DEFAULT_TARGET` и вызовов `is_artel` в них снимается (пин 6eb98eff).
TABLE_FORKS = {
    "orchestrator/advance_gates/test_integrity.py": 1,   # :686
    "orchestrator/review.py": 1,                         # :613
    "orchestrator/fsm_merge_gate.py": 2,                 # ~123, :1101
    "orchestrator/advance_gates/review.py": 1,           # :200
    "orchestrator/advance_gates/tests_writing.py": 3,    # :191, :213, :268
    "orchestrator/fsm_advance.py": 2,                    # :196, :380
    "orchestrator/advance_gates/acceptance.py": 2,       # :57, :253
    "orchestrator/amend.py": 1,                          # :180
}

ARTEL_PROFILE = {
    "command": ["python3", "-m", "pytest"],
    "long_lived_dir": "tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": ["tests/**/*.py"],
    "mutation_claim_scope": ["tests/test_*.py"],
    "report": "junit-xml",
    "install": [],
}

TARGETS = "targets.yaml"
INVARIANTS = "tests/test_invariants.py"
SLOW_INVARIANTS = ("MergeOnlyFromMergeGateTest", "AgentRunsOnlyFromRunTest")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", CODE_ROOT, *args], capture_output=True,
                          text=True)


def base_text(path: str) -> str | None:
    res = git("show", f"{DIFF_BASE}:{path}")
    return res.stdout if res.returncode == 0 else None


def head_text(path: str) -> str | None:
    res = git("show", f"HEAD:{path}")
    return res.stdout if res.returncode == 0 else None


def fork_count(source: str) -> int:
    """Сравнения, где один из операндов — `DEFAULT_TARGET`, плюс вызовы
    `is_artel`."""
    count = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(_names_default_target(op) for op in operands):
                count += 1
        elif isinstance(node, ast.Call) and _call_name(node) == "is_artel":
            count += 1
    return count


def _names_default_target(node) -> bool:
    return ((isinstance(node, ast.Attribute) and node.attr == "DEFAULT_TARGET")
            or (isinstance(node, ast.Name) and node.id == "DEFAULT_TARGET"))


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def section(text: str, title: str) -> str | None:
    match = re.search(rf"^##\s+{re.escape(title)}[^\n]*\n(.*?)(?=^##\s|\Z)",
                      text, re.M | re.S)
    return match.group(1) if match else None


def diff_files(diff: str) -> dict:
    """{путь: (новый ли файл, добавленные строки)} закоммиченного диффа."""
    files: dict = {}
    current = None
    for line in diff.splitlines():
        header = re.match(r"^diff --git a/(\S+) b/(\S+)$", line)
        if header:
            current = header.group(2)
            files[current] = [False, []]
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            files[current][0] = True
        elif line.startswith("+") and not line.startswith("+++"):
            files[current][1].append(line[1:])
    return {k: (v[0], v[1]) for k, v in files.items()}


class _PlanTest(unittest.TestCase):

    def plan(self) -> str:
        text = artifact_text("PLAN.md")
        self.assertIsNotNone(text, "PLAN.md нет в ссылке документов задачи")
        return text


class ForksRemovedTest(_PlanTest):

    def test_ac10_table_places_have_no_project_forks(self):
        """В каждом модуле мест таблицы требования 5 сравнений с
        `config.DEFAULT_TARGET` и вызовов `is_artel` стало меньше на число
        мест таблицы в нём; вызов `workspace.on_task_branch` в
        `advance_gates/tests_writing.py` не несёт `config.DEFAULT_TARGET`;
        PLAN приводит вывод поиска (`DEFAULT_TARGET`, `is_artel`).

        Ловит мутацию: одно место таблицы оставлено с развилкой по проекту
        (например, гейт строк группы с `target != config.DEFAULT_TARGET`) —
        счёт сравнений в его модуле не убывает на число мест.
        """
        self.assertTrue(DIFF_BASE, "база диффа задачи не определена")
        for path, removed in TABLE_FORKS.items():
            with self.subTest(path=path):
                before, after = base_text(path), head_text(path)
                self.assertIsNotNone(before, f"{path} нет в базе {DIFF_BASE}")
                self.assertIsNotNone(after, f"{path} нет в HEAD")
                self.assertLessEqual(
                    fork_count(after), fork_count(before) - removed,
                    f"{path}: развилок по проекту было {fork_count(before)}, "
                    f"стало {fork_count(after)}, снять ожидалось {removed}")
        tree = ast.parse(head_text("orchestrator/advance_gates/tests_writing.py"))
        hard = [node.lineno for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and _call_name(node) == "on_task_branch"
                and any(_names_default_target(arg) for arg in
                        [*node.args, *(kw.value for kw in node.keywords)])]
        self.assertEqual(hard, [], "on_task_branch с config.DEFAULT_TARGET")
        plan = self.plan()
        self.assertIn("DEFAULT_TARGET", plan)
        self.assertIn("is_artel", plan)


class TestsAndListsTest(_PlanTest):

    def test_ac13_new_tests_with_claims_and_plan_lists(self):
        """В диффе задачи есть тесты `tests/test_*.py` разработчика (не
        долгоживущие файлы планки) с заявками «Ловит мутацию»; каждый файл
        `tests/` из раздела SPEC «Меняемое поведение» назван в PLAN рядом со
        ссылкой на мандат и раздел; каждый изменённый существующий файл
        `tests/` вне раздела (фикстуры профиля артели) PLAN называет
        отдельно.

        Ловит мутацию: смена ожидания или дополнение фикстуры проведены в
        `tests/` без перечня в PLAN — путь изменённого файла в PLAN не
        встречается.
        """
        plan = self.plan()
        files = diff_files(branch_diff())
        own_prefix = f"tests/test_{TASK_ID.lower()}_"
        claimed = [path for path, (_new, added) in files.items()
                   if re.match(r"tests/test_[^/]*\.py$", path)
                   and not path.startswith(own_prefix)
                   and any("Ловит мутацию" in line for line in added)]
        self.assertTrue(claimed, "в диффе нет тестов tests/test_*.py "
                                 "разработчика с «Ловит мутацию»")
        spec = artifact_text("SPEC.md") or ""
        changed_section = section(spec, "Меняемое поведение")
        listed = set(re.findall(r"tests/[\w/]+\.py", changed_section or ""))
        if listed:
            self.assertIn("Меняемое поведение", plan)
            self.assertRegex(plan.lower(), r"мандат")
            for path in sorted(listed):
                with self.subTest(changed=path):
                    self.assertIn(path, plan)
        existing = [path for path, (new, _added) in files.items()
                    if path.startswith("tests/") and not new
                    and not path.startswith(own_prefix)
                    and path != INVARIANTS and path not in listed]
        for path in sorted(existing):
            with self.subTest(fixture=path):
                self.assertIn(path, plan, f"{path} изменён, в PLAN не назван")


class _AppendixTree(_PlanTest):
    """Временная копия дерева HEAD с наложенными приложениями PLAN к
    `targets.yaml` и `tests/test_invariants.py`."""

    def appendices(self) -> list:
        appendices, errors = guard.plan_appendices(self.plan())
        wanted = [a for a in appendices
                  if TARGETS in a.paths or INVARIANTS in a.paths]
        paths = {p for a in wanted for p in a.paths}
        self.assertIn(TARGETS, paths, f"нет приложения к {TARGETS}: {errors}")
        self.assertIn(INVARIANTS, paths,
                      f"нет приложения к {INVARIANTS}: {errors}")
        return wanted

    def applied_tree(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="appendix-tree-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        archive = subprocess.run(["git", "-C", CODE_ROOT, "archive", "HEAD"],
                                 capture_output=True)
        self.assertEqual(archive.returncode, 0, archive.stderr)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(root, filter="data")
        for number, appendix in enumerate(self.appendices()):
            patch = root / f".appendix-{number}.diff"
            patch.write_text(appendix.diff, encoding="utf-8")
            res = subprocess.run(["git", "apply", str(patch)], cwd=root,
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"git apply: {res.stderr}")
            patch.unlink()
        return root

    def run_invariants(self, root: Path, *selection: str) -> None:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", *selection, "-q",
             "-p", "no:cacheprovider"],
            cwd=root, capture_output=True, text=True, timeout=110,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(res.returncode, 0,
                         (res.stdout + res.stderr)[-4000:])


class AppendicesTest(_AppendixTree):

    def test_ac14_appendices_apply_and_plan_confirms_check(self):
        """PLAN несёт приложения к `targets.yaml` и `tests/test_invariants.py`,
        каждое применимо к дереву HEAD (`git apply --check`), PLAN называет
        прогон `git apply --check`.

        Ловит мутацию: приложение к `tests/test_invariants.py` собрано от
        устаревшей версии файла — `apply_check` возвращает ответ git.
        """
        for appendix in self.appendices():
            with self.subTest(paths=appendix.paths):
                self.assertEqual(apply_check(appendix.diff), "")
        self.assertIn("git apply --check", self.plan())

    def test_ac14_targets_appendix_adds_only_artel_test_profile(self):
        """После наложения `targets.yaml` — прежний файл с вставленными
        строками одного блока `test_profile` записи `artel`; профиль равен
        таблице требования 1, прочие поля и записи не изменились.

        Ловит мутацию: приложение заодно меняет `no_paths` или комментарий
        записи — строки прежнего файла не входят в новый как
        подпоследовательность / поле разошлось.
        """
        root = self.applied_tree()
        before = head_text(TARGETS)
        after = (root / TARGETS).read_text(encoding="utf-8")
        old_lines, new_lines = before.splitlines(), after.splitlines()
        inserted, i = [], 0
        for line in new_lines:
            if i < len(old_lines) and line == old_lines[i]:
                i += 1
            else:
                inserted.append(line)
        self.assertEqual(i, len(old_lines), "строки прежнего targets.yaml "
                                            "изменены или удалены")
        self.assertTrue(inserted)
        self.assertEqual(inserted[0], "    test_profile:", inserted)
        for line in inserted[1:]:
            self.assertTrue(line.startswith("      "), line)
        old_entries = yamlmini.mapping(before)["targets"]
        new_entries = yamlmini.mapping(after)["targets"]
        self.assertEqual(new_entries["artel"].get("test_profile"), ARTEL_PROFILE)
        artel = dict(new_entries["artel"])
        del artel["test_profile"]
        self.assertEqual(artel, old_entries["artel"])
        self.assertEqual({k: v for k, v in new_entries.items() if k != "artel"},
                         {k: v for k, v in old_entries.items() if k != "artel"})

    def test_ac14_invariants_appendix_keeps_scenarios_and_assertions(self):
        """После наложения `tests/test_invariants.py` несёт те же тестовые
        методы с тем же телом (сценарии и утверждения), а песочница создаёт
        `targets.yaml` с профилем тестов артели.

        Ловит мутацию: приложение правит утверждение или сценарий метода
        `test_*` — тело метода расходится с прежним.
        """
        root = self.applied_tree()
        before = head_text(INVARIANTS)
        after = (root / INVARIANTS).read_text(encoding="utf-8")

        def methods(source: str) -> dict:
            found = {}
            for cls in ast.parse(source).body:
                if isinstance(cls, ast.ClassDef):
                    for fn in cls.body:
                        if (isinstance(fn, ast.FunctionDef)
                                and fn.name.startswith("test")):
                            found[f"{cls.name}.{fn.name}"] = ast.dump(fn)
            return found

        self.assertEqual(methods(after), methods(before))
        self.assertIn("test_profile", after)
        self.assertIn("targets.yaml", after)

    def test_ac14_invariants_pass_after_appendices_slow_part_one(self):
        """После наложения обоих приложений проходит
        `tests/test_invariants.py::MergeOnlyFromMergeGateTest`.

        Ловит мутацию: песочница приложения не кладёт профиль артели —
        сценарий инварианта упирается в отказ «нет test_profile».
        """
        root = self.applied_tree()
        self.run_invariants(root, f"{INVARIANTS}::{SLOW_INVARIANTS[0]}")

    def test_ac14_invariants_pass_after_appendices_slow_part_two(self):
        """После наложения обоих приложений проходит
        `tests/test_invariants.py::AgentRunsOnlyFromRunTest`.

        Ловит мутацию: тот же провал песочницы без профиля артели на
        сценарии запуска агента.
        """
        root = self.applied_tree()
        self.run_invariants(root, f"{INVARIANTS}::{SLOW_INVARIANTS[1]}")

    def test_ac14_invariants_pass_after_appendices_rest(self):
        """После наложения обоих приложений проходят остальные классы
        `tests/test_invariants.py`.

        Ловит мутацию: `targets.yaml` после приложения не разбирается
        (сломан отступ блока профиля) — инварианты с песочницей падают.
        """
        root = self.applied_tree()
        deselect = []
        for name in SLOW_INVARIANTS:
            deselect += ["--deselect", f"{INVARIANTS}::{name}"]
        self.run_invariants(root, INVARIANTS, *deselect)


if __name__ == "__main__":
    unittest.main()
