"""AC-5: если чужой lease МЁРТВЫЙ (pid не адресуем) или ПРОТУХШИЙ
(heartbeat не свежий), предупреждение не печатается ни для `pause`, ни
для `release` — «живой» по SPEC (требование 1, AC-1) означает ОБЕ
условия разом: heartbeat свежий И pid адресуем; отсутствие любого из
двух — не «живой», предупреждения быть не должно.

Два сценария на команду, независимо покрывающие каждое из двух условий
дизъюнкции «мёртвый ИЛИ протухший» (SPEC, AC-5): heartbeat протух (при
заведомо живом pid — сам тестовый процесс) и pid мёртв (при заведомо
свежем heartbeat) — так тест не может пройти случайно из-за того, что
оба условия совпали в одном сценарии.

Проверка — тем же приёмом точного/допускового совпадения вывода, что и
`test_ac4_own_lease_no_warning.py`: вывод обязан остаться тем же, что и
сегодня, без добавленной строки предупреждения.

Зелёный с рождения: ни `pause.cmd_pause`, ни `release.cmd_release`
сегодня не проверяют свежесть/живость держателя lease вовсе — вывод уже
сегодня совпадает с ожидаемым; тест фиксирует это как регрессионный
барьер против ложного срабатывания предупреждения на мёртвом/протухшем
чужом lease.
"""
import os
import re
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, pause, release  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TASK, LeaseTaskTest, dead_pid, _ts_ago, capture  # noqa: E402

CURRENT_SESSION = "sess-current-ac5"
HOLDER_SESSION = "sess-holder-ac5"

PAUSE_EXPECTED_RE = re.compile(
    r"^" + re.escape(
        f"[{TASK}] приостановлена: следующий run/auto не начнёт агентный "
        f"шаг, пока не выполнишь `artel.py resume {TASK}`") + r"\n$")


def release_expected_re(task_id: str, session_id: str, pid: int,
                        hostname: str) -> re.Pattern:
    return re.compile(
        r"^" + re.escape(f"[{task_id}] lease снят Оператором: session_id="
                         f"{session_id}, pid={pid}, hostname={hostname}, "
                         f"heartbeat ") + r"\d+" + re.escape(" сек назад")
        + r"\n$")


class StaleHeartbeatNoWarningTest(LeaseTaskTest):
    """Heartbeat протух (старше `config.LEASE_STALE_AFTER_SEC`), pid при
    этом заведомо жив (сам тестовый процесс) — протух ИМЕННО по
    heartbeat, не по pid."""

    def setUp(self):
        super().setUp()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 100)
        self.insert_lease(self.TASK, HOLDER_SESSION, os.getpid(),
                          socket.gethostname(), stale_ts)

    def test_ac5_pause_no_warning_for_stale_heartbeat(self):
        """`pause` на задаче с протухшим по heartbeat чужим lease
        печатает ровно то же, что и сегодня.

        Ловит мутацию: разработчик решает «живой/мёртвый» только по
        адресуемости pid, забывая свериться со свежестью heartbeat —
        этот сценарий держит pid заведомо живым, поэтому такая мутация
        ошибочно сочла бы lease живым и напечатала предупреждение.
        """
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            output = capture(pause.cmd_pause, self.TASK)

        self.assertRegex(
            output, PAUSE_EXPECTED_RE,
            f"pause напечатала предупреждение при протухшем по heartbeat "
            f"чужом lease (AC-5): {output!r}")

    def test_ac5_release_no_warning_for_stale_heartbeat(self):
        """`release` на задаче с протухшим по heartbeat чужим lease
        печатает ровно то же, что и сегодня.

        Ловит мутацию: та же, что и у теста pause выше — свежесть
        heartbeat не проверяется, только адресуемость pid.
        """
        expected_re = release_expected_re(self.TASK, HOLDER_SESSION,
                                          os.getpid(), socket.gethostname())

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            output = capture(release.cmd_release, self.TASK)

        self.assertRegex(
            output, expected_re,
            f"release напечатала предупреждение при протухшем по "
            f"heartbeat чужом lease (AC-5): {output!r}")


class DeadPidNoWarningTest(LeaseTaskTest):
    """Heartbeat свежий, pid при этом заведомо мёртв — не «живой»
    ИМЕННО по адресуемости pid, не по heartbeat."""

    def setUp(self):
        super().setUp()
        self.holder_pid = dead_pid()
        self.insert_lease(self.TASK, HOLDER_SESSION, self.holder_pid,
                          socket.gethostname(), _ts_ago(5))

    def test_ac5_pause_no_warning_for_dead_pid(self):
        """`pause` на задаче с мёртвым по pid чужим lease печатает ровно
        то же, что и сегодня.

        Ловит мутацию: разработчик решает «живой/мёртвый» только по
        свежести heartbeat, не проверяя адресуемость pid — этот сценарий
        держит heartbeat заведомо свежим, поэтому такая мутация ошибочно
        сочла бы lease живым и напечатала предупреждение.
        """
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            output = capture(pause.cmd_pause, self.TASK)

        self.assertRegex(
            output, PAUSE_EXPECTED_RE,
            f"pause напечатала предупреждение при мёртвом по pid чужом "
            f"lease (AC-5): {output!r}")

    def test_ac5_release_no_warning_for_dead_pid(self):
        """`release` на задаче с мёртвым по pid чужим lease печатает
        ровно то же, что и сегодня.

        Ловит мутацию: та же, что и у теста pause выше — адресуемость
        pid не проверяется, только свежесть heartbeat.
        """
        expected_re = release_expected_re(self.TASK, HOLDER_SESSION,
                                          self.holder_pid,
                                          socket.gethostname())

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            output = capture(release.cmd_release, self.TASK)

        self.assertRegex(
            output, expected_re,
            f"release напечатала предупреждение при мёртвом по pid чужом "
            f"lease (AC-5): {output!r}")


if __name__ == "__main__":
    unittest.main()
