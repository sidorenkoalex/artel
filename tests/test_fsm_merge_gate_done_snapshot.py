"""Юнит-тест снапшота закрытия на пути `done` (SPEC T094, требования
12-13, AC-13) — REVIEW.md T094 итерация 1, замечание 3 (major).

Путь `killed` уже покрыт `tasks/T094/acceptance_tests/
test_ac13_ac14_snapshot_on_close.py`; путь `done`
(`orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate`) не был
проверен ни одним тестом ни в этой ветке, ни в существующем наборе —
`acceptance_tests/` залочен (tasks/T023) и новый акцептанс-тест сюда не
добавить (это эскалация, не правка разработчика); этот файл закрывает
тот же пробел юнит-тестом в `tests/`, симметрично `killed`.

`_cmd_approve_merge_gate` зовётся НАПРЯМУЮ (тем же приёмом, что уже
применяет `tests/test_merge_gate_ci_wait.py` к соседним узлам того же
гейта) — минуя lease/мьютекс/sha-подтверждение `cmd_approve`, которые
это тело не касаются.

Кодовая ветка задачи внешнего target сегодня (до A7 — SPEC «Не входит»)
мержится в main ПУЛЬТА тем же кодом, что и self: A7 ещё не развела
семантику мержа внешнего кода на его собственном фордже — заводим
реальную ветку `t["branch"]` прямо в репозитории пульта (`self.root`),
иначе `_cmd_approve_merge_gate` не смог бы её смержить вовсе. Артефактная
ветка пульта и bare-репозиторий `origin` целевого — то же самое, что уже
использует `tasks/T094/acceptance_tests/_sandbox.py::
ExternalTargetGitSandbox` для AC-13/AC-14 на пути `killed`.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, catalog, ci, config,  # noqa: E402
                          fsm_merge_gate, gitcmd, store, yamlmini)
from tests.sandbox import RealGitSandbox, capture, resilient_tmp_cleanup  # noqa: E402

TARGET = "extproj"
TASK = "01DONESNAPSHOTTASK0001"


def _snapshot_ref_exists(origin: Path, task_id: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(origin), "show-ref", "--verify", "--quiet",
         f"refs/artifacts/{task_id}"], capture_output=True, text=True)
    return res.returncode == 0


def _snapshot_files(origin: Path, task_id: str) -> list:
    res = subprocess.run(
        ["git", "-C", str(origin), "ls-tree", "-r", "--name-only",
         f"refs/artifacts/{task_id}"], capture_output=True, text=True)
    return [p for p in res.stdout.splitlines() if p] if res.returncode == 0 else []


def _snapshot_file_text(origin: Path, task_id: str, rel: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(origin), "show", f"refs/artifacts/{task_id}:{rel}"],
        capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


class DonePathSnapshotTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        # Bare-remote пульта без сети (тот же приём, что tasks/T053/
        # acceptance_tests/_sandbox.py): `_cmd_approve_merge_gate` делает
        # безусловный `git pull --ff-only` на main ДО merge — без
        # настроенного `origin`/tracking git отказывает раньше, чем тест
        # успевает проверить снапшот.
        pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pult_origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(pult_origin))
        self.git("remote", "add", "origin", str(pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        self.branch = f"task/{TASK.lower()}-x"
        self.git("checkout", "-b", self.branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        # `add` ограничен ИМЕННО этим файлом (не `-A`): `.artel/state.db`
        # — незакоммиченный побочный продукт `store.create_schema` — при
        # `-A` был бы застейджен вместе с ним, закоммичен на этой ветке и
        # СНЕСЁН с диска следующим `checkout main` (main его не отслеживает
        # вовсе) — вырожденный дефект песочницы, обойдён точным `add`.
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{TASK}: код фичи")
        self.git("checkout", config.MAIN_BRANCH)

        store.insert_task(store.db(), TASK, "Задача внешнего target",
                          "merge_gate", self.branch, TARGET,
                          config.DEFAULT_BUDGET_USD)
        artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/PLAN.md": "план\n"}, f"{TASK}: план")

        # bare-репозиторий целевого — то же, что `_sandbox.
        # ExternalTargetGitSandbox` (снапшот пушится в его `refs/artifacts/*`).
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.target_origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
                        str(self.target_origin)], check=True,
                       capture_output=True, text=True)
        target_workspace = config.PROJECTS / TARGET / "workspace"
        target_workspace.mkdir(parents=True)
        self.wgit(target_workspace, "init", "-q", "-b", config.MAIN_BRANCH)
        self.wgit(target_workspace, "remote", "add", "origin",
                  str(self.target_origin))
        self.wgit(target_workspace, "config", "user.email",
                  "artel@example.invalid")
        self.wgit(target_workspace, "config", "user.name", "artel tests")
        (target_workspace / "marker.txt").write_text("main\n", encoding="utf-8")
        self.wgit(target_workspace, "add", "-A")
        self.wgit(target_workspace, "commit", "-q", "-m", "init")
        self.wgit(target_workspace, "push", "-q", "origin", config.MAIN_BRANCH)

        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

    def wgit(self, cwd: Path, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                             text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def test_done_transition_publishes_a_snapshot_like_killed_does(self):
        t = store.get_task(store.db(), TASK)

        result = fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t)

        self.assertEqual(result, ("done",))
        row = store.db().execute("SELECT state FROM tasks WHERE id=?",
                                 (TASK,)).fetchone()
        self.assertEqual(row["state"], "done")

        self.assertTrue(
            _snapshot_ref_exists(self.target_origin, TASK),
            f"refs/artifacts/{TASK} не появился в origin целевого после "
            f"done (AC-13, путь done)")

        files = _snapshot_files(self.target_origin, TASK)
        self.assertTrue(
            any(f.startswith(f"tasks/{TASK}/") for f in files),
            f"снапшот {TASK} не несёт tasks/{TASK}/: {files}")

        retro_meta = None
        for rel in files:
            text = _snapshot_file_text(self.target_origin, TASK, rel)
            meta = yamlmini.frontmatter(text)
            if meta and {"operator", "model", "artel_sha"} <= meta.keys():
                retro_meta = meta
                break
        self.assertIsNotNone(
            retro_meta,
            f"ни один файл снапшота {TASK} не несёт frontmatter с "
            f"operator/model/artel_sha (AC-13): {files}")

    def test_done_snapshot_removes_the_pult_artifact_branch(self):
        # AC-13: снапшот публикуется ДО удаления кодовой и артефактной
        # веток — после успешного done артефактная ветка пульта убрана
        # (тот же приём, что уже проверяет `snapshot_pending` для killed).
        t = store.get_task(store.db(), TASK)

        fsm_merge_gate._cmd_approve_merge_gate(store.db(), TASK,
                                               "merge_gate", t)

        self.assertFalse(
            gitcmd.branch_exists(artifact_branch.branch_name(TASK)),
            "артефактная ветка пульта обязана быть убрана после "
            "подтверждённого снапшота (AC-13/AC-15)")


if __name__ == "__main__":
    unittest.main()
