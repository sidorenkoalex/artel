"""Юнит-тест закрытия на пути `done` (SPEC T094, требования 12-13,
AC-13) — REVIEW.md T094 итерация 1, замечание 3 (major). С ADR-0021 п.3
(SPEC 01M3Z2DMQRD0BD7AARFVTCVVG8, требование 3, AC-5) закрытие — не
снимок в origin целевого, а коммит RETRO в ссылку документов
`refs/artifacts/<id>` пульта поверх её прежней головы.

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


def _snapshot_commit_subject(origin: Path, task_id: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(origin), "log", "-1", "--format=%s",
         f"refs/artifacts/{task_id}"], capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else ""


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
        self.pult_origin = pult_origin

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
        """Успешный `done` пишет коммит закрытия в `refs/artifacts/<id>`
        и отправляет ссылку в origin пульта — тем же путём, что и `killed`
        (AC-13), с frontmatter (`operator`/`model`/`artel_sha`) хотя бы в
        одном файле.

        Ловит мутацию: путь `done` перестаёт звать коммит закрытия —
        RETRO с frontmatter не появится в `refs/artifacts/{TASK}` origin
        пульта, и `assertIsNotNone` здесь это поймает.
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
            _snapshot_ref_exists(self.pult_origin, TASK),
            f"refs/artifacts/{TASK} не появился в origin пульта после "
            f"done (AC-13, путь done)")

        files = _snapshot_files(self.pult_origin, TASK)
        self.assertTrue(
            any(f.startswith(f"tasks/{TASK}/") for f in files),
            f"снапшот {TASK} не несёт tasks/{TASK}/: {files}")

        retro_meta = None
        for rel in files:
            text = _snapshot_file_text(self.pult_origin, TASK, rel)
            meta = yamlmini.frontmatter(text)
            if meta and {"operator", "model", "artel_sha"} <= meta.keys():
                retro_meta = meta
                break
        self.assertIsNotNone(
            retro_meta,
            f"ни один файл снапшота {TASK} не несёт frontmatter с "
            f"operator/model/artel_sha (AC-13): {files}")

    def test_done_snapshot_retro_names_the_done_outcome_and_the_ref(self):
        """SPEC 01M3KE80RNBCY9G48E75Z14TA7, требования 1-3 (AC-1, AC-2,
        AC-4) СКВОЗНЫМ путём мержа: ретроспектива опубликованного снимка
        несёт «Итог: done, sha …» и адрес `refs/artifacts/<id>`, сообщение
        коммита закрытия — «закрытие (done) — RETRO» (ADR-0021 п.3).

        Ловит мутацию: путь закрытия снова передаёт в публикацию литерал
        «killed» (или берёт исход раньше `_finalize_done_state`, когда
        задача ещё на `merge_gate`) — в RETRO.md снимка окажется «Итог:
        killed — причина: …», в сообщении коммита — «(killed)», и
        `assertIn`/`assertNotIn` ниже это поймают.
        """
        t = store.get_task(store.db(), TASK)

        fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

        retro_text = _snapshot_file_text(self.pult_origin, TASK,
                                         f"tasks/{TASK}/RETRO.md")
        self.assertRegex(retro_text, r"Итог: done, sha [0-9a-f]{40}\n")
        self.assertIn(f"Адрес артефактов: refs/artifacts/{TASK}\n", retro_text)
        self.assertNotIn("Итог: killed", retro_text)
        self.assertEqual(_snapshot_commit_subject(self.pult_origin, TASK),
                         f"{TASK}: закрытие (done) — RETRO")

    def test_done_snapshot_removes_the_pult_artifact_branch(self):
        """ADR-0021 п.3 (вместо AC-13 SPEC T094 «ветка убрана»): после
        `done` ссылка документов не удаляется, коммит закрытия — потомок
        её прежней головы, ветки `artifact/<id>` нет.

        Ловит мутацию: закрытие снова пишет снимок без родителя или
        удаляет ссылку — `is_ancestor` прежней головы ниже покраснеет.
        """
        t = store.get_task(store.db(), TASK)
        before = artifact_branch.ref_head(TASK)

        # SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-5..AC-7: см. пояснение в
        # test_done_transition_publishes_a_snapshot_like_killed_does выше.
        fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

        head = artifact_branch.ref_head(TASK)
        self.assertNotEqual(head, before)
        self.assertTrue(gitcmd.is_ancestor(before, head),
                        "коммит закрытия обязан быть потомком прежней головы")
        self.assertFalse(gitcmd.branch_exists(f"artifact/{TASK.lower()}"))


if __name__ == "__main__":
    unittest.main()
