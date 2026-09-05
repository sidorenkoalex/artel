"""AC-2 (SPEC): «Автокоммит артефактов шага не заносит
`__pycache__/*.pyc` из каталога задачи (`tasks/<id>/`) в артефактную
ветку».

Буквальный сценарий инцидента 03.09 из «Контекст» SPEC: developer
прогнал `python3 -m unittest` в `tasks/<id>/acceptance_tests`,
интерпретатор создал `__pycache__/*.pyc` рядом с тестами, автокоммит
занёс их в артефактную ветку.

Красен до реализации: `checkpoint._commit_external_step_artifacts`
сегодня коммитит абсолютно всё, что лежит под `task_dir`
(`orchestrator/checkpoint.py`, `for path in sorted(task_dir.
rglob("*")):` без фильтра) — `.pyc` из теста ниже попадёт в артефактную
ветку, `assertNotIn` упадёт.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import checkpoint, store  # noqa: E402
from _sandbox import GitignoreExternalTargetSandbox  # noqa: E402


class PycacheExcludedTest(GitignoreExternalTargetSandbox):

    def test_ac2_pycache_pyc_from_acceptance_tests_is_not_committed(self):
        """Прогон приёмочных тестов роли создаёт `acceptance_tests/
        __pycache__/*.pyc` рядом с текстами тестов; шаг всё равно пишет
        и настоящий артефакт (`SPEC.md`) — оба файла лежат в одном
        `task_dir` на диске, автокоммит обязан разделить их по правилу
        `.gitignore`, не занести оба или отказаться от обоих разом.

        Ловит мутацию: снятие фильтрации целиком (возврат к безусловному
        `rglob("*")`) — `.pyc` окажется в `artifact_branch_files()`,
        `assertNotIn` покраснеет.
        """
        self.write("acceptance_tests/test_ac.py", "import unittest\n")
        self.write("acceptance_tests/__pycache__/test_ac.cpython-311.pyc",
                   bytes(range(16)))
        self.write("SPEC.md", "---\ntask: x\ntype: spec\n---\n# SPEC\n")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/acceptance_tests/test_ac.py", files)
        self.assertIn(f"tasks/{self.TASK}/SPEC.md", files)
        self.assertNotIn(
            f"tasks/{self.TASK}/acceptance_tests/__pycache__/"
            "test_ac.cpython-311.pyc", files)


if __name__ == "__main__":
    unittest.main()
