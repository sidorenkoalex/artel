"""AC-6 (tasks/T053/SPEC.md): мьютекс с мёртвым держателем (протухший
heartbeat/неживой pid) не блокирует merge навечно: следующее взятие
перешагивает замок мёртвого держателя.

Требование 4 SPEC отсылает к `doctor.check_leases` (SPEC T044, требование
11) как образцу — тест вводит `doctor.check_merge_lock(conn) -> list[Check]`
по той же форме, что и `check_leases` (`orchestrator/doctor.py`): решение
разработчика, не факт уже существующего кода (тот же приём допущения, что
`tasks/T044/acceptance_tests/test_lease_readonly_and_doctor.py` уже
применила к `check_leases` самой). Порог протухания heartbeat —
`config.LEASE_STALE_AFTER_SEC`, см. `_mutex_sandbox.py`, «Допущения
интерфейса».

Критерий явно перечисляет ДВА независимых признака мёртвого держателя
(протухший heartbeat ИЛИ неживой pid) как одинаково не блокирующие
следующее взятие — оба проверены отдельными сценариями ниже, не только
один из двух.
"""
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, config, doctor, fsm, store  # noqa: E402

from _mutex_sandbox import (CALLER_SESSION, HOLDER_HOST, HOLDER_SESSION,  # noqa: E402
                            HOLDER_TASK, MergeLockFsmTest, invoke)


def _ts_ago(seconds: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


def _dead_pid() -> int:
    """Гарантированно мёртвый pid: дочерний процесс, дождавшийся своего
    завершения (тот же приём, что `tasks/T044/acceptance_tests/
    test_lease_readonly_and_doctor.py::Ac6DoctorDetectsDeadPidLeaseTest.
    _dead_pid`)."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    proc.wait()
    return proc.pid


class Ac6StaleHeartbeatHolderIsSteppedOverTest(MergeLockFsmTest):

    def test_ac6_stale_heartbeat_holder_does_not_block_next_approve(self):
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 5)
        self.seed_merge_lock(HOLDER_SESSION, 424242, HOLDER_HOST,
                             stale_ts, HOLDER_TASK)

        invoke(lambda: fsm.cmd_approve(self.TASK, session_id=CALLER_SESSION))

        self.assertEqual(
            self.state(), "done",
            "протухший (по heartbeat) держатель мьютекса не должен "
            "блокировать merge навечно — следующее взятие обязано "
            "перешагнуть его замок")


class Ac6DeadPidHolderIsSteppedOverTest(MergeLockFsmTest):

    def test_ac6_dead_pid_holder_does_not_block_next_approve(self):
        # Мёртвый pid проверим только на ЛОКАЛЬНОМ host — тем же
        # ограничением, что и `doctor.check_leases` (docstring
        # `orchestrator/doctor.py`: «чужой host не проверяется, pid без
        # доступа к его процессной таблице нельзя ни подтвердить, ни
        # опровергнуть»). Держатель на чужом host здесь неуместен: это
        # был бы тест невозможного, а не критерия.
        dead_pid = _dead_pid()
        self.seed_merge_lock(HOLDER_SESSION, dead_pid, socket.gethostname(),
                             store.now(), HOLDER_TASK)

        invoke(lambda: fsm.cmd_approve(self.TASK, session_id=CALLER_SESSION))

        self.assertEqual(
            self.state(), "done",
            "мёртвый pid держателя мьютекса не должен блокировать merge "
            "навечно — следующее взятие обязано перешагнуть его замок")


class Ac6DoctorDetectsDeadMergeLockHolderTest(MergeLockFsmTest):

    def test_ac6_doctor_flags_dead_pid_local_holder_as_incident(self):
        dead_pid = _dead_pid()
        self.seed_merge_lock(HOLDER_SESSION, dead_pid, socket.gethostname(),
                             store.now(), HOLDER_TASK)

        checks = doctor.check_merge_lock(store.db())

        self.assertTrue(
            any(c.status == "fail" for c in checks),
            "doctor.check_merge_lock не отметил мёртвый pid держателя "
            "мьютекса merge как провал")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if "merge" in (a["source"] or "").lower()]
        self.assertTrue(
            incidents,
            "не заведён incident-алерт по мёртвому держателю мьютекса merge")
        self.assertTrue(
            any(HOLDER_TASK in (a["message"] or "") for a in incidents),
            "incident-алерт не называет задачу, чей мьютекс merge мёртв")

    def test_ac6_doctor_does_not_flag_live_local_holder(self):
        import os
        self.seed_merge_lock(HOLDER_SESSION, os.getpid(),
                             socket.gethostname(), store.now(), HOLDER_TASK)

        checks = doctor.check_merge_lock(store.db())

        self.assertTrue(
            all(c.status != "fail" for c in checks),
            "живой держатель мьютекса merge ошибочно отмечен как мёртвый")


if __name__ == "__main__":
    import unittest
    unittest.main()
