"""AC-15 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md): постоянный
регрессионный тест манифеста в `tests/test_stack.py` (в отличие от
`ManifestConstantsTest` в этой же папке — тот прогоняется только пока
жив `acceptance_tests/` этой задачи; требование 1/AC-15 просит
постоянную планку в `tests/`, которую видит штатный CI-джоб `python`
после мержа).

Красен до реализации: `tests/test_stack.py` ещё не существует —
`read_text` падает `FileNotFoundError`.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_STACK_PY = REPO_ROOT / "tests" / "test_stack.py"


class PermanentManifestRegressionTest(unittest.TestCase):

    def test_ac15_test_stack_file_covers_the_manifest_constants(self):
        """`tests/test_stack.py` существует и упоминает константу
        `REQUIRED_PYTHON` и каждый из трёх внешних инструментов
        (`git`/`gh`/`claude`) — минимальный текстовый след того, что
        постоянный тест читает манифест и проверяет наличие описанных в
        требовании 1 констант, а не что-то не связанное со стеком.

        Ловит мутацию: `tests/test_stack.py` заведён пустым файлом-
        заглушкой (импорт модуля без единой проверки констант) — ни одно
        из имён ниже не встретится в тексте, `assertIn` откажет.
        """
        source = TEST_STACK_PY.read_text(encoding="utf-8")
        self.assertIn("REQUIRED_PYTHON", source)
        for tool in ("git", "gh", "claude"):
            self.assertRegex(
                source, rf"\b{tool}\b",
                f"tests/test_stack.py не упоминает инструмент {tool!r} "
                f"манифеста (требование 1)")


if __name__ == "__main__":
    unittest.main()
