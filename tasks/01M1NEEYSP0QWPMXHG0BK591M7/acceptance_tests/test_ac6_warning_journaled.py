"""AC-6: предупреждение при чужом живом lease дублируется отдельным
событием в журнале задачи (тем же журнальным API, с session_id
держателя) — и для `pause`, и для `release`.

И `cmd_pause`, и `cmd_release` уже сегодня безусловно пишут ОДНУ
журнальную запись при успешном выполнении («задача приостановлена: ...»
/ «lease снят Оператором»), независимо от состояния lease — эта запись
не является предупреждением AC-6, только количество NEW-записей, а не
их простое наличие, отличает «предупреждение появилось» от «обычная
запись команды всё равно была бы записана». Поэтому каждый тест
СРАВНИВАЕТ число новых записей журнала между сценарием, где
предупреждения НЕ должно быть (свой живой lease, AC-4 — ровно одна
существующая запись команды), и сценарием, где предупреждение ДОЛЖНО
появиться (чужой живой lease, AC-1/AC-3) — вторых обязано быть строго
больше первых РОВНО НА ОДНУ: это и есть «предупреждение дублируется
ОТДЕЛЬНЫМ событием», а не переиспользование уже существующей записи.

Красен до реализации: сегодня число новых записей журнала одинаково в
обоих сценариях (существующая запись команды и только она) — ни
`pause.cmd_pause`, ни `release.cmd_release` не пишут второе,
предупреждающее событие ни при каких условиях lease.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, pause, release, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, any_step_carries, _ts_ago, capture  # noqa: E402

CURRENT_SESSION = "sess-current-ac6"
HOLDER_SESSION = "sess-holder-ac6"
HEARTBEAT_AGE_SEC = 5

OWN_TASK = "T001"
FOREIGN_TASK = "T002"


class _TwoTasksTest(LeaseTaskTest):
    """Две независимые задачи в одной песочнице — своя живая lease на
    `OWN_TASK` (баз-линия, AC-4: ни одной дополнительной записи), чужая
    живая lease на `FOREIGN_TASK` (сценарий AC-1/AC-3-предупреждения) —
    так сравнение количества новых записей журнала не требует повторного
    вызова `setUp()` посреди теста."""

    TASK = OWN_TASK

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), FOREIGN_TASK, "Другая задача",
                          "in_dev", f"task/{FOREIGN_TASK.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        self.insert_lease(OWN_TASK, CURRENT_SESSION, os.getpid(),
                          socket.gethostname(), _ts_ago(HEARTBEAT_AGE_SEC))
        self.insert_lease(FOREIGN_TASK, HOLDER_SESSION, os.getpid(),
                          socket.gethostname(), _ts_ago(HEARTBEAT_AGE_SEC))

    def _new_steps(self, cmd, task_id: str) -> list:
        before = len(self.steps(task_id))
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            capture(cmd, task_id)
        return self.steps(task_id)[before:]


class PauseWarningJournaledTest(_TwoTasksTest):

    def test_ac6_pause_foreign_live_lease_adds_one_extra_journal_entry(self):
        """`pause` на задаче со СВОИМ живым lease (`OWN_TASK`) пишет
        ровно одну (уже существующую сегодня) запись журнала; та же
        команда на задаче с ЧУЖИМ живым lease (`FOREIGN_TASK`) обязана
        записать РОВНО ОДНУ ДОПОЛНИТЕЛЬНУЮ запись — предупреждение как
        отдельное событие (AC-6), несущее session_id держателя.

        Ловит мутацию: разработчик печатает предупреждение в stdout
        (закрывая AC-1), но не журналирует его отдельной записью —
        число новых записей в обоих сценариях тогда совпало бы (по
        одной), и `assertEqual` ниже провалился бы.
        """
        own_new = self._new_steps(pause.cmd_pause, OWN_TASK)
        foreign_new = self._new_steps(pause.cmd_pause, FOREIGN_TASK)

        self.assertEqual(
            len(foreign_new), len(own_new) + 1,
            f"pause не записала ровно одну дополнительную запись "
            f"журнала при чужом живом lease (AC-6): своя lease -> "
            f"{len(own_new)} новых записей, чужая живая lease -> "
            f"{len(foreign_new)} новых записей")
        self.assertTrue(
            any_step_carries(foreign_new, HOLDER_SESSION),
            f"ни одна из новых записей журнала не называет держателя "
            f"lease: {foreign_new}")


class ReleaseWarningJournaledTest(_TwoTasksTest):

    def test_ac6_release_foreign_live_lease_adds_one_extra_journal_entry(self):
        """Тот же приём, что и у `pause` выше, для `release`: своя живая
        lease -> ровно одна (существующая) запись журнала; чужая живая
        lease -> ровно на одну запись больше — отдельное предупреждающее
        событие с session_id держателя.

        Ловит мутацию: разработчик добавляет предупреждение в stdout
        `cmd_release` (закрывая AC-3), но не заводит для него отдельную
        `store.journal(...)` — переиспользуя единственную уже
        существующую запись «lease снят Оператором» вместо ВТОРОЙ,
        новой — количество новых записей тогда не выросло бы.
        """
        own_new = self._new_steps(release.cmd_release, OWN_TASK)
        foreign_new = self._new_steps(release.cmd_release, FOREIGN_TASK)

        self.assertEqual(
            len(foreign_new), len(own_new) + 1,
            f"release не записал ровно одну дополнительную запись "
            f"журнала при чужом живом lease (AC-6): своя lease -> "
            f"{len(own_new)} новых записей, чужая живая lease -> "
            f"{len(foreign_new)} новых записей")
        self.assertTrue(
            any_step_carries(foreign_new, HOLDER_SESSION),
            f"ни одна из новых записей журнала не называет держателя "
            f"lease: {foreign_new}")


if __name__ == "__main__":
    unittest.main()
