"""Приёмочные тесты T044 — advisory-lease задачи: AC-5, AC-6, AC-7 (SPEC.md).

AC-1..AC-4 — в `test_lease_enforcement.py` (там же — общий разбор
допущений интерфейса, которые вводит этот файл: `session_id` как
необязательный параметр мутирующих команд, `config.LEASE_STALE_AFTER_SEC`,
форма таблицы `leases`).

Здесь дополнительно вводится:

- `doctor.check_leases(conn) -> list[Check]` — новая точечная проверка,
  по образцу уже существующих `doctor.check_orphans`/
  `doctor.check_backup_age` (SPEC требование 11 прямо отсылает к
  `check_orphans` как прецеденту структуры). Тест зовёт её напрямую, а не
  через `doctor.all_checks()` — последняя тянет живой смоук CLI и сетевые
  проверки forge, не имеющие отношения к этому критерию (тот же довод,
  что у `tests/test_doctor.py::OrphansTest`, которая тоже зовёт
  `doctor.check_orphans(store.db())` напрямую).
- Источник incident-алерта о мёртвом lease назван `doctor.leases.*` — по
  аналогии с `doctor.orphans.*`/`doctor.recovery.*`; тест проверяет
  вхождение `"lease"` в `source`, не точную строку, — минимум, который
  реально нужен критерию.

Песочница — `tests.sandbox.TmpRootTest` (пути `config` во временном
каталоге), без git-заглушки и агентского фреймворка `FsmTest`: читающие
команды (`show`/`status`/`log`) и `doctor.check_leases` не запускают ни
git, ни агента.
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

# AC-7: manual — «полный существующий набор тестов остаётся зелёным»
# уже покрыт `.github/workflows/ci.yml` (джоб `python`,
# `unittest discover -s tests -v` на каждый пуш в чистом раннере,
# прецедент tasks/T042 AC-5 / tasks/T043 SPEC): повтор всего набора
# подпроцессом внутри acceptance_tests ловил бы окружение машины
# разработчика, а не дефект этой задачи.

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, catalog, config, doctor, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class LeaseReadonlyDoctorSandbox(TmpRootTest):
    """Пути `config` — во временном каталоге; задача T001 заведена напрямую
    (`store.insert_task`, как `tests/test_doctor.py::OrphansTest`) — без
    git-веток и артефактов, читающим командам и `doctor.check_leases` они
    не нужны."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def insert_lease(self, session_id: str, pid: int, hostname: str,
                     heartbeat_ts: str) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def lease_rows(self) -> list:
        return [dict(r) for r in store.db().execute(
            "SELECT * FROM leases WHERE task_id=?", (self.TASK,))]


class Ac5ReadonlyCommandsDontTouchLeaseTest(LeaseReadonlyDoctorSandbox):
    """AC-5: `show`/`status`/`log` на задаче с чужим живым lease — без
    отказа и без изменения таблицы `leases`."""

    def setUp(self):
        super().setUp()
        self.insert_lease("session-other", 424242, "other-host",
                          store.now())

    def test_ac5_show_status_log_run_clean_against_foreign_live_lease(self):
        before = self.lease_rows()

        for name, call in (
            ("status", catalog.cmd_status),
            ("show", lambda: catalog.cmd_show(self.TASK)),
            ("log", lambda: catalog.cmd_log(self.TASK)),
        ):
            with self.subTest(команда=name):
                # Отказ по лизингу здесь и есть неожиданность: эти команды
                # обязаны выполниться как обычно (SPEC требование 10),
                # SystemExit — уже провал критерия.
                capture(call)
                self.assertEqual(
                    self.lease_rows(), before,
                    f"{name}: таблица leases изменилась от читающей команды")


class Ac6DoctorDetectsDeadPidLeaseTest(LeaseReadonlyDoctorSandbox):
    """AC-6: lease с мёртвым `pid` на локальном host — `doctor` замечает
    и заводит incident-алерт по нему."""

    @staticmethod
    def _dead_pid() -> int:
        """Гарантированно мёртвый pid: дочерний процесс, дождавшийся
        своего завершения (тот же принцип надёжности, что и остальные
        doctor-проверки — `check_orphans` полагается на реальные git/FS
        факты, не на угаданное число)."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def test_ac6_dead_pid_lease_on_local_host_raises_incident(self):
        dead_pid = self._dead_pid()
        self.insert_lease("session-crashed", dead_pid, socket.gethostname(),
                          store.now())

        checks = doctor.check_leases(store.db())

        self.assertTrue(
            any(c.status == "fail" for c in checks),
            "doctor.check_leases не отметил lease с мёртвым pid как провал")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if "lease" in (a["source"] or "").lower()]
        self.assertTrue(
            incidents, "не заведён incident-алерт по lease с мёртвым pid")
        self.assertTrue(
            any(self.TASK in (a["message"] or "") for a in incidents),
            "incident-алерт не называет задачу, чей lease мёртв")

    def test_ac6_live_pid_lease_is_not_flagged(self):
        """Контроль: свой (заведомо живой) процесс — не incident."""
        self.insert_lease("session-alive", os.getpid(), socket.gethostname(),
                          store.now())

        checks = doctor.check_leases(store.db())

        self.assertTrue(all(c.status != "fail" for c in checks),
                        "живой pid ошибочно отмечен как мёртвый lease")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if "lease" in (a["source"] or "").lower()]
        self.assertEqual(incidents, [])
