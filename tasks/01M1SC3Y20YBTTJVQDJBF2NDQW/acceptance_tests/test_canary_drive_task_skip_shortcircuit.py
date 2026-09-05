"""Приёмочные тесты AC-3, AC-6 (SPEC 01M1SC3Y20YBTTJVQDJBF2NDQW):
`canary._drive_task` не крутит холостые проходы до
`CANARY_MAX_STALL_ITERS`, когда последняя запись журнала шага —
`agent run SKIPPED` с причиной «рабочий каталог роли не создан» или
«каталог окружения роли не создан» (первый боевой прогон канарейки v2
05.09 иначе тратит все холостые проходы вслепую и теряет настоящую
причину провала в отчёте, «Контекст» SPEC). Регрессия AC-7 (стагнация
БЕЗ такой записи по-прежнему упирается в полный стоп-кран) — отдельный
файл, `test_canary_drive_task_generic_stall_regression.py`: этот файл
целиком про НОВОЕ поведение, тот — про уже существующее.

Красен до реализации: `orchestrator/canary.py::_drive_task` (строки
615-634) сегодня умеет останавливать задачу только по `stall_streak >=
config.CANARY_MAX_STALL_ITERS` — ни разу не читает журнал (`store.
task_steps`) на предмет записи `agent run SKIPPED`, поэтому раньше
общего стоп-крана не убивает ни на одном проходе: `call_count` ниже
равен `config.CANARY_MAX_STALL_ITERS + 1`, а не `1`, и текст алерта —
общая формулировка `_kill_inconclusive`, а не журнальная причина.

Юнит-уровень, тот же приём, что `tests/test_canary.py::
DriveTaskStallCapTest`/`DriveTaskEscalationCapTest`: настоящей FSM/git
здесь нет, `auto.cmd_auto`/`cleanup.cmd_kill` подменены — предмет
проверки сам `_drive_task`, не механика вокруг него.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config, store  # noqa: E402


class _DriveTaskSandbox(unittest.TestCase):
    """Общая часть трёх сценариев ниже: одна задача `in_dev`,
    `auto.cmd_auto`/`cleanup.cmd_kill` подменены (по образцу
    `tests/test_canary.py::DriveTaskStallCapTest`)."""

    TASK = "T920"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача",
                          "in_dev", "task/t920-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _drive_with_skip_reason(self, reason_detail: str) -> None:
        """Каждый проход `auto.cmd_auto` журналирует РОВНО ту запись,
        которую реально пишет `runner.run_agent_once` на отказ
        `role_cwd`/`role_env` (`agent run SKIPPED`, детали — «рабочий
        каталог роли не создан: …» / «каталог окружения роли не создан:
        …») — состояние задачи при этом не меняется, тот же класс
        стагнации, что и `DriveTaskStallCapTest`, но с ИМЕННО этой
        журнальной записью, отличающей AC-3 от общего случая."""
        def fake_auto(task_id):
            store.journal(self.conn, task_id, "developer",
                         "agent run SKIPPED", reason_detail)

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)
        canary._drive_task(self.conn, self.TASK)


class DriveTaskWorkdirSkipShortCircuitTest(_DriveTaskSandbox):
    """AC-3: причина «рабочий каталог роли не создан» останавливает
    ведение задачи немедленно, не после `CANARY_MAX_STALL_ITERS`
    холостых проходов."""

    def test_ac3_workdir_reason_kills_on_the_very_first_pass(self):
        """Один-единственный проход `auto.cmd_auto`, журналирующий
        `agent run SKIPPED` с причиной «рабочий каталог роли не создан»,
        обязан завершить ведение задачи — не докручивать
        `CANARY_MAX_STALL_ITERS` холостых проходов.

        Ловит мутацию: если `_drive_task` по-прежнему полагается только
        на `stall_streak`/`CANARY_MAX_STALL_ITERS` (не читает последнюю
        запись журнала на предмет SKIPPED-причины), `cleanup.cmd_kill`
        не будет вызван после одного прохода, а `auto.cmd_auto` позовётся
        `config.CANARY_MAX_STALL_ITERS + 1` раз, как в общем случае
        (`test_ac7_*` ниже) — `assertEqual(..., 1)` покраснеет первым.
        """
        self._drive_with_skip_reason(
            "рабочий каталог роли не создан: [Errno 13] Permission denied: "
            "'/.artel/worktrees/T920'")

        self.assertEqual(canary.auto.cmd_auto.call_count, 1)
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)

    def test_ac3_role_env_reason_kills_on_the_very_first_pass_too(self):
        """Тот же немедленный останов для второй названной ТЗ причины —
        «каталог окружения роли не создан» (`runner.role_env`, отдельная
        от `role_cwd` точка отказа).

        Ловит мутацию: реализация, распознающая только подстроку
        «рабочий каталог роли не создан» и пропускающая вторую причину
        ТЗ (например, сравнение строго по первой константе, без учёта
        второй), оставит эту задачу крутиться до `CANARY_MAX_STALL_ITERS`
        — `call_count` окажется больше 1.
        """
        self._drive_with_skip_reason(
            "каталог окружения роли не создан: [Errno 13] Permission "
            "denied: '/.artel/home/.claude'")

        self.assertEqual(canary.auto.cmd_auto.call_count, 1)
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)


class DriveTaskSkipReasonInAlertTest(_DriveTaskSandbox):
    """AC-6: текст причины убийства идёт из журнальной записи, не общая
    формулировка «проходов подряд без прогресса»."""

    def test_ac6_alert_carries_the_journaled_reason_not_the_generic_stall_message(self):
        """Алерт `kind=threshold`, поднятый убийством задачи, обязан
        нести подстроку из ЖУРНАЛЬНОЙ причины (`agent run SKIPPED` ->
        «рабочий каталог роли не создан») и НЕ нести общую формулировку
        `_kill_inconclusive` про «проходов подряд без прогресса», которую
        код печатает для генуинного отсутствия прогресса без SKIPPED-
        записи (см. `orchestrator/canary.py:624-629`).

        Ловит мутацию: реализация, которая всё ещё зовёт
        `_kill_inconclusive` с ЖЁСТКО зашитым текстом «N проходов подряд
        без прогресса» (не текстом из записи журнала) даже при найденной
        SKIPPED-причине, оставит `assertNotIn` без эффекта, а
        `assertTrue(any(...))` на подстроке причины — красным.
        """
        self._drive_with_skip_reason(
            "рабочий каталог роли не создан: [Errno 13] Permission denied: "
            "'/.artel/worktrees/T920'")

        rows = store.open_alerts(self.conn, "threshold")
        messages = [r["message"] for r in rows if r["target"] == self.TASK]
        self.assertTrue(
            any("рабочий каталог роли не создан" in m for m in messages))
        self.assertFalse(
            any("проходов подряд без прогресса" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
