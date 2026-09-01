"""Приёмочные тесты T088 — авто-ack пяти непокрытых источников `doctor`
(SPEC.md, критерии AC-1..AC-8): `doctor.live_smoke`, `doctor.recovery.sha`,
`doctor.recovery.dirty`, `doctor.recovery.fsck`, `doctor.task_counter`.

Красен до реализации: на момент написания этих тестов `live_smoke`,
`recovery_check` и `check_task_counters` (`orchestrator/doctor.py`) ещё не
зовут `_auto_ack_gone` (или её точечный аналог) для своих пяти источников —
только `check_orphans`/`check_leases`/`check_merge_lock`/`check_backup_age`
это уже делают (T035/T054). Поэтому в каждом тесте ниже часть падает
именно из-за отсутствия кода задачи (алерт остаётся неподтверждённым там,
где по AC он обязан закрыться), а не по случайной причине — проверено
временным стабом реализации перед коммитом (см. `test-authoring`, «Перед
завершением»).

Песочница — `tests.sandbox.TmpRootTest` (пути `config` во временном
каталоге), тот же минимальный набор, что у `tests/test_doctor.py::
RecoveryCheckTest`/`TaskCounterCheckTest`/`LiveSmokeTest`: `catalog.
cmd_init` заводит схему БД (без него `tasks`/`alerts`/`task_counters` не
существуют — `store.migrate` устанавливает схему только внутри `init`),
`recovery.*`-тесты используют НАСТОЯЩИЙ git двух внешних target'ов (`sled`,
`crate`, через `projects.cmd_target_init`) — сверка sha/чистоты/`fsck`
реального смысла без него не имеет; `fsck` дополнительно перехватывается
точечной заглушкой `gitcmd.in_repo` (испортить объектную базу git
настоящей командой хрупко и не нужно критерию) — все прочие git-вызовы
(`rev-parse`, `status`) идут в НАСТОящий `gitcmd.in_repo`, перехваченный
через тот же атрибут (`doctor.py` и `gitcmd.py` разделяют один объект
модуля, так что подмена `doctor.gitcmd.in_repo` видна и внутренним
вызовам `head_sha`/`is_clean`).

`RecoveryAndCounterSandbox` заводит счётчики `sled`/`crate` РАНО (`store.
db()` сразу после `cmd_target_init`, пока `tasks/` внешнего target ещё
пуст) — иначе первый же следующий `store.db()` (его зовёт и сам
`check_task_counters` неявно через переданный `conn`... нет, явный вызов
теста) молча досеял бы счётчик уже вровень с фиктивным наблюдаемым
максимумом (`store.seed_task_counters` зовётся на КАЖДОМ `store.db()`,
пока у target нет строки) — тест никогда не увидел бы «отставание», если
бы каталог `T010`/`T007` появился раньше первого посева.

AC-8 («существующий набор тестов проходит зелёным без ослаблений») —
manual, тем же доводом, что T035 AC-11 / T054 AC-4: `.github/workflows/
ci.yml` уже гоняет `python3 -m unittest discover -s tests -v` на каждый
пуш в чистом раннере — это и есть проверка критерия; повтор внутри
acceptance_tests ловил бы экологические флейки машины разработчика, не
дефект этой задачи.
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, catalog, config, doctor, gitcmd, projects, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture, claude_only_popen  # noqa: E402

# AC-8: manual — критерий уже покрыт `.github/workflows/ci.yml`
# (`unittest discover -s tests -v` на каждый пуш в чистом раннере,
# прецедент tasks/T035 AC-11 / tasks/T054 AC-4): повтор всего набора
# подпроцессом внутри acceptance_tests ловил бы экологические флейки
# машины разработчика, а не дефект T088.

TARGETS_YAML_TWO_EXTERNAL = """targets:
  sled:
    forge: github
    url: https://example.invalid/sled
    base: main
    token_slot: sled-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  crate:
    forge: github
    url: https://example.invalid/crate
    base: main
    token_slot: crate-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

