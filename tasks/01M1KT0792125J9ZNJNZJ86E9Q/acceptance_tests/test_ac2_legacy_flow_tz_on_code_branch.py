"""AC-2 (tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md): «Для задачи прежнего
флоу (TZ.md в кодовой ветке) выбор роли analyst работает как до этой
задачи».

Требование 1 SPEC явно требует ДОБАВИТЬ чтение через артефактную ветку
пульта (`artifact_source.resolve`), не ЗАМЕНИТЬ им существующую проверку
`t["branch"]`/`gitcmd.on_foreign_branch`/диск `config.TASKS`: у задачи,
чей TZ.md лежит в её СОБСТВЕННОЙ кодовой ветке (а не в артефактной ветке
пульта), `runner.step_role` обязан находить его тем же путём, что и до
этой задачи.

Зелёный с рождения: файл воспроизводит СЕГОДНЯШНЕЕ (уже работающее)
поведение `runner.step_role` на кодовой ветке — `on_foreign_branch`/
`gitcmd.show(t["branch"], ...)` уже умеют это без всякой правки этой
задачи (SPEC T025/T048). Это регрессионный тест на требование 5 SPEC
(«поведение задач прежнего флоу не меняется»): он обязан оставаться
зелёным и ДО, и ПОСЛЕ реализации требования 1 — если разработчик заменит
старую проверку новой вместо того, чтобы добавить новую поверх старой,
именно этот файл покраснеет первым.
"""
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artifact_branch, gitcmd, runner, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

TZ_TEXT = "Хотим кнопку экспорта отчёта в CSV на странице задач.\n"


def _commit_tz_to_code_branch(root: Path, branch: str, task_id: str) -> None:
    """Коммитит TZ.md ПЛОТНИЦКИ прямо в КОДОВУЮ ветку задачи (`branch`),
    без чекаута — воспроизводит задачу прежнего флоу (TZ.md, лежащий в
    собственной ветке задачи, не в артефактной ветке пульта) без побочных
    эффектов на текущую ветку `root` (остаётся `main`, тот же приём, что
    `artifact_branch.write_commit`/`commit_files`, только на ПРОИЗВОЛЬНОЕ
    имя ветки, а не жёстко на `artifact/<id>`)."""
    base = gitcmd.head_sha(root)
    subprocess.run(["git", "update-ref", f"refs/heads/{branch}", base],
                   cwd=root, check=True)
    rel = f"tasks/{task_id}/TZ.md"
    sha = artifact_branch.write_commit(
        root, {rel: TZ_TEXT}, f"{task_id}: TZ.md (кодовая ветка)",
        "Роль Артели", "role@artel.invalid", parent=branch)
    assert sha, "плотницкий коммит TZ.md в кодовую ветку не удался"
    subprocess.run(["git", "update-ref", f"refs/heads/{branch}", sha],
                   cwd=root, check=True)


class StepRoleFallsBackToCodeBranchTzTest(RealPultGitTest):

    def test_ac2_step_role_is_analyst_when_tz_only_on_code_branch(self):
        """TZ.md существует ТОЛЬКО в кодовой ветке задачи (`t["branch"]`)
        — реальная, отдельно существующая git-ветка, отличная от
        артефактной ветки пульта и от текущей ветки `main`. `runner.
        step_role` обязан по-прежнему найти его тем же путём, что и до
        этой задачи, и вернуть `"analyst"`.

        Ловит мутацию: замена старого чтения (`on_foreign_branch`/
        `gitcmd.show(t["branch"], ...)`) НОВЫМ (только через
        `artifact_source.resolve`) вместо добавления нового поверх
        старого — тогда TZ.md, лежащий только в кодовой ветке, перестанет
        находиться, и метод вернёт `None`.
        """
        t = store.get_task(store.db(), self.TASK)
        branch = t["branch"]
        _commit_tz_to_code_branch(self.root, branch, self.TASK)
        self.assertTrue(gitcmd.branch_exists(branch),
                        "предпосылка сценария: кодовая ветка реально существует")
        self.assertEqual(
            gitcmd.current_branch(), "main",
            "предпосылка сценария: рабочая копия пульта НЕ на этой ветке")

        self.assertEqual(
            runner.step_role(store.get_task(store.db(), self.TASK)),
            "analyst")


if __name__ == "__main__":
    unittest.main()
