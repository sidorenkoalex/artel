"""Подставной `DOCKER_CONFIG` теста compose с настоящим Docker: ссылка `cli-plugins` и её место в тесте.

Группа: долгоживущий

`docker_config_sandbox()` модуля `tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py`
создаёт пустой временный каталог и кладёт в него единственную символическую
ссылку `cli-plugins` на каталог дополнений настоящей конфигурации Docker
(`DOCKER_CONFIG`, пустая строка — как отсутствие; иначе `<HOME>/.docker`).
Настоящие конфигурации здесь вымышленные — каталоги во временной песочнице
`tmp_path`, окружение подменено `monkeypatch`; `docker` эти тесты не зовут
(проба при импорте модуля — его собственная). Тест AC-5 разбирает исходный
текст `test_ac17_real_docker_compose_run` модулем `ast`, файл не меняет.

Красен до реализации: функции `docker_config_sandbox` в модуле теста compose ещё нет — обращение к ней падает AttributeError, а тело `test_ac17_real_docker_compose_run` берёт каталог прямым `tempfile.mkdtemp`.
"""
import ast
import os
import random
import shutil
import string
from pathlib import Path

import pytest

from tests import test_01m6paj61d4pyap79adrpa6mwv_compose_docker as compose_docker

LETTERS = string.ascii_lowercase
TEST_NAME = "test_ac17_real_docker_compose_run"


def word(rng, k: int = 8) -> str:
    return "".join(rng.choices(LETTERS, k=k))


def fictional_config(root: Path, rng, plugins: bool = True) -> Path:
    """Вымышленная конфигурация Docker: `config.json`, каталог контекстов и, по
    желанию, `cli-plugins` с файлом дополнения."""
    conf = root / f"conf_{word(rng)}"
    conf.mkdir(parents=True)
    (conf / "config.json").write_text('{"auths": {}}', encoding="utf-8")
    (conf / "contexts").mkdir()
    if plugins:
        (conf / "cli-plugins").mkdir()
        (conf / "cli-plugins" / f"docker-{word(rng)}").write_text(
            "#!/bin/sh\n", encoding="utf-8")
    return conf


def call_sandbox() -> Path:
    return Path(compose_docker.docker_config_sandbox())


