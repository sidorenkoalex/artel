"""Правила шаблона байткода интерпретатора: чистые функции решения (AC-1…AC-8).

Группа: долгоживущий
Красен до реализации: функций `acceptance.pycache_source`, `template_admits`, `template_dir`, `manifest_intact`, `publish_template`, `template_decision`, `command_interpreter` и `config.pycache_templates_dir`/`PYCACHE_TEMPLATES_ENV`/`PYCACHE_TEMPLATES_DIR` ещё нет — обращение к атрибуту модуля падает `AttributeError`.

Каждое правило проверяется на поверхности решения, названной критерием:
конечные варианты — литералами `parametrize`, значения внутри варианта
(имена каталогов, файлов, хэши, uid) — от `random` при каждом запуске;
зерно печатается и входит в текст провала. Файловая система — только
временный каталог теста (`tmp_path`): ссылки на каталог (AC-2, AC-4) и
публикация переименованием (AC-6).

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы файла зелёные.
"""
import hashlib
import json
import os
import random
import stat
import string
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import acceptance, config

pytestmark = pytest.mark.size("small")

TAGS = ("cpython-311", "cpython-312", "cpython-313", "pypy310")


def make_rng():
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def ident(rng, k: int = 8) -> str:
    return rng.choice(string.ascii_lowercase) + "".join(
        rng.choices(string.ascii_lowercase + string.digits + "_", k=k))


def rel_dir(rng) -> str:
    return "/".join(ident(rng) for _ in range(rng.randint(1, 5)))


def sha(rng) -> str:
    return hashlib.sha256(rng.randbytes(16)).hexdigest()


# --------------------------------------------------------------- AC-1


def test_ac1_tagged_pyc_maps_to_absolute_source():
    """Путь `<каталог>/<имя>.<тег>.pyc` префикса даёт `/<каталог>/<имя>.py`.

    Каталоги, имена и теги интерпретатора случайны (зерно печатается);
    на каждом из десятков входов исходник — абсолютный путь с тем же
    каталогом и именем, расширение `.py`.

    Ловит мутацию: ведущий `/` не добавлен (исходник относительный) либо
    тег не отрезан (`<имя>.<тег>.py`) — сравнение с ожидаемым путём краснеет.
    """
    seed, rng = make_rng()
    for _ in range(40):
        directory, name, tag = rel_dir(rng), ident(rng), rng.choice(TAGS)
        got = acceptance.pycache_source(f"{directory}/{name}.{tag}.pyc")
        assert got == f"/{directory}/{name}.py", f"зерно {seed}: {directory}, {name}, {tag}"


@pytest.mark.parametrize("tail", [
    "{name}.{tag}.opt-1.pyc",
    "{name}.{tag}.opt-2.pyc",
    "{name}.pyc",
    "{name}.{tag}.py",
    "{name}.{tag}.pyo",
    "{name}.{tag}",
    "{name}",
    "{name}.{tag}.pyc.tmp",
])
def test_ac1_untagged_optimized_or_foreign_gives_none(tail):
    """Не `.pyc`, `.pyc` без тега интерпретатора и `.opt-N.pyc` дают `None`.

    Каталог, имя и тег случайны; имя файла строится по варианту литерала.

    Ловит мутацию: уровень оптимизации не отличается от тега
    (`<имя>.<тег>.opt-1.pyc` переводится в `<имя>.<тег>.py` или
    `<имя>.py`) либо проверка суффикса `.pyc` снята — функция отдаёт путь
    вместо `None`.
    """
    seed, rng = make_rng()
    for _ in range(10):
        directory = rel_dir(rng)
        name = tail.format(name=ident(rng), tag=rng.choice(TAGS))
        got = acceptance.pycache_source(f"{directory}/{name}")
        assert got is None, f"зерно {seed}: {directory}/{name} -> {got}"


# --------------------------------------------------------------- AC-2


@pytest.fixture
def linked_tree(tmp_path):
    """Реальный каталог `real/<a>/<lib>` и ссылка `link` на `real`."""
    rng = random.Random(random.randrange(1 << 32))
    real = tmp_path / "real"
    lib = real / ident(rng) / ident(rng)
    lib.mkdir(parents=True)
    (lib.parent / (lib.name + "2")).mkdir()
    (lib / "sub").mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    return {"real": real, "lib": lib, "link": link}


