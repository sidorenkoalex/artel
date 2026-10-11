"""AC-3: `doctor.recovery_check` для `target == "artel"` сверяет sha
`.artel/projects/artel/` (артефактный репозиторий новых задач артели) той
же логикой, что и для любого внешнего target. Сверка HEAD самой главной
копии пульта (`config.ROOT`) в объём `recovery_check` не входит — это
отдельная забота doctor-проверки пина (AC-13); явное решение, а не
молчаливый skip.

Красен до реализации: сегодня `orchestrator/doctor.py::recovery_check`
несёт буквально `if target == config.DEFAULT_TARGET: return [Check(
"recovery", "skip", "догфуд вне объёма recovery-сверки")]` (строки
~433-434, докстринг там же обосновывает это тем, что HEAD ветки пульта
двигают процессы вне FSM) — тесты ниже сравнивают `recovery_check(conn,
"artel")` с `recovery_check(conn, "sled")` при идентичном состоянии
артефактного репо (оба заведены `projects.cmd_target_init`, оба получают
одну и ту же фиксацию/расхождение/грязь) и падают именно потому, что
сегодня 'artel' получает единственный `skip`-Check вместо трёх содержательных
под-проверок (`recovery-sha`/`recovery-clean`/`recovery-fsck`), которые
получает 'sled'. Прецедент паттерна — `tests/test_doctor.py::
RecoveryCheckTest` (тот же `commit_artifact`/`store.update_task(...,
fixed_sha=...)` приём), которая сегодня явно кодирует старое поведение
методом `test_dogfood_is_out_of_scope`.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import alerts, config, doctor, gitcmd, projects, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

OTHER_TARGET = "sled"

TARGETS_YAML = f"""targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  {OTHER_TARGET}:
    forge: github
    url: https://example.invalid/{OTHER_TARGET}
    base: main
    token_slot: {OTHER_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class RecoveryCheckArtelParityTest(TmpRootTest):
    """`recovery_check(conn, "artel")` под тем же кодом, что и для любого
    другого объявленного target — при идентичном состоянии артефактного
    репо оба дают одинаковый класс результата."""

    ARTEL_TASK = "01ARTELRECOVERYTASK0001"
    OTHER_TASK = "01SLEDRECOVERYTASK00001"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        store.create_schema(store.db())
        capture(projects.cmd_target_init, config.DEFAULT_TARGET)
        capture(projects.cmd_target_init, OTHER_TARGET)
        store.insert_task(store.db(), self.ARTEL_TASK, "Задача артели",
                          "in_dev", f"task/{self.ARTEL_TASK.lower()}",
                          config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.OTHER_TASK, "Задача sled",
                          "in_dev", f"task/{self.OTHER_TASK.lower()}",
                          OTHER_TARGET, 25.0)

    def repo(self, target: str) -> Path:
        return config.PROJECTS / target

    def commit_artifact(self, target: str, task_id: str,
                        name: str = "SPEC.md") -> str:
        tdir = self.repo(target) / "tasks" / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text("артефакт\n", encoding="utf-8")
        gitcmd.in_repo(self.repo(target), "add", "-A")
        gitcmd.in_repo(self.repo(target), "-c", "user.name=t", "-c",
                       "user.email=t@t.invalid", "commit", "-q", "-m", "фиксация")
        return gitcmd.head_sha(self.repo(target))

    def test_ac3_healthy_repo_is_ok_for_artel_same_as_for_other_target(self):
        """Артефактный репозиторий `.artel/projects/artel/` заведён, чист и
        совпадает с зафиксированным sha — `recovery_check` для 'artel'
        обязана вернуть три `ok`-подпроверки (`recovery-sha`,
        `recovery-clean`, `recovery-fsck`), тем же классом результата, что
        и для 'sled' при идентичном состоянии.

        Ловит мутацию: строку `if target == config.DEFAULT_TARGET: return
        [Check("recovery", "skip", ...)]` в начале `recovery_check` —
        тогда для 'artel' вернётся один `skip`-Check вместо трёх `ok`.
        """
        artel_sha = self.commit_artifact(config.DEFAULT_TARGET, self.ARTEL_TASK)
        store.update_task(store.db(), self.ARTEL_TASK, fixed_sha=artel_sha)
        other_sha = self.commit_artifact(OTHER_TARGET, self.OTHER_TASK)
        store.update_task(store.db(), self.OTHER_TASK, fixed_sha=other_sha)

        artel_checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)
        other_checks = doctor.recovery_check(store.db(), OTHER_TARGET)

        artel_by_name = {c.name: c.status for c in artel_checks}
        other_by_name = {c.name: c.status for c in other_checks}
        self.assertEqual(artel_by_name, other_by_name)
        self.assertEqual(artel_by_name.get("recovery-sha"), "ok")
        self.assertEqual(artel_by_name.get("recovery-clean"), "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_ac3_sha_mismatch_raises_an_incident_for_artel_same_as_other(self):
        """Зафиксированный sha артели разошёлся с фактическим HEAD
        артефактного репо — `recovery_check("artel")` обязана завести
        `incident`-алерт `doctor.recovery.sha` тем же порядком, что и для
        'sled' при том же расхождении.

        Ловит мутацию: тот же `skip`-ранний-возврат — тогда расхождение
        sha артели не заведёт alert вовсе (0 incidents вместо 2).
        """
        self.commit_artifact(config.DEFAULT_TARGET, self.ARTEL_TASK)
        store.update_task(store.db(), self.ARTEL_TASK, fixed_sha="0" * 40)
        self.commit_artifact(OTHER_TARGET, self.OTHER_TASK)
        store.update_task(store.db(), self.OTHER_TASK, fixed_sha="0" * 40)

        artel_checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)
        other_checks = doctor.recovery_check(store.db(), OTHER_TARGET)

        artel_by_name = {c.name: c for c in artel_checks}
        other_by_name = {c.name: c for c in other_checks}
        self.assertEqual(artel_by_name["recovery-sha"].status, "fail")
        self.assertEqual(other_by_name["recovery-sha"].status, "fail")
        incidents = alerts.open_alerts(store.db(), "incident")
        targets_alerted = {a["target"] for a in incidents
                           if a["source"] == "doctor.recovery.sha"}
        self.assertEqual(targets_alerted, {config.DEFAULT_TARGET, OTHER_TARGET})

    def test_ac3_dirty_artifact_repo_raises_an_incident_for_artel(self):
        """Незакоммиченная правка в `.artel/projects/artel/tasks/<id>/`
        (не в рабочем дереве `config.ROOT`!) делает `recovery-clean`
        `fail` для 'artel' — тем же основанием, что и для 'sled'.

        Ловит мутацию: тот же ранний `skip`-возврат для артели — грязный
        артефактный репозиторий артели остался бы незамеченным.
        """
        artel_sha = self.commit_artifact(config.DEFAULT_TARGET, self.ARTEL_TASK)
        store.update_task(store.db(), self.ARTEL_TASK, fixed_sha=artel_sha)
        (self.repo(config.DEFAULT_TARGET) / "tasks" / self.ARTEL_TASK /
         "SPEC.md").write_text("незакоммиченная правка\n", encoding="utf-8")

        checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["recovery-clean"].status, "fail")
        incidents = alerts.open_alerts(store.db(), "incident")
        self.assertTrue(any(a["target"] == config.DEFAULT_TARGET
                            and "грязный" in a["message"] for a in incidents))

    def test_ac3_recovery_check_never_reads_config_root_head(self):
        """Контроль требования 2 предложения: `recovery_check("artel")` не
        обязана и не должна сверять HEAD `config.ROOT` — она смотрит
        ТОЛЬКО на `.artel/projects/artel/`. Порча HEAD/чистоты рабочего
        дерева `config.ROOT` (главной копии пульта, отдельной от
        артефактного репо артели в песочнице) не меняет исход проверки,
        пока сам артефактный репо чист и sha сходится.

        Ловит мутацию: реализация по ошибке сверяет `gitcmd.head_sha()`
        (HEAD `config.ROOT`) вместо `gitcmd.head_sha(config.PROJECTS /
        "artel")` — тогда грязная правка ИМЕННО в `config.ROOT` (не в
        артефактном репо) неожиданно повлияла бы на исход, чего это
        утверждение и не допускает.
        """
        artel_sha = self.commit_artifact(config.DEFAULT_TARGET, self.ARTEL_TASK)
        store.update_task(store.db(), self.ARTEL_TASK, fixed_sha=artel_sha)
        # Грязнит РАБОЧЕЕ ДЕРЕВО config.ROOT (песочница TmpRootTest — не
        # git-репозиторий сама по себе, но факт «файл создан вне
        # артефактного репо артели» уже достаточен: recovery_check не
        # имеет причины его увидеть).
        (config.ROOT / "root-side-effect.txt").write_text(
            "не артефактный репозиторий\n", encoding="utf-8")

        checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["recovery-clean"].status, "ok")
        self.assertEqual(by_name["recovery-sha"].status, "ok")


if __name__ == "__main__":
    unittest.main()