def test_ac1_only_symlink_to_cli_plugins_of_docker_config(tmp_path, monkeypatch):
    """`DOCKER_CONFIG` на вымышленной конфигурации с `cli-plugins` и `config.json`.

    На нескольких случайных конфигурациях (имена из зерна) возвращённый
    каталог содержит ровно один элемент — символическую ссылку `cli-plugins`,
    `os.readlink` которой равен `<конфигурация>/cli-plugins`; `config.json`
    в возвращённом каталоге нет.

    Ловит мутацию: каталог дополнений скопирован (`copytree`) вместо ссылки —
    элемент не символическая ссылка; ссылка поставлена на саму конфигурацию,
    а не на её `cli-plugins` — `os.readlink` другой; скопирован или связан
    `config.json` — в каталоге лишний элемент.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    for _ in range(3):
        conf = fictional_config(tmp_path / word(rng), rng)
        monkeypatch.setenv("DOCKER_CONFIG", str(conf))
        result = call_sandbox()
        try:
            where = f"зерно {seed}: {conf} -> {result}"
            assert result.is_dir() and result != conf, where
            assert sorted(os.listdir(result)) == ["cli-plugins"], where
            link = result / "cli-plugins"
            assert link.is_symlink(), where
            assert os.readlink(link) == str(conf / "cli-plugins"), where
            assert not (result / "config.json").exists(), where
        finally:
            shutil.rmtree(result, ignore_errors=True)


@pytest.mark.parametrize("docker_config", [None, ""])
def test_ac2_home_docker_cli_plugins_when_docker_config_unset_or_empty(
        tmp_path, monkeypatch, docker_config):
    """`DOCKER_CONFIG` не выставлена или пуста, `HOME` — вымышленный с `.docker/cli-plugins`.

    Ссылка `cli-plugins` возвращённого каталога ведёт на
    `<HOME>/.docker/cli-plugins` — и при снятой переменной, и при
    `DOCKER_CONFIG=""`.

    Ловит мутацию: пустая строка `DOCKER_CONFIG` считается заданной
    (`is not None` вместо истинности) — путь `cli-plugins` относителен, ссылки
    нет или она не туда; запасной путь без `.docker` или от `Path.home()` в
    обход переменной `HOME` — `os.readlink` другой.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    home = tmp_path / f"home_{word(rng)}"
    home.mkdir()
    plugins = home / ".docker" / "cli-plugins"
    plugins.mkdir(parents=True)
    (home / ".docker" / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    if docker_config is None:
        monkeypatch.delenv("DOCKER_CONFIG", raising=False)
    else:
        monkeypatch.setenv("DOCKER_CONFIG", docker_config)
    result = call_sandbox()
    try:
        where = f"зерно {seed}, DOCKER_CONFIG={docker_config!r}: {result}"
        link = result / "cli-plugins"
        assert link.is_symlink(), where
        assert os.readlink(link) == str(plugins), where
    finally:
        shutil.rmtree(result, ignore_errors=True)


@pytest.mark.parametrize("via", ["docker_config", "home"])
def test_ac3_no_cli_plugins_gives_empty_dir(tmp_path, monkeypatch, via):
    """В вымышленной конфигурации нет `cli-plugins` — пустой каталог без ссылки.

    Варианты: `DOCKER_CONFIG` на конфигурации с `config.json`, но без
    `cli-plugins`; `DOCKER_CONFIG` снята, у вымышленного `HOME` нет `.docker`.
    Вызов не падает и возвращает существующий пустой каталог.

    Ловит мутацию: ссылка ставится без проверки существования цели — в
    каталоге висячая ссылка `cli-plugins`; создание каталога дополнений или
    копия `config.json` при его отсутствии — каталог не пуст; `os.symlink`
    на отсутствующую цель с падением — вызов бросает исключение.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    if via == "docker_config":
        conf = fictional_config(tmp_path, rng, plugins=False)
        monkeypatch.setenv("DOCKER_CONFIG", str(conf))
    else:
        home = tmp_path / f"home_{word(rng)}"
        home.mkdir()
        monkeypatch.delenv("DOCKER_CONFIG", raising=False)
        monkeypatch.setenv("HOME", str(home))
    result = call_sandbox()
    try:
        where = f"зерно {seed}, {via}: {result}"
        assert result.is_dir(), where
        assert os.listdir(result) == [], where
        assert not os.path.lexists(result / "cli-plugins"), where
    finally:
        shutil.rmtree(result, ignore_errors=True)


def test_ac4_each_call_reads_environment_anew(tmp_path, monkeypatch):
    """Два вызова подряд: `DOCKER_CONFIG` сначала на A, затем на B — ссылки на `A/cli-plugins` и `B/cli-plugins`.

    Ловит мутацию: путь настоящей конфигурации вычислен при импорте модуля
    или закэширован после первого вызова — вторая ссылка ведёт в
    `A/cli-plugins`; оба вызова возвращают один и тот же каталог — первая
    ссылка перезаписана.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    first = fictional_config(tmp_path / "a", rng)
    second = fictional_config(tmp_path / "b", rng)
    results = []
    try:
        for conf in (first, second):
            monkeypatch.setenv("DOCKER_CONFIG", str(conf))
            results.append(call_sandbox())
        where = f"зерно {seed}: {results}"
        assert results[0] != results[1], where
        assert os.readlink(results[0] / "cli-plugins") == str(
            first / "cli-plugins"), where
        assert os.readlink(results[1] / "cli-plugins") == str(
            second / "cli-plugins"), where
    finally:
        for result in results:
            shutil.rmtree(result, ignore_errors=True)


def call_name(node) -> str:
    """Точечное имя вызываемого: `acceptance.report_run`, `str`, … — иначе пусто."""
    func = node.func
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        return ".".join(reversed(parts))
    return ""


def is_str_of(node, expected: str) -> bool:
    """`node` — вызов `str(<выражение>)`, выражение которого записано как `expected`."""
    return (isinstance(node, ast.Call) and call_name(node) == "str"
            and len(node.args) == 1 and ast.unparse(node.args[0]) == expected)


def test_ac5_compose_test_takes_docker_config_from_helper():
    """Статика тела `test_ac17_real_docker_compose_run`: каталог — от `docker_config_sandbox()`.

    Разбор исходного текста модуля теста compose (`ast`): присваивание
    `<имя> = docker_config_sandbox()` стоит раньше `acceptance.report_run`;
    `monkeypatch.setenv("DOCKER_CONFIG", str(<имя>))`,
    `monkeypatch.setenv("HOME", str(<имя>.parent))` и
    `real_git.addCleanup(shutil.rmtree, <имя>, …)` берут это имя, обе подмены
    — после присваивания; `tempfile.mkdtemp` в теле не вызывается.

    Ловит мутацию: подмена `HOME` до вызова помощника — её позиция раньше
    присваивания; `HOME` не от его результата (прежний `mkdtemp` или другой
    каталог) — второй аргумент не `str(<имя>.parent)`; помощник добавлен, а
    каталог по-прежнему из `tempfile.mkdtemp` — вызов найден в теле.
    """
    source = Path(compose_docker.__file__).read_text(encoding="utf-8")
    funcs = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.FunctionDef) and node.name == TEST_NAME]
    assert len(funcs) == 1, f"{TEST_NAME}: найдено определений {len(funcs)}"
    body = funcs[0]
    pos = lambda node: (node.lineno, node.col_offset)  # noqa: E731
    assigns = [node for node in ast.walk(body)
               if isinstance(node, ast.Assign) and len(node.targets) == 1
               and isinstance(node.targets[0], ast.Name)
               and isinstance(node.value, ast.Call)
               and call_name(node.value) == "docker_config_sandbox"]
    assert len(assigns) == 1, "нет присваивания <имя> = docker_config_sandbox()"
    assign = assigns[0]
    name = assign.targets[0].id
    calls = [node for node in ast.walk(body) if isinstance(node, ast.Call)]
    report = [node for node in calls
              if call_name(node) == "acceptance.report_run"]
    assert report, "в теле нет вызова acceptance.report_run"
    assert pos(assign) < min(pos(node) for node in report), (
        f"{name} = docker_config_sandbox() не раньше acceptance.report_run")
    setenv = {}
    for node in calls:
        if (call_name(node) == "monkeypatch.setenv" and len(node.args) == 2
                and isinstance(node.args[0], ast.Constant)):
            setenv.setdefault(node.args[0].value, []).append(node)
    for var, expected in (("DOCKER_CONFIG", name), ("HOME", f"{name}.parent")):
        found = setenv.get(var, [])
        assert found, f"нет monkeypatch.setenv({var!r}, …)"
        for node in found:
            assert is_str_of(node.args[1], expected), (
                f"setenv({var!r}, {ast.unparse(node.args[1])}) — "
                f"ожидалось str({expected})")
            assert pos(node) > pos(assign), (
                f"setenv({var!r}, …) раньше {name} = docker_config_sandbox()")
    cleanups = [node for node in calls
                if call_name(node) == "real_git.addCleanup"
                and len(node.args) >= 2
                and ast.unparse(node.args[0]) == "shutil.rmtree"
                and ast.unparse(node.args[1]) == name]
    assert cleanups, f"нет real_git.addCleanup(shutil.rmtree, {name}, …)"
    mkdtemp = [ast.unparse(node) for node in calls
               if call_name(node).split(".")[-1] == "mkdtemp"]
    assert mkdtemp == [], f"в теле остался вызов: {mkdtemp}"
