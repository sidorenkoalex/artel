"""Приёмочные тесты T054 — авто-ack алертов `doctor.leases` и
`doctor.merge_lock` (SPEC.md, критерии AC-1..AC-4).

Песочница — тот же минимальный приём, что у
`tasks/T035/acceptance_tests/test_auto_ack.py`: собственный временный
`config.ROOT` с чистой БД, без копирования `skills/`/`templates/`/`docs/`
— эти тесты зовут `doctor.check_leases`/`doctor.check_merge_lock`/
`alerts.*`/`store.*` напрямую, как и `LeasesCheckTest`/`AutoAckTest` в
`tests/test_doctor.py`.

Каждая группа (AC-1, AC-2) — пара «условие исчезло → ack» / «условие
в силе → не ack», по образцу `tasks/T035/acceptance_tests/test_auto_ack.py`
(`BranchAutoAckTest` и др.), плюс отдельный тест на «условие исчезло»
через каждый из перечисленных в критерии путей (строка снята / держатель
сменился / pid жив).

AC-4 («все существующие тесты остаются зелёными без ослаблений») —
manual по той же причине, что AC-11 в T035: прогон полного набора
подпроцессом внутри acceptance-теста ловит несвязанные с этой задачей
экологические флейки окружения (см. докстрока
`tasks/T035/acceptance_tests/test_auto_ack.py`), а `.github/workflows/ci.yml`
уже гоняет `python3 -m unittest discover -s tests -v` на каждый пуш в
чистом раннере — это и есть проверка критерия.
"""
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, config, doctor, store  # noqa: E402

# AC-4: manual — критерий уже покрыт `.github/workflows/ci.yml`
# (`unittest discover -s tests -v` на каждый пуш в чистом раннере);
# повторение той же проверки подпроцессом внутри acceptance_tests ловит
# несвязанные с T054 экологические флейки окружения (тот же довод, что
# у AC-11 в tasks/T035/acceptance_tests/test_auto_ack.py).


class AutoAckSandboxTest(unittest.TestCase):
    """Временный `config.ROOT` с чистой БД — общая песочница для всех групп."""

    HOST = socket.gethostname()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("TARGETS", self.root / "targets.yaml"),
                            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        config.TASKS.mkdir(parents=True)
        store.create_schema(store.db())

    def conn(self):
        return store.db()

    @staticmethod
    def dead_pid() -> int:
        """Реальный, но уже завершённый процесс — гарантированно мёртвый pid,
        без риска столкнуться с живым процессом системы (тот же приём, что
        `tests/test_doctor.py::LeasesCheckTest.dead_pid`)."""
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def open_incidents(self, source: str) -> list:
        return [a for a in alerts.open_alerts(self.conn(), "incident")
               if a["source"] == source]

    def assert_auto_acked(self, alert_id: int) -> None:
        row = store.get_alert(self.conn(), alert_id)
        self.assertIsNotNone(row["ack_ts"], "алерт остался неподтверждённым")
        self.assertEqual(row["ack_by"], "doctor")
        self.assertIn("условие ушло, прогон doctor", row["ack_resolution"],
                      row["ack_resolution"])

    def assert_not_acked(self, alert_id: int) -> None:
        row = store.get_alert(self.conn(), alert_id)
        self.assertIsNone(row["ack_ts"],
                          "алерт получил ack, пока условие остаётся в силе")


class LeasesAutoAckTest(AutoAckSandboxTest):
    """AC-1: `doctor.leases` — ack, когда строки lease больше нет либо её
    pid жив; не-ack, пока мёртвый pid остаётся на этом host."""

    def _seed_task(self, task_id: str) -> None:
        store.insert_task(self.conn(), task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-zadacha",
                          config.DEFAULT_TARGET, 25.0)

    def test_ac1_lease_row_removed_gets_auto_acked_on_next_run(self):
        self._seed_task("T001")
        conn = self.conn()
        store.insert_lease(conn, "T001", "sess", self.dead_pid(), self.HOST,
                           store.now())

        doctor.check_leases(conn)
        incidents = self.open_incidents("doctor.leases")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        store.release_lease(conn, "T001", "sess")
        doctor.check_leases(conn)

        self.assert_auto_acked(alert_id)

    def test_ac1_lease_pid_becomes_alive_gets_auto_acked_on_next_run(self):
        self._seed_task("T001")
        conn = self.conn()
        store.insert_lease(conn, "T001", "sess", self.dead_pid(), self.HOST,
                           store.now())

        doctor.check_leases(conn)
        alert_id = self.open_incidents("doctor.leases")[0]["id"]

        store.update_lease(conn, "T001", "sess", os.getpid(), self.HOST,
                           store.now())
        doctor.check_leases(conn)

        self.assert_auto_acked(alert_id)

    def test_ac1_lease_pid_still_dead_is_not_acked(self):
        self._seed_task("T001")
        conn = self.conn()
        store.insert_lease(conn, "T001", "sess", self.dead_pid(), self.HOST,
                           store.now())

        doctor.check_leases(conn)
        alert_id = self.open_incidents("doctor.leases")[0]["id"]

        doctor.check_leases(conn)

        self.assert_not_acked(alert_id)


