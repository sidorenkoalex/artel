"""Скрипт с `#!` под именем интерпретатора не наполняет префикс шаблоном
(`orchestrator/acceptance.py::_warm_prefix`, SPEC 01M6ZEMZB8Q1PKRXMJBJSTPR7T,
уточнение требования 9 и AC-8 в ANSWER-3).

Базовое имя `python3` проходит распознавание AC-8, но интерпретатор шаблона —
только исполняемый файл Python: скрипт-обёртка проекта или шим менеджера
версий после `os.path.realpath` начинается с `#!`, и запрос со сборкой шаблона
исполнили бы код проекта вне прогона. Случаи распознанного настоящего
интерпретатора держит долгоживущий файл задачи
`tests/test_01m6zemzb8q1pkrxmjbjstpr7t_template_runs.py` (AC-14).
"""
import os
from pathlib import Path
from types import MappingProxyType
from unittest import mock

import pytest

from orchestrator import acceptance, config, project_profile, stack, targets

pytestmark = pytest.mark.size("medium")

PHRASE = "шаблон байткода интерпретатора недоступен"
PREFIX_VAR = "PYTHONPYCACHEPREFIX"


def own_profile(command) -> project_profile.Profile:
    return project_profile.Profile(
        command=tuple(command), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py", weakening_scope=("tests/**",),
        mutation_claim_scope=("tests/**",), runner=targets.PROFILE_RUNNER_OWN,
        workdir="", env=MappingProxyType({}))


def test_shebang_script_named_python3_runs_once_cold(tmp_path, capsys):
    """Обёртка `./bin/python3` с `#!` — префикс пуст, строки нет, скрипт исполнен один раз.

    Команда профиля `pytest-own` — исполняемый скрипт `bin/python3` в дереве
    прогона: он дописывает в файл-счётчик строку с числом файлов префикса в
    момент своего запуска и передаёт управление pytest интерпретатора пульта.
    После прогона в счётчике ровно одна строка `run 0` (вызван только самим
    прогоном, префикс пуст), строки о сбое в stderr нет, место шаблонов не
    создано — ни запроса, ни сборки не было.

    Ловит мутацию: скрипт с `#!` принят за интерпретатор (проверка первых
    байтов после `realpath` снята) — запрос и сборка шаблона запускают
    обёртку, в счётчике больше одной строки, место шаблонов создано.
    """
    base = Path(os.path.realpath(tmp_path))
    place = base / "templates"
    tree = base / "tree"
    (tree / "bin").mkdir(parents=True)
    (tree / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8")
    counter = base / "counter.txt"
    wrapper = tree / "bin" / "python3"
    wrapper.write_text(
        "#!/bin/sh\n"
        f'n=$(find "${PREFIX_VAR}" -type f | wc -l | tr -d " ")\n'
        f'echo "run $n" >> "{counter}"\n'
        f'exec "{stack.pytest_python_executable()}" "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    profile = own_profile(["./bin/python3", "-m", "pytest"])
    capsys.readouterr()
    with mock.patch.object(config, "PYCACHE_TEMPLATES_DIR", str(place)), \
         mock.patch.dict(os.environ, {config.PYCACHE_TEMPLATES_ENV: str(place)}):
        code, output = acceptance.run_plank(["test_probe.py"], tree, profile=profile)
    err = capsys.readouterr().err

    assert code == 0, output
    assert counter.read_text(encoding="utf-8").splitlines() == ["run 0"]
    assert [line for line in err.splitlines() if line.startswith(PHRASE)] == [], err
    assert not place.exists()
