"""Общие фикстуры pytest: устойчивое подключение в корневом `conftest.py` и инвариант 42.

Группа: долгоживущий
Красен до реализации: без Приложения 1 `conftest.py` зовёт `find_spec("tests.fixtures")` без перехвата — в зеркале без пакета `tests` сбор падает кодом 4; без Приложения 4 класса `SharedFixturesWrapSandboxClassesInvariantTest` в `tests/test_invariants.py` нет — импорт в тестах AC-4 падает.

Тесты AC-2 и AC-3 строят во временном каталоге зеркало корня репозитория
(копия `conftest.py`, пакеты по симлинку) и гоняют pytest подпроцессом;
тест AC-4 запускает методы инварианта на мутированных временных копиях
`tests/fixtures.py`. Входы (имена файлов, число тестов, выбранная фикстура,
подставленный класс) порождаются при каждом запуске модулем `random`,
зерно печатается и входит в текст провала.
"""
import ast
import io
import os
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import pytest

from orchestrator.config import ARTEL_ROLE_ENV

REPO = Path(__file__).resolve().parent.parent
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _seeded():
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def _mirror(root: Path, packages: list) -> None:
    """Зеркало корня: копия `conftest.py` и пакеты `packages` по симлинку."""
    (root / "conftest.py").write_text(
        (REPO / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name in packages:
        (root / name).symlink_to(REPO / name, target_is_directory=True)


def _pytest(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in (ARTEL_ROLE_ENV, "PYTHONPATH")}
    env["PYTHONPATH"] = str(root)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=root, env=env, capture_output=True, text=True, timeout=110)


def test_ac2_collect_without_tests_package_exits_zero(tmp_path):
    """Сбор в зеркале без каталога `tests/` проходит с кодом 0.

    Во временном каталоге — копия корневого `conftest.py` и `orchestrator`
    по симлинку, `tests/` нет, `PYTHONPATH` — только этот каталог, в
    окружении нет `ARTEL_ROLE`. Сбор явно названного тест-файла со случайным
    именем и случайным числом тестов, с загруженным `conftest.py`
    (без `--noconftest`), обязан завершиться кодом 0 и собрать все тесты
    файла.

    Ловит мутацию: `_fixtures_plugins()` без перехвата `ModuleNotFoundError`
    (или прежний голый `find_spec("tests.fixtures")`) — загрузка
    `conftest.py` падает, pytest выходит кодом 4 вместо 0; либо он отдаёт
    `["tests.fixtures"]` без проверки — плагин не импортируется, код не 0.
    """
    seed, rng = _seeded()
    _mirror(tmp_path, ["orchestrator"])
    assert not (tmp_path / "tests").exists()
    count = rng.randint(1, 5)
    name = f"test_probe_{rng.getrandbits(32):08x}.py"
    (tmp_path / name).write_text("".join(
        f"def test_probe_{i}():\n    assert True\n\n\n" for i in range(count)),
        encoding="utf-8")
    run = _pytest(tmp_path, "--collect-only", "-q", name)
    out = run.stdout + run.stderr
    assert run.returncode == 0, f"зерно {seed}: код {run.returncode}\n{out}"
    assert f"{count} test" in run.stdout, f"зерно {seed}: собрано не всё\n{out}"


def test_ac3_tmp_root_visible_under_acceptance_tests_without_import(tmp_path):
    """Тест-функция планки получает `tmp_root` параметром без импорта.

    Зеркало: копия корневого `conftest.py`, `orchestrator`, `scripts` и
    `tests` (с `tests/fixtures.py`) по симлинку. Под каталогом задач
    `<id>/acceptance_tests/` со случайным id лежит файл, функции которого
    просят `tmp_root` параметром и ничего не импортируют; подпроцесс pytest
    по этому файлу обязан пройти все тесты: фикстура — экземпляр
    `TmpRootTest` с существующим каталогом `root`.

    Ловит мутацию: `_fixtures_plugins()` отдаёт `[]` и при найденном
    `tests.fixtures` (перепутанное условие или перехват, проглатывающий
    находку) — тест планки падает «fixture 'tmp_root' not found», код 1.
    """
    seed, rng = _seeded()
    _mirror(tmp_path, ["orchestrator", "scripts", "tests"])
    assert (tmp_path / "tests" / "fixtures.py").is_file()
    task = "".join(rng.choice(CROCKFORD) for _ in range(26))
    plank = tmp_path / "tasks" / task / "acceptance_tests"
    plank.mkdir(parents=True)
    count = rng.randint(1, 3)
    (plank / "test_probe.py").write_text("".join(
        f"def test_probe_{i}(tmp_root):\n"
        f"    assert type(tmp_root).__name__ == 'TmpRootTest'\n"
        f"    assert tmp_root.root.is_dir()\n\n\n" for i in range(count)),
        encoding="utf-8")
    run = _pytest(tmp_path, "-q", str((plank / "test_probe.py").relative_to(tmp_path)))
    out = run.stdout + run.stderr
    assert run.returncode == 0, f"зерно {seed}: код {run.returncode}\n{out}"
    assert f"{count} passed" in run.stdout, f"зерно {seed}\n{out}"


EXTRA_CONFIG_FIXTURE = '''

@pytest.fixture
def patched_config_root(tmp_path):
    """Своя подмена путей `config` вместо класса песочницы."""
    from orchestrator import config
    from unittest import mock
    with mock.patch.object(config, "ROOT", tmp_path):
        yield tmp_path
'''


def _function(tree, name):
    return next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _fixtures(tree):
    return [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.decorator_list]


def _insert_into_sandbox(source: str, statement: str) -> str:
    lines = source.splitlines(keepends=True)
    first = _function(ast.parse(source), "_sandbox").body[0]
    at = first.lineno - 1
    lines.insert(at, " " * first.col_offset + statement + "\n")
    return "".join(lines)


def _foreign_classes(sandbox) -> list:
    """Классы `tests/sandbox.py`, не наследники `TmpDirTest`/`TmpRootTest`."""
    return sorted(
        name for name, obj in vars(sandbox).items()
        if isinstance(obj, type) and obj.__module__ == sandbox.__name__
        and not issubclass(obj, (sandbox.TmpDirTest, sandbox.TmpRootTest)))


def _mutate(source: str, mutation: str, rng) -> str:
    """Копия текста `tests/fixtures.py` с мутацией `mutation`."""
    if mutation == "config_fixture":
        return source.rstrip("\n") + "\n" + EXTRA_CONFIG_FIXTURE
    if mutation == "sandbox_imports_config":
        return _insert_into_sandbox(source, "from orchestrator import config")
    if mutation == "sandbox_imports_config_alias":
        return _insert_into_sandbox(source, "import orchestrator.config as cfg")
    node = rng.choice(_fixtures(ast.parse(source)))
    lines = source.splitlines(keepends=True)
    def_at = node.lineno - 1
    if mutation == "extra_decorator":
        lines.insert(def_at, '@pytest.mark.usefixtures("tmp_path")\n')
        return "".join(lines)
    if mutation == "assigned_fixture":
        impl = f"{node.name}_impl"
        lines[def_at] = lines[def_at].replace(f"def {node.name}(", f"def {impl}(", 1)
        for dec in node.decorator_list:
            lines[dec.lineno - 1] = ""
        lines.append(f"\n\n{node.name} = pytest.fixture({impl})\n")
        return "".join(lines)
    if mutation == "foreign_class":
        from tests import sandbox
        imp = node.body[-2]
        old = imp.names[0].name
        new = rng.choice(_foreign_classes(sandbox))
        for stmt in node.body[-2:]:
            at = stmt.lineno - 1
            lines[at] = re.sub(rf"\b{old}\b", new, lines[at])
        return "".join(lines)
    raise ValueError(mutation)


def _run_invariant(path: Path) -> unittest.TestResult:
    from tests.test_invariants import SharedFixturesWrapSandboxClassesInvariantTest as inv
    with mock.patch.object(inv, "PATH", path):
        suite = unittest.TestLoader().loadTestsFromTestCase(inv)
        return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


def _report(result: unittest.TestResult) -> str:
    return "\n".join(text for _case, text in result.failures + result.errors)


def test_ac4_invariant_green_on_unmutated_copy(tmp_path):
    """Немутированная временная копия `tests/fixtures.py`: все методы инварианта зелёные.

    Методы `SharedFixturesWrapSandboxClassesInvariantTest` запускаются
    раннером unittest с `PATH`, подменённым на побайтовую копию файла во
    временном каталоге; провалов и ошибок нет, запущен хотя бы один метод.

    Ловит мутацию: инвариант запрещает то, чем нынешний `tests/fixtures.py`
    законно пользуется (например, относит к запрещённым именам `pytest`
    или `yield`, требует второй декоратор) — метод краснеет на исправной
    копии.
    """
    copy = tmp_path / "fixtures.py"
    copy.write_text((REPO / "tests" / "fixtures.py").read_text(encoding="utf-8"),
                    encoding="utf-8")
    result = _run_invariant(copy)
    assert result.testsRun >= 1
    assert result.wasSuccessful(), _report(result)


@pytest.mark.parametrize("mutation", [
    "config_fixture",
    "sandbox_imports_config",
    "extra_decorator",
    "assigned_fixture",
    "foreign_class",
    "sandbox_imports_config_alias",
])
def test_ac4_invariant_red_on_each_mutation(tmp_path, mutation):
    """Каждая из шести мутаций временной копии `tests/fixtures.py` краснит инвариант.

    Мутации AC-4: (0) добавлена фикстура, подменяющая `config` сама;
    (1) `_sandbox` импортирует `config`; (2) у случайной фикстуры
    дополнительный декоратор сверх `pytest.fixture`; (3) случайная фикстура
    задана присваиванием `<имя> = pytest.fixture(<функция>)`; (4) случайная
    фикстура импортирует из `tests.sandbox` и отдаёт через `_sandbox`
    случайный класс модуля, не наследник `TmpDirTest`/`TmpRootTest`;
    (5) `_sandbox` импортирует `config` с псевдонимом. Методы инварианта с
    `PATH` на мутированную копию — хотя бы один провален.

    Ловит мутацию: инвариант не смотрит вложенные узлы функций (только
    верхний уровень), сравнивает с запретом только полное имя модуля
    импорта без сегментов и псевдонима, принимает любой декоратор,
    содержащий `fixture`, пропускает присваивание на верхнем уровне или не
    проверяет базовый класс — соответствующий вариант остаётся зелёным.
    """
    seed, rng = _seeded()
    original = (REPO / "tests" / "fixtures.py").read_text(encoding="utf-8")
    mutated = _mutate(original, mutation, rng)
    assert mutated != original, f"зерно {seed}: мутация {mutation} не применилась"
    ast.parse(mutated)
    copy = tmp_path / "fixtures.py"
    copy.write_text(mutated, encoding="utf-8")
    result = _run_invariant(copy)
    assert result.testsRun >= 1
    assert not result.wasSuccessful(), (
        f"зерно {seed}: мутация {mutation} не поймана\n{mutated}")
