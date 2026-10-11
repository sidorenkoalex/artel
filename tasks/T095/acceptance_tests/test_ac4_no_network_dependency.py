"""AC-4 (tasks/T095/SPEC.md): блок метрики трения не превращает `report`
в команду, зависящую от сети, внешних сервисов или демона — данные
берутся только из уже доступных локально источников (файлы логов и/или
`state.db`).

Проверка — поведенческая, без единого мока источника данных: сеть
запрещается на уровне сокетов (`socket.socket.connect`/
`socket.create_connection` бросают исключение при любом обращении), и
`cmd_report()` с фикстурами логов трения обязан завершиться успешно —
если бы реализация полезла в сеть, тест упал бы на исключении из
патча, а не «прошёл бы, потому что мы велели ему не ходить в сеть».

Красен до реализации: `orchestrator.report`/`orchestrator.agent_log` не
несут метрику трения (`FrictionSandboxTest.setUp`, `_sandbox.py`).
"""
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (FrictionSandboxTest, bash_call, edit_call,  # noqa: E402
                      read_call)


def _forbidden(*args, **kwargs):
    raise AssertionError(
        "report/метрика трения попытались обратиться к сети — "
        "AC-4 требует данные только из локальных файлов")


class ReportHasNoNetworkDependencyTest(FrictionSandboxTest):

    def test_ac4_report_succeeds_with_sockets_blocked(self):
        self.mk_task("T001", "Задача-фикстура для AC-4")
        self.write_log("T001", "developer", 1, [
            read_call("t1", "a.py"),
            read_call("t2", "a.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])

        with mock.patch.object(socket.socket, "connect", _forbidden), \
             mock.patch("socket.create_connection", _forbidden):
            html = self.run_report_html()

        self.assertIn("трен", html.lower(),
                      "report завершился, но блок трения из вывода пропал")


if __name__ == "__main__":
    unittest.main()
