"""Приёмочные тесты T035 — авто-закрытие алертов `doctor` при исчезновении
условия (SPEC.md, критерии AC-1..AC-11).

Песочница — минимальный вариант приёма `tests/test_doctor.py::TmpRootTest`
(тот же список подменённых путей `config`), без копирования `skills/`,
`templates/`, `docs/` — эти тесты не зовут `runner`/бриф ролей, только
`doctor.check_orphans`/`doctor.check_backup_age`/`alerts.*` напрямую, как и
`OrphansTest`/`AlertAckTest` в `tests/test_doctor.py`.

Пара тестов на условие (AC-1/2, AC-3/4, AC-5/6, AC-7/8): первый прогон
заводит алерт при живом условии, второй прогон — либо условие снято (ack
ожидается), либо условие всё ещё в силе (ack не ожидается). Формат
`ack_by=doctor` / `ack_resolution` с «условие ушло, прогон doctor» —
общий контракт требования 6 SPEC, поэтому проверяется во всех четырёх
группах авто-ack (AC-1, AC-3, AC-5, AC-7), а не только там, где AC
проговаривает его явно.

AC-11 («существующий набор тестов проходит зелёным») размечен `manual`:
`.github/workflows/ci.yml` уже гоняет `python3 -m unittest discover -s
tests -v` на каждый пуш в чистом раннере — это и есть проверка критерия.
Дублировать её здесь подпроцессом опасно ложной красным: на машине
автора этих тестов `tests/test_multitarget.py::RoleEnvTest` уже падает
тремя тестами из-за амбиентной git-идентичности окружения (то же самое
воспроизводится на `main` без единой правки T035) — это несвязанная с
doctor/alerts экологическая проблема машины, не дефект кода, и жёсткая
проверка «весь набор зелёный» внутри acceptance_tests заблокировала бы
разработчика по причине вне зоны задачи.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, config, doctor, store  # noqa: E402

# AC-11: manual — критерий уже покрыт `.github/workflows/ci.yml`
# (`unittest discover -s tests -v` на каждый пуш в чистом раннере);
# воспроизведение той же проверки внутри acceptance_tests на этой машине
# ловит несвязанный с T035 экологический флейк `RoleEnvTest` (ambient git
# identity), см. докстрока модуля.


def _no_git(*args) -> subprocess.CompletedProcess:
    """Замена `gitcmd.git`: любая команда отказывает — `_orphan_worktrees`
    детерминированно видит пустой список, независимо от реального
    состояния репозитория, в котором гоняются тесты."""
    return subprocess.CompletedProcess(list(args), 1, "", "")


class AutoAckSandboxTest(unittest.TestCase):
    """Временный `config.ROOT` с чистой БД — общая песочница для всех групп."""

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

    def touch_backup(self, age_days: float = 0.0) -> None:
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")
        stamp = time.time() - age_days * 86400
        os.utime(config.BACKUP_MARKER, (stamp, stamp))


class BranchAutoAckTest(AutoAckSandboxTest):
    """AC-1/AC-2: `doctor.orphans.branch` — ack при удалении ветки, не при живой."""

    def _seed_done_task(self) -> None:
        store.insert_task(self.conn(), "T001", "Готова", "done",
                          "task/t001-gotova", config.DEFAULT_TARGET, 25.0)

    def test_ac1_branch_deleted_gets_auto_acked_on_next_run(self):
        self._seed_done_task()
        with mock.patch.object(doctor.gitcmd, "git", _no_git), \
                mock.patch.object(doctor.gitcmd, "branch_exists", return_value=True):
            doctor.check_orphans(self.conn())
        incidents = self.open_incidents("doctor.orphans.branch")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        with mock.patch.object(doctor.gitcmd, "git", _no_git), \
                mock.patch.object(doctor.gitcmd, "branch_exists", return_value=False):
            doctor.check_orphans(self.conn())

        self.assert_auto_acked(alert_id)

    def test_ac2_branch_still_alive_is_not_acked(self):
        self._seed_done_task()
        with mock.patch.object(doctor.gitcmd, "git", _no_git), \
                mock.patch.object(doctor.gitcmd, "branch_exists", return_value=True):
            doctor.check_orphans(self.conn())
        alert_id = self.open_incidents("doctor.orphans.branch")[0]["id"]

        with mock.patch.object(doctor.gitcmd, "git", _no_git), \
                mock.patch.object(doctor.gitcmd, "branch_exists", return_value=True):
            doctor.check_orphans(self.conn())

        self.assert_not_acked(alert_id)


class DirAutoAckTest(AutoAckSandboxTest):
    """AC-3/AC-4: `doctor.orphans.dir` — ack, когда у каталога появилась строка БД."""

    def test_ac3_dir_gets_a_db_row_gets_auto_acked_on_next_run(self):
        (config.TASKS / "T777").mkdir(parents=True)
        with mock.patch.object(doctor.gitcmd, "git", _no_git):
            doctor.check_orphans(self.conn())
        incidents = self.open_incidents("doctor.orphans.dir")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        store.insert_task(self.conn(), "T777", "Появилась строка", "in_dev",
                          "task/t777-x", config.DEFAULT_TARGET, 25.0)

        with mock.patch.object(doctor.gitcmd, "git", _no_git):
            doctor.check_orphans(self.conn())

        self.assert_auto_acked(alert_id)

    def test_ac4_dir_still_without_a_db_row_is_not_acked(self):
        (config.TASKS / "T777").mkdir(parents=True)
        with mock.patch.object(doctor.gitcmd, "git", _no_git):
            doctor.check_orphans(self.conn())
        alert_id = self.open_incidents("doctor.orphans.dir")[0]["id"]

        with mock.patch.object(doctor.gitcmd, "git", _no_git):
            doctor.check_orphans(self.conn())

        self.assert_not_acked(alert_id)


class WorktreeAutoAckTest(AutoAckSandboxTest):
    """AC-5/AC-6: `doctor.orphans.worktree` — ack, когда лишний worktree убран."""

    WITH_EXTRA = "worktree /main\nHEAD abc\n\nworktree /some/extra\nHEAD def\n\n"
    CLEAN = "worktree /main\nHEAD abc\n\n"

    def _git(self, porcelain: str):
        def fn(*args):
            if args[:2] == ("worktree", "list"):
                return subprocess.CompletedProcess(list(args), 0, porcelain, "")
            return subprocess.CompletedProcess(list(args), 1, "", "")
        return fn

    def test_ac5_worktree_removed_gets_auto_acked_on_next_run(self):
        with mock.patch.object(doctor.gitcmd, "git", self._git(self.WITH_EXTRA)):
            doctor.check_orphans(self.conn())
        incidents = self.open_incidents("doctor.orphans.worktree")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        with mock.patch.object(doctor.gitcmd, "git", self._git(self.CLEAN)):
            doctor.check_orphans(self.conn())

        self.assert_auto_acked(alert_id)

    def test_ac6_worktree_still_present_is_not_acked(self):
        with mock.patch.object(doctor.gitcmd, "git", self._git(self.WITH_EXTRA)):
            doctor.check_orphans(self.conn())
        alert_id = self.open_incidents("doctor.orphans.worktree")[0]["id"]

        with mock.patch.object(doctor.gitcmd, "git", self._git(self.WITH_EXTRA)):
            doctor.check_orphans(self.conn())

        self.assert_not_acked(alert_id)


class BackupAgeAutoAckTest(AutoAckSandboxTest):
    """AC-7/AC-8: `doctor.backup_age` — ack, когда маркер бэкапа посвежел."""

    def test_ac7_marker_freshens_gets_auto_acked_on_next_run(self):
        self.touch_backup(age_days=config.BACKUP_MAX_AGE_DAYS + 1)
        doctor.check_backup_age(self.conn())
        incidents = self.open_incidents("doctor.backup_age")
        self.assertEqual(len(incidents), 1)
        alert_id = incidents[0]["id"]

        self.touch_backup(age_days=0)
        doctor.check_backup_age(self.conn())

        self.assert_auto_acked(alert_id)

    def test_ac8_marker_still_stale_is_not_acked(self):
        self.touch_backup(age_days=config.BACKUP_MAX_AGE_DAYS + 1)
        doctor.check_backup_age(self.conn())
        alert_id = self.open_incidents("doctor.backup_age")[0]["id"]

        self.touch_backup(age_days=config.BACKUP_MAX_AGE_DAYS + 2)
        doctor.check_backup_age(self.conn())

        self.assert_not_acked(alert_id)


class ManualAckAndDedupUnaffectedTest(AutoAckSandboxTest):
    """AC-9: дедуп `raise_alert` и ручной `ack` для живых условий не меняются."""

    def test_ac9_dedup_and_manual_ack_for_a_live_condition_are_unchanged(self):
        (config.TASKS / "T777").mkdir(parents=True)
        with mock.patch.object(doctor.gitcmd, "git", _no_git):
            doctor.check_orphans(self.conn())
            doctor.check_orphans(self.conn())

        incidents = self.open_incidents("doctor.orphans.dir")
        self.assertEqual(len(incidents), 1,
                         "повторный прогон живого условия не должен дублировать алерт")

        error = alerts.ack(self.conn(), incidents[0]["id"], "operator", "")

        self.assertIsNone(error, "ручной ack incident-алерта продолжает работать")
        self.assertEqual(self.open_incidents("doctor.orphans.dir"), [],
                         "ручной ack закрыл алерт как обычно")


class OtherSourceNotAutoAckedTest(AutoAckSandboxTest):
    """AC-10: source вне {orphans.dir/branch/worktree, backup_age} авто-ack не получает."""

    def test_ac10_unrelated_source_alert_is_not_auto_acked_by_a_doctor_run(self):
        conn = self.conn()
        alerts.raise_alert(conn, config.DEFAULT_TARGET, "incident",
                           "doctor.recovery.sha", "sha разошёлся")
        alert_id = self.open_incidents("doctor.recovery.sha")[0]["id"]

        self.touch_backup(age_days=0)
        with mock.patch.object(doctor.gitcmd, "git", _no_git):
            doctor.check_orphans(self.conn())
        doctor.check_backup_age(self.conn())

        self.assert_not_acked(alert_id)


if __name__ == "__main__":
    unittest.main()
