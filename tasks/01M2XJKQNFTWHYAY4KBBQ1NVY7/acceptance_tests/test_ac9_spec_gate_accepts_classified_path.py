"""AC-9: approve на `spec_gate` проходит, когда путь SPEC назван в
«## Материалы» либо в «## Не входит».

Зелёный с рождения: `fsm._approve_spec_gate` сегодня не сверяет текст SPEC с зонами вовсе и уводит задачу с гейта при любом содержании — сценарии проверяют ОТСУТСТВИЕ отказа и покраснеют ровно на ложном срабатывании новой сверки (классифицирующие разделы SPEC перечислены неполно).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from _gate_sandbox import SpecGateSandbox  # noqa: E402

REQUIREMENT = f"Починить разбор ответа в {_util.UNCLASSIFIED_PATH}."


class SpecGateAcceptsClassifiedPathTest(SpecGateSandbox):

    def _assert_gate_passed(self, text: str) -> None:
        _util.assert_no_unclassified_refusal(self, text)
        self.assertNotEqual(self.state(), "spec_gate",
                            f"задача осталась на гейте:\n{text}")

    def test_ac9_path_named_in_materials_passes(self):
        """Тот же SPEC, что в AC-8 отказывает, но путь назван в разделе
        «## Материалы» — approve проходит, задача уходит с гейта.

        Ловит мутацию: классифицирующими для SPEC считаются только
        frontmatter `zones:` и «## Не входит» (раздел «## Материалы»
        забыт) — каждый SPEC, честно перечисливший источники, упирался
        бы в отказ гейта.
        """
        self.arrange_gate(requirement=REQUIREMENT, zones=_util.ZONE_PATH,
                          materials=f"Адрес кода: {_util.UNCLASSIFIED_PATH}.")

        text = self.run_approve()

        self._assert_gate_passed(text)

    def test_ac9_path_named_in_not_included_passes(self):
        """Тот же путь назван в разделе «## Не входит» — approve тоже
        проходит.

        Ловит мутацию: разбор «## Не входит» привязан к точному
        заголовку другого уровня/написания и раздел не находится —
        объявленное вне объёма всё равно требовало бы зоны.
        """
        self.arrange_gate(
            requirement=REQUIREMENT, zones=_util.ZONE_PATH,
            not_included=f"Изменение {_util.UNCLASSIFIED_PATH}.")

        text = self.run_approve()

        self._assert_gate_passed(text)

    def test_ac9_passing_gate_writes_the_spec_zones_into_the_task(self):
        """Прошедший гейт по-прежнему записывает `zones:` SPEC в
        `tasks.zones` — сверка вставлена ПЕРЕД записью, а не вместо неё
        (оборотная сторона оговорки AC-8 «`tasks.zones` значением этого
        SPEC не переписан»: на отказе не переписан, на проходе —
        переписан).

        Ловит мутацию: новая проверка заменила собой
        `store.update_task(..., zones=...)` (или вернула управление
        раньше неё на успешном пути) — колонка осталась бы с меткой,
        стоявшей до approve, и механика зон задачи ослепла бы.
        """
        self.arrange_gate(requirement=REQUIREMENT, zones=_util.ZONE_PATH,
                          materials=f"Адрес кода: {_util.UNCLASSIFIED_PATH}.")

        text = self.run_approve()

        self._assert_gate_passed(text)
        self.assertEqual(self.zones_column(), _util.ZONE_PATH,
                         f"zones SPEC не доехали до колонки задачи:\n{text}")


if __name__ == "__main__":
    unittest.main()
