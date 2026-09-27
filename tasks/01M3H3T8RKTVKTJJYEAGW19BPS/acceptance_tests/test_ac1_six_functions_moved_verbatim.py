"""AC-1 — 01M3H3T8RKTVKTJJYEAGW19BPS: шесть функций команды `ci-rerun`
лежат в `orchestrator/ci_rerun.py` и перенесены из `orchestrator/fsm.py`
дословно — тексты отказов, коды выхода, порядок и тексты записей
журнала, обращения к `gh` не изменены.

Версия «до» берётся не копией текста в планке, а из git (точка
расхождения ветки с `origin/main`, `_util.base_source`): так сверка
переживает любую подтяжку main в ветку задачи.

Сверяются ровно те величины, которые называет критерий: строковые
литералы тела (тексты отказов и записей журнала, аргументы `sys.exit`) и
порядок вызовов по последнему сегменту имени (`ci.trigger_rerun`,
`ci.verifying_status`, `store.journal`, `sys.exit` — всё, через что
команда ходит в `gh` и в журнал). Квалификация имён при переносе
меняется неизбежно (`_origin_main_sha` -> `fsm._origin_main_sha`), и
побайтная сверка исходника отказывала бы корректному переносу —
поэтому сверка по AST.

Красен до реализации: модуля `orchestrator/ci_rerun.py` ещё нет — все
три метода падают на его отсутствии (`_util.current_source` не находит
файл), перенос шести функций делает разработчик.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402


class SixFunctionsMovedVerbatimTest(unittest.TestCase):

    def setUp(self):
        module_path = _util.REPO_ROOT / _util.CI_RERUN_REL
        if not module_path.is_file():
            self.fail(f"{_util.CI_RERUN_REL} не существует — шесть функций "
                      f"команды ci-rerun ещё не перенесены из "
                      f"{_util.FSM_REL} (AC-1)")
        self.new_funcs = _util.functions(_util.current_source(_util.CI_RERUN_REL))
        self.base_funcs = _util.functions(_util.base_source(_util.FSM_REL))
        missing_in_base = [n for n in _util.MOVED_FUNCTIONS
                           if n not in self.base_funcs]
        self.assertFalse(
            missing_in_base,
            f"версия «до» ({_util.FSM_REL} в точке расхождения с "
            f"origin/main) не содержит {missing_in_base} — не с чем "
            f"сверять дословность переноса")

    def test_ac1_all_six_functions_are_defined_in_the_new_module(self):
        """Все шесть имён — функции верхнего уровня самого
        `orchestrator/ci_rerun.py`, а импортом из `fsm` не подменены.

        Ловит мутацию: перенесены пять функций из шести (например,
        `_ci_rerun_outcome` оставлен в `fsm.py` и подтянут в новый модуль
        импортом) — имя в модуле тогда есть, но определения верхнего
        уровня нет, и `assertIn` по разобранному AST покраснеет.
        """
        for name in _util.MOVED_FUNCTIONS:
            with self.subTest(name=name):
                self.assertIn(
                    name, self.new_funcs,
                    f"{_util.CI_RERUN_REL} не определяет {name} — AC-1 "
                    f"требует перенести в него все шесть функций команды")

        from orchestrator import ci_rerun

        for name in _util.MOVED_FUNCTIONS:
            with self.subTest(name=name, check="__module__"):
                obj = getattr(ci_rerun, name, None)
                self.assertIsNotNone(
                    obj, f"orchestrator.ci_rerun.{name} недоступен")
                self.assertEqual(
                    "orchestrator.ci_rerun", getattr(obj, "__module__", ""),
                    f"{name} объявлен не в orchestrator/ci_rerun.py, а в "
                    f"{getattr(obj, '__module__', '?')} — это реэкспорт, а "
                    f"не перенос")

    def test_ac1_refusal_and_journal_texts_are_unchanged(self):
        """Строковые литералы тела каждой из шести функций совпадают с
        дорефакторинговыми посимвольно и в том же порядке: тексты
        отказов, текст записи журнала, аргументы `sys.exit`.

        Ловит мутацию: при переносе текст отказа переписан «по дороге» —
        например, `«CI ветки {branch} не завершённо-красный»` набран
        заново с другим словом или из f-строки выпала подстановка
        `{note}`; последовательность литералов разойдётся с версией
        «до», и `assertEqual` назовёт функцию.
        """
        for name in _util.MOVED_FUNCTIONS:
            with self.subTest(name=name):
                self.assertEqual(
                    _util.string_literals(self.base_funcs[name]),
                    _util.string_literals(self.new_funcs[name]),
                    f"строковые литералы {name} разошлись с версией до "
                    f"переноса — AC-1 требует переноса дословно")

    def test_ac1_call_order_including_gh_and_journal_is_unchanged(self):
        """Порядок вызовов в теле каждой функции — тот же, что до
        переноса: обращения к `ci.*` (узлы `gh`), `store.journal`,
        `sys.exit`, `lease.run_locked` идут в прежней
        последовательности.

        Ловит мутацию: запись журнала переставлена относительно
        `ci.trigger_rerun`/`sys.exit` (например, `store.journal`
        перенесён после `print`, а отказ `sys.exit` — до записи) либо
        предусловие сверки с главной веткой потеряло вызов
        `ci.failed_check_names`; последовательность имён вызовов
        разойдётся с версией «до».
        """
        for name in _util.MOVED_FUNCTIONS:
            with self.subTest(name=name):
                self.assertEqual(
                    _util.call_names(self.base_funcs[name]),
                    _util.call_names(self.new_funcs[name]),
                    f"порядок вызовов {name} разошёлся с версией до "
                    f"переноса — AC-1 требует переноса дословно")

    def test_ac1_exit_calls_keep_their_single_string_argument(self):
        """Каждый `sys.exit` перенесённых функций вызван ровно одним
        строковым аргументом — кодом выхода 1, как до переноса.

        Ловит мутацию: `sys.exit(f"…")` заменён на `sys.exit(1)` с
        печатью текста рядом (код выхода тот же, а вот `SystemExit` без
        текста ломает сверку отказов) или на `sys.exit(2)` — число
        аргументов и их вид перестанут совпадать с дорефакторинговыми.
        """
        def exit_arg_kinds(node):
            kinds = []
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                name = func.attr if isinstance(func, ast.Attribute) else \
                    getattr(func, "id", "")
                if name != "exit":
                    continue
                kinds.append(tuple(type(a).__name__ for a in sub.args))
            return kinds

        for name in _util.MOVED_FUNCTIONS:
            with self.subTest(name=name):
                self.assertEqual(
                    exit_arg_kinds(self.base_funcs[name]),
                    exit_arg_kinds(self.new_funcs[name]),
                    f"форма вызовов sys.exit в {name} изменилась — коды "
                    f"выхода команды обязаны остаться прежними (AC-1)")


if __name__ == "__main__":
    unittest.main()
