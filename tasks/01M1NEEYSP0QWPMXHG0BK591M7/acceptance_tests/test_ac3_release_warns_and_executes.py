"""AC-3: `release` для задачи с ЧУЖИМ живым lease печатает ДО выполнения
команды предупреждение с тем же составом данных, что AC-1 требует от
`pause` (держатель, возраст heartbeat), и команда выполняется как
раньше (lease реально снимается).

Тот же приём контроля identity через `ARTEL_SESSION_ID`, что и
`test_ac1_ac2_pause_warns_and_executes.py` — см. его докстринг.

Красен до реализации: `orchestrator/release.py::cmd_release` сегодня
снимает ЛЮБОЙ lease безусловно, не проверяя свежесть/владельца (см.
модульный докстринг `release.py`, «Свежесть lease не проверяется перед
снятием») — предупреждения в её выводе нет.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import release  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, _ts_ago, capture  # noqa: E402

CURRENT_SESSION = "sess-current-ac3-release"
HOLDER_SESSION = "sess-holder-ac3-release"
HEARTBEAT_AGE_SEC = 5


class ReleaseWarnsOnForeignLiveLeaseTest(LeaseTaskTest):

    def setUp(self):
        super().setUp()
        self.insert_lease(self.TASK, HOLDER_SESSION, os.getpid(),
                          socket.gethostname(), _ts_ago(HEARTBEAT_AGE_SEC))

    def _run_release(self) -> str:
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            return capture(release.cmd_release, self.TASK)

    def test_ac3_warning_names_holder_and_heartbeat_age(self):
        """`release` на задаче с чужим живым lease обязан напечатать
        держателя и числовой возраст heartbeat — тот же состав данных,
        что AC-1 требует от `pause`.

        Ловит мутацию: разработчик переносит предупреждение из `pause`
        только частично (например, называет держателя, но не возраст
        heartbeat) — held-session и heartbeat проверяются раздельными
        assert'ами, оба обязаны присутствовать.
        """
        output = self._run_release()

        self.assertIn(HOLDER_SESSION, output,
                     f"предупреждение не называет держателя lease: {output!r}")
        self.assertRegex(
            output, r"\d+\s*сек",
            f"предупреждение не называет числовой возраст heartbeat: "
            f"{output!r}")

    def test_ac3_warning_printed_before_release_confirmation(self):
        """Предупреждение обязано появиться в выводе раньше существующего
        подтверждения `cmd_release` («lease снят Оператором») — тот же
        приём проверки порядка, что и AC-1 для `pause`.

        Ловит мутацию: держатель узнаётся и печатается уже ПОСЛЕ того,
        как lease снят и напечатано подтверждение (например,
        предупреждение добавлено дополнительной строкой в конце функции
        вместо самого начала) — сравнение позиций подстрок в выводе
        поймает инвертированный порядок.
        """
        output = self._run_release()

        warning_pos = output.find(HOLDER_SESSION)
        confirmation_pos = output.find("lease снят Оператором")
        self.assertNotEqual(warning_pos, -1,
                            f"держатель не найден в выводе: {output!r}")
        self.assertNotEqual(confirmation_pos, -1,
                            f"подтверждение снятия lease не найдено в "
                            f"выводе: {output!r}")
        self.assertLess(
            warning_pos, confirmation_pos,
            f"предупреждение напечатано не раньше подтверждения команды: "
            f"{output!r}")

    def test_ac3_release_still_removes_the_lease(self):
        """Несмотря на предупреждение, `release` обязан выполниться как
        раньше — чужой живой lease реально снимается, вызов не падает и
        не отказывает.

        Ловит мутацию: разработчик оборачивает `cmd_release` отказом при
        чужом живом lease (по образцу пяти команд из «Не входит» SPEC)
        вместо простого предупреждения — тогда lease остался бы на
        месте.
        """
        self._run_release()

        self.assertIsNone(
            self.lease_row(),
            "release не снял чужой живой lease, хотя предупреждение не "
            "должно блокировать выполнение (AC-3)")


if __name__ == "__main__":
    unittest.main()
