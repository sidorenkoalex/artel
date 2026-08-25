"""Приёмочные тесты T034: AC-11 — `orchestrator/__init__.py` в карте.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 8
(ревью T027): любой модуль пакета с `from . import x, y` резолвит
относительный импорт уровня 1 без имени (`base = package`, см.
`extract_imported_dotted_names`) и попутно добавляет в свои
зависимости голый `orchestrator` — то есть `orchestrator/__init__.py`.
Почти каждый модуль `orchestrator/*.py` в итоге перечисляет
`orchestrator/__init__.py` как обычную запись «Импортирует», и он же
оказывается в «Импортируется» у почти всех — шум, не несущий сигнала
о реальной зависимости от содержимого `__init__.py`.

Фикстура — временное дерево `orchestrator/{__init__,a,b}.py` с одним
`from . import b` в `a.py`: минимальный воспроизводимый случай шума,
без обращения к настоящему репозиторию.

Критерий допускает два решения: исключить `__init__.py` из списков
целиком либо явно пометить его отдельно от прочих зависимостей. Тест
проверяет свойство, общее для обоих: `orchestrator/__init__.py` не
встречается как РАВНОПРАВНАЯ запись (тот же формат `` `путь` ``, через
запятую с остальными) в строке «Импортирует:»/«Импортируется:» ни
одного модуля.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "codebase_map_under_test", REPO_ROOT / "scripts" / "codebase_map.py")
codebase_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codebase_map)

ORDINARY_ENTRY = "`orchestrator/__init__.py`"


class Ac11InitPyIsNotAnOrdinaryMapEntryTest(unittest.TestCase):
    """AC-11: `__init__.py` не наравне с прочими в списках зависимостей."""

    def build_fixture(self, root: Path) -> None:
        pkg = root / "orchestrator"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Пакет orchestrator."""\n', encoding="utf-8")
        (pkg / "a.py").write_text(
            '"""Модуль a."""\nfrom . import b\n\n\ndef pub_a():\n    pass\n',
            encoding="utf-8")
        (pkg / "b.py").write_text(
            '"""Модуль b."""\n\n\ndef pub_b():\n    pass\n', encoding="utf-8")

    def render(self, root: Path) -> str:
        modules, resolved_imports, imported_by = codebase_map.build_modules(root)
        return codebase_map.render(modules, resolved_imports, imported_by,
                                   "0" * 40)

    def dependency_lines(self, text: str) -> list[str]:
        return [line for line in text.splitlines()
               if line.startswith("**Импортирует:**")
               or line.startswith("**Импортируется:**")]

    def entries(self, line: str) -> list[str]:
        _, _, rest = line.partition("** ")
        return [e.strip() for e in rest.split(", ")]

    def test_ac11_init_py_is_absent_as_an_ordinary_entry_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root)

            text = self.render(root)

            offending = []
            for line in self.dependency_lines(text):
                if ORDINARY_ENTRY in self.entries(line):
                    offending.append(line)
            self.assertEqual(
                offending, [],
                f"orchestrator/__init__.py перечислен как обычная запись "
                f"наравне с прочими зависимостями: {offending}")

    def test_ac11_b_is_still_an_ordinary_entry_for_a(self):
        """Смежная гарантия: реальная зависимость a.py от b.py в карте
        осталась — правка не должна была скрыть настоящие связи."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root)

            text = self.render(root)
            lines = text.splitlines()
            start = lines.index("## orchestrator/a.py")
            section = lines[start:start + 15]
            imports_line = next(l for l in section
                                if l.startswith("**Импортирует:**"))

            self.assertIn("`orchestrator/b.py`", self.entries(imports_line))


if __name__ == "__main__":
    unittest.main()
