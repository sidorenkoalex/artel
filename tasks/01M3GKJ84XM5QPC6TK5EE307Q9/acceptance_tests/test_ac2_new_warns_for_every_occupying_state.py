"""AC-2 — 01M3GKJ84XM5QPC6TK5EE307Q9: предупреждение `new` печатается для
задачи в `tests_writing`, в `spec_writing`/`spec_gate` и в любом
состоянии из `zone_lock.BLOCKING_STATES`.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. То же предупреждение печатается при пересечении с задачей в
`tests_writing` (задача, которая займёт зону позже), а также при
пересечении с задачей в `spec_writing`/`spec_gate` и с задачей в любом
другом состоянии из `zone_lock.BLOCKING_STATES`.

Набор состояний берётся из `zone_lock.BLOCKING_STATES` ДИНАМИЧЕСКИ, не
списком литералов: диапазон занимающих фаз — крутилка системы (`escalated`
в него однажды уже добавляли), и планка обязана пережить её поворот.
Каждому состоянию даётся СВОЯ зона: так одно заведение проверяет сразу
весь набор, и промах по одному состоянию виден поимённо.

Красен до реализации: `catalog.cmd_new` сегодня не печатает ни одного
предупреждения о зонах — в выводе нет ни одного id задачи-держателя.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import zone_lock  # noqa: E402

#: Состояния, чьё пересечение обязано дать предупреждение: занимающие
#: зону сейчас плюс те, что займут её позже (SPEC требование 1).
WARNED_STATES = tuple(zone_lock.BLOCKING_STATES) + _sandbox.PRE_DEV_STATES


class NewWarnsForEveryOccupyingStateTest(_sandbox.ZoneOverlapSandbox):

    def test_ac2_every_occupying_and_pre_dev_state_is_named_in_the_warning(self):
        """На каждое состояние набора заведена своя задача со своей
        зоной; ТЗ называет все эти зоны разом. Вывод `new` обязан
        назвать КАЖДУЮ задачу — с её состоянием и её общим путём в той
        же строке.

        Ловит мутацию: сверка ограничена `zone_lock.BLOCKING_STATES` и не
        добавляет `spec_writing`/`spec_gate`/`tests_writing` (или,
        наоборот, смотрит только на дозаводские состояния) — пропущенные
        состояния будут перечислены в тексте ассерта поимённо.
        """
        zones = {}
        for index, state in enumerate(WARNED_STATES):
            task_id = f"T8{index:02d}"
            zone = f"orchestrator/zona_{index}.py"
            self.seed_task(task_id, state, zone)
            zones[task_id] = (state, zone)

        out, _new_id = self.new_with_zones(", ".join(
            zone for _state, zone in zones.values()))

        missed = []
        for task_id, (state, zone) in sorted(zones.items()):
            named = [line for line in _sandbox.lines_mentioning(out, task_id)
                     if state in line and zone in line]
            if not named:
                missed.append(f"{task_id} ({state}, {zone})")
        self.assertEqual(
            [], missed,
            "предупреждение `new` не назвало пересечение с задачами: "
            + ", ".join(missed) + f"\nвывод:\n{out}")

    def test_ac2_tests_writing_overlap_is_journaled_like_any_other(self):
        """Пересечение только с задачей в `tests_writing` (зону она ещё
        не занимает и `zone_lock.refusal` о ней молчит) даёт ту же
        запись журнала «пересечение зон при заведении».

        Ловит мутацию: запись журнала пишется только для состояний
        `zone_lock.BLOCKING_STATES`, а для дозаводских ограничивается
        печатью — действие в журнале заведённой задачи не появится.
        """
        zone = "orchestrator/tolko_tests_writing.py"
        self.seed_task("T820", "tests_writing", zone)

        out, new_id = self.new_with_zones(zone)

        self.assertTrue(_sandbox.lines_mentioning(out, "T820"),
                        f"`new` не назвал задачу в tests_writing:\n{out}")
        self.assertIn(_sandbox.OVERLAP_ACTION, self.journal_actions(new_id),
                      f"нет записи «{_sandbox.OVERLAP_ACTION}» в журнале "
                      f"{new_id}: {self.journal_actions(new_id)}")


if __name__ == "__main__":
    unittest.main()
