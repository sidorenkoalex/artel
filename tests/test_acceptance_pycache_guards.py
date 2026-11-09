"""Ограждения шагов шаблона байткода (`orchestrator/acceptance.py::_warm_prefix`,
SPEC 01M6ZEMZB8Q1PKRXMJBJSTPR7T, указание Оператора на гейте SPEC пп. 1(а),
1(б), 6, 8(а); замечания ревью R1-F1…R1-F4).

Каждый тест гоняет настоящий прогон `acceptance.run_plank` интерпретатором
пульта с местом шаблонов в своём временном каталоге: свойства видны только
на настоящих процессах запроса и сборки. Правила отбора и решения держат
долгоживущие файлы задачи `tests/test_01m6zemzb8q1pkrxmjbjstpr7t_*.py`.
"""
import contextlib
import json
import os
import subprocess
import time
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import acceptance, config, stack

pytestmark = pytest.mark.size("medium")

PHRASE = "шаблон байткода интерпретатора недоступен"
REAL_RUN = subprocess.run
REAL_RMTREE = acceptance.shutil.rmtree

# Сведения интерпретатора пульта для ключа шаблона (AC-3) и место `_pytest`.
KEY_SCRIPT = (
    "import importlib.util, json, os, sys\n"
    "print(json.dumps([os.path.realpath(sys.executable), sys.version,"
    " sys.prefix, list(importlib.util.find_spec('_pytest')"
    ".submodule_search_locations)]))\n")


def interpreter_facts() -> tuple[str, str, str, str]:
    res = REAL_RUN([stack.pytest_python_executable(), "-c", KEY_SCRIPT],
                   capture_output=True, text=True, check=True)
    executable, version, prefix, core = json.loads(res.stdout)
    return executable, version, prefix, core[0]


def make_tree(base: Path) -> Path:
    tree = base / "tree"
    tree.mkdir()
    (tree / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8")
    return tree


def plank(tree: Path, place: Path, capsys, *patches) -> tuple[int, str, str]:
    """Прогон планки с местом шаблонов `place` и подменами `patches`."""
    capsys.readouterr()
    with contextlib.ExitStack() as stack_:
        stack_.enter_context(
            mock.patch.object(config, "PYCACHE_TEMPLATES_DIR", str(place)))
        stack_.enter_context(mock.patch.dict(
            os.environ, {config.PYCACHE_TEMPLATES_ENV: str(place)}))
        for patcher in patches:
            stack_.enter_context(patcher)
        code, output = acceptance.run_plank(["test_probe.py"], tree)
    err = capsys.readouterr().err
    return code, output, err


def phrase_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith(PHRASE)]


def template_path(place: Path) -> Path:
    executable, version, prefix, _core = interpreter_facts()
    with mock.patch.object(config, "PYCACHE_TEMPLATES_DIR", str(place)):
        return Path(acceptance.template_dir(executable, version, prefix))


def test_helpers_read_code_from_stdin_without_pytest_in_argv(tmp_path, capsys):
    """Запрос и сборка — `[интерпретатор, "-", …]` с кодом через stdin, без подстроки `pytest` в argv.

    Шаблона нет: прогон запускает запрос сведений и сборку. Каждый вызов
    `subprocess.run` модуля, чей argv не несёт элемента `pytest` (не прогон),
    — вторым элементом `-`, код передан аргументом `input`, ни один элемент
    argv не содержит подстроки `pytest` (заглушка `tests/test_acceptance.py:248`
    ищет подстроку); таких вызовов два — запрос и сборка; шаблон собран.

    Ловит мутацию: запрос или сборка снова запускаются как `-c <скрипт>` —
    подстрока `pytest` (`pytest_timeout`, `run_module('pytest')`) в argv,
    `input` не передан, тест краснеет.
    """
    base = Path(os.path.realpath(tmp_path))
    tree, place = make_tree(base), base / "templates"
    calls = []

    def spy(cmd, *args, **kwargs):
        calls.append(([os.fspath(part) for part in cmd], kwargs))
        return REAL_RUN(cmd, *args, **kwargs)

    code, output, err = plank(tree, place, capsys,
                              mock.patch.object(acceptance.subprocess, "run", spy))
    interpreter = os.path.realpath(stack.pytest_python_executable())
    helpers = [(argv, kw) for argv, kw in calls if "pytest" not in argv
               and argv and os.path.realpath(argv[0]) == interpreter]

    assert code == 0, output
    assert phrase_lines(err) == [], err
    assert len(helpers) == 2, calls
    for argv, kw in helpers:
        assert argv[1] == "-", argv
        assert not any("pytest" in part for part in argv), argv
        assert isinstance(kw.get("input"), str) and kw["input"], kw
    assert (template_path(place) / acceptance.TEMPLATE_MANIFEST).is_file()


