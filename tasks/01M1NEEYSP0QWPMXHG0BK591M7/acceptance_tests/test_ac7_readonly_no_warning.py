"""AC-7: read-only команды `status`, `log`, `show`, `doctor` не печатают
предупреждение при чужом живом lease задачи ни при каких условиях.

Каждая команда проверяется своим способом, подобранным под то, что она
УЖЕ сегодня легитимно показывает о lease (решение разработчика прежней
задачи 01M1GCHKG8DDK4DCZWCE3DYKWC не входит в объём этой SPEC и не
трогается ею):

- `status` уже показывает держателя lease (AC-11 прежней задачи) —
  проверка не «session_id отсутствует в выводе» (это было бы ложным
  провалом уже сегодня легитимной строки), а «существующая добавка
  `_lease_holder_suffix` — последнее, что стоит в строке задачи»: новый
  текст предупреждения не допишется ПОСЛЕ неё.
- `log` показывает `session_id` только у СУЩЕСТВУЮЩИХ записей журнала,
  которые сам держатель lease не писал — держатель в её выводе просто
  не должен появиться.
- `show` вообще не касается lease — держатель не должен появиться.
- `doctor` (`doctor.check_leases`) для ЖИВОГО lease (в отличие от
  мёртвого) сегодня возвращает фиксированное сообщение без данных
  держателя — тест сверяет его дословно.

Красен НЕ будет — это ожидаемо (см. «Зелёный с рождения» ниже): AC-7
описывает свойство, которое должно оставаться истинным ДО и ПОСЛЕ
реализации AC-1..AC-6 (read-only команды никогда не должны звать
предупреждающий путь) — регрессионный барьер, а не новая функциональность.

Зелёный с рождения: ни одна из четырёх команд сегодня не знает о новом
предупреждении вовсе (оно ещё не реализовано) — тест фиксирует
ожидаемое поведение, чтобы реализация AC-1..AC-6 (скорее всего, общая
вспомогательная функция) не оказалась по ошибке подключена и к этим
командам.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, doctor, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, _ts_ago, capture  # noqa: E402

CURRENT_SESSION = "sess-current-ac7"
HOLDER_SESSION = "sess-holder-ac7"
HEARTBEAT_AGE_SEC = 5


class ReadonlyCommandsNoWarningTest(LeaseTaskTest):

    def setUp(self):
        super().setUp()
        self.insert_lease(self.TASK, HOLDER_SESSION, os.getpid(),
                          socket.gethostname(), _ts_ago(HEARTBEAT_AGE_SEC))

    def _run(self, fn, *args) -> str:
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            return capture(fn, *args)

    def test_ac7_status_appends_nothing_after_existing_lease_suffix(self):
        """`status` для задачи с чужим живым lease обязана оставить
        существующую добавку держателя (`[lease: <session_id> жив]`,
        AC-11 задачи 01M1G...) ПОСЛЕДНИМ, что стоит в строке — без
        дописанного вслед за ней текста предупреждения.

        Ловит мутацию: разработчик по ошибке подключает предупреждение и
        к `cmd_status` (например, переиспользуя общий хелпер AC-1/AC-3
        отовсюду, где виден live-лизинг) — тогда строка задачи обзаведётся
        текстом ПОСЛЕ уже существующей добавки `[lease: ... жив]`, и
        `endswith` ниже перестанет совпадать.
        """
        output = self._run(catalog.cmd_status)
        line = next(ln for ln in output.splitlines()
                   if ln.startswith(self.TASK))

        expected_suffix = f"[lease: {HOLDER_SESSION} жив]"
        self.assertTrue(
            line.endswith(expected_suffix),
            f"строка status получила текст ПОСЛЕ существующей добавки "
            f"держателя lease — похоже на предупреждение read-only "
            f"команды (AC-7): {line!r}")

    def test_ac7_log_does_not_mention_the_foreign_holder(self):
        """`log` для задачи с чужим живым lease не должен вообще
        упоминать держателя — `log` показывает `session_id` только у
        существующих записей журнала, которые держатель не писал.

        Ловит мутацию: разработчик подключает предупреждение и к
        `cmd_log` — держатель тогда появился бы в выводе, хотя ни одной
        записи от его имени в журнале нет.
        """
        self.insert_step(self.TASK, "developer", "pre-flight ok")

        output = self._run(catalog.cmd_log, self.TASK)

        self.assertNotIn(
            HOLDER_SESSION, output,
            f"log упомянул держателя чужого lease — read-only команда "
            f"не должна печатать предупреждение (AC-7): {output!r}")

    def test_ac7_show_does_not_mention_the_foreign_holder(self):
        """`show` вообще не касается lease — держатель чужого живого
        lease не должен появиться в её выводе.

        Ловит мутацию: разработчик подключает предупреждение и к
        `cmd_show` — держатель тогда появился бы в её выводе, хотя
        `show` сегодня о lease вообще не знает.
        """
        output = self._run(catalog.cmd_show, self.TASK)

        self.assertNotIn(
            HOLDER_SESSION, output,
            f"show упомянул держателя чужого lease — read-only команда "
            f"не должна печатать предупреждение (AC-7): {output!r}")

    def test_ac7_doctor_lease_check_unchanged_for_live_foreign_lease(self):
        """`doctor` (`doctor.check_leases`) для ЖИВОГО чужого lease
        обязан вернуть ровно то же фиксированное сообщение, что и
        сегодня («нет lease с мёртвым pid на этом host») — доктор
        проверяет только МЁРТВЫЕ leases, живой чужой lease не должен
        породить ни строку про держателя, ни тем более предупреждение.

        Ловит мутацию: разработчик подключает предупреждение и к
        `doctor.check_leases` для любого чужого lease (не только
        мёртвого) — тогда результат перестал бы дословно совпадать с
        сегодняшним фиксированным сообщением.
        """
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": CURRENT_SESSION}):
            checks = doctor.check_leases(store.db())

        self.assertEqual(len(checks), 1, checks)
        self.assertEqual(checks[0].status, "ok", checks)
        self.assertEqual(
            checks[0].detail, "нет lease с мёртвым pid на этом host",
            f"doctor изменил сообщение для живого чужого lease — похоже "
            f"на добавленное предупреждение read-only команды (AC-7): "
            f"{checks[0]!r}")


if __name__ == "__main__":
    unittest.main()
