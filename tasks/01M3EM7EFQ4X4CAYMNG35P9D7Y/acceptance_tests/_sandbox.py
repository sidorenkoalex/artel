"""Общие фикстуры приёмочных тестов 01M3EM7EFQ4X4CAYMNG35P9D7Y (уборка
родителя при делении на гейте SPEC; удаление влитой ветки при kill).

Две песочницы, обе поверх `tests.sandbox.RealGitSandbox` (настоящий
git-репозиторий во временном каталоге, все пути `config` подменены) —
предмет проверки у обеих в том, что именно ответит настоящий git на
`branch --merged`/`branch -d`/`worktree remove`, заглушкой это не
изобразить:

- `DivisionApproveSandbox` (AC-1..AC-4) — родитель на `spec_gate` с
  валидной секцией «## Деление» и УЖЕ заведённой кодовой веткой и
  worktree. Конструкция входа в `spec_gate` (строка задачи напрямую
  через `store.insert_task`, SPEC.md плотницким коммитом в артефактную
  ветку пульта, `fsm.cmd_advance` -> `spec_gate`) повторяет проверенную
  `SplitApproveSandbox` задачи 01M1SHJZCE0Y4DXAAWQ2W585A7, которой то же
  деление уже покрыто; новое здесь — только `ensure_code_worktree()`:
  без кодовой ветки и worktree родителя проверять уборку нечего.
- `KillBranchSandbox` (AC-5..AC-7) — задача с кодовой веткой и worktree,
  которую убивает `cleanup.cmd_kill`.

`ensure_code_worktree` заводит ветку через `workspace.ensure` — тот же
путь, которым её заводит роль-разработчик первым действием шага (A7).
`workspace.ensure` для НОВОЙ ветки делает `git fetch origin
<MAIN_BRANCH>` (SPEC 01M297HFSKV3GVZJ9YF20FZEZE), поэтому обе песочницы
заводят синхронный origin (`RealGitSandbox.add_synced_origin`). Ветка,
заведённая так и не получившая собственных коммитов, — ровно «пустая
ветка поделённого родителя» из «Контекста» SPEC: голова совпадает с
main, `gitcmd.branch_merged` отвечает True.

Зоны фикстуры (`orchestrator/foo_zone.py`) — вымышленный путь, не
пересекающийся ни с одним реальным модулем: сверка путей SPEC с `zones:`
на входе approve (`guard.spec_unclassified_paths`) обязана пройти, иначе
сценарий деления до уборки не доходит вовсе.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import (artifact_branch, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

PARENT_TASK_ID = "01M3EMFIXTUREPARENTDIVISION"
PARENT_TITLE = "Родительская фикстура уборки при делении"
PARENT_BRANCH = "task/01m3emfixtureparentdivision-uborka"
FIXTURE_ZONE = "orchestrator/foo_zone.py"

KILL_TASK_ID = "01M3EMFIXTUREKILLCLEANUP"
KILL_TITLE = "Фикстура уборки ветки при kill"
KILL_BRANCH = "task/01m3emfixturekillcleanup-uborka"

CLEANUP_ACTION = "уборка"

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: 15
zones: {zones}
---

# SPEC: {title}

## Контекст
Фикстура приёмочного теста задачи 01M3EM7EFQ4X4CAYMNG35P9D7Y — короткий
безобидный текст, не связанный с реальной механикой пульта.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры (schema_version 1 не требует сквозной
AC-разметки, `guard.requires_ac_markup`).

## Деление
{division_body}

## Не входит
- Всё остальное.
"""

FIRST_SUBTASK_TITLE = "Первая часть фикстуры деления"
SECOND_SUBTASK_TITLE = "Вторая часть фикстуры деления"


def _subsection(title: str, order: str, body: str) -> str:
    return "\n".join([f"### {title}", "", f"Зоны: {FIXTURE_ZONE}",
                      f"Порядок: {order}", "", body])


def division_spec_text(task: str = PARENT_TASK_ID,
                       title: str = PARENT_TITLE) -> str:
    """SPEC родителя с валидной секцией «## Деление» из двух подразделов —
    той же формы, что уже принимает guard на переходе `spec_writing ->
    spec_gate` (образец — фикстура 01M1SHJZCE0Y4DXAAWQ2W585A7)."""
    body = "\n\n".join([
        _subsection(FIRST_SUBTASK_TITLE, "первая, без зависимостей",
                    "Текст ТЗ первой части фикстуры деления."),
        _subsection(SECOND_SUBTASK_TITLE, "после части 1",
                    "Текст ТЗ второй части фикстуры деления."),
    ])
    return SPEC_TEMPLATE.format(task=task, title=title, zones=FIXTURE_ZONE,
                                division_body=body)


