"""Приёмочные тесты AC-4, AC-7 (tasks/01M1SAA01YRRTWAVADT2F81RRQ/
SPEC.md): `scripts/codebase_map.py` пишет `docs/codebase-map.md` только
в корень дерева, определённый `git rev-parse --show-toplevel`, а не
рядом с рабочим каталогом запуска.

Красен до реализации: `codebase_map.main()` сегодня буквально берёт
`root = Path.cwd()` и пишет `root / OUTPUT_PATH` — запуск с cwd внутри
подкаталога (ровно инцидент 05.09: `tasks/<id>/acceptance_tests/`
изнутри роли test_author) кладёт файл рядом с этим подкаталогом, не в
корень репозитория.

Песочница — отдельный временный git-репозиторий (не пульт): нужен
настоящий `git rev-parse`, но НИКАК не связан с реальным деревом этой
задачи — `codebase_map.main()` не должен трогать `.git` пульта.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import codebase_map  # noqa: E402


class _TmpGitRepoTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo_root = Path(tmp.name).resolve()
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "artel@example.invalid")
        self._git("config", "user.name", "artel tests")
        (self.repo_root / "marker.txt").write_text("x\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")

        self._orig_cwd = Path.cwd()
        self.addCleanup(self._chdir, self._orig_cwd)

    def _chdir(self, path: Path) -> None:
        import os
        os.chdir(path)

    def _git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.repo_root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def run_main_from(self, subdir: Path) -> int:
        subdir.mkdir(parents=True, exist_ok=True)
        self._chdir(subdir)
        return codebase_map.main()

    def output_at_root(self) -> Path:
        return self.repo_root / "docs" / "codebase-map.md"


class Ac4WritesToRootFromShallowSubdirTest(_TmpGitRepoTest):
    """AC-4: запуск из подкаталога ПЕРВОГО уровня (`scripts/`) — карта
    появляется в корне, не рядом с cwd запуска."""

    def test_ac4_shallow_subdir_run_lands_map_in_repo_root(self):
        """Ловит мутацию: реализация оставляет `root = Path.cwd()`
        безусловно (не зовёт `git rev-parse --show-toplevel` вовсе) — для
        любого запуска не из корня, включая этот подкаталог первого
        уровня, карта осела бы рядом с cwd запуска (`scripts/docs/
        codebase-map.md`), а не в `<корень>/docs/codebase-map.md`.
        Разбор мутаций фиксированной глубины подъёма — тест `Ac7...`
        ниже (там глубина подкаталога другая, ровно эту мутацию и
        ловит)."""
        rc = self.run_main_from(self.repo_root / "scripts")

        self.assertEqual(rc, 0)
        self.assertTrue(self.output_at_root().is_file(),
                        "карта обязана появиться в <корень>/docs/codebase-map.md")
        self.assertFalse(
            (self.repo_root / "scripts" / "docs" / "codebase-map.md").exists(),
            "карта не должна появляться рядом с cwd запуска")


class Ac7WritesToRootFromDeepAcceptanceTestsSubdirTest(_TmpGitRepoTest):
    """AC-7: запуск из ГЛУБОКОГО подкаталога, буквально повторяющего путь
    инцидента (`tasks/<id>/acceptance_tests/`, три уровня вложенности) —
    карта всё равно появляется в корне."""

    def test_ac7_deep_acceptance_tests_subdir_run_lands_map_in_repo_root(self):
        """Ловит мутацию: корень ищется фиксированным числом подъёмов
        (например, `Path.cwd().parents[1]` — работало бы только для
        подкаталога ровно нужной глубины) вместо настоящего `git
        rev-parse --show-toplevel` — для ТРЁХУРОВНЕВОГО подкаталога
        такая мутация даёт неверный (несуществующий или чужой) путь,
        отличимый от результата этого теста при правильной реализации;
        отдельно от `Ac4...` (глубина подкаталога там не совпадает с
        этой, что и создаёт разницу в мутациях, которые ловит каждый
        тест)."""
        deep = self.repo_root / "tasks" / "01FAKEDEEPMAPRUN0001" / "acceptance_tests"

        rc = self.run_main_from(deep)

        self.assertEqual(rc, 0)
        self.assertTrue(self.output_at_root().is_file(),
                        "карта обязана появиться в <корень>/docs/codebase-map.md")
        self.assertFalse((deep / "docs" / "codebase-map.md").exists(),
                         "карта не должна появляться рядом с cwd запуска")


if __name__ == "__main__":
    unittest.main()