def spelled(path: Path, tree: dict, via_link: bool) -> str:
    """`path` под `real`, записанный через ссылку `link` либо как есть."""
    if not via_link:
        return str(path)
    return str(tree["link"] / path.relative_to(tree["real"]))


@pytest.mark.parametrize("source_link,paths_link,excluded_link", [
    (False, False, False), (True, False, False), (False, True, False),
    (True, True, False), (False, False, True), (True, True, True),
])
def test_ac2_admission_compares_real_paths(linked_tree, source_link,
                                           paths_link, excluded_link):
    """Покрытие и исключение считаются после `realpath` всех трёх входов.

    Во временном каталоге — реальное дерево и ссылка на него. Исходник под
    путём интерпретатора допускается, как бы ни были записаны исходник и
    путь (через ссылку или нет); тот же исходник под исключённым каталогом
    отвергается при любом написании исключения.

    Ловит мутацию: сравнение строк без `os.path.realpath` (или только у
    одного из входов) — исходник `link/…` не признаётся лежащим под
    `real/…`, допуск или исключение промахиваются.
    """
    tree = linked_tree
    lib, sub = tree["lib"], tree["lib"] / "sub"
    source = spelled(sub / "x.py", tree, source_link)
    paths = [spelled(lib, tree, paths_link)]
    assert acceptance.template_admits(source, paths, []) is True, (source, paths)
    excluded = [spelled(sub, tree, excluded_link)]
    assert acceptance.template_admits(source, paths, excluded) is False, (
        source, paths, excluded)


def test_ac2_component_boundary(linked_tree):
    """`/a/lib` не покрывает `/a/lib2/x.py`, а `/a/lib/x.py` покрывает.

    Пути — реальные каталоги временного дерева; та же граница действует
    и у исключённого каталога: исключение `/a/lib` не выбрасывает
    исходник `/a/lib2/x.py` из пути `/a`.

    Ловит мутацию: «лежит под» проверено `startswith` без разделителя —
    `/a/lib2/x.py` признан лежащим под `/a/lib` (допущен или исключён).
    """
    lib = linked_tree["lib"]
    sibling = lib.parent / (lib.name + "2")
    assert acceptance.template_admits(str(lib / "x.py"), [str(lib)], []) is True
    assert acceptance.template_admits(str(sibling / "x.py"), [str(lib)], []) is False
    assert acceptance.template_admits(
        str(sibling / "x.py"), [str(lib.parent)], [str(lib)]) is True


def test_ac2_filesystem_root_is_not_an_interpreter_path(linked_tree):
    """Корень `/` среди путей интерпретатора исходник не допускает.

    Исходник лежит вне прочих путей интерпретатора; в перечне путей есть
    `/` — исход «не допущен». С настоящим путём рядом исходник под ним
    по-прежнему допущен.

    Ловит мутацию: корень не отброшен из путей — под `/` лежит любой
    исходник, и файл вне путей интерпретатора допускается в шаблон.
    """
    lib = linked_tree["lib"]
    other = linked_tree["real"] / "elsewhere.py"
    assert acceptance.template_admits(str(other), ["/", str(lib)], []) is False
    assert acceptance.template_admits(str(lib / "x.py"), ["/", str(lib)], []) is True


# --------------------------------------------------------------- AC-3


def test_ac3_template_dir_is_child_and_keyed_by_three_values(tmp_path):
    """Каталог шаблона — прямой потомок места, без `.`; ключ — три значения.

    Место подменено временным каталогом. Случайные исполняемый файл,
    `sys.version` и `sys.prefix`: повторный вызов с теми же значениями даёт
    тот же каталог, смена любого одного из трёх — другой.

    Ловит мутацию: `sys.prefix` не входит в ключ (у разных venv одного
    Python общий каталог) или ключ — только версия — смена соответствующего
    значения отдаёт тот же каталог.
    """
    seed, rng = make_rng()
    place = str(tmp_path / "templates")
    with mock.patch.object(config, "PYCACHE_TEMPLATES_DIR", place):
        for _ in range(10):
            exe = "/" + rel_dir(rng) + "/python3." + str(rng.randint(8, 14))
            version = f"3.{rng.randint(8, 14)}.{rng.randint(0, 20)} ({ident(rng)})"
            prefix = "/" + rel_dir(rng)
            base = acceptance.template_dir(exe, version, prefix)
            assert os.path.dirname(base) == place, f"зерно {seed}: {base}"
            assert not os.path.basename(base).startswith("."), f"зерно {seed}: {base}"
            assert acceptance.template_dir(exe, version, prefix) == base
            variants = (
                (exe + "x", version, prefix),
                (exe, version + "+", prefix),
                (exe, version, prefix + "/venv"),
            )
            for args in variants:
                other = acceptance.template_dir(*args)
                assert other != base, f"зерно {seed}: {args} -> {other}"
                assert os.path.dirname(other) == place, f"зерно {seed}: {other}"


