"""Общая песочница приёмочных тестов задачи 01M1K7KP0D8ZKRM9KTE75DCCYR (не
test_*.py — не подхватывается `unittest discover` напрямую, только импортом
из test_ac*.py).

SPEC требует ветко-корректное чтение скилов/CLAUDE.md с ГОЛОВЫ ветки
`main` (`gitcmd.show`/`git show main:<path>`, тот же приём инварианта 28),
а не с диска рабочей копии пульта (`config.ROOT`) — это различимо ТОЛЬКО
настоящим git-репозиторием, где содержимое диска и содержимое коммита
`main` можно развести (незакоммиченная правка на диске, либо чекаут
`config.ROOT` на ветку/коммит, отличный от текущей головы `main`).
Отсюда — `TaskSandbox(sandbox.RealGitSandbox)`, тот же рецепт настоящего
git, что уже применяет `tasks/T031/acceptance_tests/test_branch_correct_
reads.py::RealGitBranchTest` для симметричного случая (ветка ЗАДАЧИ, не
`main`).

`config.ROLES`/`config.TEMPLATES` (`orchestrator/config.py`) якорятся на
РЕАЛЬНЫЙ корень репозитория при загрузке модуля и `mock.patch.object(
config, "ROOT", ...)` их не трогает (комментарий в config.py, «сознательно
вне ALL_CONFIG_ATTRS») — поэтому здесь НЕ копируются ни `roles.yaml`, ни
`templates/`: `roles.skills(role)` и `catalog.cmd_new` читают настоящие
файлы репозитория независимо от песочницы. Копируются только `skills/*.md`
и `CLAUDE.md`/`docs/codebase-map.md` — единственные пути, которые код
читает ЧЕРЕЗ `config.ROOT` динамически (`config.ROOT / "skills" / ...`,
`config.ROOT / CONVENTIONS_REL`, `config.ROOT / MAP_REL`).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artifact_branch, brief, catalog, checkpoint,  # noqa: E402
                          config, context_package, fixation, gitcmd, roles,  # noqa: E402
                          runner, store)  # noqa: E402
from tests.sandbox import (FakeProc, RealGitSandbox, capture,  # noqa: E402
                           capture_new_task_id, resilient_tmp_cleanup)

# Роли, задействованные тестами этого набора, и их скилы (SPEC «Не входит»
# — состав скилов роли не меняется этой задачей; те же имена, что реально
# перечислены в roles.yaml — единственном источнике истины, который эта
# песочница не подменяет, см. докстринг модуля).
TEST_AUTHOR_SKILLS = ("conventions-core", "escalation-rules", "test-authoring")
DEVELOPER_SKILLS = ("conventions-core", "escalation-rules", "coding-standards")
ALL_SANDBOX_SKILLS = tuple(sorted(set(TEST_AUTHOR_SKILLS) | set(DEVELOPER_SKILLS)))


def skill_marker(name: str, version: str) -> str:
    """Содержимое скила-фикстуры: минимальный, но узнаваемый текст —
    различимый и по имени скила, и по версии (V1/V2/НЕЗАКОММИЧЕНО)."""
    return f"# Скил {name}\n\nМАРКЕР-СКИЛА-{name.upper()}-{version}\n"


def claude_md_marker(version: str) -> str:
    return f"# Конвенции\n\nМАРКЕР-КОНВЕНЦИЙ-{version}\n"


class TaskSandbox(RealGitSandbox):
    """Настоящий git-репозиторий (`RealGitSandbox`) + минимум фикстур для
    сборки промпта роли (`skills/*.md`, `CLAUDE.md`, `docs/codebase-map.md`)
    + одна задача, заведённая `catalog.cmd_new` (SPEC T048/T045: своя
    ветка + свой worktree в `config.WORKTREES/<id>`, `config.ROOT`
    воркдерево задачи не трогает и остаётся на `main`).
    """

    def setUp(self):
        super().setUp()  # git init -b main, коммит marker.txt, патчи config
        self.scratch_dirs: list[Path] = []
        self.addCleanup(self._cleanup_scratch_dirs)

        (self.root / "skills").mkdir()
        for name in ALL_SANDBOX_SKILLS:
            (self.root / "skills" / f"{name}.md").write_text(
                skill_marker(name, "V1"), encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(claude_md_marker("V1"),
                                             encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "фикстуры: skills/CLAUDE.md")

        # Карта — вторым коммитом, чтобы `built_at_sha` мог сослаться на
        # уже существующий (первый) коммит: сверка свежести карты
        # (`brief._stale_paths`) отвечает "нечего сравнивать" по путям
        # orchestrator/scripts/tests (их в этой песочнице нет вовсе), пока
        # `built_at_sha` — валидный, достижимый из HEAD коммит.
        base_sha = self.head()
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            f"---\nbuilt_at_sha: {base_sha}\n---\n\n# Карта\n",
            encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "фикстуры: карта")

        self.capture(catalog.cmd_init)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Скилы и правила в бриф роли из main")

    def _cleanup_scratch_dirs(self) -> None:
        for d in self.scratch_dirs:
            shutil.rmtree(d, ignore_errors=True)

    # -- git-утилиты, специфичные этой песочнице ------------------------

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def write_and_commit(self, rel: str, content: str, message: str) -> str:
        """Пишет `rel` (относительно `self.root`) и коммитит — на ветке,
        ЧЕКАУЧЕННОЙ СЕЙЧАС в `self.root`. Возвращает новый head."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.head()

    def advance_branch_without_checkout(self, branch: str, rel: str,
                                        content: str, message: str) -> str:
        """Коммитит `rel`=`content` НА `branch`, не трогая текущий чекаут
        `self.root` (может стоять на другой ветке в этот момент) — через
        временный linked worktree, тем же приёмом, что и `workspace.ensure`
        заводит worktree задачи, только для `main`/произвольной ветки,
        которую тест продвигает «за спиной» текущего чекаута пульта.
        Возвращает новый head `branch`."""
        scratch = Path(tempfile.mkdtemp(prefix="artel-scratch-"))
        self.scratch_dirs.append(scratch)
        wt = scratch / "wt"
        self.git("worktree", "add", str(wt), branch)
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True,
                       capture_output=True, text=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=wt,
                       check=True, capture_output=True, text=True)
        new_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=wt, check=True,
            capture_output=True, text=True).stdout.strip()
        self.git("worktree", "remove", "--force", str(wt))
        return new_head

    # -- задача -----------------------------------------------------

    def worktree_path(self) -> Path:
        return config.WORKTREES / self.TASK

    def write_and_commit_in_worktree(self, rel_under_task_dir: str,
                                     content: str, message: str) -> str:
        """Коммитит `tasks/<id>/<rel_under_task_dir>` в АРТЕФАКТНУЮ ВЕТКУ
        пульта (`artifact_branch.commit_files`) — тем же местом, где
        реальная роль коммитит артефакты ЛЮБОГО target'а, включая self,
        ПОСЛЕ A7 (ANSWER-2 к эскалации этой задачи, ADR-0012):
        `artifact_source.resolve` теперь безусловно `foreign=True`,
        `tasks/<id>/` self-таргета больше не живёт в ветке/worktree кода
        (`config.WORKTREES/<id>`, T045) вовсе — до A7 этот метод писал
        именно туда, тем приёмом self-таргет и работал."""
        rel = f"tasks/{self.TASK}/{rel_under_task_dir}"
        return artifact_branch.commit_files(self.TASK, {rel: content}, message)

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def journal_details(self, action: str | None = None) -> list[str]:
        rows = store.task_steps(store.db(), self.TASK)
        if action is not None:
            rows = [r for r in rows if r["action"] == action]
        return [r["detail"] for r in rows]

    def journal_all(self) -> list[str]:
        return [f"{r['action']}: {r['detail']}"
               for r in store.task_steps(store.db(), self.TASK)]

    # -- прогон роли, захват промпта --------------------------------

    def run_role(self, state: str) -> tuple[str, mock.Mock]:
        """Ставит состояние задачи и гонит `runner.cmd_run` с подменённым
        процессом агента (тот же рецепт, что `tests/test_agent_prompt.py`,
        `PromptChannelTest.run_agent`) — возвращает (stdout оркестратора,
        мок Popen), из которого `prompt_text_of` достаёт реальный текст
        промпта."""
        self.set_state(state)
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = self.capture(runner.cmd_run, self.TASK)
        return out, popen

    def prompt_text_of(self, popen: mock.Mock) -> str:
        path = Path(popen.call_args.kwargs["stdin"].name)
        return path.read_text(encoding="utf-8")
