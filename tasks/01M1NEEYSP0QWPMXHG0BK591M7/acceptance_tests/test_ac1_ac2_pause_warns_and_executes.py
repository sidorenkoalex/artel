"""AC-1: `pause` для задачи с ЧУЖИМ живым lease (heartbeat свежий, pid
адресуем, session_id ≠ текущей сессии) печатает ДО выполнения команды
предупреждение, содержащее session_id держателя и возраст heartbeat.

AC-2: та же команда `pause` при этом выполняется как раньше —
предупреждение не блокирует выполнение и не запрашивает подтверждения.

Identity текущей сессии контролируется через `ARTEL_SESSION_ID` (тот же
источник, что резолвит `orchestrator.session.resolve_session_id`, общий
для всех команд по предпосылке «Наблюдаемость сессий» — см. SPEC,
«Материалы»); держатель lease заводится ЯВНО отличной identity, чтобы
совпадение в выводе не могло быть случайным.

Красен до реализации: `orchestrator/pause.py::cmd_pause` сегодня вовсе
не читает таблицу `leases` (см. модульный докстринг `pause.py`) — ни
предупреждения, ни данных держателя в её выводе нет.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import pause, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, _ts_ago, capture  # noqa: E402

CURRENT_SESSION = "sess-current-ac1-pause"
HOLDER_SESSION = "sess-holder-ac1-pause"
HEARTBEAT_AGE_SEC = 5


class PauseWarnsOnForeignLiveLeaseTest(LeaseTaskTest):

    def setUp(self):
        super().setUp()
        self.insert_lease(self.TASK, HOLDER_SESSION, os.getpid(),
                          socket.gethostname(), _ts_ago(HEARTBEAT_AGE_SEC))

    def _run_pause(self) -> str:
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            return capture(pause.cmd_pause, self.TASK)

    def test_ac1_warning_names_holder_and_heartbeat_age(self):
        """`pause` на задаче с чужим живым lease обязан напечатать
        держателя (`session_id`) и числовой возраст его heartbeat.

        Ловит мутацию: разработчик добавляет предупреждение, но
        подставляет в него identity ТЕКУЩЕЙ сессии (или вовсе не
        держателя), либо печатает возраст heartbeat не числом (например,
        сырой timestamp) — держатель заведён заведомо ДРУГОЙ identity,
        чем текущая сессия, поэтому подмена не пройдёт незамеченной.
        """
        output = self._run_pause()

        self.assertIn(HOLDER_SESSION, output,
                     f"предупреждение не называет держателя lease: {output!r}")
        self.assertRegex(
            output, r"\d+\s*сек",
            f"предупреждение не называет числовой возраст heartbeat: "
            f"{output!r}")

    def test_ac1_warning_printed_before_pause_confirmation(self):
        """Предупреждение обязано появиться в выводе РАНЬШЕ, чем
        подтверждение самой команды (существующее сообщение
        `cmd_pause` о постановке на паузу) — «до выполнения команды»
        (AC-1) проверяется порядком печати, единственным наблюдаемым
        здесь прокси для порядка исполнения синхронного CLI-вызова.

        Ловит мутацию: разработчик ставит паузу и печатает штатное
        подтверждение ПЕРВЫМ, а предупреждение — ПОСЛЕ (например, читает
        lease уже в конце функции) — тест сравнивает позиции обеих
        подстрок в выводе и упадёт, если порядок инвертирован.
        """
        output = self._run_pause()

        warning_pos = output.find(HOLDER_SESSION)
        confirmation_pos = output.find("приостановлена")
        self.assertNotEqual(warning_pos, -1,
                            f"держатель не найден в выводе: {output!r}")
        self.assertNotEqual(confirmation_pos, -1,
                            f"подтверждение паузы не найдено в выводе: "
                            f"{output!r}")
        self.assertLess(
            warning_pos, confirmation_pos,
            f"предупреждение напечатано не раньше подтверждения команды: "
            f"{output!r}")

    def test_ac2_pause_still_pauses_the_task(self):
        """Несмотря на предупреждение, `pause` обязан выполниться как
        раньше: пометка паузы ставится, вызов не блокируется и не падает
        (ни `SystemExit`, ни исключение) — предупреждение только
        информирует.

        Ловит мутацию: разработчик оборачивает `cmd_pause` в
        `lease.run_locked(..., on_refusal="exit")` (как это уже сделано
        у пяти команд из «Не входит» SPEC) вместо простого
        предупреждения — тогда чужой живой lease привёл бы к
        `SystemExit`/`sys.exit`, и пометка паузы не появилась бы вовсе.
        """
        self._run_pause()

        self.assertTrue(
            pause.is_paused(self.task_row()),
            "pause не выполнилась (задача не помечена на паузе), хотя "
            "предупреждение не должно блокировать выполнение (AC-2)")


if __name__ == "__main__":
    unittest.main()
