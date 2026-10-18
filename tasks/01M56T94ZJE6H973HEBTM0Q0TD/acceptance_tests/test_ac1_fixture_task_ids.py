"""AC-1: id задачи фикстуры не даёт в строке «не уложился» отдельно стоящего COPY_LIMIT.

Группа: разовый
Красен до реализации: генератор `task_id` фикстуры берёт алфавит с цифрами — среди ids фиксированного набора зёрен есть id с отдельно стоящим «60» (…K60X…), а после префикса стоят цифры.

Предмет — фикстура теста `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`
(метод предела полного прогона `suite-run`); после мержа это свойство
держит сам тот файл, планка проверяет факт его правки этой задачей.
Генератор id фикстуры — метод `task_id` песочницы класса метода
(SPEC «Материалы»: `task_id` — `:164`), зерно — её `self.rng`.
"""
import inspect
import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _meta import LIMIT_CLASS, LIMIT_METHOD  # noqa: E402
from _pult import CODE_ROOT  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

SEEDS = range(3000)
PREFIX = "01M"


def limit_module():
    import importlib
    return importlib.import_module(
        "tests.test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs")


class FixtureTaskIdTest(unittest.TestCase):

    def fixture_ids(self) -> list:
        """(зерно, id) — по одному id от каждого зерна фиксированного набора,
        тем же генератором, которым метод заводит задачу проекта."""
        cls = getattr(limit_module(), LIMIT_CLASS)
        probe = cls(LIMIT_METHOD)
        out = []
        for seed in SEEDS:
            probe.rng = random.Random(seed)
            out.append((seed, probe.task_id()))
        return out

    def test_ac1_report_line_has_no_standalone_copy_limit_for_any_seed(self):
        """Строка отчёта «не уложился» с id задачи фикстуры не несёт отдельно стоящего COPY_LIMIT.

        Сценарий: для 3000 фиксированных зёрен строится id задачи генератором
        фикстуры, из него — строка заголовка отчёта `suite-run` в форме
        `render` (`[<id>] suite-run №<n> (полный набор): прогон не уложился
        в предел <N> с (источник: профиль тестов проекта p<буквы>) …`) при
        N 11–13 и номерах прогона 1–3; ни одна строка не даёт
        `standalone(COPY_LIMIT, line)` теста. Перебор фиксированного набора
        не зависит от зерна прогона планки.

        Ловит мутацию: генератор id фикстуры откатили к алфавиту с цифрами
        (`ALPHABET`) — около 1% ids несут «60» между буквами, и на 3000
        зёрнах такая строка находится всегда.
        """
        module = limit_module()
        limit_value = getattr(module, LIMIT_CLASS).COPY_LIMIT
        bad = []
        for seed, task_id in self.fixture_ids():
            for run_no in (1, 2, 3):
                for n in (11, 12, 13):
                    line = (f"[{task_id}] suite-run №{run_no} (полный набор): "
                            f"прогон не уложился в предел {n} с (источник: "
                            f"профиль тестов проекта pabcdefgh) и оборван — "
                            f"числа и упавшие по успевшей части")
                    if module.standalone(limit_value, line):
                        bad.append((seed, task_id, run_no, n))
        self.assertEqual(bad[:5], [], f"строки с отдельно стоящим "
                         f"{limit_value}: {len(bad)}")

    def test_ac1_fixture_ids_have_no_digits_after_prefix(self):
        """После префикса в id задачи фикстуры нет цифр — ни при одном зерне набора.

        Сценарий: 3000 фиксированных зёрен, id генератора фикстуры; часть id
        после `01M` не содержит ни одной цифры и не пуста. Это структурная
        форма свойства: число в id не может дать отдельно стоящего значения
        config ни при каком зерне.

        Ловит мутацию: в алфавит генератора вернули цифры (или одну цифру
        «6»/«0») — на 3000 зёрнах id с цифрой после префикса находится
        всегда.
        """
        bad = [(seed, tid) for seed, tid in self.fixture_ids()
               if not tid.startswith(PREFIX) or len(tid) <= len(PREFIX)
               or re.search(r"\d", tid[len(PREFIX):])]
        self.assertEqual(bad[:5], [], f"ids с цифрами после префикса или без "
                         f"префикса: {len(bad)}")

    def test_ac1_standalone_assertion_of_method_is_unchanged(self):
        """Утверждение «нет отдельно стоящего COPY_LIMIT» в методе осталось прежним.

        Сценарий: исходный текст метода предела `suite-run` содержит
        `self.assertFalse(any(standalone(self.COPY_LIMIT, line) for line in
        lines)…` (пробелы и переносы не важны), а `standalone` по-прежнему
        не считает отдельно стоящим число, примыкающее к цифре, точке или
        двоеточию, и считает — окружённое буквами.

        Ловит мутацию: флейк «починили» правкой утверждения, а не фикстуры —
        `assertFalse` убран или переписан (например, на `self.COPY_LIMIT in
        line.split()`), либо `standalone` стал считать букву границей.
        """
        module = limit_module()
        method = getattr(getattr(module, LIMIT_CLASS), LIMIT_METHOD)
        source = re.sub(r"\s+", "", inspect.getsource(method))
        self.assertIn(
            "self.assertFalse(any(standalone(self.COPY_LIMIT,line)forlineinlines)",
            source)
        self.assertTrue(module.standalone(60, "K60X"))
        self.assertTrue(module.standalone(60, "в 60 с"))
        for text in ("160", "601", "0.60", "60.5", "1:60"):
            with self.subTest(text=text):
                self.assertFalse(module.standalone(60, text))


if __name__ == "__main__":
    unittest.main()
