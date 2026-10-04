"""Узлы области проекта, которые долгоживущий файл задачи проверить не
может: `artifact_branch.repo_for_target` (импорт `artifact_branch`
долгоживущему файлу запрещён) и прогон канарейки через вход фазы 1
`canary._run_task_in_ephemeral_clone` (закрытое имя; тот же вход зовут
`tests/test_canary_drive.py`).

Группа: разовый

Файл разовый не по предмету — это свойства кода, — а по рубежу:
статические правила долгоживущего файла (только публичный интерфейс, без
`artifact_branch`) закрывают оба узла. Долгоживущие тесты тех же
требований (1, 7) разработчик кладёт в `tests/` по требованию 10 SPEC.

Песочница — `ProjectAreaSandbox` долгоживущего файла задачи
(`tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`): главная копия
пульта на настоящем git, bare `origin`, `targets.yaml` с записью артели.
Для канарейки главная копия несёт копию `orchestrator/` и `templates/`, а
её `orchestrator/canary_drive.py` — зонд: процесс клона заводит задачу
настоящим `catalog.cmd_new` кода клона и записывает, где оказались клон
области проекта и рабочая копия задачи.

Красен до реализации: `repo_for_target("artel")` отдаёт `config.ROOT`;
`new` в эфемерном клоне канарейки не заводит
`.artel/projects/artel/repo` и `worktrees/<id>/` — зонд видит их
отсутствие.

Провалидирован временным стабом реализации (удалён): `init` заводит клон
по `url` записи проекта, `repo_for_target` отдаёт клон, зонд после `new`
заводит рабочую копию задачи в клоне — оба метода зелёные.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch, canary, config
from tests.test_01m42pencs26d0656x8fr7dfa7_project_area import (
    ARTEL, ProjectAreaSandbox)

# AC-6 — repo_for_target здесь; resolve/path_or_none/git — в долгоживущем
# файле задачи (RepoContextOfArtelTest).


class RepoForTargetTest(ProjectAreaSandbox):

    def test_ac6_repo_for_target_of_artel_is_the_project_clone(self):
        """`init`; `artifact_branch.repo_for_target("artel")` —
        `.artel/projects/artel/repo`, не главная копия.

        Ловит мутацию: особый случай `config.ROOT` для артели в
        `repo_for_target` оставлен — ссылки документов артели пишутся в git
        главной копии.
        """
        self.init()

        repo = artifact_branch.repo_for_target(ARTEL)

        self.assertEqual(Path(repo).resolve(), self.clone.resolve(),
                         self.msg(f"repo_for_target(artel) = {repo}"))


# AC-12 — прогон канарейки.

METRICS = {
    "steps": 2, "cost_usd": 0.0, "review_iterations": 0, "escalations": [],
    "dev_retries": 0, "outcome": "killed", "kill_note": "штатно",
    "test_author_visited": False, "ceiling_exhausted": False,
    "ceiling_raise": None,
}

STUB_DRIVE = r'''"""Зонд канарейки песочницы планки (не код пульта)."""
import argparse
import json
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--result")
args, _ = parser.parse_known_args()

from orchestrator import catalog, config, store


def git(*argv, cwd):
    res = subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else ""


probe = {"root": str(config.ROOT)}
task_id = None
try:
    task_id = catalog.cmd_new("Канарейка-зонд", canary=True)
except SystemExit as exc:
    probe["new_refusal"] = str(exc.code)
area = config.PROJECTS / config.DEFAULT_TARGET
clone = area / "repo"
probe["clone"] = str(clone)
probe["clone_git_dir"] = (git("rev-parse", "--path-format=absolute",
                              "--git-common-dir", cwd=clone)
                          if clone.is_dir() else "")
if task_id:
    wt = area / "worktrees" / task_id
    probe["task_id"] = task_id
    probe["branch"] = store.get_task(store.db(), task_id)["branch"]
    probe["worktree"] = str(wt)
    probe["worktree_exists"] = wt.is_dir()
    probe["worktree_branch"] = (git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt)
                                if wt.is_dir() else "")
    probe["worktree_git_dir"] = (git("rev-parse", "--path-format=absolute",
                                     "--git-common-dir", cwd=wt)
                                 if wt.is_dir() else "")
with open(os.environ["ARTEL_CANARY_PROBE"], "w", encoding="utf-8") as fh:
    json.dump(probe, fh, ensure_ascii=False)
result = {"task_id": task_id or "01ZONDNETZADACHI", "head": git("rev-parse", "HEAD", cwd="."),
          "outcome": "killed", "escalated": False,
          "metrics": json.loads(METRICS_JSON),
          "steps": [{"ts": "t", "actor": "clone", "action": "state -> merge_gate",
                     "detail": "зонд"}]}
with open(args.result, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False)
'''


class CanaryProjectAreaSandbox(ProjectAreaSandbox):
    """Главная копия с кодом пульта и зондом вместо входа ведения
    канарейки."""

    COPY_CODE = True

    def extra_main_files(self) -> None:
        stub = STUB_DRIVE.replace(
            "json.loads(METRICS_JSON)",
            f"json.loads({json.dumps(json.dumps(METRICS, ensure_ascii=False))})")
        (self.root / "orchestrator" / "canary_drive.py").write_text(
            stub, encoding="utf-8")

    def battle_state(self) -> dict:
        """Главная копия и боевая область `.artel/projects/artel`."""
        area = config.PROJECTS / ARTEL
        files = sorted(p.relative_to(area).as_posix()
                       for p in area.rglob("*") if p.is_file()
                       and ".git" not in p.relative_to(area).parts[:2]) \
            if area.is_dir() else []
        clone = {}
        if self.is_git_repo(self.clone):
            clone = {"refs": self.in_repo(self.clone, "for-each-ref",
                                          "--format=%(refname) %(objectname)"),
                     "head": self.in_repo(self.clone, "rev-parse", "HEAD").strip(),
                     "worktrees": self.in_repo(self.clone, "worktree", "list",
                                               "--porcelain")}
        return {"main_refs": self.main_refs(), "main_head": self.main_head(),
                "main_worktrees": self.main_worktrees(),
                "main_status": self.main_status(),
                "area_files": files, "clone": clone}


class CanaryBuildsItsOwnProjectAreaTest(CanaryProjectAreaSandbox):

    def test_ac12_canary_builds_projects_artel_in_its_temp_dir(self):
        """Фаза 1 канарейки на проверяемом коммите (HEAD главной копии
        песочницы): процесс клона — код этого коммита — заводит задачу.

        Зонд видит во временном каталоге клона (не в каталоге пульта)
        клон `projects/artel/repo` и рабочую копию `projects/artel/
        worktrees/<id>/` на ветке задачи, принадлежащую этому клону;
        коммит кода, ведшего задачу, — проверяемый. Главная копия (ссылки,
        HEAD, `git worktree list`, `git status`) и боевая
        `.artel/projects/artel` после прогона те же, что до него.

        Ловит мутацию: эфемерный клон канарейки не строит область
        `projects/artel` (для артели корнем служит сам клон) — рабочая
        копия задачи не заводится в его `projects/artel/worktrees/`.
        """
        self.init()
        template = self.scratch / "shablon.md"
        template.write_text("# ТЗ зонда\n", encoding="utf-8")
        probe_path = self.scratch / "zond-kanareyki.json"
        target = self.main_head()
        before = self.battle_state()

        with mock.patch.dict(os.environ, {"ARTEL_CANARY_PROBE": str(probe_path)}):
            result = canary._run_task_in_ephemeral_clone(
                template, "20261004T000000Z", target, config.ROOT)

        metrics = result[4]
        self.assertTrue(probe_path.is_file(), self.msg("зонд не исполнен"))
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
        text = self.msg(json.dumps(probe, ensure_ascii=False))
        root = Path(probe["root"]).resolve()
        self.assertFalse(root.is_relative_to(self.root.resolve()), text)
        self.assertNotIn("new_refusal", probe, text)
        clone = (root / ".artel" / "projects" / ARTEL / "repo").resolve()
        self.assertTrue(probe["clone_git_dir"], text)
        self.assertTrue(Path(probe["clone_git_dir"]).resolve().is_relative_to(clone), text)
        self.assertTrue(probe.get("worktree_exists"), text)
        self.assertTrue(Path(probe["worktree"]).resolve().is_relative_to(
            (root / ".artel" / "projects" / ARTEL / "worktrees").resolve()), text)
        self.assertEqual(probe["worktree_branch"], probe["branch"], text)
        self.assertEqual(Path(probe["worktree_git_dir"]).resolve(),
                         Path(probe["clone_git_dir"]).resolve(), text)
        self.assertEqual(metrics.get("code_sha"), target, text)
        self.assertEqual(self.battle_state(), before,
                         self.msg("главная копия или боевая область изменились"))


if __name__ == "__main__":
    unittest.main()
