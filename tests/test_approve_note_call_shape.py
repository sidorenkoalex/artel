"""`approve` без `--note` зовёт `fsm.cmd_approve` и `fsm._cmd_approve`
прежним вызовом, без нового аргумента (SPEC 01M6KWKZ8GKZZFABDG8QC9RDJF,
требования 1, 8): закрепляющие обвязку тесты диспетчера и lease сверяют
аргументы вызова, и новый ключ со значением `None` их бы сломал.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, config, fsm, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class ApproveNoteCallShapeTest(TmpRootTest):

    TASK = "01APPROVENOTECALLSHAPETS"

    def dispatch(self, *argv: str) -> dict:
        calls = []
        with mock.patch.object(fsm, "cmd_approve",
                               lambda *a, **kw: calls.append(kw)), \
                mock.patch.object(sys, "argv", ["artel.py", "approve", *argv]):
            capture(artel.main)
        self.assertEqual(len(calls), 1)
        return calls[0]

    def test_dispatcher_passes_note_only_with_flag(self):
        """Без `--note` в именованных аргументах `fsm.cmd_approve` ключа
        `note` нет; с флагом — `note` равен пути файла.

        Ловит мутацию: диспетчер передаёт `note=None` всегда (вместо
        приёма `_approve_as_epic_kwargs`) — ключ `note` есть и без флага.
        """
        self.assertNotIn("note", self.dispatch(self.TASK))
        self.assertNotIn("note", self.dispatch(self.TASK, "--as-epic"))
        self.assertEqual(self.dispatch(self.TASK, "--note", "f.md")["note"],
                         "f.md")

    def test_cmd_approve_without_note_calls_body_without_note_text(self):
        """`fsm.cmd_approve` без `note` зовёт `_cmd_approve` под lease без
        ключа `note_text`, ровно одиннадцатью позиционными аргументами.

        Ловит мутацию: тело зовётся с `note_text=None` всегда — ключ
        `note_text` появляется и в вызове без флага.
        """
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Форма вызова", "spec_gate",
                          f"task/{self.TASK.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        calls = []
        with mock.patch.object(lease, "run_locked",
                               lambda conn, tid, sid, body: body("sid")), \
                mock.patch.object(fsm, "_cmd_approve",
                                  lambda *a, **kw: calls.append((a, kw))):
            fsm.cmd_approve(self.TASK)
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(kwargs, {})
        self.assertEqual(len(args), 11)


if __name__ == "__main__":
    unittest.main()
