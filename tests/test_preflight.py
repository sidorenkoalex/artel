"""`orchestrator/preflight.py`: вырожденные входы предпроверки, которых не
касается долгоживущий файл задачи 01M4P4ZP37WV81410YTZHKQC8D — нет файла БД
пульта и нет SPEC.md в каталоге документов задачи.
"""
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from orchestrator import artifact_branch, config, preflight, store
from tests.sandbox import InitializedTmpRootTest, TmpRootTest

TASK = "T001"


def run_preflight(arg: str) -> tuple:
    """(код выхода, весь вывод) `preflight.cmd_preflight(arg)`."""
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        try:
            preflight.cmd_preflight(arg)
            code = 0
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


class NoDatabaseTest(TmpRootTest):

    def test_missing_db_exits_2_and_creates_no_db(self):
        """Файла БД пульта нет: код 2, файл БД так и не появился.

        Ловит мутацию: строка задачи читается через `store.db()` — он
        заводит файл БД со схемой, и вместо кода 2 идёт отказ «не найдена»
        с кодом сообщения `sys.exit`, а файл БД после команды есть.
        """
        self.assertFalse(config.DB.exists())
        code, output = run_preflight(TASK)
        self.assertEqual(code, 2, output)
        self.assertIn("не найдена", output)
        self.assertFalse(config.DB.exists(), output)


class MissingSpecTest(InitializedTmpRootTest):

    def test_missing_spec_refuses_traceability(self):
        """Нет SPEC.md в каталоге документов: отказ трассируемости, код 1.

        Ловит мутацию: непрочитанный SPEC.md считается SPEC без критериев
        (пустой текст в `traceability_errors_from_content`) — трассируемость
        «пройдена» и код 0, хотя переход на такой задаче отказал бы.
        """
        store.insert_task(store.db(), TASK, "Задача", preflight.STATE,
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        docs = artifact_branch.docs_dir(TASK, config.DEFAULT_TARGET)
        plank = docs / "acceptance_tests"
        plank.mkdir(parents=True, exist_ok=True)
        (plank / "test_x.py").write_text(
            '"""Х.\n\nГруппа: разовый\n\nКрасен до реализации: нет кода.\n"""\n',
            encoding="utf-8")
        code, output = run_preflight(TASK)
        lines = output.splitlines()
        header = f"{preflight.CHECK_TRACEABILITY}: {preflight.REFUSED}"
        self.assertIn(header, lines, output)
        below = lines[lines.index(header) + 1]
        self.assertTrue(below.startswith("  ") and "SPEC.md: не прочитан" in below,
                        output)
        self.assertEqual(code, 1, output)


if __name__ == "__main__":
    unittest.main()
