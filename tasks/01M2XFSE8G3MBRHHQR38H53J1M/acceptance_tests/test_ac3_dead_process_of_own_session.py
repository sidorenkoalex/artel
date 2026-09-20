"""AC-3 (продолжение) — мёртвый держатель СВОЕЙ сессии перехватывается той
же прежней записью журнала, а не отказывает по AC-1 (задача
01M2XFSE8G3MBRHHQR38H53J1M).

Красен до реализации: строка своей сессии сегодня проходит через ветку
«мьютекс свой» (`orchestrator/merge_lock.py:52`) — она переписывает
держателя МОЛЧА, не разбирая, жив ли его процесс, и записи «мьютекс merge
перехвачен» в журнале не появляется. Вынесен из
`test_ac2_ac3_reentry_and_dead_holder.py` отдельным файлом именно потому,
что маркер красноты у него обратный: остальные проверки AC-2/AC-3 — про
сохранение сегодняшнего поведения.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import merge_lock, store  # noqa: E402

from _sandbox import MergeOwnerSandbox, _dead_pid  # noqa: E402


class DeadProcessOfOwnSessionTest(MergeOwnerSandbox):

    def test_ac3_dead_process_of_own_session_is_intercepted_with_journal(self):
        """Держатель той же сессии `sess-a`, но мёртвого процесса (неживой
        pid на этом host): это мёртвый держатель — значит прежний перехват
        с записью «мьютекс merge перехвачен», а не отказ «окно занято»
        (отказ оставил бы задачу ждать процесс, которого уже нет).

        Ловит мутацию: «другой pid той же сессии» реализован безусловным
        отказом ПЕРЕД проверкой живости (`if row["session_id"] ==
        session_id and row["pid"] != os.getpid(): return refusal`) —
        мёртвый держатель своей сессии перестанет перехватываться:
        `assertIsNone` покраснеет.
        """
        self.seed_lock(self.TASK_B, "sess-a", _dead_pid(),
                       socket.gethostname())

        refusal = merge_lock.acquire(store.db(), self.TASK_A, "sess-a")

        self.assertIsNone(refusal, "мёртвый держатель обязан перехватываться "
                                   "независимо от его сессии")
        row = self.lock_row()
        self.assertEqual(row["task_id"], self.TASK_A)
        self.assertEqual(row["pid"], os.getpid())
        records = self.journal_records(self.TASK_A)
        self.assertTrue(
            any("мьютекс merge перехвачен" in r for r in records),
            f"перехват обязан журналироваться прежней записью: {records}")


if __name__ == "__main__":
    unittest.main()
