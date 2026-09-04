"""AC-1 (SPEC): «Автокоммит артефактов шага не включает в коммит файлы,
которые `.gitignore` пульта считает игнорируемыми (эквивалент `git
check-ignore`, не список расширений)».

Красен до реализации: `checkpoint._commit_external_step_artifacts`
сегодня (`orchestrator/checkpoint.py`, `for path in sorted(task_dir.
rglob("*")):`) обходит КАЖДЫЙ файл `task_dir` без единой проверки
`.gitignore` — `dropme/notes.txt` из теста ниже попадёт в артефактную
ветку наравне с `PLAN.md`, `assertNotIn` упадёт.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import checkpoint, store  # noqa: E402
from _sandbox import GitignoreExternalTargetSandbox  # noqa: E402


class GitignoreEquivalentFilterTest(GitignoreExternalTargetSandbox):

    def test_ac1_directory_rule_not_expressible_as_extension_list_is_excluded(self):
        """Правило `.gitignore` пульта `dropme/` — директорное, не суффикс:
        список расширений в коде никогда не сопоставит `notes.txt` внутри
        `dropme/` с этим правилом, только настоящий разбор `.gitignore`
        (`git check-ignore` или эквивалент по тем же правилам сопоставления
        путей). Обычный файл того же шага (`PLAN.md`) в артефактную ветку
        обязан попасть — фильтр не должен исключать вообще всё.

        Ловит мутацию: замена git-эквивалентной проверки на список
        зашитых в код расширений (`.pyc`, `.log`, ...) — `dropme/notes.txt`
        не попадёт ни под одно расширение из такого списка и продолжит
        коммититься, тест покраснеет на `assertNotIn`.
        """
        self.write("PLAN.md", "план разработчика")
        self.write("dropme/notes.txt", "мусор, игнорируемый по каталогу")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files)
        self.assertNotIn(f"tasks/{self.TASK}/dropme/notes.txt", files)
        self.assertIn("артефактная ветка", detail)


if __name__ == "__main__":
    unittest.main()
