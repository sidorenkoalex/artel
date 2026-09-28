"""AC-9 — одна точка правды в `scripts/guard.py`: заявку мутации выход из
`tests_writing` проверяет тем же узлом, что `_mutation_claim_gate`
(`guard.test_functions_without_mutation_claim`), а строку группы разбирает
одно регулярное выражение модуля `guard`, которым пользуются и выход из
`tests_writing`, и `amend-tests`.

«Пользуется одним выражением» наблюдается подменой: выражение строки
группы (единственный объект `re.Pattern` модуля `guard`, чей шаблон несёт
«Группа») подменяется на узнающее только значение `разовый` — тогда ОБА
места обязаны перестать видеть строку у корректного файла `Группа:
долгоживущий` и отказать. Место со своей копией правила подмены не
заметит и файл пропустит. Значение `разовый` подмена по-прежнему узнаёт:
зафиксированная планка вложенной задачи размечена им, и реализация,
отличающая планку «после мержа» по строкам группы тем же выражением,
продолжает её так отличать.

Группа: разовый
Красен до реализации: в `scripts/guard.py` нет выражения строки группы, а выход из `tests_writing` не зовёт `guard.test_functions_without_mutation_claim` — подсчёт выражений даёт ноль, шпион не видит ни одного вызова.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _amend_sandbox  # noqa: E402
import _sandbox  # noqa: E402
from scripts import guard  # noqa: E402

ONLY_ONCE = re.compile(r"Группа:[^\S\n]*(разовый)")


def group_pattern_names() -> list[str]:
    """Имена атрибутов модуля `guard` — скомпилированных выражений, чей
    шаблон несёт метку «Группа»."""
    return [name for name, value in vars(guard).items()
            if isinstance(value, re.Pattern) and "Группа" in value.pattern]


class SingleNodeAtTestsWritingTest(_sandbox.GroupPlankSandbox):

    def test_ac9_mutation_claim_uses_review_gate_node(self):
        """Долгоживущий файл с методом без заявки: при выходе из
        `tests_writing` шпион на `guard.test_functions_without_mutation_
        claim` (обёртка настоящей функции) вызван с текстом этого файла
        как HEAD-версией, и переход отклонён.

        Ловит мутацию: выход из `tests_writing` проверяет заявку
        собственным разбором докстрингов (второй копией `MUTATION_CLAIM`)
        — отказ есть, но шпион узла `_mutation_claim_gate` не вызван ни
        разу.
        """
        source = _sandbox.plank_source(claim=None)
        self.write_plank({"test_ac.py": source})
        spy = mock.Mock(wraps=guard.test_functions_without_mutation_claim)
        with mock.patch.object(guard, "test_functions_without_mutation_claim",
                               spy):
            out, refusals = self.advance()
        self.assertEqual(self.state(), "tests_writing",
                         f"метод без заявки обязан отклонить переход: {out!r}")
        heads = [call.kwargs.get("head_source",
                                 call.args[1] if len(call.args) > 1 else None)
                 for call in spy.call_args_list]
        self.assertIn(source, heads,
                      f"узел guard не получил текст долгоживущего файла; "
                      f"вызовы: {spy.call_args_list!r}")

    def test_ac9_group_line_single_regex_used_at_tests_writing(self):
        """В `guard` ровно одно выражение строки группы; подменённое на
        узнающее только `разовый`, оно заставляет выход из `tests_writing`
        отклонить корректный файл `Группа: долгоживущий` (а без подмены
        тот же файл проходит).

        Ловит мутацию: `fsm.py` разбирает строку группы собственным
        выражением — подмена в `guard` его не касается, корректный файл
        проходит в `in_dev` и под подменой.
        """
        names = group_pattern_names()
        self.assertEqual(len(names), 1,
                         f"выражений строки группы в guard: {names!r}")
        files = {"test_ac.py": _sandbox.plank_source(group=_sandbox.GROUP_LONG)}
        with mock.patch.object(guard, names[0], ONLY_ONCE):
            self.assert_refused_naming(
                files, "test_ac.py", why="выражение группы подменено")
        self.assert_passes(files, why="выражение группы на месте")


class SingleNodeAtAmendTest(_amend_sandbox.AmendSandbox):

    def test_ac9_group_line_single_regex_used_at_amend_tests(self):
        """Задача прошла новый выход из `tests_writing`; Оператор правит
        файл планки на корректную `Группа: долгоживущий`. Под подменой
        выражения строки группы в `guard` на узнающее только `разовый`
        `amend-tests` отказывает, называя файл, и лок не сдвигается; без
        подмены та же правка проходит.

        Ловит мутацию: `amend.py` несёт свою копию выражения строки
        группы — подмена в `guard` на `amend-tests` не действует, правка
        под подменой проходит и сдвигает `tests_locked_sha`.
        """
        names = group_pattern_names()
        self.assertEqual(len(names), 1,
                         f"выражений строки группы в guard: {names!r}")
        self.enter_in_dev_through_gate()
        locked = self.row()["tests_locked_sha"]
        self.write_worktree_plank(
            _amend_sandbox.plank_file("Группа: долгоживущий", variant="правка"))

        with mock.patch.object(guard, names[0], ONLY_ONCE):
            refused, text = self.amend()
        self.assertTrue(refused, f"amend-tests под подменой прошёл: {text}")
        self.assertIn("test_ac.py", text)
        self.assertEqual(self.row()["tests_locked_sha"], locked)

        refused, text = self.amend()
        self.assertFalse(refused, f"amend-tests без подмены отказал: {text}")
        self.assertNotEqual(self.row()["tests_locked_sha"], locked)


if __name__ == "__main__":
    unittest.main()
