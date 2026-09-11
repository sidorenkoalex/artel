"""AC-5 (tasks/01M290PVYG2VJK6442H5BAX9MA/SPEC.md): `commit_step_
artifacts` переносит в артефактную ветку из `tasks/<id>/` только файлы,
допустимые белым списком `scripts/guard.py` (`TASK_ROOT_ALLOWED_MD`,
правила `acceptance_tests/` планки) и `RETRO.md`, определяемые ВЫЗОВОМ
функций guard, не независимой копией.

Красен до реализации: `orchestrator/checkpoint.py::_is_stray_acceptance_
test_file` — собственная копия regex `guard.is_extraneous_acceptance_
test_file` (байт-в-байт тот же список правил, но не вызов функции guard);
`RETRO.md` первого уровня `tasks/<id>/` не входит в `guard.
TASK_ROOT_ALLOWED_MD` и сегодня фильтруется как посторонний файл без
исключения.

Песочница — `RealGitSandbox` (tests/sandbox.py) с ВНЕШНИМ target (тот же
приём, что и `tests/test_checkpoint_external_step_artifacts.py`):
`_commit_external_step_artifacts` для внешнего target читает `tasks/
<id>/` с обычного диска (не из git worktree self-target) — не нужен
git-репозиторий внутри рабочего каталога роли, только реальный git пульта
для плотницкой записи в артефактную ветку.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import checkpoint, config, gitcmd, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "ac5extproj"


class StepArtifactsUsesGuardAllowlistTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01AC5GUARDSOURCETASK01"
        store.insert_task(store.db(), self.TASK, "AC-5: источник критерия",
                          "in_dev", f"task/{self.TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_ac5_acceptance_stray_criterion_is_delegated_to_guard_function(self):
        """Файл `acceptance_tests/docs/codebase-map.md` — посторонний по
        любому прочтению правила (вложенный путь, инцидент 05.09);
        подмена `guard.is_extraneous_acceptance_test_file` на «ничего не
        постороннее» обязана поменять исход автокоммита — иначе критерий
        всё ещё определяет независимая копия regex в checkpoint.py, не
        вызов функции guard (AC-5).

        Ловит мутацию: `checkpoint.py` держит собственную копию критерия
        вместо вызова `guard.is_extraneous_acceptance_test_file` —
        подмена атрибута guard никак не повлияет на исход, файл
        останется исключённым из артефактной ветки, и `assertIn` ниже
        покраснеет."""
        self.write("acceptance_tests/docs/codebase-map.md", "мусор роли\n")

        with mock.patch.object(guard, "is_extraneous_acceptance_test_file",
                               return_value=False):
            checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                              "test_author")

        self.assertIn(
            f"tasks/{self.TASK}/acceptance_tests/docs/codebase-map.md",
            self.artifact_branch_files())

    def test_ac5_retro_md_at_task_root_is_allowed_into_the_artifact_branch(self):
        """`RETRO.md` первого уровня `tasks/<id>/` — легитимный, наравне
        со списком `guard.TASK_ROOT_ALLOWED_MD` (сам список его не
        содержит — AC-5 добавляет его отдельно: «... и RETRO.md»).

        Ловит мутацию: `RETRO.md` фильтруется как посторонний файл
        `guard.is_extraneous_task_root_file` наравне с любым другим
        `.md`-именем вне `TASK_ROOT_ALLOWED_MD` — не доедет до
        артефактной ветки, `assertIn` ниже покраснеет."""
        self.write("RETRO.md", "# RETRO\n")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.assertIn(f"tasks/{self.TASK}/RETRO.md",
                      self.artifact_branch_files())


if __name__ == "__main__":
    unittest.main()
