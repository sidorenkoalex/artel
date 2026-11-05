"""Отчёт JUnit: прежний разбор пути и имени теста сохранён.

Отчёт xunit1 (атрибут `file`) файла в скрытом каталоге даёт путь из
`file`; `classname` без пустых частей (точечный путь модуля с классом
теста, путь через `/`) разбирают `parse_junit` и `parse_forge_report` как
до задачи. Скрытое имя каталога и id — случайные; зерно печатается и
входит в текст провала.

Группа: долгоживущий
Зелёный с рождения: разбор с атрибутом `file` и `classname` без пустых частей до задачи уже верен — тест держит его неизменным
"""
import os
import random
import signal
import string
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from orchestrator import project_profile
from orchestrator.reporters import outcome

SEED = random.randrange(1 << 30)
CHILD_TIMEOUT_SEC = 60
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TEST_TEXT = ("def test_ok():\n    pass\n\n\n"
             "class TestK:\n    def test_in_class(self):\n        pass\n")
CLASS_NAME = "TestK::test_in_class"


def rng_for(*salt) -> random.Random:
    print(f"зерно: {SEED}")
    return random.Random(f"{SEED}:{':'.join(map(str, salt))}")


def hidden_name(kind: str, rng: random.Random) -> str:
    if kind != "random":
        return kind
    return "." + "".join(rng.choice(string.ascii_lowercase) for _ in range(6))


