"""Юнит-тесты разбора и исхода массовой формы `alert-ack` (SPEC
01M3YDHTY1Y67KB98FVSHREC4N, требования 4, 7) — углы, не покрытые
долгоживущим файлом задачи `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`:
флаг без значения, лишний позиционный аргумент, частичный отказ `ack`.
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

from orchestrator import alerts, artel, config, store
from tests.sandbox import SchemaConnTmpRootTest


class AlertAckBulkParsingTest(SchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        self.ids = [self.add_incident(f"No commits between main и task/{n}")
                    for n in range(3)]

    def add_incident(self, message: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO alerts (target, kind, source, message, ts) "
            "VALUES (?,?,?,?,?)",
            (config.DEFAULT_TARGET, "incident", "github_adapter", message,
             "2026-09-30 10:00:00Z"))
        self.conn.commit()
        return cur.lastrowid

    def dispatch(self, argv) -> tuple:
        out = io.StringIO()
        env = {"HOME": "/tmp/operator_parsing", "PATH": os.environ.get("PATH", "")}
        code = None
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def acked(self) -> list:
        return [store.get_alert(self.conn, i)["ack_ts"] is not None
                for i in self.ids]

    def test_flag_without_value_is_refused(self):
        """`--grep` последним аргументом или сразу перед `--yes` — отказ,
        ни один алерт не подтверждён.

        Ловит мутацию: разбор берёт следующий токен как значение без
        проверки — `--grep --yes` отбирает по подстроке «--yes» молча, а
        `--grep` в конце падает `IndexError` вместо внятного отказа.
        """
        for argv in (["alert-ack", "--source", "github_adapter", "решение",
                      "--yes", "--grep"],
                     ["alert-ack", "--source", "github_adapter", "решение",
                      "--grep", "--yes"]):
            with self.subTest(argv=argv):
                code, output = self.dispatch(argv)
                self.assertNotIn(code, (None, 0), output)
                self.assertIn("--grep требует значение", str(code))
                self.assertEqual(self.acked(), [False, False, False])

    def test_extra_positional_is_refused(self):
        """Два позиционных аргумента в массовой форме — отказ: какой из них
        решение, неизвестно.

        Ловит мутацию: лишний позиционный аргумент молча отбрасывается (или
        берётся последний) — пачка закрывается не тем текстом решения.
        """
        code, output = self.dispatch(
            ["alert-ack", "--source", "github_adapter", "--grep", "No commits",
             "первое", "второе", "--yes"])

        self.assertNotIn(code, (None, 0), output)
        self.assertEqual(self.acked(), [False, False, False])

    def test_one_failed_ack_does_not_stop_the_rest_but_fails_the_command(self):
        """`ack` отказал на одном отобранном — остальные подтверждены, код
        возврата ненулевой, отказ назван.

        Ловит мутацию: результат `alerts.ack` в цикле игнорируется — команда
        отвечает успехом, хотя часть пачки осталась открытой; либо первый
        отказ прерывает цикл, и хвост пачки не подтверждается.
        """
        real_ack = alerts.ack
        failing = self.ids[0]

        def flaky_ack(conn, alert_id, actor, resolution=""):
            if alert_id == failing:
                return f"alert {alert_id} уже подтверждён гонкой"
            return real_ack(conn, alert_id, actor, resolution)

        with mock.patch.object(alerts, "ack", flaky_ack):
            code, output = self.dispatch(
                ["alert-ack", "--source", "github_adapter", "--grep",
                 "No commits", "решение", "--yes"])

        self.assertNotIn(code, (None, 0), output)
        self.assertIn(f"alert {failing}", str(code))
        self.assertEqual(self.acked(), [False, True, True])
        self.assertIn("подтверждено: 2 из 3", output)


if __name__ == "__main__":
    unittest.main()
