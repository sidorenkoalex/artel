"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-6.

AC-6. Второй вызов `run`/`auto` той же сессии, пока lease первого жив
(другой pid, та же сессия, `same_host_ok=False`) — получает отказ по
AC-1 до запуска роли агента.

В отличие от AC-1 (сам `lease.acquire` в изоляции) здесь проверяется
уровень пульта требования 2 SPEC: команды `runner.cmd_run`/
`auto.cmd_auto` обязаны остановиться на отказе `lease.run_locked` ДО
вызова тела шага (`runner._cmd_run`/`auto._cmd_auto`), которое и
запускает агента (`runner.spawn_agent`) — подменённое тело здесь
играет роль «запуска роли»: если оно позвано, роль была бы запущена
поверх уже работающего цикла.

Красен до реализации: `lease.acquire` сегодня не отказывает в этом
сценарии вовсе (см. AC-1) — оба вызова `run_locked` увидят `refusal is
None` и выполнят тело; `SystemExit` не будет поднят `cmd_run`, а
`_cmd_run`/`_cmd_auto` будут вызваны, хотя не должны.
"""
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, runner, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTmpRootTest, insert_lease_row, spawn_alive_pid  # noqa: E402


class SecondRunOrAutoRefusesBeforeAgentLaunchTest(LeaseTmpRootTest):

    def test_ac6_second_run_of_the_same_session_refuses_before_the_role_body_runs(self):
        """`runner.cmd_run` второй раз той же сессии, пока первый (другой
        pid) жив — `sys.exit` именованным отказом, `runner._cmd_run`
        (тело шага, запускающее агента) не вызывается вовсе.

        Ловит мутацию: если `runner.cmd_run` перестанет передавать отказ
        `lease.run_locked` дальше в `sys.exit` (например, начнёт
        игнорировать возврат `run_locked`), `_cmd_run` будет вызвана
        поверх уже работающего цикла — ровно инцидент из «Контекст» SPEC.
        """
        conn = store.db()
        other_pid = spawn_alive_pid(self)
        insert_lease_row(conn, self.TASK, "sess-same", other_pid,
                         socket.gethostname(), store.now())

        with mock.patch.object(runner, "_cmd_run") as body:
            with self.assertRaises(SystemExit) as ctx:
                runner.cmd_run(self.TASK, session_id="sess-same")

        self.assertIn("этой же сессии", str(ctx.exception))
        body.assert_not_called()

    def test_ac6_second_auto_of_the_same_session_refuses_before_the_cycle_runs(self):
        """`auto.cmd_auto` (канал отказа `on_refusal="print"`, не
        `sys.exit`) второй раз той же сессии, пока первый (другой pid)
        жив — печатает отказ, `auto._cmd_auto` (тело цикла) не
        вызывается.

        Ловит мутацию: если `auto.cmd_auto` при отказе всё равно дойдёт
        до `_cmd_auto` (например, перепутает `on_refusal="print"` с
        «отказ игнорируется»), второй `auto` запустит цикл поверх
        первого — тот же класс дефекта, что и для `run` выше, но по
        другому каналу отказа `run_locked`.
        """
        conn = store.db()
        other_pid = spawn_alive_pid(self)
        insert_lease_row(conn, self.TASK, "sess-same", other_pid,
                         socket.gethostname(), store.now())

        with mock.patch.object(auto, "_cmd_auto") as body:
            out = capture(auto.cmd_auto, self.TASK, "sess-same")

        self.assertIn("этой же сессии", out)
        body.assert_not_called()


if __name__ == "__main__":
    unittest.main()
