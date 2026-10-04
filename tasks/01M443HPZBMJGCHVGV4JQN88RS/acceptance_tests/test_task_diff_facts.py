"""Дифф задачи: `tests/test_merge_gate_clock_isolation.py` не тронут, утверждения изменённых тестов не ослаблены (AC-3, AC-5).

Группа: разовый

Зелёный с рождения: до правки разработчика дифф ветки от базы пуст — файл часов не тронут, изменённых методов нет; тесты сторожат, чтобы правка 32 мест не задела файл часов и не потеряла утверждений.

Группа «разовый»: предмет — разница ветки задачи с её базой
(`gitcmd.diff_base` — точка расхождения с `origin/main`); после мержа
сравнивать не с чем.
"""
import ast
import unittest
from collections import Counter

from _plank import CODE_ROOT, INV_REL, base_or_fail, changed_paths, text_at

CLOCK_REL = "tests/test_merge_gate_clock_isolation.py"
EMPTY = "∅"
_EMPTY_ASSERTS = {"assert_not_called", "assertFalse"}


def _functions(source: str) -> dict[str, ast.AST]:
    """{квалифицированное имя: узел} всех функций и методов модуля."""
    out: dict[str, ast.AST] = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    out[name] = child
                visit(child, f"{name}.")
            else:
                visit(child, prefix)

    visit(ast.parse(source), "")
    return out


def _tokens(node: ast.AST) -> list[str]:
    """Существенные части утверждения: литералы, константы `config.X`, «пусто»."""
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant):
            value = sub.value
            empty = value is False or (not isinstance(value, bool)
                                       and value in (0, ""))
            out.append(EMPTY if empty else repr(value))
        elif isinstance(sub, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            if not getattr(sub, "elts", getattr(sub, "keys", None)):
                out.append(EMPTY)
        elif isinstance(sub, ast.Attribute):
            if sub.attr in _EMPTY_ASSERTS:
                out.append(EMPTY)
            elif sub.attr[:1].isupper():
                out.append(sub.attr)
    return out


def _assertions(func: ast.AST) -> list[ast.AST]:
    found = []
    for sub in ast.walk(func):
        if isinstance(sub, ast.Assert):
            found.append(sub)
        elif (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
              and sub.func.attr.startswith("assert")):
            found.append(sub)
    return found


def weakened(base_src: str, cur_src: str) -> list[str]:
    """Изменённые функции, где утверждений стало меньше или пропали их части."""
    problems = []
    current = _functions(cur_src)
    for name, base_fn in _functions(base_src).items():
        base_asserts = _assertions(base_fn)
        if not base_asserts:
            continue
        cur_fn = current.get(name)
        if cur_fn is None:
            problems.append(f"{name}: функции с утверждениями больше нет")
            continue
        if ast.dump(base_fn) == ast.dump(cur_fn):
            continue
        cur_asserts = _assertions(cur_fn)
        if len(cur_asserts) < len(base_asserts):
            problems.append(f"{name}: утверждений было {len(base_asserts)}, "
                            f"стало {len(cur_asserts)}")
        lost = (Counter(t for a in base_asserts for t in _tokens(a))
                - Counter(t for a in cur_asserts for t in _tokens(a)))
        if lost:
            problems.append(f"{name}: из утверждений пропало {dict(lost)}")
    return problems


class TaskDiffFactsTest(unittest.TestCase):

    def test_ac3_clock_isolation_file_unchanged_vs_base(self):
        """`tests/test_merge_gate_clock_isolation.py` в рабочем дереве ветки байт-в-байт равен файлу базы диффа.

        Сценарий: база — точка расхождения HEAD с `origin/main`
        (`gitcmd.diff_base`); текст файла в базе сравнивается с текстом на
        диске рабочей копии (включая незакоммиченное).

        Ловит мутацию: разработчик «чинит» строку документации 31 файла
        часов (убирает упоминание `mock.patch.object(time, "sleep", …)`),
        чтобы текстовый поиск его не цеплял, — тексты разойдутся.
        """
        base = base_or_fail(self)
        before = text_at(base, CLOCK_REL)
        self.assertIsNotNone(before, f"{CLOCK_REL} нет в базе {base}")
        now = (CODE_ROOT / CLOCK_REL).read_text(encoding="utf-8")
        self.assertEqual(now, before, f"{CLOCK_REL} изменён относительно базы")

    def test_ac5_assertions_of_changed_tests_are_kept(self):
        """В изменённых функциях файлов `tests/` утверждений не меньше, и ни одна их часть не пропала.

        Сценарий: для каждого файла `tests/`, изменённого от базы диффа
        (кроме `tests/test_invariants.py` — он едет приложением) и
        существовавшего в базе, функции базы с утверждениями сопоставляются
        с одноимёнными функциями рабочего дерева. Утверждение — `assert`
        или вызов `.assert*(...)` (`self.assertEqual`,
        `sleep.assert_not_called` …). Для изменённой функции: утверждений
        не меньше, чем в базе, и все их литералы, константы `config.X` и
        признаки «пусто» (`[]`, `0`, `assert_not_called`, `assertFalse`)
        остались — замена `sleep.assert_not_called()` на
        `assertEqual(<паузы>, [])` равносильна, удаление — нет.

        Ловит мутацию: при переводе `tests/test_main_ci_line.py` на
        заместитель `fsm_merge_gate.time` удалена строка
        `sleep.assert_not_called()` (мок больше так не называется) — число
        утверждений метода уменьшится; либо в `tests/test_agent_failure.py`
        `assertEqual(self.pauses, [config.RETRY_BACKOFF_SEC, …])` смягчён
        до `assertTrue(self.pauses)` — пропадёт `RETRY_BACKOFF_SEC`.
        """
        base = base_or_fail(self)
        problems = []
        for rel in changed_paths(base):
            if (not rel.startswith("tests/") or not rel.endswith(".py")
                    or rel == INV_REL):
                continue
            before = text_at(base, rel)
            path = CODE_ROOT / rel
            if before is None or not path.is_file():
                continue
            problems += [f"{rel}::{p}" for p in
                         weakened(before, path.read_text(encoding="utf-8"))]
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