class CodeWorktreeSandbox(RealGitSandbox):
    """Общее обеим песочницам: синхронный origin, заведение кодовой ветки
    и worktree задачи, чтение веток/журнала."""

    TASK = ""
    TITLE = ""
    BRANCH = ""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()

    # ------------------------------------------------------------ утилиты

    def ensure_code_worktree(self) -> Path:
        """Кодовая ветка + worktree задачи — то же первое действие шага
        разработчика (`workspace.ensure`). Собственных коммитов у ветки
        нет: её голова совпадает с головой main."""
        wt_path, error = workspace.ensure(self.TASK, self.BRANCH)
        self.assertIsNone(error, f"worktree не заведён: {error}")
        self.assertTrue(wt_path.exists(), f"каталога worktree {wt_path} нет")
        return wt_path

    def commit_in_worktree(self, name: str, text: str) -> None:
        """Собственный коммит ветки задачи — прямо в её worktree (второй
        чекаут той же ветки в ROOT git не даст, SPEC T045)."""
        wt_path = workspace.path(self.TASK)
        (wt_path / name).write_text(text, encoding="utf-8")
        self.git_wt("add", "-A")
        self.git_wt("commit", "-q", "-m", f"{self.TASK}: {name}")

    def git_wt(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(workspace.path(self.TASK)),
                              *args], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C worktree {' '.join(args)}: {res.stderr}")
        return res.stdout

    def merge_branch_into_main(self) -> None:
        self.git("merge", "-q", "--no-ff", self.BRANCH, "-m",
                 f"merge {self.BRANCH}")

    def branches(self) -> list:
        return self.git("branch", "--format=%(refname:short)").split()

    def worktree_registered(self) -> bool:
        resolved = workspace.path(self.TASK).resolve()
        listed = self.git("worktree", "list", "--porcelain")
        return any(Path(line.split(" ", 1)[1]).resolve() == resolved
                   for line in listed.splitlines()
                   if line.startswith("worktree "))

    def task_row(self, task_id: str | None = None) -> dict:
        return dict(store.get_task(store.db(), task_id or self.TASK))

    def steps(self, task_id: str | None = None) -> list:
        return store.task_steps(store.db(), task_id or self.TASK)

    def journal_text(self, task_id: str | None = None) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in self.steps(task_id))

    def cleanup_notes(self, task_id: str | None = None) -> list:
        """Детали всех записей журнала с действием «уборка»."""
        return [r["detail"] or "" for r in self.steps(task_id)
                if r["action"] == CLEANUP_ACTION]


class DivisionApproveSandbox(CodeWorktreeSandbox):
    """Родитель на `spec_gate` с секцией «## Деление», кодовой веткой и
    worktree — вход всех сценариев AC-1..AC-4."""

    TASK = PARENT_TASK_ID
    TITLE = PARENT_TITLE
    BRANCH = PARENT_BRANCH

    def enter_spec_gate(self) -> str:
        """Заводит родителя, коммитит SPEC с «## Деление» в его
        артефактную ветку, доводит `spec_writing -> spec_gate` и заводит
        кодовую ветку с worktree. Возвращает `fixed_sha`, которым
        `approve` подтверждает гейт."""
        store.insert_task(store.db(), self.TASK, self.TITLE, "spec_writing",
                          self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/SPEC.md": division_spec_text()},
            f"{self.TASK}: SPEC готов")
        capture(fsm.cmd_advance, self.TASK)
        self.ensure_code_worktree()
        return store.get_task(store.db(), self.TASK)["fixed_sha"]

    def approve(self, sha: str) -> str:
        return capture(fsm.cmd_approve, self.TASK, sha)

    def subtask_ids(self) -> list:
        """id задач, заведённых делением ЭТОГО родителя."""
        return sorted(row["id"] for row in store.all_tasks(store.db())
                      if row["parent_task_id"] == self.TASK)

    def artifact_head(self) -> str:
        """sha головы артефактной ветки родителя; пустая строка —
        ветки нет."""
        return gitcmd.branch_head_sha(artifact_branch.branch_name(self.TASK))

    def artifact_spec_text(self) -> str | None:
        """Текст SPEC.md С АРТЕФАКТНОЙ ВЕТКИ родителя (`gitcmd.show`) —
        рабочая копия шага источником артефактов не является."""
        text, _ = gitcmd.show(artifact_branch.branch_name(self.TASK),
                              f"tasks/{self.TASK}/SPEC.md")
        return text


class KillBranchSandbox(CodeWorktreeSandbox):
    """Задача с кодовой веткой и worktree, которую убивает `kill` —
    вход сценариев AC-5..AC-7."""

    TASK = KILL_TASK_ID
    TITLE = KILL_TITLE
    BRANCH = KILL_BRANCH

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.TASK, self.TITLE, "in_dev",
                          self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)


def failing_branch_delete(real_git, marker: str):
    """Подмена `gitcmd.git`, в которой отказывает ТОЛЬКО удаление ветки
    (`git branch -d`/`-D`) — остальные подкоманды идут в настоящий git.

    Узко именно на удаление, а не на всю подкоманду `branch`: `git branch
    --merged` в том же проходе решает, влита ветка или нет, и его подмена
    подменила бы заодно предмет требования 4, а не сбой уборки.
    """
    def flaky(*args: str):
        if args and args[0] == "branch" and ("-d" in args or "-D" in args):
            return subprocess.CompletedProcess(args, 128, "", marker)
        return real_git(*args)

    return flaky
