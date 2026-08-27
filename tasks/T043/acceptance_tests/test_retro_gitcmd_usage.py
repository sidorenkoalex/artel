"""Приёмочные тесты T043 — новые git-вызовы идут только через `gitcmd.git`
(SPEC.md, AC-5), по образцу
`tasks/T042/acceptance_tests/test_map_regen_on_merge.py`
(`NewGitCallsGoThroughGitcmdTest`), но применена к обоим модулям, куда SPEC
(требования 1, 2) целит реализацию RETRO: `orchestrator/fsm.py`
(merge_gate) и `orchestrator/cleanup.py` (`cleanup_killed_task`).

`orchestrator/fsm.py` уже несёт такую же неослабляемую проверку от T042
(та же логика, не переносится сюда повторно как отдельный лок — эта
проверка независима и покрывает файл целиком, включая код T043); здесь
она добавлена и для `fsm.py` тоже, чтобы AC-5 T043 не зависел от того,
останется ли тест T042 в дереве."""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import unittest  # noqa: E402


def direct_git_subprocess_run_lines(path: Path) -> list[int]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.name)
    offending = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_subprocess_run = (
            isinstance(func, ast.Attribute) and func.attr == "run"
            and isinstance(func.value, ast.Name) and func.value.id == "subprocess")
        if not is_subprocess_run or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
            head = first.elts[0]
            if isinstance(head, ast.Constant) and head.value == "git":
                offending.append(node.lineno)
    return offending


class NewGitCallsGoThroughGitcmdTest(unittest.TestCase):
    """AC-5: `subprocess.run(["git", ...])` напрямую запрещён в модулях
    точек встраивания RETRO (требования 1, 2 SPEC); допустимы только
    вызовы через `gitcmd.git`."""

    def test_ac5_fsm_has_no_direct_git_subprocess_run(self):
        offending = direct_git_subprocess_run_lines(
            REPO_ROOT / "orchestrator" / "fsm.py")
        self.assertEqual(
            offending, [],
            f"orchestrator/fsm.py: прямые subprocess.run(['git', ...]) на "
            f"строках {offending} — должны идти через gitcmd.git")

    def test_ac5_cleanup_has_no_direct_git_subprocess_run(self):
        offending = direct_git_subprocess_run_lines(
            REPO_ROOT / "orchestrator" / "cleanup.py")
        self.assertEqual(
            offending, [],
            f"orchestrator/cleanup.py: прямые subprocess.run(['git', ...]) "
            f"на строках {offending} — должны идти через gitcmd.git")


if __name__ == "__main__":
    unittest.main()
