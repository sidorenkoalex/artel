"""AC-6 — вывод держателя merge-окна называет его pid: и журнальная запись
входа в очередь, и суффикс `status` ожидающей задачи (задача
01M2XFSE8G3MBRHHQR38H53J1M).

Красен до реализации: запись «ждёт merge-окна: держит …»
(`orchestrator/merge_queue.py:103-108`) и суффикс `wait_suffix`
(`:71-80`, единственный существующий вывод держателя в `status`) знают
только `task_id` держателя — `_current_holder_id` возвращает
`row["task_id"]` и pid строки мьютекса не читает вовсе.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import catalog, merge_queue, store  # noqa: E402

from _sandbox import MergeOwnerSandbox, _ts_ago, capture  # noqa: E402

# Pid держателя — фиксированное значение, отличимое в тексте от остальных
# чисел записи (интервал опроса 90 и потолок 7200 секунд): сверка идёт
# подстрокой, а настоящий pid живого процесса (`_alive_foreign_pid`) мог бы
# случайно совпасть с ними и дать ложный пропуск. Держатель поэтому стоит
# на ЧУЖОМ host — там `_holder_is_dead` судит только по heartbeat и не
# заглядывает в pid (тот же приём, что `seed_holder` планки
# 01M291EPQ2VFGCHZTXXC81616V), так что выдуманный pid гарантированно
# считается живым и окно остаётся занятым.
HOLDER_PID = 40404


class HolderPidInQueueJournalTest(MergeOwnerSandbox):

    def test_ac6_queue_entry_journal_names_the_holder_pid(self):
        """Вход в очередь при занятом окне журналируется записью «ждёт
        merge-окна: держит …», и она обязана называть pid держателя
        мьютекса (по task_id держателя Оператор не отличит два
        параллельных цикла одного пульта друг от друга).

        Ловит мутацию: `_current_holder_id`/текст записи оставлены на одном
        `task_id` держателя — `assertIn(str(HOLDER_PID), ...)` не найдёт
        pid ни в действии, ни в деталях записи.
        """
        self.seed_lock(self.TASK_B, "sess-holder", HOLDER_PID, "holder-host")
        self.fake_clock()

        with self.assertRaises(SystemExit):
            merge_queue.wait_for_window(store.db(), self.TASK_A, "sess-a")

        entries = [r for r in self.journal_records(self.TASK_A)
                   if "ждёт merge-окна" in r]
        self.assertTrue(entries, self.journal_records(self.TASK_A))
        self.assertIn(self.TASK_B, entries[0])
        self.assertIn(str(HOLDER_PID), entries[0],
                      f"запись обязана называть pid держателя: {entries[0]}")


class HolderPidInStatusSuffixTest(MergeOwnerSandbox):

    def test_ac6_status_suffix_of_a_waiting_task_names_the_holder_pid(self):
        """`artel.py status` для задачи, стоящей в очереди merge-окна,
        печатает добавку «ждёт merge-окна: …» — она обязана называть pid
        держателя рядом с его задачей и прежними минутами ожидания.
        Нового места вывода держателя не заводится: сверяется тот самый
        суффикс, который `status` печатает сегодня.

        Ловит мутацию: pid добавлен в журнальную запись входа в очередь,
        но не в `wait_suffix` — строка `status` ожидающей задачи останется
        без pid, и `assertIn` покраснеет (регулярка на «N мин» при этом
        подтвердит, что сам суффикс не потерян).
        """
        self.seed_lock(self.TASK_B, "sess-holder", HOLDER_PID, "holder-host")
        self.enqueue(self.TASK_A, "sess-a", os.getpid(),
                     socket.gethostname(), _ts_ago(180))

        output = capture(catalog.cmd_status)

        line = next(ln for ln in output.splitlines()
                    if ln.startswith(self.TASK_A))
        self.assertRegex(line, r"ждёт merge-окна:.*\d+ мин", line)
        self.assertIn(self.TASK_B, line, line)
        self.assertIn(str(HOLDER_PID), line,
                      f"суффикс status обязан называть pid держателя: {line}")


if __name__ == "__main__":
    unittest.main()
