"""Приёмочные тесты T074 — AC-2, AC-3, AC-4, AC-5.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-2. `pause --now <id>` при этом ставит обычную пометку паузы задачи —
той же семантики, что и `pause` (T070).

AC-3. Незакоммиченный WIP worktree задачи на момент прерывания
зачекпоинчен служебным коммитом с пометкой причины «pause --now» —
механика T041/T059 (актёр orchestrator, `git add` только путей worktree
задачи).

AC-4. Lease держателя прерванного шага освобождается.

AC-5. Журнал задачи содержит полную последовательность действий `pause
--now`: обнаружение бегущего шага, прерывание процесса, чекпоинт, снятие
lease, пометка паузы.

Один общий сценарий (`setUp`/`_interrupt` ниже): задача `in_dev`, грязный
worktree, реальный дочерний процесс адресован через lease, `pause --now`
вызвана один раз — каждый критерий проверяется своим срезом результата
одного и того же вызова (тот же приём, что `tasks/T041/acceptance_tests/
test_checkpoint_after_timeout.py::test_ac1_...` проверяет несколько
следствий одного `run_agent`).

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


class InterruptSequenceTest(InterruptSandbox):

    def _interrupt(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)
        self.write_dirty_wip()
        out = self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        return out

    def test_ac2_regular_pause_mark_is_set(self):
        self._interrupt()

        self.assertTrue(
            pause.is_paused(self.task_row()),
            "AC-2: pause --now обязана поставить ту же пометку паузы, "
            "что и обычная pause (T070)")

    def test_ac3_dirty_worktree_is_checkpointed_with_pause_now_marker(self):
        out = self._interrupt()

        self.assertTrue(
            self.git_in_worktree("status", "--porcelain").strip() == "",
            "AC-3: рабочее дерево worktree задачи обязано стать чистым — "
            "незакоммиченный WIP зачекпоинчен")
        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        marker = f"{subject}\n{out}\n{self.journal_text()}"
        self.assertIn(
            "pause --now", marker,
            f"AC-3: коммит-чекпоинт и/или журнал обязаны нести пометку "
            f"причины «pause --now» — фактически: {marker!r}")

    def test_ac4_lease_of_interrupted_step_is_released(self):
        self._interrupt()

        self.assertIsNone(
            self.lease_row(),
            "AC-4: lease держателя прерванного шага обязан быть снят")

    def test_ac5_journal_carries_the_full_action_sequence(self):
        self._interrupt()

        text = self.journal_text().lower()
        expectations = {
            "обнаружение бегущего шага": ("шаг", "агент", "бег"),
            "прерывание процесса": ("процесс", "прерв", "заверш"),
            "чекпоинт": ("чекпоинт",),
            "снятие lease": ("lease",),
            "пометка паузы": ("пауз", "pause"),
        }
        missing = [label for label, keywords in expectations.items()
                  if not any(kw in text for kw in keywords)]
        self.assertEqual(
            missing, [],
            f"AC-5: журнал обязан нести полную последовательность "
            f"действий pause --now — не найдено упоминаний: {missing}; "
            f"фактический журнал:\n{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