# --------------------------------------------------------------- AC-4


def test_ac4_env_name_constant():
    """Имя переменной переопределения места — `PYCACHE_TEMPLATES_DIR`.

    Ловит мутацию: имя с названием продукта (`ARTEL_PYCACHE_TEMPLATES_DIR`)
    — дочерние процессы и подмена песочницы ищут другую переменную.
    """
    assert config.PYCACHE_TEMPLATES_ENV == "PYCACHE_TEMPLATES_DIR"


def test_ac4_env_value_default_and_root_exclusion(tmp_path):
    """Непустая переменная побеждает, иначе `<tmp_root>/pycache-templates-<uid>`; под `root` — `None`.

    Временный каталог: `root`, его соседи `root2` (граница компонента) и
    ссылка `link` на `root`. Значение переменной вне `root` возвращается
    как есть; пустое или отсутствующее — место по умолчанию от `tmp_root`
    и `uid`; результат, лежащий под `root` или равный ему (в том числе
    через ссылку), — `None`. uid и имена случайны.

    Ловит мутацию: пустая строка переменной принята за значение (место
    `""`), граница `root` — `startswith` без разделителя (`root2` отключён)
    либо сравнение без `realpath` (ссылка в `root` не отключена).
    """
    seed, rng = make_rng()
    name = config.PYCACHE_TEMPLATES_ENV
    root = tmp_path / "root"
    (root / "inner").mkdir(parents=True)
    sibling = tmp_path / "root2"
    sibling.mkdir()
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    outside = tmp_path / ident(rng)
    outside.mkdir()
    uid = rng.randint(1, 60000)
    noise = {"PATH": "/usr/bin", ident(rng).upper(): ident(rng)}

    def call(environ, tmp_root):
        return config.pycache_templates_dir(environ, str(tmp_root), uid, str(root))

    value = str(outside / ident(rng))
    assert call({**noise, name: value}, outside) == value, f"зерно {seed}"
    assert call({**noise, name: str(sibling / "t")}, outside) == str(sibling / "t"), \
        f"зерно {seed}"
    default = os.path.join(str(outside), f"pycache-templates-{uid}")
    assert call(dict(noise), outside) == default, f"зерно {seed}"
    assert call({**noise, name: ""}, outside) == default, f"зерно {seed}"
    for inside in (str(root), str(root / "inner" / "t"), str(link / "t"), str(link)):
        assert call({**noise, name: inside}, outside) is None, f"зерно {seed}: {inside}"
    assert call(dict(noise), root / "inner") is None, f"зерно {seed}"
    assert call(dict(noise), link) is None, f"зерно {seed}"


# --------------------------------------------------------------- AC-5


def intact_hashes(rng) -> dict:
    files = {f"{rel_dir(rng)}/_pytest/{ident(rng)}.cpython-313.pyc": sha(rng)}
    for _ in range(rng.randint(0, 6)):
        files[f"{rel_dir(rng)}/{ident(rng)}.cpython-313.pyc"] = sha(rng)
    return files


def test_ac5_consistent_manifest_with_pytest_is_intact():
    """Манифест, совпадающий с набором файлов и несущий `_pytest`, — цел.

    Набор файлов и хэши случайны; порядок ключей манифеста перемешан.

    Ловит мутацию: манифест сверяется с самим собой (не с хэшами файлов)
    или признак `_pytest` ищется в имени файла, а не в каталоге — случайный
    целый набор признаётся повреждённым.
    """
    seed, rng = make_rng()
    for _ in range(20):
        files = intact_hashes(rng)
        keys = list(files)
        rng.shuffle(keys)
        text = json.dumps({k: files[k] for k in keys})
        assert acceptance.manifest_intact(text, dict(files)) is True, f"зерно {seed}"


