"""AC-4: если lease задачи принадлежит ТЕКУЩЕЙ сессии (session_id
совпадает), предупреждение не печатается ни для `pause`, ни для
`release` — вывод обеих команд обязан остаться БУКВАЛЬНО тем же, что и
сегодня (см. текущий текст `cmd_pause`/`cmd_release`
в `orchestrator/pause.py`/`orchestrator/release.py`): точное совпадение
строкой — самый прямой способ убедиться, что предупреждение не
добавлено вовсе, не гадая о его будущей формулировке.

Зелёный с рождения: ни `pause.cmd_pause`, ни `release.cmd_release`
сегодня не читают `session_id` держателя lease вовсе (см. их модульные
докстрайны) — вывод уже сегодня в точности совпадает с ожидаемым;
тест фиксирует это как регрессионный барьер против добавления
предупреждения ДЛЯ СВОЕГО lease при реализации AC-1/AC-3.
"""
import os
import re
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import pause, release  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, _ts_ago, capture  # noqa: E402

CURRENT_SESSION = "sess-current-ac4"
HEARTBEAT_AGE_SEC = 5


class OwnLeaseNoWarningTest(LeaseTaskTest):

    def setUp(self):
        super().setUp()
        self.insert_lease(self.TASK, CURRENT_SESSION, os.getpid(),
                          socket.gethostname(), _ts_ago(HEARTBEAT_AGE_SEC))

    def test_ac4_pause_output_unchanged_for_own_live_lease(self):
        """`pause` на задаче со СВОИМ живым lease обязана напечатать
        ровно то же сообщение, что и сегодня, без единой добавленной
        строки предупреждения.

        Ловит мутацию: разработчик проверяет только «lease живой», но
        забывает исключить случай `session_id держателя == текущая
        сессия» — тогда предупреждение появилось бы и для своего же
        lease, output перестал бы совпадать с текущим байт-в-байт.
        """
        expected = (
            f"[{self.TASK}] приостановлена: следующий run/auto не начнёт "
            f"агентный шаг, пока не выполнишь `artel.py resume "
            f"{self.TASK}`\n")

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            output = capture(pause.cmd_pause, self.TASK)

        self.assertEqual(
            output, expected,
            f"pause добавила текст в вывод при СВОЁМ живом lease "
            f"(предупреждения быть не должно, AC-4): {output!r}")

    def test_ac4_release_output_unchanged_for_own_live_lease(self):
        """`release` на задаче со СВОИМ живым lease обязана напечатать
        ровно то же сообщение, что и сегодня (снятие + существующие
        данные держателя в информационном сообщении о снятии), без
        добавленного предупреждения ПЕРЕД ним.

        Ловит мутацию: разработчик добавляет предупреждение по одному
        лишь признаку «lease живой», не сверяя session_id держателя с
        текущей сессией — вывод тогда обзавёлся бы лишней строкой перед
        существующим сообщением о снятии.
        """
        row = self.lease_row()
        # Возраст heartbeat не фиксируется точным числом секунд (тест и
        # `cmd_release` считают его в разные моменты времени, число
        # может разойтись на 1) — только диапазон `\d+`, тем же приёмом
        # терпимости, что `tests/test_release.py` уже применяет к
        # похожей проверке.
        expected_re = re.compile(
            r"^" + re.escape(f"[{self.TASK}] lease снят Оператором: "
                             f"session_id={CURRENT_SESSION}, "
                             f"pid={row['pid']}, hostname={row['hostname']}, "
                             f"heartbeat ") + r"\d+"
            + re.escape(" сек назад") + r"\n$")

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            output = capture(release.cmd_release, self.TASK)

        self.assertRegex(
            output, expected_re,
            f"release добавила текст в вывод при СВОЁМ живом lease "
            f"(предупреждения быть не должно, AC-4): {output!r}")


if __name__ == "__main__":
    unittest.main()
