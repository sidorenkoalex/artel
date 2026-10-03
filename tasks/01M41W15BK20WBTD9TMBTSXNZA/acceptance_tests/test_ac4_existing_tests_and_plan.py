"""Факты задачи 01M41W15BK20WBTD9TMBTSXNZA по AC-4: существующие тесты
`plank-run` зелёные, а каждая правка их тестовых методов названа в PLAN.md.

Группа: разовый
Зелёный с рождения: tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py и tests/test_plank_run_edges.py в ветке ещё не правлены и зелёны на текущем коде — PLAN.md перечислять нечего; тест краснеет, если правка их метода не названа в PLAN.md или они покраснели.

Свойства кода (AC-1…AC-3 и поведение без окружения роли из AC-4) сторожит
долгоживущий файл задачи
`tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`. Здесь — то, что
после мержа проверять не на чем: разница двух существующих файлов с базой
ветки (`gitcmd.diff_base`) и PLAN.md из артефактной ветки (`gitcmd.show`,
не с диска).
"""
import ast
import subprocess
import sys
import unittest

from orchestrator import artifact_branch, config, gitcmd

TASK_ID = "01M41W15BK20WBTD9TMBTSXNZA"
EXISTING = ("tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py",
            "tests/test_plank_run_edges.py")


def plan_text() -> str | None:
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text


def _test_methods(source: str | None) -> dict:
    """{имя метода test_*: его исходный текст} модуля."""
    if source is None:
        return {}
    tree = ast.parse(source)
    return {node.name: ast.get_source_segment(source, node)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


class ExistingPlankRunTestsTest(unittest.TestCase):

    def test_ac4_existing_tests_green_and_edits_listed_in_plan(self):
        """Существующие тесты plank-run зелёные, их правки названы в PLAN.md.

        Сценарий: для `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py` и
        `tests/test_plank_run_edges.py` тестовые методы базы ветки
        (`gitcmd.diff_base`) сравниваются с методами рабочей копии; каждый
        изменённый или удалённый метод обязан быть назван в PLAN.md
        артефактной ветки вместе с именем своего файла. Затем оба файла
        прогоняются pytest из рабочей копии кода — код выхода 0.

        Ловит мутацию: разработчик правит утверждение метода
        `test_ac1_tests_writing_runs_draft_with_pult_runner` (или удаляет
        метод), не перечислив правку в PLAN.md — имени метода нет в PLAN;
        правка кода ломает прежний тест `plank-run` — прогон двух файлов
        красный.
        """
        base = gitcmd.diff_base("HEAD")
        self.assertIsNotNone(base, "база ветки задачи не определена")
        plan = None
        for rel in EXISTING:
            before, _reason = gitcmd.show(base, rel)
            path = config.ROOT / rel
            after = path.read_text(encoding="utf-8") if path.is_file() else None
            old, new = _test_methods(before), _test_methods(after)
            changed = sorted(name for name, text in old.items()
                             if new.get(name) != text)
            if not changed:
                continue
            if plan is None:
                plan = plan_text()
            self.assertIsNotNone(plan, f"{rel}: методы {changed} изменены, "
                                       f"а PLAN.md в артефактной ветке нет")
            with self.subTest(file=rel):
                self.assertIn(rel.rsplit("/", 1)[1], plan,
                              f"{rel} правлен, но не назван в PLAN.md")
                for name in changed:
                    self.assertIn(name, plan, f"{rel}: изменённый метод {name} "
                                              f"не перечислен в PLAN.md")
        res = subprocess.run(
            [sys.executable, "-m", "pytest", *EXISTING, "-q",
             "-p", "no:cacheprovider"],
            cwd=config.ROOT, capture_output=True, text=True, timeout=110)
        self.assertEqual(res.returncode, 0,
                         f"существующие тесты plank-run красные:\n"
                         f"{(res.stdout + res.stderr)[-3000:]}")


if __name__ == "__main__":
    unittest.main()
