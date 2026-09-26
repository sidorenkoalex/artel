"""AC-3 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — `orchestrator/amend.py`
после правки пишет ту же выжимку итоговой строки pytest, что и до
задачи.

Зелёный с рождения: tests/test_amend.py зелёный и сегодня, а его класс
`RunSummaryTest` уже фиксирует выжимку итоговой строки — критерий
требует сохранить это состояние, а не завести новое, поэтому тест
обязан быть зелёным до кода и покраснеть только от ослабления.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]
AMEND_TESTS_REL = "tests/test_amend.py"

# Ожидания выжимки итоговой строки, уже стоящие в tests/test_amend.py на
# момент написания планки: разбор типичного зелёного хвоста, разбор
# красного (без traceback) и падение обратно на весь хвост при
# несовпадении. Снятие любого из них — снятая проверка, а не «правка».
RUN_SUMMARY_EXPECTATIONS = (
    "test_extracts_ran_line_and_ok",
    "test_extracts_ran_line_and_failed_with_count",
    "test_missing_ran_line_falls_back_to_full_tail",
)


def _test_method_names(rel: str) -> set:
    """Имена тестовых методов файла — статическим разбором AST, без
    импорта модуля (тот же приём, что `guard.count_test_methods`)."""
    tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name.startswith("test_"):
            names.add(node.name)
    return names


def _run_pytest(*rels: str) -> subprocess.CompletedProcess:
    """Прогон указанных файлов набора `tests/` тем же интерпретатором и
    с теми же флагами изоляции, что и сама планка."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", *rels, "-q",
         "-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=120"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=600)


class AmendSummaryPreservedTest(unittest.TestCase):

    def test_ac3_amend_module_tests_stay_green(self):
        """Файл tests/test_amend.py целиком проходит после правки
        `orchestrator/amend.py`: переиспользование общего узла разбора
        (либо замена им `amend._RUN_SUMMARY`) не имеет права сдвинуть
        выжимку итоговой строки, которую amend пишет в журнал.

        Ловит мутацию: общий узел возвращает не голую итоговую строку, а
        итог вместе с именами упавших тестов, и amend начинает писать
        в журнал правки планки другую выжимку —
        `RunSummaryTest.test_extracts_ran_line_and_ok` (assertEqual на
        «2 passed in 0.01s») падает.
        """
        res = _run_pytest(AMEND_TESTS_REL)

        self.assertEqual(res.returncode, 0,
                         f"{AMEND_TESTS_REL} не зелёный:\n"
                         f"{(res.stdout + res.stderr)[-3000:]}")

    def test_ac3_run_summary_expectations_are_not_edited_away(self):
        """Ожидания выжимки итоговой строки остаются в tests/test_amend.py
        теми же тестовыми методами: зелёность файла достигается правкой
        `orchestrator/amend.py`, не подгонкой ожиданий под новый ответ.

        Ловит мутацию: `amend._run_summary` исчез вместе с общим узлом, и
        `RunSummaryTest` подогнан под новое поведение удалением или
        переименованием своих методов — файл снова зелёный, но выжимка
        итоговой строки больше ничем не зафиксирована.
        """
        present = _test_method_names(AMEND_TESTS_REL)

        missing = [name for name in RUN_SUMMARY_EXPECTATIONS
                   if name not in present]
        self.assertEqual(
            missing, [],
            f"{AMEND_TESTS_REL}: нет тестовых методов {missing} — ожидания "
            f"выжимки итоговой строки pytest сняты, а не сохранены")


if __name__ == "__main__":
    unittest.main()
