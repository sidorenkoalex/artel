"""Приёмочные тесты AC-8: `scripts/guard.py` выдаёт предупреждение (не
ошибку — элемент результата `warnings`, не `errors`, не блокирует
переход гейта) для планки, чей `_sandbox.py` определяет собственные
функции `disk_backed_*`/`advance_from_in_dev` вместо импорта из `tests/
sandbox.py` (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J, требование 3).

Красен до реализации: `scripts/guard.py` сегодня не несёт функции
`sandbox_reuse_check` — обращение к ней падает `AttributeError` во всех
тестах этого файла.
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

OWN_COPY_SANDBOX = '''
def disk_backed_show(branch, rel):
    return None, "своя копия"
'''

OWN_ADVANCE_SANDBOX = '''
def advance_from_in_dev(self):
    pass
'''

IMPORTED_SANDBOX = '''
from tests.sandbox import (disk_backed_show, disk_backed_ls_tree_files,
                           TmpRootTest)


class Scenario(TmpRootTest):

    def make_in_repo_side_effect(self, conflict_files):
        """Тонкая надстройка сценария — своя, но НЕ disk_backed_*/
        advance_from_in_dev эталона."""
        return conflict_files
'''


def _make_plank(root: Path, name: str, sandbox_source: str | None) -> Path:
    tdir = root / name
    tests_dir = tdir / "acceptance_tests"
    tests_dir.mkdir(parents=True)
    if sandbox_source is not None:
        (tests_dir / "_sandbox.py").write_text(sandbox_source,
                                               encoding="utf-8")
    return tdir


class GuardSandboxReuseWarningTest(unittest.TestCase):

    def test_ac8_own_disk_backed_definition_warns_not_errors(self):
        """`_sandbox.py`, определяющий собственный `disk_backed_show`,
        получает предупреждение guard'а — элемент результата
        `warnings`, не `errors`.

        Ловит мутацию: предупреждение попадает в `errors` вместо
        `warnings` (сигнал начинает блокировать переход гейта) —
        `assertEqual(result["errors"], [])` ниже поймает регресс.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _make_plank(Path(tmp), "T1", OWN_COPY_SANDBOX)
            result = guard.sandbox_reuse_check(tdir)

        self.assertEqual(result.get("errors"), [])
        self.assertTrue(result.get("warnings"),
                        "собственная копия disk_backed_show обязана дать "
                        "предупреждение")

    def test_ac8_own_advance_from_in_dev_definition_also_warns(self):
        """Тот же сигнал срабатывает и на собственном `advance_from_
        in_dev`, не только на `disk_backed_*`.

        Ловит мутацию: проверка распознаёт только `disk_backed_*` и
        пропускает `advance_from_in_dev` — `assertTrue` ниже не найдёт
        предупреждения на файле, определяющем только этот метод.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _make_plank(Path(tmp), "T2", OWN_ADVANCE_SANDBOX)
            result = guard.sandbox_reuse_check(tdir)

        self.assertEqual(result.get("errors"), [])
        self.assertTrue(result.get("warnings"))

    def test_ac8_import_from_sandbox_does_not_warn(self):
        """`_sandbox.py`, импортирующий помощники из `tests.sandbox` (не
        определяющий их заново), не получает предупреждения — иначе
        ЛЮБАЯ планка, следующая правилу скила (AC-7), красила бы
        `guard` ложным предупреждением.

        Ловит мутацию: проверка ищет только имя функции текстом, не
        различая `def disk_backed_show` и упоминание того же имени в
        `from tests.sandbox import disk_backed_show` — `assertEqual`
        ниже поймает ложное срабатывание.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _make_plank(Path(tmp), "T3", IMPORTED_SANDBOX)
            result = guard.sandbox_reuse_check(tdir)

        self.assertEqual(result.get("errors"), [])
        self.assertEqual(result.get("warnings"), [])

    def test_ac8_missing_sandbox_file_is_neither_error_nor_warning(self):
        """Планка без `_sandbox.py` вовсе (сценарий не нуждается в
        локальной надстройке) не получает ни ошибок, ни предупреждений.

        Ловит мутацию: отсутствие файла трактуется как повод для ошибки
        — `guard.sandbox_reuse_check` бросает исключение вместо пустого
        результата.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _make_plank(Path(tmp), "T4", None)
            result = guard.sandbox_reuse_check(tdir)

        self.assertEqual(result.get("errors"), [])
        self.assertEqual(result.get("warnings"), [])


if __name__ == "__main__":
    unittest.main()