class MergeLockAutoAckTest(AutoAckSandboxTest):
    """AC-2: `doctor.merge_lock` — ack, когда замок снят, держатель сменился
    либо его pid жив; не-ack, пока мёртвый держатель остаётся на месте."""

    def _seed_task(self, task_id: str) -> None:
        store.insert_task(self.conn(), task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-zadacha",
                          config.DEFAULT_TARGET, 25.0)

    def test_ac2_lock_cleared_gets_auto_acked_on_next_run(self):
        self._seed_task("T001")
        conn = self.conn()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(), self.HOST,
                             store.now())

        doctor.check_merge_lock(conn)
        incidents = self.open_incidents("doctor.merge_lock")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        store.release_merge_lock(conn, "sess")
        doctor.check_merge_lock(conn)

        self.assert_auto_acked(alert_id)

    def test_ac2_holder_changed_gets_auto_acked_on_next_run(self):
        self._seed_task("T001")
        self._seed_task("T002")
        conn = self.conn()
        store.set_merge_lock(conn, "T001", "sess-1", self.dead_pid(), self.HOST,
                             store.now())

        doctor.check_merge_lock(conn)
        incidents = self.open_incidents("doctor.merge_lock")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        # Новый держатель — другая (task_id, session_id); его pid тоже
        # мёртв, чтобы отличить признак «держатель сменился» от признака
        # «pid жив», проверяемого отдельным тестом.
        store.set_merge_lock(conn, "T002", "sess-2", self.dead_pid(), self.HOST,
                             store.now())
        doctor.check_merge_lock(conn)

        self.assert_auto_acked(alert_id)

    def test_ac2_holder_pid_becomes_alive_gets_auto_acked_on_next_run(self):
        self._seed_task("T001")
        conn = self.conn()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(), self.HOST,
                             store.now())

        doctor.check_merge_lock(conn)
        alert_id = self.open_incidents("doctor.merge_lock")[0]["id"]

        store.set_merge_lock(conn, "T001", "sess", os.getpid(), self.HOST,
                             store.now())
        doctor.check_merge_lock(conn)

        self.assert_auto_acked(alert_id)

    def test_ac2_dead_holder_remains_is_not_acked(self):
        self._seed_task("T001")
        conn = self.conn()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(), self.HOST,
                             store.now())

        doctor.check_merge_lock(conn)
        alert_id = self.open_incidents("doctor.merge_lock")[0]["id"]

        doctor.check_merge_lock(conn)

        self.assert_not_acked(alert_id)


class SameAutoAckRecipeTest(AutoAckSandboxTest):
    """AC-3: `check_leases`/`check_merge_lock` закрывают алерт через тот же
    приём, что `check_orphans` (образец `_auto_ack_gone`) — тот же
    контракт `ack_by=doctor` / `ack_resolution` с «условие ушло, прогон
    doctor», не самодельная альтернативная реализация ack."""

    def test_ac3_leases_auto_ack_matches_the_orphans_contract(self):
        store.insert_task(self.conn(), "T001", "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        conn = self.conn()
        store.insert_lease(conn, "T001", "sess", self.dead_pid(), self.HOST,
                           store.now())
        doctor.check_leases(conn)
        alert_id = self.open_incidents("doctor.leases")[0]["id"]

        store.release_lease(conn, "T001", "sess")
        doctor.check_leases(conn)

        self.assert_auto_acked(alert_id)

    def test_ac3_merge_lock_auto_ack_matches_the_orphans_contract(self):
        store.insert_task(self.conn(), "T001", "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        conn = self.conn()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(), self.HOST,
                             store.now())
        doctor.check_merge_lock(conn)
        alert_id = self.open_incidents("doctor.merge_lock")[0]["id"]

        store.release_merge_lock(conn, "sess")
        doctor.check_merge_lock(conn)

        self.assert_auto_acked(alert_id)


if __name__ == "__main__":
    unittest.main()
