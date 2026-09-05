"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-3 (`scripts/guard.py`
отказывает SPEC, если у подраздела секции «## Деление» отсутствует
обязательное поле — название, `Зоны:`, `Порядок:` либо пуст текст ТЗ —
сообщение называет отсутствующее поле и подраздел) и AC-13 (тест того же
критерия: секция с подразделом без обязательного поля отказывает и
называет отсутствующее поле).

Оба AC описывают одно и то же свойство guard'а (AC-13 — «тестовая»
формулировка AC-3, повтор из раздела SPEC «Критерии приёмки» пункта 5
«Тесты») — файл несёт два теста на РАЗНЫХ полях (AC-3: отсутствует
`Порядок:` целиком; AC-13: поле `Порядок:` на месте, но текст ТЗ подраздела
пуст), чтобы каждый тест ловил свою мутацию, а не дублировал сценарий
соседнего.

Красен до реализации: `scripts/guard.py` сегодня не читает секцию
«## Деление» вовсе (см. докстринг `test_ac2_division_subsection_count.py`)
— оба теста ниже покраснеют на пустом списке ошибок, пока разработчик не
добавит проверку обязательных полей подраздела.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FIXTURE_ZONE, check, division_subsection  # noqa: E402

VALID_SECOND_TITLE = "Вторая часть"


class MissingOrderFieldTest(unittest.TestCase):
    """Первый подраздел не несёт поля `Порядок:` вовсе (второй — валиден).

    Ловит мутацию: проверка обязательных полей подраздела не смотрит на
    `Порядок:` (например код проверяет только название и `Зоны:`) — SPEC
    с полностью пропущенным полем прошёл бы `check_content` без единой
    ошибки.
    """

    TITLE = "Первая часть без порядка"

    def test_ac3_missing_order_field_is_refused_and_named(self):
        broken = "\n".join([
            f"### {self.TITLE}", "", f"Зоны: {FIXTURE_ZONE}", "",
            "Текст ТЗ первой части без обязательного поля Порядок.",
        ])
        valid = division_subsection(
            VALID_SECOND_TITLE, zones=FIXTURE_ZONE, order="после части 1",
            tz_text="Текст ТЗ второй части фикстуры пропущенного поля.")

        errors = check(zones=FIXTURE_ZONE, subsections=[broken, valid])

        self.assertTrue(
            errors,
            f"guard принял подраздел «{self.TITLE}» секции «## Деление» "
            f"без поля Порядок: — ожидался отказ (AC-3)")
        combined = " ".join(errors)
        self.assertIn(
            "Порядок", combined,
            f"отказ guard'а не называет отсутствующее поле 'Порядок' "
            f"(AC-3): {errors}")
        self.assertIn(
            self.TITLE, combined,
            f"отказ guard'а не называет подраздел «{self.TITLE}» с "
            f"пропущенным полем (AC-3): {errors}")


class EmptyTzTextTest(unittest.TestCase):
    """Второй подраздел несёт все поля, но пустой текст ТЗ (первый —
    валиден).

    Ловит мутацию: проверка обязательных полей ограничена только
    название/`Зоны:`/`Порядок:` и не смотрит на непустоту текста ТЗ после
    них — подраздел без единого слова свободного текста прошёл бы
    `check_content` без ошибок, хотя `TZ.md` будущей подзадачи (AC-5)
    остался бы пустым.
    """

    TITLE = "Вторая часть без текста ТЗ"

    def test_ac13_empty_tz_text_is_refused_and_field_named(self):
        valid = division_subsection(
            "Первая часть", zones=FIXTURE_ZONE,
            order="первая, без зависимостей",
            tz_text="Текст ТЗ первой части фикстуры пустого текста ТЗ.")
        broken = "\n".join([
            f"### {self.TITLE}", "", f"Зоны: {FIXTURE_ZONE}",
            "Порядок: после части 1", "",
        ])

        errors = check(zones=FIXTURE_ZONE, subsections=[valid, broken])

        self.assertTrue(
            errors,
            f"guard принял подраздел «{self.TITLE}» секции «## Деление» "
            f"с пустым текстом ТЗ — ожидался отказ (AC-13)")
        combined = " ".join(errors)
        self.assertIn(
            self.TITLE, combined,
            f"отказ guard'а не называет подраздел «{self.TITLE}» с "
            f"пустым текстом ТЗ (AC-13): {errors}")
        self.assertIn(
            "ТЗ", combined,
            f"отказ guard'а не называет отсутствующее поле — текст ТЗ "
            f"(AC-13): {errors}")


if __name__ == "__main__":
    unittest.main()
