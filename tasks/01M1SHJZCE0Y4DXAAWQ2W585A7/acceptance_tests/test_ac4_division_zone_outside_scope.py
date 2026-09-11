"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-4 (`scripts/guard.py`
отказывает SPEC, если хотя бы одна зона подраздела секции «## Деление» не
входит ни в зоны родителя (frontmatter `zones:`), ни в общие зоны
(`orchestrator/config.py::COMMON_ZONES`) — сообщение называет непокрытую
зону и подраздел) и AC-14 (тест того же критерия).

Оба теста дают подразделу зону-элемент `config.COMMON_ZONES` (не входящую
в зоны родителя), чтобы проверить, что guard принимает её ЧЕРЕЗ общий
список, а не только через зоны родителя — мутация «код сверяет зону
только со списком родителя, забыв про общие зоны» иначе осталась бы
незамеченной (общая зона ошибочно попала бы в «непокрытые» вместе с
настоящим нарушением). AC-4 ставит нарушение во ВТОРОЙ (последний)
подраздел двухчастного деления, AC-14 — в ПЕРВЫЙ подраздел трёхчастного
(верхняя треть валидного диапазона 2-4), чтобы отказ не зависел от
позиции нарушителя.

Красен до реализации: `scripts/guard.py` сегодня не читает секцию
«## Деление» вовсе (см. докстринг `test_ac2_division_subsection_count.py`)
— оба теста ниже покраснеют на пустом списке ошибок, пока разработчик не
добавит проверку принадлежности зон подраздела.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FIXTURE_ZONE, check, division_subsection  # noqa: E402
from orchestrator import config  # noqa: E402

COMMON_ZONE = config.COMMON_ZONES[0]
FOREIGN_ZONE = "totally/unrelated/module/outside/scope.py"


class ZoneOutsideScopeInLastSubsectionTest(unittest.TestCase):
    """Деление на 2 части: первая берёт зону родителя, вторая — одну зону
    из `COMMON_ZONES` (валидно, родитель её не заявлял) и одну зону,
    которой нет ни у родителя, ни в `COMMON_ZONES` (нарушение).

    Ловит мутацию: сверка «зона подраздела входит в зоны родителя ИЛИ в
    COMMON_ZONES» реализована только через «И» (пересечение) вместо «ИЛИ»,
    либо не учитывает `COMMON_ZONES` вовсе — либо ложно отказала бы
    валидной общей зоне, либо не назвала бы по-настоящему чужую.
    """

    SECOND_TITLE = "Вторая часть с нарушением зоны"

    def test_ac4_foreign_zone_is_refused_and_named_common_zone_is_not(self):
        first = division_subsection(
            "Первая часть", zones=FIXTURE_ZONE,
            order="первая, без зависимостей",
            tz_text="Текст ТЗ первой части фикстуры зоны вне охвата.")
        second = division_subsection(
            self.SECOND_TITLE, zones=f"{COMMON_ZONE}, {FOREIGN_ZONE}",
            order="после части 1",
            tz_text="Текст ТЗ второй части фикстуры зоны вне охвата.")

        errors = check(zones=FIXTURE_ZONE, subsections=[first, second])

        self.assertTrue(
            errors,
            f"guard принял подраздел «{self.SECOND_TITLE}» с зоной "
            f"{FOREIGN_ZONE!r}, не входящей ни в зоны родителя, ни в "
            f"COMMON_ZONES — ожидался отказ (AC-4)")
        combined = " ".join(errors)
        self.assertIn(
            FOREIGN_ZONE, combined,
            f"отказ guard'а не называет непокрытую зону {FOREIGN_ZONE!r} "
            f"(AC-4): {errors}")
        self.assertIn(
            self.SECOND_TITLE, combined,
            f"отказ guard'а не называет подраздел «{self.SECOND_TITLE}» "
            f"с непокрытой зоной (AC-4): {errors}")
        self.assertNotIn(
            COMMON_ZONE, combined,
            f"отказ guard'а ошибочно жалуется на зону {COMMON_ZONE!r} из "
            f"COMMON_ZONES, хотя она валидна сама по себе (AC-4): {errors}")


class ZoneOutsideScopeInFirstSubsectionTest(unittest.TestCase):
    """Деление на 3 части: нарушитель — ПЕРВЫЙ подраздел, второй и третий
    валидны (через зону родителя). Отказ не должен зависеть от позиции
    подраздела-нарушителя в секции.

    Ловит мутацию: код сверяет зоны только последнего подраздела секции
    (например цикл сохраняет состояние только с последней итерации) —
    нарушение в НЕ последнем подразделе осталось бы незамеченным.
    """

    FIRST_TITLE = "Первая часть с нарушением зоны"

    def test_ac14_foreign_zone_in_first_subsection_is_refused_and_named(self):
        first = division_subsection(
            self.FIRST_TITLE, zones=FOREIGN_ZONE,
            order="первая, без зависимостей",
            tz_text="Текст ТЗ первой части трёхчастной фикстуры.")
        second = division_subsection(
            "Вторая часть", zones=FIXTURE_ZONE, order="после части 1",
            tz_text="Текст ТЗ второй части трёхчастной фикстуры.")
        third = division_subsection(
            "Третья часть", zones=FIXTURE_ZONE, order="после части 2",
            tz_text="Текст ТЗ третьей части трёхчастной фикстуры.")

        errors = check(zones=FIXTURE_ZONE, subsections=[first, second, third])

        self.assertTrue(
            errors,
            f"guard принял подраздел «{self.FIRST_TITLE}» с зоной "
            f"{FOREIGN_ZONE!r}, не входящей ни в зоны родителя, ни в "
            f"COMMON_ZONES — ожидался отказ (AC-14)")
        combined = " ".join(errors)
        self.assertIn(
            FOREIGN_ZONE, combined,
            f"отказ guard'а не называет непокрытую зону {FOREIGN_ZONE!r} "
            f"в первом подразделе (AC-14): {errors}")


if __name__ == "__main__":
    unittest.main()
