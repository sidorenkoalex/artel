"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-2 (`scripts/guard.py`
отказывает SPEC, если число подразделов секции «## Деление» меньше 2 или
больше 4 — сообщение называет фактическое число).

`_sandbox.py::check` — чёрный ящик над `guard.check_content`. Обе
фикстуры ниже несут только валидные подразделы (зоны совпадают с
frontmatter `zones:` родителя, все обязательные поля на месте) — единственная
переменная между тестами и валидным сценарием (соседние файлы AC-5/AC-11)
это ЧИСЛО подразделов, так что красноту/зелень assertion решает только
проверяемая этим AC граница, не побочные ошибки формата.

Красен до реализации: `scripts/guard.py` сегодня не читает секцию
«## Деление» вовсе (проверено `grep -n "Деление" scripts/guard.py` —
пусто, кроме несвязанного `SPLIT_ASSESSMENT_SECTION = "Оценка объёма и
деление"`, другое имя секции) — `guard.check_content` не видит новых
подразделов и не может назвать их число, оба теста ниже покраснеют на
`assertIn` числа в сообщении (список ошибок пуст либо не содержит его),
пока разработчик не добавит проверку количества подразделов.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FIXTURE_ZONE, check, division_subsection  # noqa: E402


def _valid_subsection(n: int) -> str:
    order = "первая, без зависимостей" if n == 1 else f"после части {n - 1}"
    return division_subsection(
        f"Часть {n}", zones=FIXTURE_ZONE, order=order,
        tz_text=f"Текст ТЗ части {n} фикстуры количества подразделов.")


class TooFewSubsectionsTest(unittest.TestCase):
    """Ровно 1 подраздел — меньше нижней границы диапазона 2-4.

    Ловит мутацию: нижняя граница диапазона сдвинута (например `< 2`
    заменено на `< 1`, что молча приняло бы единственный подраздел) —
    список ошибок остался бы пустым вместо отказа, называющего число 1.
    """

    def test_ac2_single_subsection_is_refused_and_count_named(self):
        errors = check(zones=FIXTURE_ZONE, subsections=[_valid_subsection(1)])

        self.assertTrue(
            errors,
            "guard принял SPEC с 1 подразделом секции «## Деление» — "
            "ожидался отказ (AC-2)")
        self.assertTrue(
            any("1" in e and ("Деление" in e or "подразд" in e.lower())
               for e in errors),
            f"отказ guard'а для SPEC с 1 подразделом секции «## Деление» "
            f"не называет фактическое число подразделов (AC-2): {errors}")


class TooManySubsectionsTest(unittest.TestCase):
    """Ровно 5 подразделов — больше верхней границы диапазона 2-4.

    Ловит мутацию: верхняя граница диапазона сдвинута (например `> 4`
    заменено на `> 5`, что молча приняло бы пятый подраздел) — список
    ошибок остался бы пустым вместо отказа, называющего число 5.
    """

    def test_ac2_five_subsections_is_refused_and_count_named(self):
        subsections = [_valid_subsection(n) for n in range(1, 6)]

        errors = check(zones=FIXTURE_ZONE, subsections=subsections)

        self.assertTrue(
            errors,
            "guard принял SPEC с 5 подразделами секции «## Деление» — "
            "ожидался отказ (AC-2)")
        self.assertTrue(
            any("5" in e and ("Деление" in e or "подразд" in e.lower())
               for e in errors),
            f"отказ guard'а для SPEC с 5 подразделами секции «## Деление» "
            f"не называет фактическое число подразделов (AC-2): {errors}")


if __name__ == "__main__":
    unittest.main()
