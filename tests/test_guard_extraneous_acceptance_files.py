"""Юнит-тесты `guard.is_extraneous_acceptance_test_file`/`guard.
scan_extraneous_acceptance_files` (SPEC 01M1SAA01YRRTWAVADT2F81RRQ, AC-1,
AC-3, AC-6).

Поведение `guard.main()` целиком (обе именованные ошибки, оба режима
`--all`/`--all --artifact-branch`) уже покрыто залоченной планкой
приёмки (tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/
test_guard_extraneous_acceptance_test_file.py, AC-3/AC-6) — дублировать
её тут смысла нет. Здесь — юниты на сам предикат и на обход нескольких
задач сразу, включая `__pycache__`, который приёмочная планка не трогает
(она проверяет посторонний файл per-задачу, не сам обход `tasks/*/`).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402


class IsExtraneousAcceptanceTestFileTest(unittest.TestCase):

    def test_allowed_top_level_names_are_not_extraneous(self):
        """Ловит мутацию: из списка разрешённых имён/расширений guard'а
        выпадает одно из них, и легитимный файл планки ошибочно
        помечается посторонним."""
        for rel in ("test_x.py", "_sandbox.py", "_util.py", "markers.py", "__init__.py",
                   "NOTES.md", "README.txt"):
            with self.subTest(файл=rel):
                self.assertFalse(guard.is_extraneous_acceptance_test_file(rel))

    def test_disallowed_top_level_extension_is_extraneous(self):
        """Ловит мутацию: guard-предикат перестаёт отклонять неразрешённое
        расширение первого уровня (`.json`)."""
        self.assertTrue(
            guard.is_extraneous_acceptance_test_file("fixtures.json"))

    def test_nested_path_is_extraneous_even_with_allowed_extension(self):
        """Ловит мутацию: guard-предикат не проверяет глубину пути и
        пропускает вложенный файл с разрешённым расширением (`.md`)."""
        self.assertTrue(
            guard.is_extraneous_acceptance_test_file("docs/codebase-map.md"))


class ScanExtraneousAcceptanceFilesTest(unittest.TestCase):

    def test_missing_tasks_root_returns_empty(self):
        """Ловит мутацию: обход несуществующего каталога `tasks/` бросает
        исключение вместо пустого списка (пропущена проверка
        `.exists()`)."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                guard.scan_extraneous_acceptance_files(Path(tmp) / "no-such-dir"),
                [])

    def test_scans_multiple_task_directories_and_skips_pycache(self):
        """Ловит мутацию: обход не проходит все `tasks/*/acceptance_tests/`
        или не исключает `__pycache__`, и служебные `.pyc`-файлы попадают
        в результат сканирования."""
        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = Path(tmp)
            for task in ("T1", "T2"):
                tests_dir = tasks_root / task / "acceptance_tests"
                tests_dir.mkdir(parents=True)
                (tests_dir / "test_ok.py").write_text("# ок\n", encoding="utf-8")
                (tests_dir / "extra.json").write_text("{}", encoding="utf-8")
                pycache = tests_dir / "__pycache__"
                pycache.mkdir()
                (pycache / "test_ok.cpython-311.pyc").write_bytes(b"\x00")

            found = guard.scan_extraneous_acceptance_files(tasks_root)

            names = sorted(f.relative_to(tasks_root).as_posix() for f in found)
            self.assertEqual(
                names,
                ["T1/acceptance_tests/extra.json",
                 "T2/acceptance_tests/extra.json"])

    def test_task_without_acceptance_tests_dir_is_skipped(self):
        """Ловит мутацию: обход падает или возвращает ложный результат для
        задачи без каталога `acceptance_tests/` (пропущена проверка
        существования подкаталога перед сканированием)."""
        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = Path(tmp)
            (tasks_root / "T1").mkdir(parents=True)
            self.assertEqual(
                guard.scan_extraneous_acceptance_files(tasks_root), [])

    def test_task_closed_before_this_rule_is_not_scanned(self):
        """Ловит мутацию: исключение для уже закрытых задач удаляется или
        читает не тот путь к RETRO_DIR — правило начинает красить
        исторические ветки с легитимными вспомогательными файлами.

        Найдено эмпирически: `guard --all` на реальном дереве пульта
        красил несколько давно закрытых задач с легитимными
        вспомогательными файлами вида `_util.py` в `acceptance_tests/`
        — то же исключение, что `_closed_before_split_assessment`
        (docs/retro/<id>.md на месте — задача не под этим правилом).
        """
        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = Path(tmp) / "tasks"
            retro_dir = Path(tmp) / "retro"
            retro_dir.mkdir(parents=True)
            tests_dir = tasks_root / "T1" / "acceptance_tests"
            tests_dir.mkdir(parents=True)
            (tests_dir / "_util.py").write_text("# хелпер\n", encoding="utf-8")
            (retro_dir / "T1.md").write_text("# ретро\n", encoding="utf-8")

            with mock.patch.object(guard, "RETRO_DIR", retro_dir):
                found = guard.scan_extraneous_acceptance_files(tasks_root)

            self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
