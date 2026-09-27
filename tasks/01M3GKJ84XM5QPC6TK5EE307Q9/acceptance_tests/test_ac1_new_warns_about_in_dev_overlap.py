"""AC-1 — 01M3GKJ84XM5QPC6TK5EE307Q9: `new --tz` предупреждает о
пересечении зон ТЗ с зоной задачи в `in_dev`, но задачу заводит.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `new --tz` с ТЗ, чья строка `Зоны:` пересекается с зоной задачи в
`in_dev`, печатает предупреждение, содержащее id этой задачи, её
состояние и общий путь, и пишет запись журнала «пересечение зон при
заведении» в журнал заведённой задачи; задача при этом заведена, код
возврата — тот же, что у `new` без пересечения.

Задача-держатель заводится БЕЗ маркера «занимает зону»: SPEC требование 1
прямо снимает признак `zone_lock._occupies` со сверки при заведении —
это прогноз будущей очереди, а не отказ `zone_lock.refusal`.

Красен до реализации: сегодняшний `catalog.cmd_new` сверки зон не делает
вовсе — ни предупреждения в stdout, ни записи журнала «пересечение зон
при заведении» не появляется, и оба ассерта падают.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import store  # noqa: E402

HOLDER = "T801"
SHARED_ZONE = "orchestrator/pull.py"


class NewWarnsAboutInDevOverlapTest(_sandbox.ZoneOverlapSandbox):

    def test_ac1_new_warns_and_journals_overlap_with_in_dev_task(self):
        """Задача T801 в `in_dev` держит зону `orchestrator/pull.py`;
        `new --tz` с той же зоной печатает строку, где разом названы id
        T801, её состояние `in_dev` и общий путь, и пишет в журнал ИМЕННО
        заведённой задачи запись с фиксированным действием «пересечение
        зон при заведении».

        Ловит мутацию: предупреждение собрано без состояния держателя
        (или id держателя ушёл в detail записи журнала, а действие
        осталось вариативным текстом) — строка вывода не содержит всех
        трёх частей разом, а `assertIn` по действию журнала не находит
        фиксированного текста.
        """
        self.seed_task(HOLDER, "in_dev", SHARED_ZONE)

        out, new_id = self.new_with_zones(SHARED_ZONE)

        warnings = _sandbox.lines_mentioning(out, HOLDER)
        self.assertTrue(
            warnings,
            f"`new` не назвал задачу {HOLDER}, чья зона {SHARED_ZONE} "
            f"пересекается с зонами ТЗ:\n{out}")
        self.assertTrue(
            any("in_dev" in line and SHARED_ZONE in line for line in warnings),
            f"предупреждение обязано называть состояние держателя и общий "
            f"путь в одной строке с его id, получено: {warnings}")
        self.assertIn(
            _sandbox.OVERLAP_ACTION, self.journal_actions(new_id),
            f"в журнале заведённой задачи {new_id} нет записи с "
            f"фиксированным действием «{_sandbox.OVERLAP_ACTION}»: "
            f"{self.journal_actions(new_id)}")

    def test_ac1_overlap_does_not_turn_new_into_a_refusal(self):
        """Два заведения подряд — без пересечения и с пересечением —
        одинаково возвращают id заведённой задачи, и обе строки задач
        существуют в `spec_writing`: предупреждение отказом не
        становится.

        Ловит мутацию: сверка пересечения оформлена как `sys.exit(...)`
        по образцу соседнего отказа `_tz_path_refusal` — второй вызов
        поднял бы `SystemExit`, и строки задачи не появилось бы.
        """
        _, control_id = self.new_with_zones(SHARED_ZONE, title="Без пересечения")
        self.seed_task(HOLDER, "in_dev", SHARED_ZONE)

        _, overlapped_id = self.new_with_zones(SHARED_ZONE, title="С пересечением")

        self.assertTrue(control_id and overlapped_id,
                        "оба вызова `new` обязаны вернуть id заведённой задачи")
        self.assertNotEqual(control_id, overlapped_id)
        for task_id in (control_id, overlapped_id):
            row = store.get_task(self.conn, task_id)
            self.assertEqual(
                row["state"], "spec_writing",
                f"задача {task_id} обязана быть заведена в том же "
                f"состоянии, что и без пересечения зон")


if __name__ == "__main__":
    unittest.main()
