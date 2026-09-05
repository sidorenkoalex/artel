"""Приёмочные тесты 01M1P9QAG65GVF69YJEV0V18D9 — AC-7 (SPEC.md).

## Допущение интерфейса — `orchestrator/zone_lock.py::cmd_zone_release`

Ни SPEC, ни ТЗ не называют ни CLI-глагол новой операторской команды, ни
модуль/функцию, которая её реализует (в отличие от `tasks/T062/SPEC.md`,
которое хотя бы зафиксировало внешний глагол `release` для лимитера
параллельных задач) — оба выбора делает этот файл, тем же приёмом, что
`tasks/T062/acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py`
применил к внутреннему модулю `orchestrator/release.py::cmd_release`:

- Новый модуль `orchestrator/zone_lock.py`, функция
  `cmd_zone_release(task_id: str) -> None`.
- Снимает ожидание зоны ИМЕННО для `task_id`: следующий `run`/`auto` этой
  задачи не отказывает по конфликту, который блокировал её на момент
  вызова, даже если занявшая зону задача НИКУДА не делась (осталась в той
  же фазе `in_dev`…`merge_gate`) — иначе команда была бы неотличима от
  AC-6 (естественное снятие после мержа/kill) и не добавляла бы Оператору
  никакого рычага (SPEC, «Оценка объёма и деление»: «...без recourse»).
Красен до реализации: `orchestrator/zone_lock.py` не существует —
прогон падает `ModuleNotFoundError: No module named 'orchestrator.
zone_lock'` уже на импорте модуля (skills/test-authoring: «падать на
отсутствующей пока реализации — нормально»), не брак теста.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneSandbox  # noqa: E402

from orchestrator import runner, zone_lock  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac7OperatorReleasesZoneWaitTest(ZoneSandbox):
    """AC-7: Оператор может снять ожидание зоны явной командой; снятие
    пишется в журнал задачи как осознанный риск.

    Ловит мутацию: `cmd_zone_release` снимает lease/паузу вместо ожидания
    зоны (журналирует что-то, но следующий `run` продолжает отказывать по
    ТОЙ ЖЕ причине), либо журналирует снятие без пометки «осознанный
    риск» (Оператор не видит в журнале, что решение было сознательным
    принятием риска, а не автоматическим снятием по AC-6).
    """

    def setUp(self):
        super().setUp()
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "in_dev", CONFLICT_PATH)

    def test_ac7_release_journals_as_conscious_risk(self):
        journalled_before = self.journal_len()

        zone_lock.cmd_zone_release(self.TASK)

        journal = self.journal_tail(self.TASK, journalled_before)
        self.assertTrue(journal.strip(),
                        "cmd_zone_release не добавил запись в журнал задачи")
        self.assertIn("осознанный риск", journal,
                     f"снятие ожидания зоны не помечено как «осознанный "
                     f"риск» в журнале: {journal!r}")

    def test_ac7_run_passes_after_release_even_though_occupier_unchanged(self):
        out1, popen1 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        popen1.assert_not_called()
        self.assertEqual(self.task_state(self.TASK), "in_dev",
                         f"предусловие теста не выполнено — run не был "
                         f"заблокирован занявшей зону задачей: {out1!r}")
        self.assertEqual(self.task_state(OCCUPIER), "in_dev",
                         "предусловие теста: занявшая зону задача не должна "
                         "была никуда переместиться сама")

        zone_lock.cmd_zone_release(self.TASK)

        out2, popen2 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        self.assertTrue(
            popen2.called,
            f"run продолжает отказывать после явного снятия ожидания "
            f"Оператором, хотя занявшая зону задача {OCCUPIER} осталась "
            f"в in_dev: {out2!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
