"""AC-6 (tasks/01M3SF7DPFGEZ7VYEGGXGTX49E/SPEC.md): факты ветки задачи о
каталоге `tests/` — существующие файлы не удалены и не переименованы,
тест отказа мержа при нарушающем `guard --all` снимке помечен «Ловит
мутацию: мерж без guard после снимка».

Группа: разовый

Красен до реализации: тестов задачи в `tests/` кодовой ветки ещё нет — долгоживущий файл планки с отметкой «мерж без guard после снимка» пульт коммитит в ветку только на чекпоинте шага test_author.

Поведенческая часть AC-6 (отказ до push, прохождение чистого снимка,
исходы `pin-update` и `pin --to`, три исхода строки `doctor`, ожидание
CI main после мержа, отказ следующего мержа и `--fixes-main`, сценарий
«красный мерж, затем документный коммит») — долгоживущий файл планки
`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, его методы
`test_ac1_…`–`test_ac6_…`. «Не ослабляются» сверяет гейт неослабления
тестов пульта на `in_dev -> verifying` и `merge_gate`; здесь — то, что
видно по диффу ветки: ни один существующий файл `tests/` не удалён и не
переименован.

Дифф — от точки расхождения ветки задачи с origin (`gitcmd.diff_base`),
тексты файлов — из ветки (`gitcmd.show`), не с диска рабочей копии.
"""
import ast
import unittest

from orchestrator import gitcmd

TASK_ID = "01M3SF7DPFGEZ7VYEGGXGTX49E"
MARK = "Ловит мутацию: мерж без guard после снимка"


def task_branch() -> str:
    res = gitcmd.git("for-each-ref", "--format=%(refname:short)",
                     f"refs/heads/task/{TASK_ID.lower()}-*")
    names = res.stdout.split() if res is not None and res.returncode == 0 else []
    return names[0] if names else ""


def branch_tests_diff(test: unittest.TestCase) -> list[tuple[str, str]]:
    """[(статус, путь)] изменений `tests/` ветки задачи от базы сравнения."""
    branch = task_branch()
    test.assertTrue(branch, f"ветка задачи {TASK_ID} не найдена")
    base = gitcmd.diff_base(branch)
    test.assertTrue(base, f"база сравнения ветки {branch} не определена")
    res = gitcmd.git("diff", "--name-status", "-M", base, branch, "--", "tests/")
    test.assertTrue(res is not None and res.returncode == 0,
                    f"git diff не ответил: {res.stderr if res else '—'}")
    out = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0], parts[-1] if parts[0][:1] != "R" else parts[1]))
    return out


def marked_methods(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            and MARK in (ast.get_docstring(node) or "")]


class TestsDirInBranchTest(unittest.TestCase):

    def test_ac6_no_existing_tests_file_deleted_or_renamed(self):
        """Дифф `tests/` ветки задачи от базы сравнения.

        Ни одной записи удаления (`D`) или переименования (`R`)
        существующего файла.

        Зелёный с рождения: ветка задачи до работы разработчика `tests/`
        не удаляет; метод держит это до мержа.
        """
        removed = [(status, path) for status, path in branch_tests_diff(self)
                   if status[:1] in ("D", "R")]
        self.assertEqual(removed, [],
                         f"существующие файлы tests/ удалены или "
                         f"переименованы: {removed}")

    def test_ac6_guard_refusal_test_carries_the_mutation_mark(self):
        """Добавленные и изменённые веткой файлы `tests/*.py`, тексты — из
        ветки задачи.

        Хотя бы один тестовый метод несёт в докстринге «Ловит мутацию:
        мерж без guard после снимка».

        Ловит мутацию: тест отказа мержа при нарушающем снимке не
        написан либо помечен другой мутацией — ни один метод ветки не
        несёт отметки.
        """
        branch = task_branch()
        marked = []
        for status, path in branch_tests_diff(self):
            if status[:1] not in ("A", "M") or not path.endswith(".py"):
                continue
            text, _why = gitcmd.show(branch, path)
            marked += [f"{path}::{name}" for name in marked_methods(text or "")]
        self.assertTrue(marked, f"в tests/ ветки {branch} нет метода с "
                                f"«{MARK}»")


if __name__ == "__main__":
    unittest.main()
