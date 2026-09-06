"""AC-1 задачи 01M1TKP08PKB87K8772H69GCXJ: `orchestrator/pull.py`
существует, определяет типы исходов `Fresh`/`Pulled(sha)`/
`Conflict(files, note)`/`Refused(reason)`, и логика сегодняшней
`_pull_main_or_escalate` (218 строк) разложена в нём отдельными
короткими функциями, а не перенесена одной функцией на 200+ строк.

Красен до реализации: `orchestrator/pull.py` не существует ещё —
`import orchestrator.pull` падает `ModuleNotFoundError` на первом же
тесте.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]
PULL_PY = REPO_ROOT / "orchestrator" / "pull.py"

# Требование 1/AC-1: логика сегодняшней `_pull_main_or_escalate` (218
# строк, `orchestrator/fsm.py:240-457`) — заведомо больше этого потолка;
# после разбиения ни одна ОТДЕЛЬНАЯ функция pull.py не имеет права
# остаться такой же длинной, иначе разбиения не произошло вовсе.
MAX_FUNCTION_LINES = 150
MIN_TOP_LEVEL_FUNCTIONS = 4


class PullModuleOutcomeTypesTest(unittest.TestCase):

    def test_ac1_pull_module_defines_four_outcome_types(self):
        """`orchestrator.pull` определяет четыре типа исхода подтяжки:
        `Fresh` (без полей), `Pulled(sha)`, `Conflict(files, note)`,
        `Refused(reason)` — сигнатуры конструкторов проверяются через
        `inspect.signature`, не привязываясь к тому, реализованы ли типы
        как `dataclass`, `NamedTuple` или обычные классы (SPEC говорит
        «тип(ы)», не называя конкретную технику).

        Ловит мутацию: один из четырёх исходов не заведён отдельным
        типом (например, `Conflict` и `Refused` схлопнуты в один класс с
        необязательными полями, либо `Pulled` не несёт `sha`) —
        `inspect.signature`/`hasattr` по каждому имени и полю это
        поймает.
        """
        from orchestrator import pull

        self.assertTrue(hasattr(pull, "Fresh"), "orchestrator.pull.Fresh отсутствует")
        pull.Fresh()  # не должен требовать полей

        self.assertTrue(hasattr(pull, "Pulled"), "orchestrator.pull.Pulled отсутствует")
        self.assertIn("sha", inspect.signature(pull.Pulled).parameters,
                      "Pulled обязан нести поле sha (SPEC AC-1)")

        self.assertTrue(hasattr(pull, "Conflict"), "orchestrator.pull.Conflict отсутствует")
        conflict_params = inspect.signature(pull.Conflict).parameters
        self.assertIn("files", conflict_params,
                      "Conflict обязан нести поле files (SPEC AC-1)")
        self.assertIn("note", conflict_params,
                      "Conflict обязан нести поле note (SPEC AC-1)")

        self.assertTrue(hasattr(pull, "Refused"), "orchestrator.pull.Refused отсутствует")
        self.assertIn("reason", inspect.signature(pull.Refused).parameters,
                      "Refused обязан нести поле reason (SPEC AC-1)")


class PullModuleDecompositionTest(unittest.TestCase):

    def test_ac1_pull_logic_is_split_into_several_short_functions(self):
        """`orchestrator/pull.py` разбирает логику подтяжки на несколько
        отдельных функций верхнего уровня, ни одна из которых не
        дотягивает до размера прежней монолитной `_pull_main_or_escalate`
        (218 строк) — не «перенесли файл, переименовали функцию».

        Ловит мутацию: разработчик копирует тело `_pull_main_or_escalate`
        в `pull.py` одной функцией (по сути тем же кодом под новым
        именем) — либо число функций верхнего уровня останется мало
        (<4), либо длина этой единственной функции останется в районе
        исходных 200+ строк; `assertGreaterEqual`/`assertLessEqual` ниже
        поймают любой из двух вариантов.
        """
        self.assertTrue(PULL_PY.is_file(),
                        f"{PULL_PY} не существует — модуль pull.py не заведён")
        source = PULL_PY.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(PULL_PY))
        top_level_funcs = [n for n in tree.body
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        self.assertGreaterEqual(
            len(top_level_funcs), MIN_TOP_LEVEL_FUNCTIONS,
            f"pull.py несёт только {len(top_level_funcs)} функций верхнего "
            f"уровня — логика сверки/merge/авторазрешения/детализации/"
            f"чекпоинта/прогона планки обязана разойтись минимум по "
            f"{MIN_TOP_LEVEL_FUNCTIONS}, а не остаться одним блоком")

        longest_name, longest_len = None, 0
        for node in top_level_funcs:
            length = (node.end_lineno - node.lineno + 1)
            if length > longest_len:
                longest_name, longest_len = node.name, length
        self.assertLessEqual(
            longest_len, MAX_FUNCTION_LINES,
            f"функция {longest_name!r} несёт {longest_len} строк (порог "
            f"{MAX_FUNCTION_LINES}) — это переписанная монолитная "
            f"_pull_main_or_escalate под новым именем, не разбиение на "
            f"короткие функции")


if __name__ == "__main__":
    unittest.main()