@pytest.mark.parametrize("defect", [
    "none", "not_json", "json_list", "json_string", "extra_file",
    "missing_file", "hash_mismatch", "no_pytest", "pytest_named_file",
    "pytest_like_dir",
])
def test_ac5_any_defect_breaks_intactness(defect):
    """Каждый дефект манифеста или набора делает шаблон не целым.

    Из случайного целого набора строится вариант литерала: нет манифеста,
    не JSON, JSON не объект, лишний или недостающий файл, один несовпавший
    хэш, набор без каталога `_pytest` (в том числе файл с именем `_pytest`
    и каталог `_pytestx`).

    Ловит мутацию: сверка только по ключам без значений, только «манифест
    ⊆ файлы» без обратного включения или без признака `_pytest` — вариант
    признаётся целым.
    """
    seed, rng = make_rng()
    files = intact_hashes(rng)
    manifest = dict(files)
    text = None
    if defect == "extra_file":
        files[f"{rel_dir(rng)}/{ident(rng)}.cpython-313.pyc"] = sha(rng)
    elif defect == "missing_file":
        manifest[f"{rel_dir(rng)}/{ident(rng)}.cpython-313.pyc"] = sha(rng)
    elif defect == "hash_mismatch":
        key = rng.choice(list(files))
        value = files[key]
        flipped = "0" if value[-1] != "0" else "1"
        manifest[key] = value[:-1] + flipped
    elif defect in ("no_pytest", "pytest_named_file", "pytest_like_dir"):
        directory = {"no_pytest": "site", "pytest_named_file": "site",
                     "pytest_like_dir": "_pytestx"}[defect]
        stem = "_pytest" if defect == "pytest_named_file" else ident(rng)
        files = {f"{rel_dir(rng)}/{directory}/{stem}.cpython-313.pyc": sha(rng)}
        manifest = dict(files)
    if defect == "none":
        text = None
    elif defect == "not_json":
        text = "{" + json.dumps(manifest)
    elif defect == "json_list":
        text = json.dumps(list(manifest.items()))
    elif defect == "json_string":
        text = json.dumps(json.dumps(manifest))
    else:
        text = json.dumps(manifest)
    assert acceptance.manifest_intact(text, files) is False, f"зерно {seed}: {defect}"


# --------------------------------------------------------------- AC-6


def write_tree(root: Path, rng) -> dict:
    content = {}
    for _ in range(rng.randint(1, 6)):
        rel = f"{rel_dir(rng)}/{ident(rng)}.cpython-313.pyc"
        data = rng.randbytes(rng.randint(0, 64))
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        content[rel] = data
    (root / "manifest.json").write_text(json.dumps(sorted(content)), encoding="utf-8")
    content["manifest.json"] = (root / "manifest.json").read_bytes()
    return content


