"""AC-9 (tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md): «Тест перехвата из
AC-1 подтверждает: обращение к адресу с DNS-именем (например,
несуществующий домен либо адрес, у которого подменён резолвер)
завершается быстрее секунды и без сетевого DNS-резолва.»

Красен до реализации: как и AC-1, `SpyRun(passthrough_unknown=True)`
сегодня не перехватывает `fetch` с DNS-адресом вовсе (`tests/
sandbox.py:476`) — без перехвата код ушёл бы в реальный git-процесс;
мок `_REAL_RUN` ниже не даёт этому попытаться связаться с сетью, но
ассерты о rc/времени остаются заточены под КОРРЕКТНЫЙ именованный отказ,
которого без перехвата не будет.
"""
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import gitcmd  # noqa: E402
from tests import sandbox  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class NetworkInterceptionIsInstantAndResolverFreeTest(TmpRootTest):

    def test_ac9_dns_address_fetch_completes_under_a_second_without_resolving(self):
        """`fetch` с адресом на DNS-имя, при подменённом резолвере
        (`socket.getaddrinfo` мгновенно бросает `gaierror`), обязан
        завершиться быстрее секунды именованным отказом — перехват
        решает по ФОРМЕ адреса (текстовый префикс `file://`/абсолютный
        путь), не пытаясь его резолвить.

        Ловит мутацию: перехват решает «локальный ли адрес» вызовом
        реального резолвера (`socket.getaddrinfo` или аналог) вместо
        текстовой проверки префикса — подменённый резолвер здесь
        мгновенно бросает `socket.gaierror` при любом обращении;
        реализация, которая его вызывает и не ловит исключение, упадёт
        трейсбеком (тест поймает это как ошибку, не тихий повод),
        реализация, которая вообще не резолвит, не заметит подмену и
        уложится в секунду с корректным отказом.
        """
        with mock.patch.object(sandbox, "_REAL_RUN") as real_run, \
             mock.patch.object(socket, "getaddrinfo",
                               side_effect=socket.gaierror(
                                   "Name or service not known")):
            start = time.monotonic()
            res = gitcmd.git("fetch", "-q",
                             "https://no-such-host-ac9.invalid.example/x",
                             "main")
            elapsed = time.monotonic() - start

        self.assertLess(elapsed, 1.0,
                        "перехват обязан отвечать быстрее секунды")
        self.assertNotEqual(0, res.returncode)
        self.assertIn("сеть в тестах запрещена: fetch", res.stderr)
        real_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
