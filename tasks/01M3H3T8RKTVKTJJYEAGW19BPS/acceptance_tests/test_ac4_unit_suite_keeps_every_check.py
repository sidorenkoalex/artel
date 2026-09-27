"""AC-4 — 01M3H3T8RKTVKTJJYEAGW19BPS: в `tests/test_ci_rerun_command.py`
изменены только импорты и пути подмен, ни одна прежняя проверка не
изменена и не удалена; добавлен тест тождества `fsm.cmd_ci_rerun` и
`ci_rerun.cmd_ci_rerun`.

Единица сверки — тело каждой функции/метода файла в версии «до» (из git,
точка расхождения с `origin/main`) против сегодняшнего, с одной
нормализацией: снимаются квалификаторы `fsm.`/`ci_rerun.` — ровно то,
что критерий разрешает менять как «путь подмены»
(`mock.patch.object(fsm, "_origin_main_sha", …)` ->
`mock.patch.object(ci_rerun, …)`). Докстринги в сверку не входят:
критерий защищает проверки, а ссылка на модуль в докстринге после
переноса законно устаревает.

Красен до реализации: сегодня в файле нет теста тождества алиаса (и
самого `orchestrator/ci_rerun.py`) — `test_ac4_identity_test_added`
падает; сверка тел и прогон набора зелены с рождения: они фиксируют
то, что перенос обязан НЕ сломать, и покраснеют на первой же тронутой
проверке или неверном пути подмены.
"""
import ast
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

IDENTITY_MARKS = ("fsm.cmd_ci_rerun", "ci_rerun.cmd_ci_rerun")


class UnitSuiteKeepsEveryCheckTest(unittest.TestCase):

    def setUp(self):
        self.base_src = _util.base_source(_util.UNIT_TESTS_REL)
        self.cur_src = _util.current_source(_util.UNIT_TESTS_REL)
        self.base_funcs = _util.qualified_functions(self.base_src)
        self.cur_funcs = _util.qualified_functions(self.cur_src)

    def test_ac4_no_previous_check_is_changed_or_removed(self):
        """Каждая функция и каждый метод, бывшие в файле до переноса,
        на месте, и их тела совпадают с прежними с точностью до
        квалификатора модуля.

        Ловит мутацию: подмена, переставшая работать после переноса,
        «починена» правкой самой проверки — например, в
        `test_second_rerun_with_the_same_reason_never_touches_gh`
        ассерт `assertEqual(self.trigger_calls, [self.BRANCH])` ослаблен
        до `assertTrue(...)`, или метод целиком удалён как «устаревший»;
        нормализованный исходник разойдётся с версией «до».
        """
        missing = [name for name in self.base_funcs
                   if name not in self.cur_funcs]
        self.assertFalse(
            missing,
            f"из {_util.UNIT_TESTS_REL} исчезли прежние проверки: "
            f"{missing} (AC-4)")

        for name, node in self.base_funcs.items():
            with self.subTest(name=name):
                self.assertEqual(
                    _util.normalized_function_source(self.base_src, node),
                    _util.normalized_function_source(self.cur_src,
                                                     self.cur_funcs[name]),
                    f"тело {name} изменилось не только путём подмены — "
                    f"AC-4 разрешает править лишь импорты и пути подмен")

    def test_ac4_module_level_fixtures_are_unchanged(self):
        """Константы-фикстуры уровня модуля (`HEAD`, `MAIN_SHA`,
        `REASON`, …) остались прежними.

        Ловит мутацию: проверки формально целы, но подогнаны входные
        данные — например, `HEAD` и `OLD_HEAD` совпали по первым восьми
        символам, и сверка «голова ветки уехала» перестала что-либо
        проверять; словарь присваиваний разойдётся с версией «до».
        """
        base_assigns = _util.module_assignments(self.base_src)
        cur_assigns = _util.module_assignments(self.cur_src)
        for name, text in base_assigns.items():
            with self.subTest(name=name):
                self.assertEqual(
                    text, cur_assigns.get(name),
                    f"фикстура {name} в {_util.UNIT_TESTS_REL} изменилась "
                    f"или исчезла (AC-4)")

    def test_ac4_identity_test_added(self):
        """В файле появился новый тестовый метод, сверяющий тождество
        `fsm.cmd_ci_rerun` и `ci_rerun.cmd_ci_rerun`, и само тождество
        выполняется.

        Ловит мутацию: тест добавлен, но сверяет равенство поведения, а
        не объекта (`assertEqual(fsm.cmd_ci_rerun.__name__, …)`) — алиас
        мог бы разойтись с функцией нового модуля, и подмены прежних
        тестов через `fsm` перестали бы видеть команду; проверка ищет
        именно тождество (`assertIs`/` is `) и оба имени в одном методе.
        """
        added = [name for name in self.cur_funcs if name not in self.base_funcs]
        identity_tests = []
        for name in added:
            src = ast.get_source_segment(self.cur_src, self.cur_funcs[name])
            if not src:
                continue
            if all(mark in src for mark in IDENTITY_MARKS) and \
                    ("assertIs" in src or " is " in src):
                identity_tests.append(name)
        self.assertTrue(
            identity_tests,
            f"в {_util.UNIT_TESTS_REL} нет нового теста тождества алиаса: "
            f"добавленные методы {added or '(нет)'} не сверяют "
            f"{IDENTITY_MARKS[0]} с {IDENTITY_MARKS[1]} через assertIs")

        from orchestrator import ci_rerun, fsm

        self.assertIs(fsm.cmd_ci_rerun, ci_rerun.cmd_ci_rerun)

    def test_ac4_unit_suite_stays_green(self):
        """`tests/test_ci_rerun_command.py` целиком проходит на
        сегодняшнем коде.

        Гоняется один файл, названный самим критерием (полный набор
        `tests/` — дело CI). Ловит мутацию: пути подмен переведены на
        новый модуль не везде — например, `mock.patch.object(ci_rerun,
        "_origin_main_sha", …)` при том, что команда зовёт
        `fsm._origin_main_sha`: сверка тел выше этого не видит (там
        квалификатор нормализован), а прогон падает обращением к
        настоящему git.
        """
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(
            "tests." + Path(_util.UNIT_TESTS_REL).stem)
        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)
        base_test_methods = [n for n in self.base_funcs
                             if n.rsplit(".", 1)[-1].startswith("test_")]
        self.assertGreaterEqual(
            result.testsRun, len(base_test_methods),
            f"из {_util.UNIT_TESTS_REL} запустилось меньше тестов, чем в "
            f"нём было до переноса — зелёный набор оказался бы пустым")
        self.assertTrue(
            result.wasSuccessful(),
            f"{_util.UNIT_TESTS_REL} не зелён: провалы="
            f"{[str(t) for t, _ in result.failures]}; ошибки="
            f"{[str(t) for t, _ in result.errors]}")


if __name__ == "__main__":
    unittest.main()
