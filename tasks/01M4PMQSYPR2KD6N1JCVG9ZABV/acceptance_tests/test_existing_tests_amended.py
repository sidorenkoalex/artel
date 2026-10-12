"""Правки двух существующих тестов `tests/`, разрешённые мандатом задачи:
счёт запросов `actions/runs` в `RunEventLabelTest` (AC-8) и одна строка
фикстуры `head_branch` в долгоживущем тесте событий CI (AC-9).

Группа: разовый

Красен до реализации: в `test_green_outcome_does_not_ask_workflow_runs` ещё стоит `assertFalse` без запросов `actions/runs`, а фикстура `FakeGitHub.add_run` несёт `"head_branch": "main"` — разницы с базой нет (AC-8 и AC-9 падают на разборе метода и диффа).

Планка провалидирована временным стабом: правка метода по требованию 8,
правка строки фикстуры по требованию 9 (во временном коммите) и стаб
фильтра в `orchestrator/ci.py` — оба метода зелёные; стаб и коммит убраны.

AC-1…AC-7 покрыты долгоживущим файлом
`tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py`.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, branch_diff  # noqa: E402

STATUS_TESTS = "tests/test_ci_status.py"
EVENT_TESTS = "tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py"
GREEN_METHOD = "test_green_outcome_does_not_ask_workflow_runs"
UNLINKED_METHOD = "test_unlinked_check_runs_do_not_ask_workflow_runs"


def run_pytest(*node_ids: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *node_ids, "-q",
         "-p", "no:cacheprovider"],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=110)


def method_node(source: str, cls: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    raise AssertionError(f"{cls}.{name} не найден в {STATUS_TESTS}")


def calls_named(node: ast.AST, attr: str) -> list[ast.Call]:
    return [c for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == attr]


def file_section(diff: str, path: str) -> list[str]:
    """Строки хунков диффа одного файла (без заголовков `---`/`+++`)."""
    out, inside = [], False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            inside = line.endswith(f" b/{path}")
            continue
        if inside and not line.startswith(("--- ", "+++ ", "index ",
                                           "new file", "deleted file")):
            out.append(line)
    return out


class AmendedExistingTestsTest(unittest.TestCase):
    """Разрешённые мандатом правки существующих тестов."""

    def test_ac8_green_outcome_counts_one_runs_query_per_reader(self):
        """Метод зелёного исхода считает ровно один запрос прогонов на
        каждого читателя статуса и зелен вместе с соседом.

        Разбирается исходник `RunEventLabelTest.test_green_outcome_does_not_
        ask_workflow_runs` рабочей копии: в нём нет `assertFalse` над
        запросами `actions/runs`, есть не меньше двух `assertEqual` над
        выражениями с `actions/runs` и значением 1; утверждения о зелёном
        исходе (`VERIFYING_GREEN` у `verifying_status`, `True` у
        `branch_status`) остались; докстринг несёт «Ловит мутацию». Затем
        оба метода — он и `test_unlinked_check_runs_do_not_ask_workflow_runs`
        — прогоняются pytest и проходят.

        Ловит мутацию: прежний `assertFalse` оставлен (метод красен на новом
        коде) либо заменён одним общим счётом на оба вызова; утверждения о
        зелёном исходе удалены вместе с правкой; ослаблен соседний метод
        без связи с прогоном (он красен или пропал).
        """
        source = (Path(CODE_ROOT) / STATUS_TESTS).read_text(encoding="utf-8")
        node = method_node(source, "RunEventLabelTest", GREEN_METHOD)
        segment = lambda n: ast.get_source_segment(source, n) or ""

        falses = [c for c in calls_named(node, "assertFalse")
                  if "actions/runs" in segment(c)]
        self.assertFalse(falses, "assertFalse над actions/runs остался:\n"
                         + "\n".join(map(segment, falses)))

        def counts_one(call: ast.Call) -> bool:
            text = segment(call)
            ones = [a for a in call.args
                    if isinstance(a, ast.Constant) and a.value == 1
                    and not isinstance(a.value, bool)]
            return "actions/runs" in text and bool(ones)

        # Счёт мог быть вынесен в переменную: тогда `actions/runs` ищется
        # и в присваиваниях имён, которые читает `assertEqual`.
        assigned = {}
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        assigned[target.id] = segment(stmt)

        def counts_one_via_names(call: ast.Call) -> bool:
            if counts_one(call):
                return True
            names = {n.id for n in ast.walk(call) if isinstance(n, ast.Name)}
            via = any("actions/runs" in assigned.get(n, "") for n in names)
            ones = any(isinstance(a, ast.Constant) and a.value == 1
                       and not isinstance(a.value, bool) for a in call.args)
            return via and ones

        equal_ones = [c for c in calls_named(node, "assertEqual")
                      if counts_one_via_names(c)]
        self.assertGreaterEqual(len(equal_ones), 2, segment(node))

        body = segment(node)
        self.assertIn("VERIFYING_GREEN", body, body)
        self.assertRegex(body, r"assertIs\(\s*ci\.branch_status\([^)]*\)"
                               r"\[0\],\s*True", body)
        self.assertIn("Ловит мутацию", ast.get_docstring(node) or "", body)

        result = run_pytest(
            f"{STATUS_TESTS}::RunEventLabelTest::{GREEN_METHOD}",
            f"{STATUS_TESTS}::RunEventLabelTest::{UNLINKED_METHOD}")
        self.assertEqual(result.returncode, 0,
                         result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("2 passed", result.stdout, result.stdout[-4000:])

    def test_ac9_event_fixture_differs_by_one_head_branch_line(self):
        """Долгоживущий тест событий CI отличается от базы ровно строкой
        `head_branch` фикстуры и зелен целиком.

        Из закоммиченного диффа задачи берётся раздел файла
        `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`: ровно одна
        удалённая и одна добавленная строка; удалённая несёт
        `"head_branch": "main"`, добавленная — та же строка с
        `"head_branch": "task/x"`. Затем файл прогоняется pytest целиком и
        проходит.

        Ловит мутацию: вместе с фикстурой поправлены утверждения или иные
        строки файла (в разделе больше одной пары строк); подставлена
        другая ветка, не та, что тест спрашивает; правка не сделана, и
        методы AC1-AC8 файла красны на новом фильтре.
        """
        section = file_section(branch_diff(), EVENT_TESTS)
        removed = [l[1:] for l in section if l.startswith("-")]
        added = [l[1:] for l in section if l.startswith("+")]
        self.assertEqual(len(removed), 1, "\n".join(section))
        self.assertEqual(len(added), 1, "\n".join(section))
        self.assertIn('"head_branch": "main"', removed[0], removed[0])
        self.assertEqual(
            added[0],
            removed[0].replace('"head_branch": "main"',
                               '"head_branch": "task/x"'),
            "\n".join(section))

        result = run_pytest(EVENT_TESTS)
        self.assertEqual(result.returncode, 0,
                         result.stdout[-4000:] + result.stderr[-2000:])
        self.assertNotIn("failed", result.stdout.splitlines()[-1]
                         if result.stdout else "", result.stdout[-4000:])


if __name__ == "__main__":
    unittest.main()