def task_id(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def sandbox(tmp_path: Path, rel: str) -> Path:
    """Корень песочницы (через `resolve()`) с одним файлом теста `rel`."""
    root = (tmp_path / "sb").resolve()
    path = root / rel
    path.parent.mkdir(parents=True)
    path.write_text(TEST_TEXT, encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return root


def run_pytest(root: Path, rel: str, family: str) -> Path:
    """Отчёт настоящего pytest по файлу `rel` песочницы `root`: свой
    предел времени, своя группа процессов, пустой `PYTEST_ADDOPTS`."""
    report = root.parent / f"report-{family}.xml"
    cmd = [sys.executable, "-m", "pytest", rel, "-q", "-p", "no:cacheprovider",
           "-c", str(root / "pytest.ini"), f"--rootdir={root}",
           f"--junitxml={report}", "-o", f"junit_family={family}"]
    env = dict(os.environ, PYTEST_ADDOPTS="", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    proc = subprocess.Popen(cmd, cwd=root, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=CHILD_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        pytest.fail(f"дочерний pytest не уложился в {CHILD_TIMEOUT_SEC} с")
    print(out)
    return report


def report_classname(report: Path, name: str) -> str:
    for case in ElementTree.parse(report).getroot().iter("testcase"):
        if case.get("name") == name:
            return case.get("classname") or ""
    return ""


def junit_locations(report: Path, root: Path) -> dict:
    """{имя теста отчёта: (путь, полное имя)} записей `parse_junit`."""
    records, reason = outcome.parse_junit(report, "c", "", root)
    assert records is not None, reason
    found = {}
    for record in records:
        _c, path, full, _n = project_profile.parse_test_id(record.id)
        found[full.rsplit("::", 1)[-1]] = (path, full)
    return found


def tree_files(root: Path) -> set:
    return {os.path.relpath(Path(d) / f, root).replace(os.sep, "/")
            for d, _dirs, files in os.walk(root) for f in files}


def forge_location(classname: str, name: str, root: Path):
    """(путь, полное имя) записи `parse_forge_report` по ключу
    `<classname>::<name>`; `None` — ключ не разобран."""
    records, unresolved = outcome.parse_forge_report(
        {f"{classname}::{name}": "success"}, "c", "", tree_files(root))
    if unresolved or not records:
        return None
    _c, path, full, _n = project_profile.parse_test_id(records[0].id)
    return path, full


@pytest.mark.parametrize("kind", [".artel-plank", "random"])
def test_ac5_xunit1_file_attribute_gives_path(kind, tmp_path):
    """Отчёт xunit1 файла `tests/<H>/<id>/test_x.py` с атрибутом `file`.

    Настоящий pytest пишет отчёт `junit_family=xunit1`; `parse_junit`
    берёт путь из `file`: `tests/<H>/<id>/test_x.py` для `test_ok` и для
    теста класса, имена `test_ok` и `TestK::test_in_class`.

    Ловит мутацию: новый разбор `classname` применён и при наличии
    `file` либо класс отрезается неверно — имя теста класса становится
    `<id>::test_x::TestK::…` или путь перестаёт совпадать с `file`.
    Зелёный с рождения: путь из атрибута `file` до задачи уже верен.
    """
    rng = rng_for("ac5-xunit1", kind)
    rel = f"tests/{hidden_name(kind, rng)}/{task_id(rng)}/test_x.py"
    root = sandbox(tmp_path, rel)
    found = junit_locations(run_pytest(root, rel, "xunit1"), root)
    assert found.get("test_ok") == (rel, "test_ok"), f"зерно {SEED}"
    assert found.get("test_in_class") == (rel, CLASS_NAME), f"зерно {SEED}"


def test_ac5_dotted_classname_without_empty_parts(tmp_path):
    """`classname` `tests.test_m.TestK` настоящего отчёта xunit2.

    Файл `tests/test_m.py`; `parse_junit` и `parse_forge_report` дают
    путь `tests/test_m.py`, имена `test_ok` и `TestK::test_in_class`.

    Ловит мутацию: новое правило склеивает точку и с непустой частью
    (или обрезает класс) — путь `tests/test_m/TestK.py` не найден, имя
    без класса или запись не разобрана.
    Зелёный с рождения: точечный путь без пустых частей до задачи уже
    разбирался верно.
    """
    print(f"зерно: {SEED}")
    rel = "tests/test_m.py"
    root = sandbox(tmp_path, rel)
    report = run_pytest(root, rel, "xunit2")
    found = junit_locations(report, root)
    assert found.get("test_ok") == (rel, "test_ok")
    assert found.get("test_in_class") == (rel, CLASS_NAME)
    classname = report_classname(report, "test_in_class")
    assert classname == "tests.test_m.TestK"
    assert forge_location(classname, "test_in_class", root) == (rel, CLASS_NAME)
    assert forge_location(report_classname(report, "test_ok"), "test_ok",
                          root) == (rel, "test_ok")


@pytest.mark.parametrize("kind", [".artel-plank", "random"])
def test_ac5_slash_classname_kept_as_path(kind, tmp_path):
    """`classname` с путём через `/` — путь записи как есть.

    Запись отчёта JUnit без `file` с `classname` `tests/<H>/<id>/test_x.py`
    и ключ CI `tests/<H>/<id>/test_x.py::test_ok`: путь — сам `classname`,
    имя — `test_ok`.

    Ловит мутацию: новое правило разбора точек применено и к `classname`
    с `/` — путь превращается в `tests/<H>/<id>/test_x/py.py` или ключ
    уходит в неразобранные.
    Зелёный с рождения: ветка `/` в `classname` до задачи уже верна.
    """
    rng = rng_for("ac5-slash", kind)
    rel = f"tests/{hidden_name(kind, rng)}/{task_id(rng)}/test_x.py"
    root = sandbox(tmp_path, rel)
    report = tmp_path / "slash.xml"
    report.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuites>'
        f'<testsuite name="pytest"><testcase classname="{rel}" '
        'name="test_ok" time="0.01"/></testsuite></testsuites>',
        encoding="utf-8")
    assert junit_locations(report, root).get("test_ok") == \
        (rel, "test_ok"), f"зерно {SEED}"
    assert forge_location(rel, "test_ok", root) == (rel, "test_ok"), \
        f"зерно {SEED}"
