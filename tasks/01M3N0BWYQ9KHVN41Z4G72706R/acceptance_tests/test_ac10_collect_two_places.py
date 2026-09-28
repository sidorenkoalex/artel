"""AC-10 — сбор долгоживущего файла: сухой сбор выхода из `tests_writing`
применяется к нему без ослабления, а файл, проходящий требование 3,
собирается `pytest --collect-only` из каталога `tests/`.

Каталог `tests/` здесь — временное зеркало репозитория: `orchestrator/`,
`scripts/`, `conftest.py`, `pyproject.toml` — ссылки на настоящие, `tests/`
— настоящий каталог со ссылками на файлы репозитория и копией фикстуры.
Настоящий `tests/` репозитория планка не трогает.

Группа: разовый
Зелёный с рождения: сухой сбор выхода из `tests_writing` уже применяется ко всем файлам планки, а чистая фикстура уже собирается из `tests/`; файл сторожит, что новые проверки не выключили сбор долгоживущих файлов и не отвергли законный файл.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

COLLECT_REFUSAL = "переход отклонён: планка не собирается"

# Чистый долгоживущий файл, пользующийся помощником `tests/sandbox.py`.
SANDBOX_HEAD = [
    "from tests import sandbox as sandbox_mod  # noqa: F401",
    "from tests.sandbox import capture  # noqa: F401",
]
SANDBOX_BODY = ["helper = sandbox_mod.capture", "self._value = helper"]


def mirror_repo(tmp: Path) -> Path:
    """Зеркало корня репозитория в `tmp`; возвращает его каталог `tests/`."""
    root = _sandbox.REPO_ROOT
    for name in ("orchestrator", "scripts", "conftest.py", "pyproject.toml"):
        os.symlink(root / name, tmp / name)
    tests_dir = tmp / "tests"
    tests_dir.mkdir()
    for entry in (root / "tests").iterdir():
        if entry.name == "__pycache__":
            continue
        os.symlink(entry, tests_dir / entry.name)
    return tests_dir


class CollectTwoPlacesTest(_sandbox.GroupPlankSandbox):

    def test_ac10_dry_collect_still_applies_to_long_lived_file(self):
        """Долгоживущий файл без признаков требования 3, чей импорт падает
        при сборе (`from orchestrator import no_such_module_for_collect`),
        — настоящий сухой сбор отклоняет выход из `tests_writing` прежним
        действием «переход отклонён: планка не собирается».

        Ловит мутацию: статическую проверку долгоживущих файлов сочли
        заменой сухого сбора и `_tests_writing_dry_collect_gate` для них
        пропускают — файл, не собирающийся pytest, уходит в `in_dev`.
        """
        source = _sandbox.plank_source(
            head=["from orchestrator import no_such_module_for_collect  # noqa: F401"])
        self.write_plank({"test_ac.py": source})
        out, refusals = self.advance(real_collect=True)
        self.assertEqual(self.state(), "tests_writing",
                         f"несобирающийся файл ушёл дальше: {out!r}")
        self.assertTrue(
            any(text.startswith(COLLECT_REFUSAL) for text in refusals),
            f"нет отказа «{COLLECT_REFUSAL}»: {refusals!r}")

    def test_ac10_clean_long_lived_file_collects_from_tests_dir(self):
        """Долгоживущий файл, импортирующий `tests.sandbox`, проходит выход
        из `tests_writing`, а его копия в каталоге `tests/` зеркала
        репозитория собирается `pytest --collect-only` с кодом 0 и одним
        тестом `test_ac1_fixture_criterion`.

        Ловит мутацию: признак «импорт вне перечня» не знает пакета
        `tests` (перечень составлен только из `orchestrator`/`scripts`) —
        файл, собирающийся из `tests/`, отклонён на выходе из
        `tests_writing`.
        """
        source = _sandbox.plank_source(head=SANDBOX_HEAD, body=SANDBOX_BODY)
        self.assert_passes({"test_ac.py": source},
                           why="чистый долгоживущий файл с tests.sandbox")

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tests_dir = mirror_repo(tmp)
        (tests_dir / "test_long_lived_fixture.py").write_text(
            source, encoding="utf-8")
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "-p", "no:cacheprovider", "tests/test_long_lived_fixture.py"],
            cwd=tmp, capture_output=True, text=True, timeout=110)
        self.assertEqual(res.returncode, 0,
                         f"сбор из tests/ не прошёл:\n{res.stdout}\n{res.stderr}")
        self.assertIn("test_ac1_fixture_criterion", res.stdout)


if __name__ == "__main__":
    unittest.main()
