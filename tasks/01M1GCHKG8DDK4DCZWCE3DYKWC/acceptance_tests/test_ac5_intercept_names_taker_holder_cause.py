"""AC-5: перехват lease мёртвого держателя журналируется записью,
называющей перенявшую сессию, прежнего держателя и причину перехвата
(pid мёртв или heartbeat протух).

Требование 3 SPEC называет ДВЕ возможные причины: «pid мёртв» — когда
прежний держатель на ЭТОМ ЖЕ host и его pid проверяемо мёртв (тот же
приём различения «свой/чужой host», которым уже пользуется `doctor.
check_leases`/`check_merge_lock` — чужой host не проверяется, потому
что нет доступа к его процессной таблице); «heartbeat протух» —
fallback, когда pid держателя проверить нельзя (чужой host). Сам
триггер перехвата (возраст heartbeat) не меняется (SPEC, «Не входит»:
«изменение механики advisory lease... не меняет его») — меняется
только то, ЧТО записывается как причина.

Сценарий B (чужой host) уже проходит СЕГОДНЯ — существующее сообщение
`lease.acquire` при перехвате уже пишет "lease протух (...) ... "
буквальным текстом с "протух" и обеими identity; отмечено докстрингом
теста как "зелёный с рождения": это не новая функциональность, а
существующее корректное поведение, которое сценарий A (мёртвый pid НА
ЭТОМ host) обязан НЕ сломать заодно с добавлением новой ветки причины.

Сценарий A (мёртвый pid на этом host) красный до реализации: сегодня
`lease.acquire` не проверяет `liveness._pid_alive` вовсе при перехвате
— причина всегда только "heartbeat протух", даже когда pid прежнего
держателя проверяемо мёртв на этой же машине.
"""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, lease, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, _ts_ago, any_step_carries, dead_pid  # noqa: E402


class InterceptCauseTest(LeaseTaskTest):

    def _stale_ts(self):
        return _ts_ago(config.LEASE_STALE_AFTER_SEC + 10)

    def test_ac5_intercept_names_dead_pid_cause_on_this_host(self):
        """Красный до реализации (см. докстринг модуля)."""
        self.insert_lease(self.TASK, "sess-holder-deadpid", dead_pid(),
                          socket.gethostname(), self._stale_ts())
        before = len(self.steps())

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-taker-a")

        self.assertIsNone(refusal)
        self.assertFalse(fresh)
        new_steps = self.steps()[before:]
        self.assertTrue(any_step_carries(new_steps, "sess-taker-a"),
                        f"перехват не называет перенявшую сессию: {new_steps}")
        self.assertTrue(any_step_carries(new_steps, "sess-holder-deadpid"),
                        f"перехват не называет прежнего держателя: {new_steps}")
        self.assertTrue(
            any("pid" in (s["detail"] or "")
                and ("мёртв" in (s["detail"] or "") or "мертв" in (s["detail"] or ""))
                for s in new_steps),
            f"причина перехвата не называет мёртвый pid прежнего "
            f"держателя, хотя он проверяемо мёртв на этом же host "
            f"(AC-5): {new_steps}")

    def test_ac5_intercept_names_heartbeat_cause_when_pid_unverifiable(self):
        """Зелёный с рождения (см. докстринг модуля): чужой host -> pid
        держателя проверить нельзя -> причина остаётся «heartbeat
        протух» — уже так работает существующее сообщение перехвата."""
        self.insert_lease(self.TASK, "sess-holder-foreign", 999999,
                          "other-host.invalid", self._stale_ts())
        before = len(self.steps())

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-taker-b")

        self.assertIsNone(refusal)
        self.assertFalse(fresh)
        new_steps = self.steps()[before:]
        self.assertTrue(any_step_carries(new_steps, "sess-taker-b"),
                        f"перехват не называет перенявшую сессию: {new_steps}")
        self.assertTrue(any_step_carries(new_steps, "sess-holder-foreign"),
                        f"перехват не называет прежнего держателя: {new_steps}")
        self.assertTrue(
            any("heartbeat" in (s["detail"] or "") or "протух" in (s["detail"] or "")
                for s in new_steps),
            f"причина перехвата не называет протухший heartbeat, когда "
            f"pid держателя нельзя проверить (AC-5): {new_steps}")


if __name__ == "__main__":
    unittest.main()
