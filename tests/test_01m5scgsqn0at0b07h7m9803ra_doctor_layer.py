"""Строка `doctor` `targets-local-layer`: локальный слой записей внешних проектов и записи внешних проектов в `targets.yaml` репозитория.

Группа: долгоживущий
Красен до реализации: среди строк `doctor.all_checks` нет строки `targets-local-layer`, а сломанный `.artel/targets.yaml` не читается — строки `targets-yaml` со статусом `fail` нет.

Связка, которую держит файл: «файлы слоёв под корнем песочницы —
`targets.load` — `doctor.all_checks`». Песочница —
`tests.sandbox.InitializedTmpRootTest` (фикстура `initialized_tmp_root`:
пути `config` во временном каталоге, БД со схемой); строки `doctor` —
публичный `doctor.all_checks(conn)`, строка ищется по имени. Прочие
проверки `doctor` зовут CLI ролей, `gh` и сетевой git — им отвечает отказ
запуска (тот же приём, что у долгоживущего теста строки `canary-live`).
Файл локального слоя — `config.TARGETS.parent / ".artel" / "targets.yaml"`.
Имя внешнего проекта — от зерна `random`; зерно печатается и входит в текст
провала.
"""
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import config, doctor, store
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
CHECK = "targets-local-layer"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}


def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


@pytest.fixture
def pult(initialized_tmp_root):
    """Песочница с проинициализированным корнем; внешние процессы не запускаются."""
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if local_command(argv):
            return real_run(argv, *args, **kwargs)
        empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines")) else ""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local_command(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

    with mock.patch.object(subprocess, "run", run), \
            mock.patch.object(subprocess, "Popen", popen):
        yield initialized_tmp_root


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def flat_entry(name: str) -> str:
    return (f"  {name}:\n    forge: github\n"
            f"    url: https://localhost/team/{name}\n    base: main\n"
            f"    token_slot: {name}-token\n    no_paths: []\n"
            f"    project_skills: []\n    merge_gate: operator\n")


def three_entry(name: str) -> str:
    return (f"  {name}:\n"
            f"    description:\n      base: main\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


def layout(case: str, name: str) -> None:
    repo = "targets:\n" + artel_target_entry()
    local = None
    if case == "внешние только в локальном":
        local = "targets:\n" + three_entry(name)
    elif case == "внешняя только в репозитории":
        repo += flat_entry(name)
    elif case == "в обоих слоях":
        repo += flat_entry(name)
        local = "targets:\n" + three_entry(name)
    elif case == "сломанный локальный":
        local = f"targets:\n\t{name}:\n"
    config.TARGETS.write_text(repo, encoding="utf-8")
    if local is not None:
        local_file().parent.mkdir(parents=True, exist_ok=True)
        local_file().write_text(local, encoding="utf-8")


@pytest.mark.parametrize("case,status,needle", [
    ("нет файла и внешних", "ok", "файла нет, внешних записей в targets.yaml нет"),
    ("внешние только в локальном", "ok", "записи {name}"),
    ("внешняя только в репозитории", "warn", "artel.py targets-migrate {name}"),
    ("в обоих слоях", "warn", "doc-commit targets.yaml, затем pin-update"),
])
def test_ac13_local_layer_line(pult, case, status, needle):
    """Строка `targets-local-layer` по раскладке записей в двух слоях.

    Сценарий: слой репозитория — артель и, по случаю, плоская запись
    внешнего проекта; локальный слой — нет файла либо запись того же
    проекта в трёх разделах. Ровно одна строка `targets-local-layer`:
    нет файла и внешних — `ok` «файла нет, внешних записей в targets.yaml
    нет» с путём локального слоя; внешняя только в локальном — `ok` с её
    именем; только в репозитории — `warn` с командой
    `artel.py targets-migrate <имя>`; в обоих — `warn` с
    «doc-commit targets.yaml, затем pin-update».

    Ловит мутацию: проверка не добавлена в `all_checks`; статус `fail`
    вместо `warn` у записи, которую надо перенести; запись в обоих слоях
    не отличается от записи только в репозитории.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    name = "p" + "".join(random.Random(seed).choice(LETTERS) for _ in range(6))
    layout(case, name)
    checks = doctor.all_checks(store.db())
    found = [c for c in checks if c.name == CHECK]
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    assert len(found) == 1, f"зерно: {seed}; строк {CHECK}: {len(found)}\n{shown}"
    check = found[0]
    assert check.status == status, f"зерно: {seed}; {check}"
    assert needle.format(name=name) in check.detail, f"зерно: {seed}; {check}"
    if case == "нет файла и внешних":
        assert str(local_file()) in check.detail, f"зерно: {seed}; {check}"


def test_ac13_broken_local_layer_fails_targets_yaml(pult):
    """Сломанный локальный слой — строка `targets-yaml` со статусом `fail`, строки `targets-local-layer` нет.

    Сценарий: слой репозитория годен, `.artel/targets.yaml` с табуляцией в
    отступе. Среди строк `doctor` есть `targets-yaml` со статусом `fail`
    и путём локального слоя в тексте; строки `targets-local-layer` нет.

    Ловит мутацию: строка локального слоя выводится и при сломанном слое;
    сломанный слой молча считается отсутствующим (`targets-yaml` не
    провалена).
    """
    layout("сломанный локальный", "pbroken")
    checks = doctor.all_checks(store.db())
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    failed = [c for c in checks if c.name == "targets-yaml"]
    assert len(failed) == 1, shown
    assert failed[0].status == "fail", shown
    assert str(local_file()) in failed[0].detail, shown
    assert not [c for c in checks if c.name == CHECK], shown
