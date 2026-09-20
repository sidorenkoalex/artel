"""AC-8: approve на `spec_gate` отказывает по неклассифицированному пути
SPEC и не переписывает `tasks.zones`.

Красен до реализации: `fsm._approve_spec_gate` сегодня вовсе не сверяет текст SPEC с `zones:` — он безусловно пишет `store.update_task(conn, task_id, zones=meta.get("zones"))` (orchestrator/fsm.py:726) и уводит задачу на `tests_writing`, так что не будет ни отказа, ни сохранённой метки-часового.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from _gate_sandbox import SpecGateSandbox  # noqa: E402


class SpecGateRefusesUnclassifiedPathTest(SpecGateSandbox):

    def setUp(self):
        super().setUp()
        # Путь назван в «## Требования»; frontmatter `zones:` его не
        # покрывает, в «## Не входит»/«## Материалы» он не назван.
        self.arrange_gate(
            requirement=f"Починить разбор ответа в {_util.UNCLASSIFIED_PATH}.",
            zones=_util.ZONE_PATH)

    def test_ac8_approve_refuses_naming_the_path(self):
        """Отказ approve называет неклассифицированный путь и несёт ту
        же подсказку, что отказ `new` (AC-2).

        Ловит мутацию: сверка на гейте написана своим, отдельным от
        `new` текстом отказа без подсказки «назови в Зонах…» —
        Оператор на гейте не узнал бы, чем чинить SPEC.
        """
        text = self.run_approve()

        _util.assert_unclassified_refusal(self, text, _util.UNCLASSIFIED_PATH)

    def test_ac8_task_stays_on_the_spec_gate(self):
        """Переход не выполняется: задача остаётся в состоянии
        `spec_gate`.

        Ловит мутацию: сверка зовётся, отказ печатается, но выполнение
        `_approve_spec_gate` не прерывается (нет `return`/`sys.exit`) —
        задача всё равно ушла бы на `tests_writing`.
        """
        text = self.run_approve()

        self.assertEqual(self.state(), "spec_gate",
                         f"задача ушла с гейта вопреки отказу:\n{text}")

    def test_ac8_zones_column_is_not_overwritten_by_this_spec(self):
        """`tasks.zones` не переписан значением этого SPEC: в колонке
        осталась метка, стоявшая до approve.

        Ловит мутацию: сверка вставлена ПОСЛЕ `store.update_task(...,
        zones=...)` (строка 726 `orchestrator/fsm.py`), а не до неё, как
        требует критерий — отказ был бы виден, но колонка уже несла бы
        `zones:` непринятого SPEC.
        """
        text = self.run_approve()

        self.assertEqual(self.zones_column(), self.ZONES_SENTINEL,
                         f"колонка zones переписана отказанным SPEC:\n{text}")


if __name__ == "__main__":
    unittest.main()
