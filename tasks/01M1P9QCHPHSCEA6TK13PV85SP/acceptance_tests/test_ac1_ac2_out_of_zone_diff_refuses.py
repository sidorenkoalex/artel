"""AC-1/AC-2 (tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md): переход
`in_dev -> review` отклоняется, если дифф ветки задачи к main трогает
файлы вне заявленных в `zones` задачи путей и вне общего списка
`orchestrator/config.COMMON_ZONES` (AC-1); отказ называет конкретные
файлы диффа, лежащие вне зон, а не общую формулировку (AC-2).

Красен до реализации: `orchestrator/fsm_advance.py::in_dev` сегодня не
сверяет дифф с `zones` вовсе — переход в `review` проходит для ЛЮБОГО
диффа, пока PLAN.md ready и лок/свежесть/ёмкость в порядке; ни один из
тестов ниже не проходит без новой сверки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZonesGateSandbox  # noqa: E402


class Ac1OutOfZoneDiffRefusesTest(ZonesGateSandbox):

    def test_ac1_diff_touching_a_file_outside_declared_and_common_zones_refuses(self):
        """Дифф трогает файл, которого нет ни в объявленных `zones`
        задачи, ни в общем списке зон — переход обязан остаться в
        `in_dev`, не дойти до `review`.

        Ловит мутацию: сверка диффа с зонами не подключена к переходу
        (условие `_zones_gate_refuses`-подобной функции удалено из
        цепочки `in_dev`, либо всегда возвращает `False`) — переход
        прошёл бы в `review` для любого диффа, как сегодня до
        реализации."""
        self.set_zones("orchestrator/store.py")

        self.advance_with_diff_files(["docs/unrelated_note.md"])

        self.assertEqual(
            self.state(), "in_dev",
            "дифф трогает docs/unrelated_note.md — путь вне zones "
            "('orchestrator/store.py') и вне COMMON_ZONES, переход "
            "обязан отказать (AC-1)")


class Ac2RefusalNamesTheFilesTest(ZonesGateSandbox):

    def test_ac2_refusal_names_the_exact_out_of_zone_files(self):
        """Отказ по AC-1 называет ОБА конкретных файла диффа, лежащих
        вне зон, а не общую формулировку вида «дифф вне зон».

        Ловит мутацию: отказ печатает/журналирует общую фразу без
        перечисления файлов (например «дифф трогает файлы вне
        заявленных зон» без имён) — тест не нашёл бы конкретные пути в
        объединённом тексте вывода и журнала."""
        self.set_zones("orchestrator/store.py")

        out = self.advance_with_diff_files(
            ["docs/unrelated_note.md", "scripts/unexpected_tool.py"])

        combined = out + "\n".join(self.journal_details())
        self.assertIn("docs/unrelated_note.md", combined,
                     "первый файл вне зон обязан быть назван по имени (AC-2)")
        self.assertIn("scripts/unexpected_tool.py", combined,
                     "второй файл вне зон обязан быть назван по имени, не "
                     "поглощён общей формулировкой (AC-2)")

    def test_ac2_refusal_is_journaled_the_same_way_as_other_advance_refusals(self):
        """Отказ ложится в `store.journal` тем же способом, что и
        остальные отказы `advance` (лок планки, свежесть, гейт
        ёмкости) — предпосылка доставки через T078 (AC-5).

        Ловит мутацию: отказ печатается в stdout, но не журналируется
        через `store.journal` — `journal_details()` остался бы пустым,
        и AC-5 (история отказов для следующего запуска роли) молча
        сломалась бы, даже если AC-1 внешне выглядит рабочим."""
        self.set_zones("orchestrator/store.py")

        self.advance_with_diff_files(["docs/unrelated_note.md"])

        details = self.journal_details()
        self.assertTrue(
            any("docs/unrelated_note.md" in d for d in details),
            f"отказ гейта зон обязан лечь в store.journal с именем файла: "
            f"{details}")


if __name__ == "__main__":
    unittest.main()
