"""Общая песочница приёмочных тестов задачи 01M283NC4JJXK7QS68Y9ET8TBK
(выход шага developer при грязном дереве — WIP-коммит кода пультом).

SPEC называет точку встройки (`orchestrator/runner.py`, ветка `rc=0` без
`pump.error`, где сегодня безусловно зовётся только `checkpoint.
commit_step_artifacts`) и образец приёма (`checkpoint.commit_timeout_
checkpoint`/`_commit_worktree_change`), но НЕ называет имя новой функции
чекпоинта — она ещё не существует. Поэтому сценарии ниже проверяют
наблюдаемое поведение ЦЕЛОГО шага через `run_faked()` (подложный процесс
агента, настоящий git worktree кодовой ветки задачи, `RealPultGitTest` из
`tests/test_git_fixation.py`), а не вызывают внутреннюю функцию по имени,
которого разработчик волен выбрать сам.

`RealPultGitTest` — та же тяжёлая песочница (реальный git), что уже несёт
`tests/test_timeout_checkpoint.py`: WIP-коммит — это настоящие `git add`/
`git diff`/`git commit`, заглушкой `gitcmd.git` эту механику не проверить.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import gitcmd, store, workspace  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class DeveloperWipCommitSandbox(RealPultGitTest):
    """Хелперы поверх `RealPultGitTest`: рабочий каталог кодовой ветки
    задачи (`workspace.path`, НЕ репо фиксации `self.repo()`/`task_dir()`
    родителя — те два разных места, тот же довод, что и в докстринге
    `tests/test_step_autocommit.py`)."""

    def ensure_worktree(self) -> Path:
        """Заводит (идемпотентно) worktree кодовой ветки задачи ДО
        первого реального шага роли — тем же приёмом, что `_WorktreeCheckpointTest.
        setUp` в `tests/test_timeout_checkpoint.py`: без явного вызова
        worktree появляется только внутри `runner.role_cwd`, вызванного
        `run_faked()`, и до этого некуда писать «незакоммиченный код
        роли», который сценарий кладёт заранее."""
        branch = store.get_task(store.db(), self.TASK)["branch"]
        wt_path, error = workspace.ensure(self.TASK, branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        return wt_path

    def worktree(self) -> Path:
        return workspace.path(self.TASK)

    def write_code_file(self, rel: str, text: str) -> Path:
        """Файл кодовой ветки ВНЕ `tasks/<id>/` — путь мандата `developer`
        (тот же приём, что `_WorktreeCheckpointTest.write_code_file`):
        без него сценарии, где меняется только `tasks/<id>/`
        (материализуемый `role_cwd` на каждом шаге), не имеют ни одного
        пути в мандате кода, и код-коммит закономерно не случается."""
        wt = self.ensure_worktree()
        path = wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def worktree_git(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.worktree()), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def worktree_status(self) -> str:
        return self.worktree_git("status", "--porcelain", "--untracked-files=all")

    def worktree_head(self) -> str:
        return gitcmd.head_sha(self.worktree())

    def enter_review(self) -> str:
        """Переводит задачу из `in_dev` в `review` напрямую (`store.
        set_state`, та же admin-точка, что уже применяет
        `RunnerEscalationHintsIncludeShaTest`/автогейт-тест в `tests/
        test_git_fixation.py` для форсирования состояния в тестах) —
        обходит гейты перехода (`orchestrator/fsm.py`, вне зоны этой
        задачи — «Не входит» SPEC), чтобы получить роль БЕЗ мандата кода
        (`reviewer`, `config.STATE_ROLE["review"]`) для сценария AC-5."""
        self.enter_in_dev()
        conn = store.db()
        store.set_state(conn, self.TASK, "review", "operator",
                        expected_state="in_dev",
                        detail="тест: форсированный переход на review")
        return self.worktree_head()

    def code_commit_journal_entries(self) -> list:
        """Записи журнала нового механизма (SPEC, требование 3/AC-3):
        `actor=orchestrator`, действие буквально «код закоммичен пультом
        за роль» — тот же приём фильтрации, что `orchestrator_steps()` в
        `tests/test_timeout_checkpoint.py`/`tests/test_step_autocommit.py`,
        но по имени действия ЭТОЙ задачи, не по префиксу «WIP-чекпоинт»
        (тот способ обозначения этой задаче не назначен — AC-3 называет
        буквальное действие «код закоммичен пультом за роль»)."""
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"
               and r["action"] == "код закоммичен пультом за роль"]
