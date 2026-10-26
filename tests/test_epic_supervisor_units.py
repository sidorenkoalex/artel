"""Юнит-тесты надзора эпика `auto --epic` (SPEC 01M5TBF7JRZ6FGRR4K53KPAJDS)
на свойства вне долгоживущего файла задачи: сверка живости записанного
процесса (`lease.process_alive`), запрет `auto --epic` процессу роли и
отказ `epic stop` эпику без надзора и без дочерних `auto`.
"""
import io
import os
import socket
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import artel, config, doctor, lease, store
from tests.sandbox import InitializedTmpRootTest, TmpRootTest

NOW_FORMAT = "%Y-%m-%d %H:%M:%SZ"


def _moment(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime(NOW_FORMAT)


class ProcessAliveTest(TmpRootTest):

    def test_own_process_recorded_after_its_start_is_alive(self):
        """Процесс теста, записанный «сейчас», жив: pid есть, старт раньше.

        Ловит мутацию: сравнение времени старта перевёрнуто (`>=` вместо
        `<=`) — свой живой процесс считался бы мёртвым.
        """
        self.assertTrue(lease.process_alive(os.getpid(), socket.gethostname(),
                                            _moment(timedelta(seconds=5))))

    def test_undetermined_start_time_is_not_alive(self):
        """Время старта не определено (`process_start_time` → `None`) — не жив.

        Ловит мутацию: неопределённое время старта принимается за «жив»
        (проверка `None` убрана) — блокировка с переиспользованным pid
        держала бы эпик вечно.
        """
        with mock.patch.object(doctor, "process_start_time", return_value=None):
            self.assertFalse(lease.process_alive(
                os.getpid(), socket.gethostname(), _moment(timedelta(seconds=5))))

    def test_other_host_is_not_alive(self):
        """Строка другого хоста — не живой процесс этого хоста.

        Ловит мутацию: сверка хоста убрана — pid чужой машины, совпавший с
        живым локальным, считался бы живым.
        """
        self.assertFalse(lease.process_alive(
            os.getpid(), socket.gethostname() + "-другой",
            _moment(timedelta(seconds=5))))


class RoleGateTest(TmpRootTest):

    def test_epic_supervisor_refused_to_role_even_with_attach(self):
        """`auto --epic … --attach` процессу роли недоступен, `auto <id> --attach` — доступен.

        Ловит мутацию: исключение `--attach` для `run`/`auto` не сверяет
        `--epic` — роль могла бы запустить надзор эпика в своём процессе.
        """
        self.assertFalse(artel._role_allowed_command(
            "auto", ["--epic", "E01", "--observation", "x", "--attach"]))
        self.assertTrue(artel._role_allowed_command("auto", ["T001", "--attach"]))


class EpicStopWithoutSupervisorTest(InitializedTmpRootTest):

    def test_stop_without_supervisor_and_children_refused(self):
        """`epic stop` эпика без блокировки и без дочерних — отказ с причиной, журнал без записей остановки.

        Ловит мутацию: `epic stop` молча «успешен», когда останавливать
        нечего (нет проверки «ни блокировки, ни дочерних»).
        """
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "epic", "new",
                                             config.DEFAULT_TARGET, "Эпик",
                                             "--goal", "Цель"]), \
                redirect_stdout(buf):
            artel.main()
        epic_id = store.db().execute("SELECT id FROM epics").fetchone()["id"]
        before = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        with mock.patch.object(sys, "argv", ["artel.py", "epic", "stop", epic_id]), \
                self.assertRaises(SystemExit) as ctx:
            artel.main()
        self.assertIn("нечего останавливать", str(ctx.exception.code))
        after = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        self.assertEqual(before, after)
