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

Кодовая ветка задачи внешнего target мержится в её СОБСТВЕННЫЙ клон и
origin (`config.PROJECTS/<target>/workspace`, её bare `origin`), не в
main ПУЛЬТА — репозиторный контекст target'а (SPEC
01M1R5B33CC7E6BZK085XV3ZCX, orchestrator/repo_context.py) переведён на
это этой задачей; артефактная ветка (`tasks/<id>/`) остаётся в пульте
(`self.root`) — то же самое, что уже использует `tasks/T094/
acceptance_tests/_sandbox.py::ExternalTargetGitSandbox` для AC-13/AC-14
на пути `killed`.
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
        # acceptance_tests/_sandbox.py): артефактная ветка (`tasks/<id>/`)
        # и снапшот публикуются через её origin — без настроенного
        # `origin`/tracking git отказывает раньше, чем тест успевает
        # проверить снапшот.
        pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pult_origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(pult_origin))
        self.git("remote", "add", "origin", str(pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        self.branch = f"task/{TASK.lower()}-x"

        # Репозиторный контекст target'а (SPEC 01M1R5B33CC7E6BZK085XV3ZCX):
        # объявление "extproj" в targets.yaml — предпосылка
        # `repo_context.resolve`, без которой merge_gate теперь отказывает
        # ДО какого-либо merge (targets.yaml не читается — fail-closed).
        config.TARGETS.write_text(
            "targets:\n"
            f"  {TARGET}:\n"
            "    forge: github\n"
            f"    url: http://localhost/{TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {TARGET}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")

        store.insert_task(store.db(), TASK, "Задача внешнего target",
                          "merge_gate", self.branch, TARGET,
                          config.DEFAULT_BUDGET_USD)
        artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/PLAN.md": "план\n"}, f"{TASK}: план")

        # bare-репозиторий целевого — то же, что `_sandbox.
        # ExternalTargetGitSandbox` (снапшот пушится в его `refs/artifacts/*`,
        # а теперь и код задачи мержится в его `refs/heads/<base>`,
        # SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-12).
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.target_origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
                        str(self.target_origin)], check=True,
                       capture_output=True, text=True)
        self.target_workspace = config.PROJECTS / TARGET / "workspace"
        self.target_workspace.mkdir(parents=True)
        self.wgit(self.target_workspace, "init", "-q", "-b", config.MAIN_BRANCH)
        self.wgit(self.target_workspace, "remote", "add", "origin",
                  str(self.target_origin))
        self.wgit(self.target_workspace, "config", "user.email",
                  "artel@example.invalid")
        self.wgit(self.target_workspace, "config", "user.name", "artel tests")
        (self.target_workspace / "marker.txt").write_text(
            "main\n", encoding="utf-8")
        self.wgit(self.target_workspace, "add", "-A")
        self.wgit(self.target_workspace, "commit", "-q", "-m", "init")
        self.wgit(self.target_workspace, "push", "-q", "origin",
                  config.MAIN_BRANCH)

        # Ветка задачи — В КЛОНЕ ЦЕЛЕВОГО (не в `self.root`, SPEC
        # 01M1R5B33CC7E6BZK085XV3ZCX): merge_gate внешнего target теперь
        # мержит эту ветку прямо там, не код пульта.
        self.wgit(self.target_workspace, "checkout", "-q", "-b", self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit(self.target_workspace, "add", "feature.txt")
        self.wgit(self.target_workspace, "commit", "-q", "-m",
                  f"{TASK}: код фичи")

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
        """Успешный `done` публикует снапшот задачи в `refs/artifacts/<id>`
        origin целевого — тем же путём, что и `killed` (AC-13), и с
        frontmatter (`operator`/`model`/`artel_sha`) хотя бы в одном файле.

        Ловит мутацию: путь `done` перестаёт звать публикацию снапшота
        (или зовёт её ПОСЛЕ удаления артефактной ветки, когда содержимое
        уже недоступно) — `refs/artifacts/{TASK}` не появится в
        `self.target_origin`, и `_snapshot_ref_exists`/`assertTrue` здесь
        это поймают.
        """
        t = store.get_task(store.db(), TASK)

        # SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-5..AC-7: путь "fresh" без
        # `confirmed_ci_note` теперь возвращает ("wait", branch) сам —
        # опрос CI переехал в `_wait_for_branch_ci_green` вызывающего
        # цикла. Тело вызывается напрямую (см. докстринг файла), поэтому
        # `confirmed_ci_note` передаём явно — тот же самый узел, что
        # реальный `_cmd_approve_merge_gate_cycle` подставил бы сюда сам
        # после того, как цикл ожидания получил бы зелёный статус от
        # замоканного `ci.branch_status` этим же setUp.
        result = fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

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
        """AC-13: снапшот публикуется ДО удаления кодовой и артефактной
        веток — после успешного `done` артефактная ветка пульта убрана
        (тот же приём, что уже проверяет `snapshot_pending` для killed).

        Ловит мутацию: удаление артефактной ветки пульта (`artifact/<id>`)
        после `done` пропущено или переставлено раньше публикации снапшота
        — `gitcmd.branch_exists(artifact_branch.branch_name(TASK))`
        останется `True`, и `assertFalse` здесь это поймает.
        """
        t = store.get_task(store.db(), TASK)

        # SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-5..AC-7: см. пояснение в
        # test_done_transition_publishes_a_snapshot_like_killed_does выше.
        fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

        self.assertFalse(
            gitcmd.branch_exists(artifact_branch.branch_name(TASK)),
            "артефактная ветка пульта обязана быть убрана после "
            "подтверждённого снапшота (AC-13/AC-15)")


if __name__ == "__main__":
    unittest.main()
