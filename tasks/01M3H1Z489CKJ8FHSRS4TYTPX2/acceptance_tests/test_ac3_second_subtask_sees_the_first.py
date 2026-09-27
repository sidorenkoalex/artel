"""AC-3 — 01M3H1Z489CKJ8FHSRS4TYTPX2: зоны подзадачи записаны раньше,
чем заводится следующая подзадача того же деления, поэтому вторая из двух
частей с общим путём получает предупреждение с id первой; пересечение с
родительской задачей тоже выводится и журналируется.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Предварительные зоны подзадачи записываются до проверки
пересечений и до заведения следующей подзадачи того же деления, поэтому
вторая из двух подзадач с общим путём получает выведенное предупреждение
и запись журнала о пересечении с id первой; пересечение с родительской
задачей также выводится и журналируется.

Порядок операций наблюдается ровно так, как его называет критерий, —
следствием: сверка пересечений видит задачу только через колонку
`tasks.zones` (`zone_lock.forecast_overlaps` → `task_zone_paths`), и
первая часть деления попадает во вывод второй лишь тогда, когда её зоны
записаны до второго заведения. Родитель в момент каждого заведения ещё в
`spec_gate` (в `killed` его переводит `fsm._spawn_division_subtasks`
ПОСЛЕ всех подзадач) — состояние из `zone_lock.FORECAST_STATES`.

Красен до реализации: сегодня `spawn_subtask` ни зон не пишет, ни
пересечений не сверяет — вторая подзадача не знает о первой, вывод не
называет ничьего id, и записи «пересечение зон при заведении» в её
журнале нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import catalog, zone_lock  # noqa: E402


class SecondSubtaskSeesTheFirstTest(_sandbox.SubtaskZoneSandbox):

    def test_ac3_second_part_is_warned_about_the_first_part(self):
        """Две части одного деления заявляют общий путь. Вторая получает
        напечатанное предупреждение, где id первой части и общий путь
        названы в одной строке, и запись журнала «пересечение зон при
        заведении» с id первой части в detail; первая при этом стоит в
        состоянии, которое прогноз очереди зон видит.

        Ловит мутацию: запись предварительных зон вынесена из
        `spawn_subtask` в конец деления (одним проходом по всем
        заведённым подзадачам в `fsm._spawn_division_subtasks`) — к
        моменту заведения второй части колонка зон первой ещё пуста,
        пересечение внутри волны деления не обнаруживается, и вывод с
        записью журнала молчат ровно в прецеденте «Контекста» SPEC.
        """
        _out_first, first = self.spawn(
            _sandbox.tz_body(_sandbox.SHARED_ZONE), title="Первая часть")

        out_second, second = self.spawn(
            _sandbox.tz_body(_sandbox.SHARED_ZONE), title="Вторая часть")

        self.assertIn(
            self.row(first)["state"], zone_lock.FORECAST_STATES,
            f"первая часть деления {first} стоит в состоянии, которого "
            f"прогноз очереди зон не видит вовсе — сценарий критерия не "
            f"воспроизведён")
        self.assertTrue(
            _sandbox.overlap_lines(out_second, first, _sandbox.SHARED_ZONE),
            f"заведение второй части {second} не назвало разом первую "
            f"часть {first} и их общую зону {_sandbox.SHARED_ZONE}:\n"
            f"{out_second}")
        details = self.journal_details(second, catalog.ZONE_OVERLAP_ACTION)
        self.assertTrue(
            details,
            f"в журнале второй части {second} нет записи с действием "
            f"«{catalog.ZONE_OVERLAP_ACTION}»: "
            f"{self.journal_actions(second)}")
        self.assertIn(
            first, " | ".join(details),
            f"запись о пересечении не называет id первой части {first}: "
            f"{details}")

    def test_ac3_overlap_with_the_parent_task_is_printed_and_journaled(self):
        """Родитель деления держит зону, которую заявляет его часть:
        заведение части печатает строку с id родителя и общим путём и
        пишет о том же запись в журнал части.

        Ловит мутацию: родитель исключён из сверки как заведомо уходящий
        в `killed` (`exclude_task_id` родителя или фильтр по
        `parent_task_id`) — Оператор не увидел бы, что часть деления
        наследует зону, которую родитель ещё держит в полёте.
        """
        self.set_parent_zones(_sandbox.SHARED_ZONE)

        out, sub_id = self.spawn(_sandbox.tz_body(_sandbox.SHARED_ZONE),
                                 title="Часть с зоной родителя")

        self.assertTrue(
            _sandbox.overlap_lines(out, _sandbox.PARENT_ID,
                                   _sandbox.SHARED_ZONE),
            f"заведение части {sub_id} не назвало разом родителя "
            f"{_sandbox.PARENT_ID} и их общую зону "
            f"{_sandbox.SHARED_ZONE}:\n{out}")
        self.assertIn(
            _sandbox.PARENT_ID,
            " | ".join(self.journal_details(sub_id,
                                            catalog.ZONE_OVERLAP_ACTION)),
            f"в журнале части {sub_id} нет записи о пересечении с "
            f"родителем: {self.journal_actions(sub_id)}")


if __name__ == "__main__":
    unittest.main()
