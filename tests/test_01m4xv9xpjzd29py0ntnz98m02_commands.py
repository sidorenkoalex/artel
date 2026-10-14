"""Проверка штатного kill через lease и переход FSM.

Группа: долгоживущий
Зелёный с рождения: прежний маршрут kill и единственный вызыватель force уже соблюдают AC-5/поведенческую часть AC-8.
"""
import ast
import os
import socket
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import cleanup, lease, liveness, store
from tests.sandbox import LightTransitionSandbox


class ForceCallersTest(unittest.TestCase):
    def test_ac5_force_has_no_other_callers(self):
        """Разрешающий флаг остаётся только у штатного kill.

        Ловит мутацию: новый явный force=True в другой команде добавляет
        запрещённого вызывателя, даже если её happy path пока не изменился.
        """
        root = Path(lease.__file__).resolve().parent
        found = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parents = {child: parent for parent in ast.walk(tree)
                       for child in ast.iter_child_nodes(parent)}
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = (node.func.attr if isinstance(node.func, ast.Attribute)
                        else node.func.id if isinstance(node.func, ast.Name) else "")
                if name not in ("acquire", "run_locked"):
                    continue
                if not any(k.arg == "force" and isinstance(k.value, ast.Constant)
                           and k.value.value is True for k in node.keywords):
                    continue
                owner = parents.get(node)
                while owner is not None and not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner = parents.get(owner)
                found.append((path.relative_to(root).as_posix(), owner.name if owner else ""))
        self.assertTrue(found, "Штатный kill должен использовать force")
        for caller in found:
            with self.subTest(caller=caller):
                self.assertEqual(caller, ("cleanup.py", "cmd_kill"))


class KillLeaseTest(LightTransitionSandbox):
    def test_kill_checks_confirmation_before_force_and_then_closes(self):
        """Живой цикл требует --yes до acquire; подтверждённый kill закрывает задачу.

        Связка: cmd_kill — acquire(force) — FSM — БД — уборка через git
        песочницы. Acquire и тело kill настоящие, сигналы процессов подменены.
        Ловит мутацию: перенос force до проверки --yes меняет lease при
        отказе; потеря force на разрешённом маршруте оставляет задачу живой.
        """
        conn = store.db()
        for holder in ("cycle-a", "cycle-b"):
            with self.subTest(holder=holder):
                self.set_state("in_dev")
                conn.execute("DELETE FROM leases WHERE task_id=?", (self.TASK,))
                conn.commit()
                store.insert_lease(conn, self.TASK, holder, os.getpid() + 1000,
                                   socket.gethostname(), store.now())
                before = dict(store.lease_row(conn, self.TASK))
                with mock.patch("os.kill") as signals, mock.patch("os.killpg"), \
                        mock.patch.object(liveness, "terminate_process_group", return_value=0), \
                        mock.patch.object(lease, "acquire", wraps=lease.acquire) as acquire:
                    with self.assertRaises(SystemExit) as refusal:
                        cleanup.cmd_kill(self.TASK, "killer")
                    self.assertIn("--yes", str(refusal.exception))
                    self.assertEqual(self.state(), "in_dev")
                    self.assertEqual(dict(store.lease_row(conn, self.TASK)), before)
                    acquire.assert_not_called()
                    cleanup.cmd_kill(self.TASK, "killer", confirmed=True)
                    self.assertEqual(self.state(), "killed")
                    self.assertIsNone(store.lease_row(conn, self.TASK))
                    self.assertTrue(any(c.kwargs.get("force") is True for c in acquire.call_args_list))
                    self.assertTrue(any(c.args[0] == before["pid"] and c.args[1] != 0
                                        for c in signals.call_args_list))
                steps = store.task_steps(conn, self.TASK)
                for action in (cleanup.KILL_REFUSAL_JOURNAL_ACTION,
                               cleanup.KILL_CONFIRM_JOURNAL_ACTION, "lease перехвачен"):
                    self.assertTrue(any(s["action"] == action for s in steps), action)
