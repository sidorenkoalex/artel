"""AC-5 (SPEC 01M2ARQGY51B99YNP9PY806AN1) — после задачи литерал
`FETCH_HEAD` в вызовах git модуля `orchestrator/` не встречается — только
в докстрингах-пояснениях истории.

Статическая проверка (ast), а не запуск git: различает «литерал —
отдельный аргумент git-вызова» (`git("rev-parse", ..., "FETCH_HEAD")` —
строковая константа, ЦЕЛИКОМ равная `"FETCH_HEAD"`) от «упоминание в
прозе докстринга» (`` `FETCH_HEAD` `` — часть куда более длинной строки,
никогда не равной ровно этому слову целиком) — обеими исходами уже
пользуются существующие докстрини этих трёх файлов (гарантированно не
пустые, требование 3 SPEC разрешает именно их), так что различение по
ТОЧНОМУ равенству строки не задевает историю, только реальные вызовы.

Красен до реализации: сегодня все три файла несут `FETCH_HEAD` именно
отдельным аргументом git-вызова — `orchestrator/gitcmd.py:432`
(`git("rev-parse", "--verify", "--quiet", "FETCH_HEAD")`),
`orchestrator/fsm.py:151-152` (`gitcmd.in_repo(repo, "rev-parse",
"FETCH_HEAD")`/`gitcmd.git("rev-parse", "FETCH_HEAD")`),
`orchestrator/fsm_merge_gate.py:104` (`repo_context.git(ctx, "rev-parse",
"FETCH_HEAD")`) — ast-обход найдёт точное совпадение в КАЖДОМ из трёх
файлов, тест упадёт по всем трём срезу.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_FILES = (
    "orchestrator/gitcmd.py",
    "orchestrator/fsm.py",
    "orchestrator/fsm_merge_gate.py",
)


class Ac5NoFetchHeadLiteralOutsideDocstringsTest(unittest.TestCase):

    def test_ac5_fetch_head_literal_absent_from_git_call_arguments(self):
        """Ни один из трёх файлов зоны задачи не несёт строковую
        константу, ЦЕЛИКОМ равную `"FETCH_HEAD"` (докстрини несут её
        только частью более длинной прозы, значит под точное равенство
        не попадают).

        Ловит мутацию: перевод одного из трёх мест на примитив забыт
        (оставлен прежний вызов с `"FETCH_HEAD"` буквальным аргументом)
        — файл с забытым местом даст непустой список совпадений.
        """
        for rel in TARGET_FILES:
            path = REPO_ROOT / rel
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            exact_literals = [
                node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value == "FETCH_HEAD"]
            self.assertEqual(
                exact_literals, [],
                f"{rel}: литерал 'FETCH_HEAD' используется как отдельный "
                f"аргумент git-вызова, не только в прозе докстринга")


if __name__ == "__main__":
    unittest.main()
