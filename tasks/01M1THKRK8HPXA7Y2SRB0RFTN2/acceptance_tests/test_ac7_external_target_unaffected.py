"""Приёмочные тесты 01M1THKRK8HPXA7Y2SRB0RFTN2 — AC-7 (SPEC.md).

Зелёный с рождения (оба теста файла, по одной и той же причине): ни
`status`, ни `run` СЕГОДНЯ вообще не знают о стоп-кране — `status` не
помечает НИКОГО (красноту самой пометки self несёт AC-5, не эта задача),
а `run` не отказывает по алерту другого target'а просто потому, что не
отказывает по алерту вовсе. Оба останутся зелёными и ПОСЛЕ требования 1
— предмет этих тестов именно в том, что негативный случай (чужой
target) не задет положительным (self), а не в самом факте блокировки.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (LightSandbox, OTHER_TARGET,  # noqa: E402
                      RunPipelineSandbox, capture, catalog, config,
                      mentions_stop_crane, raise_stop_crane_alert, runner,
                      store)


class Ac7StatusDoesNotMarkExternalTaskTest(LightSandbox):
    """AC-7 (видимость): задача внешнего target не помечается в `status`
    открытым алертом стоп-крана self."""

    EXTERNAL_TASK = "T900"

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.EXTERNAL_TASK,
                          "Задача внешнего target", "in_dev",
                          "task/t900-vneshnyaya", OTHER_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac7_status_does_not_mark_external_target_task(self):
        """Пока по target self открыт алерт стоп-крана, строка `status`
        задачи ДРУГОГО target («сравнительно к» self, помеченному в
        AC-5) не несёт пометку стоп-крана.

        Ловит мутацию: если пометка `status` начнёт вешаться на ВСЕ
        задачи (без сверки `target`), строка внешней задачи тоже понесёт
        слово «стоп-кран».
        """
        raise_stop_crane_alert(store.db(), target=config.DEFAULT_TARGET)

        out = capture(catalog.cmd_status)
        external_line = next(
            line for line in out.splitlines()
            if line.strip().startswith(self.EXTERNAL_TASK))

        self.assertFalse(mentions_stop_crane(external_line))


class Ac7RunOfSelfTaskIgnoresAlertOfAnotherTargetTest(RunPipelineSandbox):
    """AC-7 (блокировка): алерт стоп-крана ДРУГОГО target не блокирует
    задачи self — стоп-кран одного target не течёт на соседний."""

    def setUp(self):
        super().setUp()
        # См. tasks/.../test_ac1_run_auto_blocked_by_open_alert.py — без
        # SPEC.md на диске бриф developer отказывает раньше, чем
        # спавнится агент, независимо от алертов.
        self.write_spec("ready")
        self.write_plan("draft")
        self.set_state("in_dev")
        # См. tasks/.../test_ac1_run_auto_blocked_by_open_alert.py —
        # артефакт-минимум в рабочем каталоге роли, иначе успешный
        # (rc=0) прогон честно ретраится «без артефакта» вместо
        # единственного вызова, которого ждёт `assert_called_once`.
        self.seed_worktree_plan()

    def test_ac7_run_of_self_task_ignores_alert_of_another_target(self):
        """Открытый алерт стоп-крана с `target=OTHER_TARGET` не мешает
        `run` задачи target self начать агентный шаг штатно.

        Ловит мутацию: если проверка требования 1 забудет сверить
        `target` алерта с target'ом текущей задачи (заблокирует ЛЮБОЙ
        открытый `kind=incident`, а не только алерт self), `run`
        откажет и здесь, хотя алерт вообще не про self.
        """
        raise_stop_crane_alert(store.db(), target=OTHER_TARGET)

        out, popen, code = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id="session-run"))

        popen.assert_called_once()
        self.assertFalse(mentions_stop_crane(out))


if __name__ == "__main__":
    import unittest
    unittest.main()
