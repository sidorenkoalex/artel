"""AC-9, AC-10 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — флаг
`approve <id> --accept-red "<основание>"` и разбор аргументов команды
`approve` в диспетчере `orchestrator/artel.py`.

Красен до реализации: флага `--accept-red` нет ни в таблице диспетчера,
ни в строке usage — сегодня `approve <id> --accept-red "<основание>"`
разбирает `--accept-red` как позиционный sha, и ни основания, ни имён
упавших тестов в журнале не появляется.

Зелёный с рождения: `test_ac10_positional_sha_is_still_parsed` (разбор
позиционного sha эта задача не меняет — критерий требует его сохранить) и
`test_ac9_flag_with_reason_passes_acceptance_on_red_suite` — сегодня он
зелен побочно (approve красный набор вообще не смотрит), а после
реализации ловит флаг, не доехавший до решения об отказе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import FAILED_NODEIDS, SUMMARY_LINE, red_output  # noqa: E402
from _sandbox import ApproveAcceptanceSandbox  # noqa: E402
from orchestrator import artel, fsm  # noqa: E402

ACCEPT_RED_FLAG = "--accept-red"
REASON = "красный main 22-26.09, к задаче не относится"
SHA = "abcdef1234567890"


class AcceptRedFlagTest(ApproveAcceptanceSandbox):

    def test_ac9_flag_with_reason_passes_acceptance_on_red_suite(self):
        """`approve <id> --accept-red "<основание>"` при красном полном
        наборе проводит приёмку: задача уходит в `merge_gate`, несмотря на
        не-зелёный набор.

        Ловит мутацию: флаг разобран, но до решения об отказе не доходит
        (значение принято диспетчером и не передано в `fsm.cmd_approve`
        либо не проверено в `_approve_acceptance`) — приёмка отказывает и
        при осознанном принятии красноты, и выхода у Оператора нет.
        """
        self.set_red_run(red_output())

        self.approve_cli(ACCEPT_RED_FLAG, REASON)

        self.assertEqual(self.state(), "merge_gate",
                         f"{ACCEPT_RED_FLAG} с основанием не провёл приёмку")

    def test_ac9_journal_carries_reason_failed_tests_and_summary(self):
        """Журнал задачи после осознанного принятия красного набора несёт
        основание Оператора, имена упавших тестов и итоговую строку
        pytest — что именно приняли и на каком основании.

        Ловит мутацию: в журнал уходит только основание (или только факт
        принятия) — через неделю по записи не восстановить, какие тесты
        были красными в момент приёмки.
        """
        self.set_red_run(red_output())

        self.approve_cli(ACCEPT_RED_FLAG, REASON)
        journal = self.journal_blob()

        self.assertIn(REASON, journal,
                      f"основание не попало в журнал: {journal!r}")
        self.assertIn(SUMMARY_LINE, journal,
                      f"итоговая строка не попала в журнал: {journal!r}")
        for nodeid in FAILED_NODEIDS:
            self.assertIn(nodeid, journal,
                          f"журнал не назвал упавший тест {nodeid}")

    def test_ac10_flag_without_reason_is_a_named_refusal(self):
        """`approve <id> --accept-red` без основания — именованный отказ:
        приёмка не проводится, а текст отказа называет сам флаг.

        Ловит мутацию: флаг без значения разобран как «основание пустая
        строка» (или `--accept-red` съеден как позиционный sha) — красный
        набор принимается без всякого основания в журнале, ровно то, что
        флаг и должен был сделать невозможным.
        """
        self.set_red_run(red_output())

        out, exit_text = self.approve_cli(ACCEPT_RED_FLAG)

        self.assertNotEqual(
            self.state(), "merge_gate",
            f"{ACCEPT_RED_FLAG} без основания провёл приёмку красного набора")
        self.assertIn(ACCEPT_RED_FLAG, out + exit_text,
                      f"отказ не называет флаг: out={out!r}, "
                      f"exit={exit_text!r}")

    def test_ac10_positional_sha_is_still_parsed(self):
        """`approve <id> <sha>` без флага разбирает sha ровно как раньше —
        вторым позиционным аргументом, доходящим до `fsm.cmd_approve`.

        Ловит мутацию: разбор флага съел позиционный аргумент (например,
        `rest[1]` теперь всегда трактуется как флаг) — approve на гейтах
        с фиксацией перестаёт принимать sha, и весь ручной протокол
        Оператора ломается.
        """
        with mock.patch.object(fsm, "cmd_approve") as cmd_approve:
            self.approve_cli(SHA)

        cmd_approve.assert_called_once()
        args, kwargs = cmd_approve.call_args
        passed = kwargs.get("sha", args[1] if len(args) > 1 else None)
        self.assertEqual(passed, SHA,
                         f"sha не доехал до fsm.cmd_approve: args={args}, "
                         f"kwargs={kwargs}")


class ApproveUsageLineTest(unittest.TestCase):

    def test_ac10_usage_line_of_approve_names_the_flag(self):
        """Строка usage команды `approve` в справке пульта
        (`orchestrator/artel.py`, докстринг модуля) называет флаг
        `--accept-red`: иначе Оператор о выходе при красном наборе узнаёт
        только из кода.

        Ловит мутацию: флаг заведён в таблице диспетчера, а справку
        забыли — команда есть, но её никто не найдёт.
        """
        doc = artel.__doc__ or ""
        approve_lines = [line for line in doc.splitlines()
                         if "approve <id>" in line]

        self.assertNotEqual(approve_lines, [],
                            "в справке пульта нет строки usage команды approve")
        self.assertTrue(
            any(ACCEPT_RED_FLAG in line for line in approve_lines),
            f"строка usage команды approve не называет {ACCEPT_RED_FLAG}: "
            f"{approve_lines}")


if __name__ == "__main__":
    unittest.main()
