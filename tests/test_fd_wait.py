"""Функция ожидания `tests.fd_wait.wait_readable` (SPEC
01M5G6PDQA7AYDYDPA7DD5JD4S, требование 7; ANSWER-3).

Оба пути проверяются на любой машине: платформа подменяется на время
теста (`sys.platform`), функция выбирает путь в момент вызова.
"""
import os
import select
import sys
import unittest
from unittest import mock

from tests import fd_wait


def _close_quietly(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


class WaitReadableTest(unittest.TestCase):

    def pipe(self) -> tuple:
        reader, writer = os.pipe()
        self.addCleanup(_close_quietly, writer)
        return reader, writer

    def assert_ready_then_eof(self, reader: int, writer: int) -> None:
        self.assertFalse(fd_wait.wait_readable(reader, 0), "готовность без записи")
        os.write(writer, b"x")
        self.assertTrue(fd_wait.wait_readable(reader, 5), "запись не видна")
        self.assertEqual(os.read(reader, 16), b"x")
        os.close(writer)
        self.assertTrue(fd_wait.wait_readable(reader, 5), "конец файла не виден")
        self.assertEqual(os.read(reader, 16), b"")

    def test_off_darwin_waits_on_fd_above_select_limit(self):
        """Вне Darwin функция ждёт на дескрипторе ≥ 1100: готовность после записи, конец файла после закрытия пишущего конца.

        Сценарий: `sys.platform` — `linux`; читающий конец канала перенесён
        `high_fd` на номер не меньше 1100, исходный закрыт; функция без
        записи не готова, после записи готова, после закрытия пишущего
        конца готова и чтение даёт конец файла; `select.select` не зовётся.

        Ловит мутацию: функция вне Darwin вернулась к `select.select` (или к
        `selectors.SelectSelector`) — на дескрипторе ≥ 1100 он поднимает
        `ValueError: filedescriptor out of range in select()`; `high_fd` не
        закрывает исходный дескриптор — `os.fstat` по нему успешен.
        """
        reader, writer = self.pipe()
        with mock.patch.object(sys, "platform", "linux"):
            high = fd_wait.high_fd(self, reader)
            self.addCleanup(_close_quietly, high)
            self.assertGreaterEqual(high, fd_wait.HIGH_FD)
            with self.assertRaises(OSError):
                os.fstat(reader)
            with mock.patch.object(select, "select", wraps=select.select) as spy:
                self.assert_ready_then_eof(high, writer)
            spy.assert_not_called()

    def test_darwin_keeps_select_select(self):
        """На Darwin функция ждёт прежним `select.select`: готовность после записи, конец файла после закрытия пишущего конца.

        Сценарий: `sys.platform` — `darwin`; канал с исходным номером
        дескриптора; функция без записи не готова, после записи готова,
        после закрытия пишущего конца готова и чтение даёт конец файла;
        `select.select` вызван.

        Ловит мутацию: на Darwin функция ушла на `selectors`/`poll`
        (`kqueue` не сообщает конец файла именованного канала) — вызова
        `select.select` нет.
        """
        reader, writer = self.pipe()
        self.addCleanup(_close_quietly, reader)
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(select, "select", wraps=select.select) as spy:
            self.assert_ready_then_eof(reader, writer)
        self.assertTrue(spy.called, "select.select на Darwin не вызван")


if __name__ == "__main__":
    unittest.main()