_REAL_IN_REPO = gitcmd.in_repo


def _fsck_side_effect(should_fail):
    """Заглушка `gitcmd.in_repo`: перехватывает только `fsck`, остальные
    команды (sha, чистота) уходят в настоящий git — `should_fail(repo)`
    решает по репозиторию вызова, не по глобальному флагу."""
    def fake(repo, *args):
        if args[:1] == ("fsck",) and should_fail(repo):
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 1, "",
                "повреждён объект (симуляция теста)")
        return _REAL_IN_REPO(repo, *args)
    return fake


class FakeLiveSmokeProc:
    """Замена `subprocess.Popen` для `doctor.live_smoke` (образец
    `tests/test_doctor.py::FakeLiveSmokeProc`)."""

    def __init__(self, output: str, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


def result_event(usd: float) -> str:
    return f'{{"type":"result","total_cost_usd":{usd},"usage":{{}}}}\n'


class LiveSmokeAutoAckTest(TmpRootTest):
    """AC-1: `doctor.live_smoke` закрывается авто-ack'ом на успешном
    прогоне; пока прогон проваливается — не закрывается."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

    def _open_live_smoke_alert_id(self, conn) -> int:
        return [a for a in alerts.open_alerts(conn, "incident")
               if a["source"] == "doctor.live_smoke"][0]["id"]

    def test_ac1_successful_run_auto_acks_the_open_alert(self):
        conn = store.db()
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            doctor.live_smoke(conn)
        alert_id = self._open_live_smoke_alert_id(conn)

        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc(result_event(0.0123)))):
            doctor.live_smoke(conn)

        row = store.get_alert(conn, alert_id)
        self.assertIsNotNone(row["ack_ts"], "успешный прогон обязан закрыть алерт")
        self.assertEqual(row["ack_by"], "doctor")

    def test_ac1_persisting_failure_is_not_auto_acked(self):
        conn = store.db()
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            doctor.live_smoke(conn)
            alert_id = self._open_live_smoke_alert_id(conn)
            doctor.live_smoke(conn)

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"],
                          "прогон продолжает проваливаться — ack не должен проставляться")

    def test_ac7_live_smoke_condition_persists_across_repeated_runs(self):
        conn = store.db()
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            doctor.live_smoke(conn)
            alert_id = self._open_live_smoke_alert_id(conn)
            for _ in range(3):
                doctor.live_smoke(conn)
                self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class RecoveryAndCounterSandbox(TmpRootTest):
    """Общая песочница AC-2..AC-6: два внешних target (`sled`, `crate`) с
    настоящими git-репо, счётчики номеров засеяны рано (см. докстрока
    модуля)."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML_TWO_EXTERNAL, encoding="utf-8")
        capture(catalog.cmd_init)
        capture(projects.cmd_target_init, "sled")
        capture(projects.cmd_target_init, "crate")
        store.db()  # ранний сев счётчиков sled/crate, пока их tasks/ пуст

    def repo(self, target: str) -> Path:
        return config.PROJECTS / target

    def seed_task(self, task_id: str, target: str) -> None:
        store.insert_task(store.db(), task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-zadacha", target, 25.0)

    def commit_artifact(self, task_id: str, target: str, name: str = "SPEC.md") -> str:
        tdir = self.repo(target) / "tasks" / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text("артефакт\n", encoding="utf-8")
        gitcmd.in_repo(self.repo(target), "add", "-A")
        gitcmd.in_repo(self.repo(target), "-c", "user.name=t", "-c",
                       "user.email=t@t.invalid", "commit", "-q", "-m", "фиксация")
        return gitcmd.head_sha(self.repo(target))

    def open_incidents(self, source: str, target: str) -> list:
        return [a for a in alerts.open_alerts(store.db(), "incident")
               if a["source"] == source and a["target"] == target]


class RecoveryShaAutoAckTest(RecoveryAndCounterSandbox):
    """AC-2: `doctor.recovery.sha` конкретного target."""

    def test_ac2_sha_matches_again_is_auto_acked(self):
        conn = store.db()
        self.seed_task("SLED-T001", "sled")
        sha = self.commit_artifact("SLED-T001", "sled")
        store.update_task(conn, "SLED-T001", fixed_sha="0" * 40)

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.sha", "sled")[0]["id"]

        store.update_task(conn, "SLED-T001", fixed_sha=sha)
        doctor.recovery_check(conn, "sled")

        row = store.get_alert(conn, alert_id)
        self.assertIsNotNone(row["ack_ts"], "sha снова совпал — алерт обязан закрыться")
        self.assertEqual(row["ack_by"], "doctor")

    def test_ac2_persisting_mismatch_is_not_auto_acked(self):
        conn = store.db()
        self.seed_task("SLED-T001", "sled")
        self.commit_artifact("SLED-T001", "sled")
        store.update_task(conn, "SLED-T001", fixed_sha="0" * 40)

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.sha", "sled")[0]["id"]

        doctor.recovery_check(conn, "sled")

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"],
                          "расхождение сохраняется — ack не должен проставляться")

    def test_ac2_no_fixed_task_left_is_auto_acked(self):
        conn = store.db()
        self.seed_task("SLED-T001", "sled")
        self.commit_artifact("SLED-T001", "sled")
        store.update_task(conn, "SLED-T001", fixed_sha="0" * 40)

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.sha", "sled")[0]["id"]

        store.update_task(conn, "SLED-T001", fixed_sha=None)
        doctor.recovery_check(conn, "sled")

        row = store.get_alert(conn, alert_id)
        self.assertIsNotNone(
            row["ack_ts"], "у target больше нет задачи с зафиксированным sha")

    def test_ac7_recovery_sha_condition_persists_across_repeated_runs(self):
        conn = store.db()
        self.seed_task("SLED-T001", "sled")
        self.commit_artifact("SLED-T001", "sled")
        store.update_task(conn, "SLED-T001", fixed_sha="0" * 40)

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.sha", "sled")[0]["id"]

        for _ in range(3):
            doctor.recovery_check(conn, "sled")
            self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class RecoveryDirtyAutoAckTest(RecoveryAndCounterSandbox):
    """AC-3: `doctor.recovery.dirty` конкретного target."""

    def _dirty(self, task_id: str, target: str) -> None:
        (self.repo(target) / "tasks" / task_id / "SPEC.md").write_text(
            "незакоммиченная правка\n", encoding="utf-8")

    def _clean(self, target: str) -> None:
        gitcmd.in_repo(self.repo(target), "add", "-A")
        gitcmd.in_repo(self.repo(target), "-c", "user.name=t", "-c",
                       "user.email=t@t.invalid", "commit", "-q", "-m", "чистка")

    def test_ac3_clean_again_is_auto_acked(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")
        self._dirty("SLED-T001", "sled")

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.dirty", "sled")[0]["id"]

        self._clean("sled")
        doctor.recovery_check(conn, "sled")

        row = store.get_alert(conn, alert_id)
        self.assertIsNotNone(row["ack_ts"], "рабочая копия снова чистая")
        self.assertEqual(row["ack_by"], "doctor")

    def test_ac3_persisting_dirt_is_not_auto_acked(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")
        self._dirty("SLED-T001", "sled")

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.dirty", "sled")[0]["id"]

        doctor.recovery_check(conn, "sled")

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"],
                          "репо остаётся грязным — ack не должен проставляться")

    def test_ac7_recovery_dirty_condition_persists_across_repeated_runs(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")
        self._dirty("SLED-T001", "sled")

        doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.dirty", "sled")[0]["id"]

        for _ in range(3):
            doctor.recovery_check(conn, "sled")
            self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class RecoveryFsckAutoAckTest(RecoveryAndCounterSandbox):
    """AC-4: `doctor.recovery.fsck` конкретного target."""

    def test_ac4_fsck_succeeds_again_is_auto_acked(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")
        fail = {"sled": True}

        with mock.patch.object(doctor.gitcmd, "in_repo",
                               side_effect=_fsck_side_effect(lambda r: fail["sled"])):
            doctor.recovery_check(conn, "sled")
        alert_id = self.open_incidents("doctor.recovery.fsck", "sled")[0]["id"]

        fail["sled"] = False
        with mock.patch.object(doctor.gitcmd, "in_repo",
                               side_effect=_fsck_side_effect(lambda r: fail["sled"])):
            doctor.recovery_check(conn, "sled")

        row = store.get_alert(conn, alert_id)
        self.assertIsNotNone(row["ack_ts"], "fsck снова прошёл без ошибки")
        self.assertEqual(row["ack_by"], "doctor")

    def test_ac4_persisting_fsck_failure_is_not_auto_acked(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")

        with mock.patch.object(doctor.gitcmd, "in_repo",
                               side_effect=_fsck_side_effect(lambda r: True)):
            doctor.recovery_check(conn, "sled")
            alert_id = self.open_incidents("doctor.recovery.fsck", "sled")[0]["id"]
            doctor.recovery_check(conn, "sled")

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"],
                          "fsck продолжает проваливаться — ack не должен проставляться")

    def test_ac7_recovery_fsck_condition_persists_across_repeated_runs(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")

        with mock.patch.object(doctor.gitcmd, "in_repo",
                               side_effect=_fsck_side_effect(lambda r: True)):
            doctor.recovery_check(conn, "sled")
            alert_id = self.open_incidents("doctor.recovery.fsck", "sled")[0]["id"]
            for _ in range(3):
                doctor.recovery_check(conn, "sled")
                self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class TaskCounterAutoAckTest(RecoveryAndCounterSandbox):
    """AC-5: `doctor.task_counter` конкретного target."""

    def test_ac5_counter_catches_up_is_auto_acked(self):
        conn = store.db()
        (self.repo("sled") / "tasks" / "T010").mkdir(parents=True)

        doctor.check_task_counters(conn)
        alert_id = self.open_incidents("doctor.task_counter", "sled")[0]["id"]

        conn.execute("UPDATE task_counters SET next_number=10 WHERE target=?", ("sled",))
        conn.commit()
        doctor.check_task_counters(conn)

        row = store.get_alert(conn, alert_id)
        self.assertIsNotNone(row["ack_ts"], "счётчик снова ≥ наблюдаемого max")
        self.assertEqual(row["ack_by"], "doctor")

    def test_ac5_persisting_lag_is_not_auto_acked(self):
        conn = store.db()
        (self.repo("sled") / "tasks" / "T010").mkdir(parents=True)

        doctor.check_task_counters(conn)
        alert_id = self.open_incidents("doctor.task_counter", "sled")[0]["id"]

        doctor.check_task_counters(conn)

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"],
                          "счётчик всё ещё отстаёт — ack не должен проставляться")

    def test_ac7_task_counter_condition_persists_across_repeated_runs(self):
        conn = store.db()
        (self.repo("sled") / "tasks" / "T010").mkdir(parents=True)

        doctor.check_task_counters(conn)
        alert_id = self.open_incidents("doctor.task_counter", "sled")[0]["id"]

        for _ in range(3):
            doctor.check_task_counters(conn)
            self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class MultiTargetIndependenceTest(RecoveryAndCounterSandbox):
    """AC-6: авто-ack одного target для recovery.sha/dirty/fsck/task_counter
    не зависит от состояния другого target."""

    def test_ac6_recovery_sha_other_target_unaffected(self):
        conn = store.db()
        self.seed_task("SLED-T001", "sled")
        self.seed_task("CRATE-T001", "crate")
        self.commit_artifact("SLED-T001", "sled")
        crate_sha = self.commit_artifact("CRATE-T001", "crate")
        store.update_task(conn, "SLED-T001", fixed_sha="0" * 40)
        store.update_task(conn, "CRATE-T001", fixed_sha="1" * 40)

        doctor.recovery_check(conn, "sled")
        doctor.recovery_check(conn, "crate")
        sled_alert = self.open_incidents("doctor.recovery.sha", "sled")[0]
        crate_alert = self.open_incidents("doctor.recovery.sha", "crate")[0]

        store.update_task(conn, "CRATE-T001", fixed_sha=crate_sha)
        doctor.recovery_check(conn, "sled")
        doctor.recovery_check(conn, "crate")

        self.assertIsNone(store.get_alert(conn, sled_alert["id"])["ack_ts"],
                          "sled не должен получить ack по состоянию crate")
        self.assertIsNotNone(store.get_alert(conn, crate_alert["id"])["ack_ts"])

    def test_ac6_recovery_dirty_other_target_unaffected(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")
        self.commit_artifact("CRATE-T001", "crate")
        (self.repo("sled") / "tasks" / "SLED-T001" / "SPEC.md").write_text(
            "незакоммиченная правка\n", encoding="utf-8")
        (self.repo("crate") / "tasks" / "CRATE-T001" / "SPEC.md").write_text(
            "незакоммиченная правка\n", encoding="utf-8")

        doctor.recovery_check(conn, "sled")
        doctor.recovery_check(conn, "crate")
        sled_alert = self.open_incidents("doctor.recovery.dirty", "sled")[0]
        crate_alert = self.open_incidents("doctor.recovery.dirty", "crate")[0]

        gitcmd.in_repo(self.repo("crate"), "add", "-A")
        gitcmd.in_repo(self.repo("crate"), "-c", "user.name=t", "-c",
                       "user.email=t@t.invalid", "commit", "-q", "-m", "чистка")
        doctor.recovery_check(conn, "sled")
        doctor.recovery_check(conn, "crate")

        self.assertIsNone(store.get_alert(conn, sled_alert["id"])["ack_ts"],
                          "sled не должен получить ack по состоянию crate")
        self.assertIsNotNone(store.get_alert(conn, crate_alert["id"])["ack_ts"])

    def test_ac6_recovery_fsck_other_target_unaffected(self):
        conn = store.db()
        self.commit_artifact("SLED-T001", "sled")
        self.commit_artifact("CRATE-T001", "crate")
        fail = {"sled": True, "crate": True}

        def run():
            with mock.patch.object(
                    doctor.gitcmd, "in_repo",
                    side_effect=_fsck_side_effect(lambda r: fail[r.name])):
                doctor.recovery_check(conn, "sled")
                doctor.recovery_check(conn, "crate")

        run()
        sled_alert = self.open_incidents("doctor.recovery.fsck", "sled")[0]
        crate_alert = self.open_incidents("doctor.recovery.fsck", "crate")[0]

        fail["crate"] = False
        run()

        self.assertIsNone(store.get_alert(conn, sled_alert["id"])["ack_ts"],
                          "sled не должен получить ack по состоянию crate")
        self.assertIsNotNone(store.get_alert(conn, crate_alert["id"])["ack_ts"])

    def test_ac6_task_counter_other_target_unaffected(self):
        conn = store.db()
        (self.repo("sled") / "tasks" / "T010").mkdir(parents=True)
        (self.repo("crate") / "tasks" / "T007").mkdir(parents=True)

        doctor.check_task_counters(conn)
        sled_alert = self.open_incidents("doctor.task_counter", "sled")[0]
        crate_alert = self.open_incidents("doctor.task_counter", "crate")[0]

        conn.execute("UPDATE task_counters SET next_number=7 WHERE target=?", ("crate",))
        conn.commit()
        doctor.check_task_counters(conn)

        self.assertIsNone(store.get_alert(conn, sled_alert["id"])["ack_ts"],
                          "sled не должен получить ack по состоянию crate")
        self.assertIsNotNone(store.get_alert(conn, crate_alert["id"])["ack_ts"])


if __name__ == "__main__":
    import unittest
    unittest.main()
