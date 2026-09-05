"""AC-3 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): если предварительный `advance`
отказал по причине «артефакт роли не готов» (класс отказов без
журнальной записи «переход отклонён…» — как сегодня у SPEC.md/REVIEW.md/
PLAN.md «ещё не ready»/«жду вердикта»/«разработчик ещё работает») —
`auto` запускает шаг роли как раньше.

Зелёный с рождения: и до, и после этой задачи предварительный/итоговый
`advance`, отказавший классом «артефакт не готов», не мешает роли
запуститься на своей итерации — сегодня это происходит потому, что
`cmd_run` вызывается БЕЗУСЛОВНО каждую итерацию (AC-1/AC-2 этой же
планки меняют МОМЕНТ вызова `advance`, не это свойство). Тест ловит
регресс: реализацию, которая по ошибке трактует «не готов» как причину
пропустить шаг роли (класс AC-4, а не AC-3) — тогда `("run", role)`
не появился бы в `self.events`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import AutoAdvanceOrderSandbox  # noqa: E402

from orchestrator import auto, config  # noqa: E402


class Ac3NotReadyRefusalStillRunsTheRoleStepTest(AutoAdvanceOrderSandbox):

    def setUp(self) -> None:
        super().setUp()
        self.patch_object(config, "AUTO_MAX_STEPS", 1)

    def test_ac3_not_ready_refusal_still_runs_the_role_step(self):
        """`advance` отказывает «не готов» (без журнальной записи) —
        `runner.cmd_run` всё равно вызывается для той же роли/состояния.

        Ловит мутацию: реализация, трактующая ЛЮБОЙ отказ advance (в
        т.ч. класс «не готов») как причину пропустить шаг роли (смешение
        с классом AC-4) — `("run", role)` не появился бы в `self.events`.
        """
        self.set_state("in_dev")
        role = config.STATE_ROLE["in_dev"]
        self.advance.arm_not_ready()

        self.capture(auto.cmd_auto, self.TASK)

        self.assertIn(("run", role), self.events,
                      f"шаг {role} не запущен при отказе класса «не готов»")

    def test_ac3_not_ready_refusal_leaves_no_refusal_journal_entry(self):
        """Требование 3 буквально: у этого класса отказа нет записи
        `fsm` «переход отклонён…» — печатается только статус.

        Ловит мутацию: реализация, ошибочно журналирующая «переход
        отклонён…» и для класса «не готов» — эта строка появилась бы
        в журнале там, где её сегодня нет.
        """
        self.set_state("in_dev")
        self.advance.arm_not_ready()

        self.capture(auto.cmd_auto, self.TASK)

        rows = self.journal_rows()
        self.assertFalse(
            any(action.startswith("переход отклонён") for _, action, _ in rows),
            f"найдена запись «переход отклонён…» у отказа класса «не готов»: "
            f"{rows}")


if __name__ == "__main__":
    unittest.main()