def tree_content(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_ac6_publish_renames_staging_when_final_absent(tmp_path):
    """`final` нет — `staging` становится `final`, возврат `True`.

    Во временном месте — `.staging` со случайным деревом файлов. После
    вызова `final` несёт ровно прежнее содержимое `staging`, а `staging`
    исчез.

    Ловит мутацию: публикация копированием без удаления `staging` или
    возврат `False` на успешной ветке — `staging` остаётся либо возврат
    расходится.
    """
    seed, rng = make_rng()
    staging, final = tmp_path / f".{ident(rng)}", tmp_path / ident(rng)
    expected = write_tree(staging, rng)
    assert acceptance.publish_template(str(staging), str(final)) is True, f"зерно {seed}"
    assert tree_content(final) == expected, f"зерно {seed}"
    assert not staging.exists(), f"зерно {seed}"


def test_ac6_publish_keeps_existing_final_and_drops_staging(tmp_path):
    """`final` уже есть — возврат `False`, `final` прежний, `staging` удалён.

    Оба каталога — со случайными разными деревьями (проигравший гонку
    сборщик).

    Ловит мутацию: `os.replace`/`rename` поверх существующего `final` или
    слияние деревьев — содержимое `final` меняется; `staging` не убран —
    временный каталог остаётся в месте шаблонов.
    """
    seed, rng = make_rng()
    staging, final = tmp_path / f".{ident(rng)}", tmp_path / ident(rng)
    write_tree(staging, rng)
    expected = write_tree(final, rng)
    assert acceptance.publish_template(str(staging), str(final)) is False, f"зерно {seed}"
    assert tree_content(final) == expected, f"зерно {seed}"
    assert not staging.exists(), f"зерно {seed}"


# --------------------------------------------------------------- AC-7

RETRY = 3600.0


@pytest.mark.parametrize("owner_delta,mode,present,intact,age,expected", [
    (1, 0o700, True, True, None, "untrusted"),
    (1, 0o700, False, False, None, "untrusted"),
    (0, 0o750, True, True, None, "untrusted"),
    (0, 0o701, True, True, None, "untrusted"),
    (0, 0o755, False, False, None, "untrusted"),
    (0, 0o720, True, False, None, "untrusted"),
    (0, stat.S_IFDIR | 0o707, True, True, None, "untrusted"),
    (0, 0o700, True, True, None, "fill"),
    (0, stat.S_IFDIR | 0o700, True, True, 1.0, "fill"),
    (0, 0o700, True, False, None, "discard"),
    (0, 0o700, True, False, 1.0, "discard"),
    (0, 0o700, False, False, 0.0, "skip"),
    (0, 0o700, False, False, RETRY - 1, "skip"),
    (0, 0o700, False, False, RETRY, "build"),
    (0, 0o700, False, False, RETRY * 5, "build"),
    (0, stat.S_IFDIR | 0o700, False, False, None, "build"),
])
def test_ac7_decision_table(owner_delta, mode, present, intact, age, expected):
    """Решение о шаблоне — по порядку доверие, целость, отметка неудачи.

    Строка таблицы задаёт сдвиг владельца от uid, права (в том числе с
    битами типа каталога, как у `lstat`), наличие и целость шаблона и
    возраст отметки; uid случаен.

    Ловит мутацию: проверка прав перенесена после наличия шаблона (целый
    шаблон в месте 0755 даёт `fill`), граница возраста `<=` вместо `<`
    (возраст ровно `retry_sec` даёт `skip`) или отметка учитывается и при
    стоящем шаблоне — строка таблицы расходится.
    """
    seed, rng = make_rng()
    uid = rng.randint(0, 60000)
    got = acceptance.template_decision(
        owner_uid=uid + owner_delta, mode=mode, uid=uid, present=present,
        intact=intact, failed_age_sec=age, retry_sec=RETRY)
    assert got == expected, f"зерно {seed}: uid {uid}"


def test_ac7_random_trusted_absent_template():
    """Случайные возраст и срок: моложе срока — `skip`, иначе `build`.

    Ловит мутацию: сравнение возраста с константой вместо `retry_sec`
    либо перевёрнутое условие — случайная пара даёт другой исход.
    """
    seed, rng = make_rng()
    for _ in range(50):
        uid = rng.randint(0, 60000)
        retry = rng.uniform(1, 10000)
        age = rng.choice([None, rng.uniform(0, retry * 2)])
        expected = "skip" if age is not None and age < retry else "build"
        got = acceptance.template_decision(
            owner_uid=uid, mode=0o700, uid=uid, present=False, intact=False,
            failed_age_sec=age, retry_sec=retry)
        assert got == expected, f"зерно {seed}: age {age}, retry {retry}"


# --------------------------------------------------------------- AC-8


@pytest.mark.parametrize("command", [
    ["python"], ["python3"], ["python3.13", "-m", "pytest"], ["python3.9"],
    ["/usr/bin/python3", "-m", "pytest"], [".venv/bin/python"],
    ["./env/bin/python3.12", "-m", "pytest", "-q"],
])
def test_ac8_python_names_are_recognized_as_is(command):
    """Базовое имя `python`, `python3`, `python3.<N>` — возвращается сам элемент.

    Ловит мутацию: возвращается разрешённый путь или базовое имя вместо
    элемента как есть, либо распознаётся только голое имя без каталога —
    результат расходится с `command[0]`.
    """
    assert acceptance.command_interpreter(list(command)) == command[0]


@pytest.mark.parametrize("command", [
    [], ["uv", "run", "pytest"], ["./run-tests.sh"], ["pytest"],
    ["/usr/bin/pytest", "-q"], ["python2"], ["python3-config"],
    ["pythonista"], ["bin/python3.x"],
])
def test_ac8_other_commands_are_unknown(command):
    """Обёртка, `uv`, `pytest`, иные имена и пустая команда — `None`.

    Ловит мутацию: распознавание по подстроке `python` в имени
    (`python3-config`, `pythonista`) или падение на пустой команде вместо
    `None`.
    """
    assert acceptance.command_interpreter(list(command)) is None
