"""Общий сценарий отказа автогейта приёмки для файлов планки.

Задача в состоянии `acceptance` в БД песочницы (`SchemaConnTmpRootTest`),
политика гейта — `auto`, чек-лист приёмки заглушён, `_autogate_conditions`
подменён на заданную причину, `models.suspend_on_autogate_refusal`
подменён (SPEC, требование 5) — функция `_maybe_autogate_acceptance`
отрабатывает ветку отказа, печать собирается из stdout.
"""
import contextlib
import io
from pathlib import Path
from unittest import mock

from orchestrator import fsm_autogate, gates, store
from tests.sandbox import SchemaConnTmpRootTest

TASK = "T001"
REFUSAL_ACTION = "автогейт acceptance не пройден"
ENV_ACTION_TEXT = "автогейт acceptance: отказ окружения"

# Выжимка прогона и путь лога — тот вид, которым `acceptance` дописывает
# исход прогона в причину отказа.
DIGEST = ": 120 passed, 1 error (лог прогона: /tmp/T001-fullsuite-1.log)"


def env_detail(kind: str, task_id: str = TASK) -> str:
    return (f"класс: окружение ({kind}) — качество задачи не оценено; "
            f"повторить проверку: artel.py approve {task_id}")


def env_line(kind: str, task_id: str = TASK) -> str:
    return (f"[{task_id}] класс отказа: окружение ({kind}) — качество задачи "
            f"не оценено; повторить проверку: artel.py approve {task_id}")


def refusal_line(reason: str, task_id: str = TASK) -> str:
    return f"[{task_id}] {reason} — жду Оператора"


class RefusalSandbox(SchemaConnTmpRootTest):
    """Песочница одной задачи в `acceptance` и прогон ветки отказа."""

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Задача", "acceptance",
                          "task/t001-zadacha", "artel", 25.0)

    def refuse(self, reason: str):
        """(вывод, мок `suspend_on_autogate_refusal`) отказа с причиной
        `reason`."""
        out = io.StringIO()
        t = store.get_task(self.conn, TASK)
        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
                mock.patch.object(fsm_autogate, "_log_acceptance_checklist"), \
                mock.patch.object(fsm_autogate, "_autogate_conditions",
                                  return_value=(["ok"], reason)), \
                mock.patch.object(fsm_autogate.models,
                                  "suspend_on_autogate_refusal") as suspend, \
                contextlib.redirect_stdout(out):
            fsm_autogate._maybe_autogate_acceptance(
                self.conn, TASK, t, Path(self.root), 1)
        return out.getvalue(), suspend

    def steps(self):
        return store.task_steps(self.conn, TASK)

    def actions(self):
        return [(r["actor"], r["action"], r["detail"]) for r in self.steps()]

    def assert_stays_in_acceptance(self):
        self.assertEqual(store.task_state(self.conn, TASK), "acceptance")
        self.assertNotIn("state -> merge_gate",
                         [r["action"] for r in self.steps()])
