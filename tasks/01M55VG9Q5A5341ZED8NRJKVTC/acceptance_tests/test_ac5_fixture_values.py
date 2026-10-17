"""Данные фикстуры целевого теста не дают отдельно стоящего значения config
копии пульта в строке «не уложился» ни при каком зерне.

Группа: разовый
Красен до реализации: id задачи фикстуры — «01M» + 23 символа ALPHABET с цифрами, около 1% зёрен даёт в «[<id>]» отдельно стоящее 60 = COPY_LIMIT (например …K60X…).

Фикстура строится тем же экземпляром целевого класса, что и в тесте
(`SuiteRunProfileLimitTest`): генератор зерна — его `rng`, id задачи — его
`task_id()`, имя проекта — `"p" + word()` (`add_project_task`); значение
config копии — `COPY_LIMIT` класса (его дописывает в `config.py` копии
`SuiteRunLimitSandbox.setUp`). Каждое значение проверяется в своём
окружении строки отчёта `render` (`orchestrator/suite_run.py:439`,
`:432-433`): `[<id>] suite-run №<n> (…)`, `проекта <имя>)`. «Отдельно
стоящее» — определение помощника `standalone` на main.
"""
import importlib
import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutant  # noqa: E402

SEEDS = 20000
RUN_NUMBERS = (1,)


def main_standalone(number: int, text: str) -> bool:
    """Определение помощника на main (`:119-120`)."""
    return re.search(rf"(?<![\d.:]){number}(?![\d.:])", text) is not None


class FixtureValuesTest(unittest.TestCase):

    def test_ac5_fixture_values_never_give_standalone_config_value(self):
        """На 20 000 зёрен id, имя проекта и №прогона не дают config в строке.

        Сценарий: для каждого зерна (база зёрен случайна и печатается)
        экземпляр целевого класса получает `rng = Random(зерно)`; его
        `task_id()` в «[<id>] suite-run №1 (полный набор)», имя проекта
        «p» + `word()` в «(источник: профиль тестов проекта <имя>)» — ни в
        одном нет отдельно стоящего `COPY_LIMIT`.

        Ловит мутацию: id фикстуры по-прежнему из ALPHABET с цифрами (или
        `COPY_LIMIT` сменён на число, которое id всё равно может дать) — за
        20 000 зёрен находится id с отдельно стоящим значением config,
        метод красен.
        """
        root = str(_mutant.code_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        module = importlib.import_module(_mutant.TARGET_MODULE)
        cls = getattr(module, _mutant.TARGET_CLASS)
        copy_limit = cls.COPY_LIMIT
        base = random.randrange(1 << 30)
        print(f"база зёрен: {base}")
        case = cls(_mutant.TARGET_METHOD)
        for seed in range(base, base + SEEDS):
            case.seed = seed
            case.rng = random.Random(seed)
            target = "p" + case.word()
            task_id = case.task_id()
            pieces = [f"[{task_id}] suite-run №{n} (полный набор): прогон"
                      for n in RUN_NUMBERS]
            pieces.append(f"(источник: профиль тестов проекта {target}) и "
                          f"оборван")
            for piece in pieces:
                self.assertFalse(
                    main_standalone(copy_limit, piece),
                    f"зерно {seed} (база {base}): в «{piece}» отдельно стоит "
                    f"значение config копии {copy_limit}")


if __name__ == "__main__":
    unittest.main()
