"""AC-8: шесть названных критерием наборов и неприкосновенность тестов
поведения Claude в них.

Зелёность самих наборов планка не пересчитывает: полный набор `tests/`
гоняет автогейт приёмки (`orchestrator/acceptance.py::run_full_suite` как
условие approve, ADR-0007) и CI ветки — собственный прогон был бы копией
уже действующего гейта. Планка фиксирует то, чего зелёный полный прогон
поймать НЕ МОЖЕТ по построению: удалённый тест зелёному прогону не мешает,
выключенный пометкой `skip` — тоже. Остаток критерия (ассерт, ослабленный
ВНУТРИ уцелевшего метода) виден только в диффе к базовой ревизии — его
читает ревьювер ветки.

Модули наборов разбираются `ast`, а не импортируются: импорт `tests/*`
поднял бы их песочницы внутри планки, а предмет здесь — состав файла.

Зелёный с рождения: тест сохранения существующего — шесть наборов на месте и тесты поведения Claude в них не тронуты; таким он обязан остаться и после правки.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import REPO_ROOT  # noqa: E402

#: Шесть наборов, названных критерием.
NAMED_SUITES = ("tests/test_providers.py", "tests/test_providers_codex.py",
                "tests/test_stack.py", "tests/test_doctor.py",
                "tests/test_runner_role_model.py", "tests/test_models.py")

#: Тесты ПОВЕДЕНИЯ Claude, которые эта задача рискует задеть: разбор
#: вывода и набор сигнатур единственного сегодняшнего исполнителя
#: (`tests/test_providers.py::OutputEventTest`). Снимок состава на
#: 26.09.2026 — до правки задачи.
CLAUDE_BEHAVIOUR_TESTS = (
    "test_one_event_carries_both_the_text_and_the_tool_call",
    "test_log_line_and_call_key_read_different_argument_keys",
    "test_usage_is_read_even_when_the_blocks_are_unreadable",
    "test_run_result_with_a_negative_price_reports_no_price",
    "test_failure_signatures_name_only_classes_of_the_common_set",
)

#: Число тестовых методов `tests/test_providers.py` на 26.09.2026:
#: дописывать в набор можно, убирать — нет.
PROVIDERS_SUITE_TESTS = 31

#: Декоратор, выключающий тест: `@unittest.skip*`, `@pytest.mark.skip*`,
#: `@unittest.expectedFailure`, `@pytest.mark.xfail`.
SWITCH_OFF_DECORATOR = re.compile(r"^\s*@.*(skip|expectedFailure|xfail)")


class NamedSuitesTest(unittest.TestCase):
    """Состав шести наборов, названных AC-8."""

    def suite_text(self, rel: str) -> str:
        path = REPO_ROOT / rel
        self.assertTrue(path.is_file(), f"набор {rel} не найден")
        return path.read_text(encoding="utf-8")

    def method_names(self, rel: str) -> list:
        """Имена тестовых методов набора — разбором, без импорта."""
        tree = ast.parse(self.suite_text(rel))
        return [node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name.startswith("test")]

    def test_ac8_every_named_suite_keeps_its_claude_behaviour_tests(self):
        """Все шесть наборов на месте, тесты поведения Claude в
        `tests/test_providers.py` не удалены, и число его тестов не
        уменьшилось.

        Ловит мутацию: тест поведения Claude, покрасневший от общей
        правки разбора (скажем, «отрицательная цена — цены нет» или
        «классы сигнатур только из общего набора»), не починен, а удалён
        либо переименован под codex — полный прогон остаётся зелёным, и
        свойство Claude уходит без охраны молча.
        """
        for rel in NAMED_SUITES:
            with self.subTest(rel):
                self.suite_text(rel)

        names = self.method_names("tests/test_providers.py")
        missing = [name for name in CLAUDE_BEHAVIOUR_TESTS
                   if name not in names]
        self.assertEqual(missing, [], "тесты поведения Claude удалены")
        self.assertGreaterEqual(len(names), PROVIDERS_SUITE_TESTS,
                                "в наборе стало меньше тестов, чем было")

    def test_ac8_no_named_suite_switches_a_test_off(self):
        """Ни один тест шести наборов не выключен декоратором `skip`/
        `expectedFailure`/`xfail`.

        Ловит мутацию: неудобный тест Claude не удалён, а помечен
        `@unittest.skip("переписать во второй части")` — набор
        по-прежнему «проходит зелёным», а проверяемого им свойства уже
        никто не держит.
        """
        for rel in NAMED_SUITES:
            with self.subTest(rel):
                switched_off = [line.strip()
                                for line in self.suite_text(rel).splitlines()
                                if SWITCH_OFF_DECORATOR.match(line)]

                self.assertEqual(switched_off, [], "тест выключен декоратором")


if __name__ == "__main__":
    unittest.main()
