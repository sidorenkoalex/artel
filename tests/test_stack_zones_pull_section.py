"""Сторож раздела `docs/stack.md` о зонах и подтяжке main (SPEC
01M3GKJ84XM5QPC6TK5EE307Q9, требование 10, AC-13).

Тем же приёмом, что `tests/test_stack_parity_table.py`: документ
проверяется как данные, а якоря берутся ИЗ КОДА (действие журнала,
набор состояний, имя файла карты), а не переписаны сюда литералами —
иначе переименование в коде оставляло бы документ обещать механику,
которой нет, на зелёном тесте.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, pull, zone_lock  # noqa: E402

#: Раздел ищется по подстроке заголовка, а не по точной формулировке:
#: предмет требования — наличие раздела о зонах и подтяжке, не его имя.
SECTION_MARKERS = ("Зоны", "подтяжка main")


def stack_md_text() -> str:
    return config.ROOT.joinpath("docs", "stack.md").read_text(encoding="utf-8")


def section_body(text: str) -> str:
    """Тело раздела `## …`, чей заголовок несёт все `SECTION_MARKERS` —
    до следующего заголовка того же уровня; пустая строка, если такого
    раздела нет."""
    body: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = all(marker in line for marker in SECTION_MARKERS)
            continue
        if inside:
            body.append(line)
    return "\n".join(body)


class StackZonesPullSectionTest(unittest.TestCase):

    def setUp(self):
        # Пробелы нормализуются: документ свёрнут по ~72 символа, и любая
        # искомая фраза может быть разорвана переносом строки — сторож
        # проверяет наличие формулировки, не её раскладку по строкам.
        self.body = " ".join(section_body(stack_md_text()).split())

    def test_section_describes_the_new_warning_and_the_status_mark(self):
        """Раздел называет предупреждение `new` о пересечении зон (его
        действие журнала), пометку `status` «зона занята» и все три
        состояния, которые её получают.

        Ловит мутацию: действие журнала переименовано в коде, а раздел
        остался прежним — Оператор искал бы в журнале запись по тексту,
        которого там нет; либо из перечня состояний выпало одно, и
        документ обещал бы пометку не на всех задачах волны."""
        self.assertTrue(self.body,
                        "в docs/stack.md нет раздела о зонах и подтяжке main")
        self.assertIn(catalog.ZONE_OVERLAP_ACTION, self.body)
        self.assertIn("зона занята", self.body)
        for state in zone_lock.LATER_STATES:
            with self.subTest(state=state):
                self.assertIn(state, self.body)

    def test_section_lists_what_the_pull_merges_itself(self):
        """Раздел перечисляет то, что подтяжка сливает сама: карту
        кодовой базы и аддитивный конфликт документов, с порядком добавок
        «main, затем ветка».

        Ловит мутацию: из раздела исчезает аддитивное слияние (или имя
        файла карты разошлось с `pull.MAP_REL`) — механику, которую
        Оператор наблюдает по журналу, документ не объясняет, и
        следующая волна снова читает её по исходникам."""
        self.assertIn(pull.MAP_REL, self.body)
        self.assertIn("аддитив", self.body.lower())
        self.assertIn("main, затем ветка", self.body)

    def test_section_lists_what_the_pull_escalates(self):
        """Раздел перечисляет то, что подтяжка эскалирует: изменение или
        удаление базовой строки, не-документ в наборе, добавление файла
        обеими сторонами и неуспешный ответ git (fail-closed).

        Ловит мутацию: перечень «эскалирует» сведён к одному пункту —
        Оператор ждал бы автоматики там, где её нет, и читал бы
        эскалацию как дефект пульта, а не как её штатный исход."""
        lowered = self.body.lower()
        for marker in ("базов", "не-документ", "обеими сторонами",
                       "fail-closed"):
            with self.subTest(marker=marker):
                self.assertIn(marker, lowered)


if __name__ == "__main__":
    unittest.main()