def test_template_steps_never_call_shutil_rmtree(tmp_path, capsys):
    """Сборка и отбрасывание повреждённого шаблона удаляют без `shutil.rmtree`.

    Два прогона: первый собирает шаблон (staging, временный префикс сборки,
    пустые `cwd` процессов), перед вторым из шаблона удалён `manifest.json` —
    второй его отбрасывает. Подмена `acceptance.shutil.rmtree` записывает
    пути: ни один не лежит в месте шаблонов и не является `cwd` процесса
    шаблона или префиксом сборки (`artel-pycache-cwd-`, `artel-pycache-build-`);
    отброшенного шаблона после второго прогона нет.

    Ловит мутацию: шаг шаблона (публикация, уборка сборки, отбрасывание,
    очистка префикса, `cwd` процесса) удаляет через `shutil.rmtree` — путь
    шага в записях, тест краснеет.
    """
    base = Path(os.path.realpath(tmp_path))
    tree, place = make_tree(base), base / "templates"
    removed = []

    def recording_rmtree(path, *args, **kwargs):
        removed.append(os.path.realpath(os.fspath(path)))
        return REAL_RMTREE(path, *args, **kwargs)

    def patch():
        return mock.patch.object(acceptance.shutil, "rmtree", recording_rmtree)

    code, output, err = plank(tree, place, capsys, patch())
    assert code == 0, output
    assert phrase_lines(err) == [], err
    template = template_path(place)
    (template / acceptance.TEMPLATE_MANIFEST).unlink()
    code, output, err = plank(tree, place, capsys, patch())

    assert code == 0, output
    assert len(phrase_lines(err)) == 1, err
    assert not template.exists()
    real_place = os.path.realpath(place)
    for path in removed:
        name = os.path.basename(path)
        assert not acceptance._under(path, real_place), removed
        assert not name.startswith(("artel-pycache-cwd-", "artel-pycache-build-")), \
            removed


def test_interpreter_with_pytest_under_excluded_dir_is_silent(tmp_path, capsys):
    """`_pytest` интерпретатора лежит под исключённым каталогом — пусто, молча, без сборки.

    `config.WORKTREES` подменён каталогом пакетов, где лежит `_pytest`
    интерпретатора пульта (как `.venv` внутри рабочей копии): байткода pytest
    в шаблоне не будет никогда. Два прогона подряд — оба зелёные, строки о
    сбое нет ни в одном, в месте шаблонов нет ни каталога шаблона, ни
    отметки `.failed`.

    Ловит мутацию: проверка допустимости путей интерпретатора снята —
    сборка не даёт `_pytest`, первый прогон печатает строку «сборка не дала
    байткода пакета _pytest», второй — «не удалась менее 3600 с назад»,
    рядом лежит `.failed`.
    """
    base = Path(os.path.realpath(tmp_path))
    tree, place = make_tree(base), base / "templates"
    packages = os.path.dirname(interpreter_facts()[3])
    template = template_path(place)
    with mock.patch.object(config, "WORKTREES", Path(packages)):
        first = plank(tree, place, capsys)
        second = plank(tree, place, capsys)

    for code, output, err in (first, second):
        assert code == 0, output
        assert phrase_lines(err) == [], err
    assert not template.exists()
    assert not Path(str(template) + ".failed").exists()


@pytest.mark.parametrize("content", ["не число", str(int(time.time()) + 10 ** 8)])
def test_damaged_failure_mark_is_removed_and_build_runs(tmp_path, capsys, content):
    """Отметка `.failed` с нечисловым содержимым или временем в будущем удаляется, сборка идёт.

    Шаблона нет, рядом лежит `<имя шаблона>.failed` с повреждённым
    содержимым. Прогон зелёный, строки о сбое нет, шаблон собран и цел,
    отметки больше нет.

    Ловит мутацию: повреждённая отметка читается как свежая неудача
    (нечисловое — временем изменения файла, будущее — возрастом 0) —
    решение `skip`, строка «не удалась менее 3600 с назад», шаблона нет.
    """
    base = Path(os.path.realpath(tmp_path))
    tree, place = make_tree(base), base / "templates"
    place.mkdir(mode=0o700)
    place.chmod(0o700)
    template = template_path(place)
    mark = Path(str(template) + ".failed")
    mark.write_text(content, encoding="utf-8")

    code, output, err = plank(tree, place, capsys)

    assert code == 0, output
    assert phrase_lines(err) == [], err
    assert (template / acceptance.TEMPLATE_MANIFEST).is_file()
    assert not mark.exists()
