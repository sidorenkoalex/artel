"""Приёмочный тест AC-11 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-11: `acceptance.run` для target ≠ self исполняет прогон приёмочных
тестов с `cwd`, указывающим на клон контекста target'а (или его
временную материализацию), а не на `config.ROOT`; для self поведение
не меняется.

Тест не гоняет FSM целиком — только сам примитив `acceptance.run` с
намеренно cwd-чувствительным приёмочным тестом (читает файл ОТНОСИТЕЛЬНЫМ
путём: `Path("marker.txt")`, без абсолютного адреса) — так разница между
«прогон идёт в клоне целевого» и «прогон идёт в config.ROOT» становится
наблюдаемой по исходу зелено/красно, а не по косвенным признакам.

Красен до реализации: `acceptance.run` сегодня не принимает параметр
`cwd` вовсе — вызов с `cwd=` падает `TypeError`; тело функции жёстко
пришивает `cwd=config.ROOT` к `subprocess.run`.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import acceptance  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

CWD_SENSITIVE_TEST = '''
import unittest
from pathlib import Path


class MarkerTest(unittest.TestCase):
    def test_marker_is_target_workspace(self):
        self.assertEqual(Path("marker.txt").read_text(encoding="utf-8"),
                         "target\\n")
'''


class AcceptanceRunCwdTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.tdir = Path(self.mktemp_dir())
        acc = self.tdir / "acceptance_tests"
        acc.mkdir(parents=True)
        (acc / "test_marker.py").write_text(CWD_SENSITIVE_TEST,
                                            encoding="utf-8")

    def mktemp_dir(self) -> str:
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, ignore_errors=True)
        return d

    def test_ac11_cwd_pointed_at_the_target_clone_is_green(self):
        """`cwd=self.target_workspace` — прогон видит `marker.txt`
        целевого ("target\\n") и зеленеет.

        Ловит мутацию: `cwd` принимается, но не пробрасывается в
        `subprocess.run` (по-прежнему `config.ROOT`) — там `marker.txt`
        нет вовсе, прогон покраснеет тем же способом, что и второй тест
        ниже.
        """
        green, tail = acceptance.run(self.tdir, cwd=self.target_workspace)

        self.assertTrue(green, tail)

    def test_ac11_cwd_pointed_at_the_pult_root_is_red(self):
        """Контрольная проверка: `cwd=self.root` (пульт, без `marker.
        txt` со значением "target\\n") — прогон краснеет. Доказывает,
        что зелёный исход выше — заслуга именно `cwd`, а не то, что
        тест зелёный при любом `cwd`."""
        green, tail = acceptance.run(self.tdir, cwd=self.root)

        self.assertFalse(green)

    def test_ac11_without_cwd_defaults_to_root_byte_identical(self):
        """Байт-в-байт прежнее поведение self (без `cwd=`): совпадает с
        явным `cwd=self.root`."""
        green_default, _ = acceptance.run(self.tdir)
        green_explicit, _ = acceptance.run(self.tdir, cwd=self.root)

        self.assertEqual(green_default, green_explicit)


if __name__ == "__main__":
    import unittest
    unittest.main()
