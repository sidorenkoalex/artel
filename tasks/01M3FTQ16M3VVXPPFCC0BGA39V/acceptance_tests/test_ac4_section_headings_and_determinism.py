"""AC-4 — 01M3FTQ16M3VVXPPFCC0BGA39V: заголовок секции модуля подпакета
одноуровневый, подпакет идёт непрерывным блоком, повторный прогон
генератора даёт байт-идентичный текст.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Заголовок секции карты для модуля подпакета — одноуровневый
`## orchestrator/doctor/preflight.py` (префикс пакета в имени, без
дополнительного уровня заголовка и без строк-группировщиков), модули
одного подпакета идут непрерывным блоком, а повторный прогон генератора
на неизменном дереве даёт байт-идентичный текст карты.

Красен до реализации: секций модулей подпакета в карте сегодня нет вовсе
(генератор их не обходит) — `test_ac4_subpackage_section_heading_is_
single_level` и `test_ac4_subpackage_modules_form_a_contiguous_block`
падают на отсутствии заголовка `## orchestrator/doctor/preflight.py`.
`test_ac4_repeated_generator_run_is_byte_identical` зелёный уже сейчас:
он проверяет СОХРАНЕНИЕ детерминированности (сегодня она есть на дереве
без подпакетов) — его дело поймать нерекурсивный порядок обхода, который
рекурсия способна внести (`rglob` без сортировки, множество путей).
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import codebase_map  # noqa: E402


class SubpackageSectionHeadingTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _util.write_tree(self.tdir)
        self.map_text, _, _ = _util.built_map(self.tdir)

    def test_ac4_subpackage_section_heading_is_single_level(self):
        """Заголовок секции модуля подпакета — ровно
        `## orchestrator/doctor/preflight.py` отдельной строкой; уровней
        заголовка глубже второго в карте нет, а каждый заголовок `## `
        называет путь модуля из перечня (строк-группировщиков вида
        `## orchestrator/doctor/` в карте не появилось).

        Ловит мутацию: читаемость сделана добавленным уровнем заголовка
        (`### preflight.py` под группой `## orchestrator/doctor/`) — тогда
        либо не найдётся одноуровневый заголовок с полным путём, либо в
        карте появится заголовок-группировщик, не являющийся путём
        модуля; оба `assert` покраснеют.
        """
        self.assertRegex(
            self.map_text,
            re.compile(rf"^## {re.escape(_util.SUB_MODULE)}$", re.M),
            f"в карте нет одноуровневого заголовка `## {_util.SUB_MODULE}` "
            f"(AC-4); заголовки: {_util.section_headers(self.map_text)}")
        self.assertIsNone(
            re.search(r"^#{3,}\s", self.map_text, re.M),
            "в карте не должно быть заголовков глубже второго уровня (AC-4)")
        expected = set(_util.discovered_rel_paths(self.tdir))
        self.assertEqual(
            [], [h for h in _util.section_headers(self.map_text)
                 if h not in expected],
            f"каждый заголовок `## ` карты обязан называть путь модуля из "
            f"перечня, строк-группировщиков быть не должно (AC-4); перечень: "
            f"{sorted(expected)}")

    def test_ac4_subpackage_modules_form_a_contiguous_block(self):
        """Секции модулей одного подпакета идут в карте подряд: между
        `orchestrator/doctor/__init__.py`, `.../misc_checks.py` и
        `.../preflight.py` не вклинивается секция модуля другого
        каталога.

        Ловит мутацию: рекурсивный обход собирает пути в порядке `rglob`
        (сначала все файлы верхнего уровня одного каталога, потом
        подкаталоги другого) либо сортирует перечень по имени файла, как
        нерекурсивный вариант сегодня (`key=lambda p: p.name`) — тогда
        `misc_checks.py` подпакета встанет рядом с модулями верхнего
        уровня по алфавиту, блок подпакета разорвётся, и тест покраснеет.
        """
        headers = _util.section_headers(self.map_text)
        prefix = f"{_util.PKG}/{_util.SUBPKG}/"
        positions = [i for i, h in enumerate(headers) if h.startswith(prefix)]
        self.assertEqual(
            3, len(positions),
            f"в карте ожидаются три секции подпакета {prefix} (AC-4); "
            f"заголовки: {headers}")
        self.assertEqual(
            list(range(positions[0], positions[0] + len(positions))), positions,
            f"секции подпакета {prefix} обязаны идти непрерывным блоком "
            f"(AC-4); заголовки: {headers}")


class GeneratorDeterminismTest(unittest.TestCase):

    def test_ac4_repeated_generator_run_is_byte_identical(self):
        """Генератор, запущенный на неизменном дереве с подпакетом дважды
        отдельными процессами, оба раза пишет байт-идентичный файл карты
        (два процесса — две разные рандомизации хешей строк, поэтому
        порядок обхода, зависящий от множества/словаря, различается
        именно здесь, а не внутри одного процесса).

        Ловит мутацию: перечень модулей собран через `set()` (например,
        дедупликация путей подпакетов множеством) без последующей
        сортировки — порядок секций между прогонами разъедется, и
        `assertEqual` по байтам покраснеет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _util.write_tree(Path(tmp))
            _util.init_git_repo(root)
            map_path = root / codebase_map.OUTPUT_PATH

            first = self._generate(root, map_path)
            second = self._generate(root, map_path)

        self.assertEqual(
            first, second,
            "повторный прогон генератора на неизменном дереве обязан давать "
            "байт-идентичный текст карты (AC-4)")

    def _generate(self, root: Path, map_path: Path) -> bytes:
        result = _util.run_generator(root)
        self.assertEqual(
            0, result.returncode,
            f"генератор обязан отработать с кодом 0 (AC-4):\n"
            f"{result.stdout}\n{result.stderr}")
        return map_path.read_bytes()


if __name__ == "__main__":
    unittest.main()
