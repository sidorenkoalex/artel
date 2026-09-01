"""Приёмочный тест T094 — AC-9 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-9: «После завершения шага роли артефакты tasks/<id>/ закоммичены в
артефактную ветку пульта; кодовая ветка task/* целевого не несёт
изменений tasks/<id>/.»

Первый «шаг роли» задачи — сам `cmd_new` (коммитит ТЗ/SPEC.md
оркестраторским авторством, `orchestrator/catalog.py`): его исход и
проверяется. Красен до реализации по той же причине, что AC-8:
`cmd_new` без `target` не заводит задач вне self, а self требование 16
исключает — см. докстринг `test_ac8_cmd_new_artifact_branch.py`.

Кодовая ветка целевого здесь — РЕАЛЬНАЯ ветка в клоне-workspace
внешнего target (`self.target_workspace`, `_sandbox.
ExternalTargetGitSandbox`) с закоммиченным туда кодом (роль-разработчик
пишет код именно там, `orchestrator/runner.role_env`, «эфемерный клон
целевого») — отрицательная часть критерия проверяется на НАСТОЯЩЕМ
коммите кода, не на пустом дереве.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, gitcmd, config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402


class Ac9RoleStepArtifactSeparationTest(ExternalTargetGitSandbox):

    def test_ac9_artifacts_land_in_pult_branch_code_branch_stays_clean(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)

        # Код роли-разработчика — реальный коммит в клоне целевого,
        # НЕ в репозитории пульта.
        code_branch = f"task/{task_id.lower()}-code"
        self.checkout_task_branch(code_branch)
        self.commit_workspace_file(
            "app/feature.py", "print('готово')\n",
            f"{task_id}: код фичи (роль developer)")

        # Положительная часть: артефактная ветка ПУЛЬТА несёт tasks/<id>/.
        pult_branches = [b for b in (gitcmd.list_branches() or [])
                         if b != config.MAIN_BRANCH]
        hosting = [b for b in pult_branches
                  if gitcmd.ls_tree_files(b, f"tasks/{task_id}")]
        self.assertTrue(
            hosting,
            f"ни одна ветка пульта, кроме main, не несёт tasks/{task_id}/ "
            f"после шага роли (AC-9)")

        # Отрицательная часть: кодовая ветка ЦЕЛЕВОГО свободна от tasks/<id>/.
        res = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", code_branch, "--",
             f"tasks/{task_id}"],
            cwd=self.target_workspace, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(
            res.stdout.strip(), "",
            f"кодовая ветка {code_branch} целевого несёт tasks/{task_id}/ "
            f"— требование 8/AC-9 запрещает это")


if __name__ == "__main__":
    import unittest
    unittest.main()
