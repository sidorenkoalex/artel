"""AC-7 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Каждый из путей
AC-3–AC-6 записывает в журнал шага факт добивания потомков — число снятых
процессов группы.»

Допущение (SPEC не называет формулировку записи): факт ищется как строка
журнала, содержащая ОДНОВРЕМЕННО цифру и корень «групп» — SPEC сама
формулирует требование 2 словами «снял всей его группе процессов»/«группу
целиком», это ближайший словарь, который реализация вероятно унаследует.
Тест НЕ фиксирует точное число (агент + потомок — 2, только потомок — 1,
обе трактовки согласуются с текстом критерия) — только то, что число
вообще попало в журнал рядом со словом о группе; это ловит явную мутацию
«снял, но не записал сколько», не выбор автора между двумя трактовками
счёта.

Красен до реализации: журнал шага сегодня не пишет ничего похожего на
«N процессов группы» ни на одном из четырёх путей — ни один из четырёх
`assertTrue(_group_kill_count_mentioned(...))` не находит такую строку.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, cleanup, pause, release  # noqa: E402

_GROUP_KILL_COUNT_RE = re.compile(r"(?i)групп\w*[^\n]*\d|\d[^\n]*групп\w*")


def _group_kill_count_mentioned(text: str) -> bool:
    return _GROUP_KILL_COUNT_RE.search(text) is not None


class GroupKillCountJournalledTest(AgentStepSandbox):

    SESSION = "ac7-test-session"

    def test_ac7_timeout_journals_group_kill_count(self):
        """Таймаут шага с потомком — журнал задачи после таймаута содержит
        число снятых процессов группы рядом со словом о группе.

        Ловит мутацию: если реализация AC-3 снимает группу, но не
        добавляет в журнал ни строки с количеством (пишет только сам
        факт таймаута, как уже делает сегодняшний код) —
        `_group_kill_count_mentioned` не найдёт цифру рядом с «групп» и
        тест покраснеет, даже когда потомок корректно снят (AC-3 отдельно
        проверен `test_ac3_timeout_kills_step_group.py`).
        """
        outcome, _, _ = self.run_step(self.agent_with_child_cmd(), timeout_sec=0.3)
        self.assertEqual(outcome, "timeout")

        self.assertTrue(
            _group_kill_count_mentioned(self.journal_text()),
            "журнал шага после таймаута не содержит числа снятых "
            "процессов группы рядом со словом о группе")

    def test_ac7_kill_journals_group_kill_count(self):
        """`kill` на задаче с реально бегущим шагом — журнал после
        завершения содержит число снятых процессов группы.

        Ловит мутацию: если `cmd_kill` снимает группу (AC-4), но пишет в
        журнал только факт `kill` без количества снятых процессов —
        `_group_kill_count_mentioned` не найдёт цифру рядом с «групп».
        """
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id=self.SESSION)

        thread = self.run_step_in_background(self.agent_with_child_cmd())
        self.read_agent_and_child_pid()
        self.assert_lease_pid_unchanged(holder.pid)

        cleanup.cmd_kill(self.TASK, session_id=self.SESSION)
        thread.join(timeout=10)

        self.assertTrue(
            _group_kill_count_mentioned(self.journal_text()),
            "журнал шага после kill не содержит числа снятых процессов "
            "группы рядом со словом о группе")

    def test_ac7_pause_now_journals_group_kill_count(self):
        """`pause --now` на задаче с реально бегущим шагом — журнал после
        прерывания содержит число снятых процессов группы.

        Ловит мутацию: если `cmd_pause_now` снимает группу (AC-5), но не
        журналирует количество снятых процессов — та же проверка не
        находит цифру рядом с «групп».
        """
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id=self.SESSION)

        thread = self.run_step_in_background(self.agent_with_child_cmd())
        self.read_agent_and_child_pid()
        self.assert_lease_pid_unchanged(holder.pid)

        pause.cmd_pause_now(self.TASK)
        thread.join(timeout=10)

        self.assertTrue(
            _group_kill_count_mentioned(self.journal_text()),
            "журнал шага после pause --now не содержит числа снятых "
            "процессов группы рядом со словом о группе")

    def test_ac7_release_journals_group_kill_count(self):
        """`release` мёртвого lease с реально бегущим шагом — журнал после
        снятия содержит число снятых процессов группы.

        Ловит мутацию: если `cmd_release` снимает остаточную группу
        (AC-6), но не журналирует количество — та же проверка не находит
        цифру рядом с «групп».
        """
        dead = self.dead_pid()
        self.install_dummy_lease(dead, session_id=self.SESSION)

        thread = self.run_step_in_background(self.agent_with_child_cmd())
        self.read_agent_and_child_pid()

        release.cmd_release(self.TASK)
        thread.join(timeout=10)

        self.assertTrue(
            _group_kill_count_mentioned(self.journal_text()),
            "журнал шага после release мёртвого lease не содержит числа "
            "снятых процессов группы рядом со словом о группе")


if __name__ == "__main__":
    unittest.main()
