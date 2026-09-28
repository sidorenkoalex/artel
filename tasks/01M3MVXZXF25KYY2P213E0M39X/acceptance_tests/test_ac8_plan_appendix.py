"""AC-8 — допуск приложения к PLAN: новые пути признаются защищёнными,
незащищённый по-прежнему отвергается именованной ошибкой.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. `guard.plan_appendices` принимает приложение к `conftest.py` и к
`tests/sub/conftest.py` без ошибки `appendix_unprotected_path_error`, а
приложение к `orchestrator/store.py` по-прежнему отвергает ею же.

Красен до реализации: `_appendix_path_is_protected` сверяет путь префиксом, маски в перечне нет — приложение к `conftest.py` отвергается ошибкой «путь не защищённый», и законного пути правки вложенного conftest.py не существует вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# `_protected` кладёт корень репозитория в `sys.path` — без этого импорта
# пакет `scripts` ниже не резолвится из каталога планки.
import _protected  # noqa: E402,F401
from scripts import guard  # noqa: E402

UNPROTECTED_PATH = "orchestrator/store.py"
APPENDIX_PATHS = ("conftest.py", "tests/sub/conftest.py")


def plan_with_appendix(path: str) -> str:
    """PLAN.md с одним разделом «## Приложение» и минимальным, но
    настоящим блоком ```diff по `path` — та же форма фикстуры, что у
    `tests/test_plan_appendix.py::diff_block`."""
    return (f"# PLAN\n\n## Приложение: правка {path}\n\n"
            f"```diff\n"
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            f"```\n")


class PlanAppendixToNewProtectedPathsTest(unittest.TestCase):

    def test_ac8_appendix_to_new_paths_is_accepted(self):
        """Приложение к корневому `conftest.py` и к вложенному
        `tests/sub/conftest.py` разбирается в приложение и НЕ даёт ошибки
        `appendix_unprotected_path_error`.

        Ловит мутацию: общего помощника позвали в гейтах пульта, а
        `guard._appendix_path_is_protected` оставили префиксной (пометку
        «только чтение» с `scripts/guard.py` снял ANSWER-1, и её легко
        прочитать как «этот файл не трогаем»). Наблюдаемое расхождение:
        `plan_appendices` возвращает пустой список приложений и ошибку
        «приложение PLAN: путь tests/sub/conftest.py не защищённый — правь
        в ветке задачи» — гейт зон правку в ветке не пускает, приложение
        Оператора тоже отвергнуто, и вложенный `conftest.py` нельзя
        поправить ни одним законным путём.
        """
        for path in APPENDIX_PATHS:
            with self.subTest(path=path):
                appendices, errors = guard.plan_appendices(
                    plan_with_appendix(path))

                self.assertNotIn(guard.appendix_unprotected_path_error(path),
                                 errors)
                self.assertEqual([a.paths for a in appendices], [(path,)])

    def test_ac8_appendix_to_an_unprotected_path_is_still_refused(self):
        """Приложение к `orchestrator/store.py` по-прежнему отвергается
        именно ошибкой `appendix_unprotected_path_error` — прежнее
        поведение сохранено.

        Ловит мутацию: помощник, научившись маске, стал признавать
        защищённым любой путь (пустая проверка, «маска покрывает всё», или
        `any()` по пустому перечню, вырожденному в `True`). Наблюдаемое
        расхождение: ошибки нет, приложение к обычному коду `orchestrator/
        store.py` признано законным, и роль начинает возить в main правки
        кода коммитом Оператора, минуя ревью и CI ветки.
        """
        appendices, errors = guard.plan_appendices(
            plan_with_appendix(UNPROTECTED_PATH))

        self.assertIn(
            guard.appendix_unprotected_path_error(UNPROTECTED_PATH), errors)
        self.assertEqual(appendices, [])


if __name__ == "__main__":
    unittest.main()
