"""Отчёт JUnit: путь теста в каталоге, имя которого начинается с точки.

pytest в формате xunit2 не пишет атрибут `file`, и путь теста
восстанавливается из `classname`; у каталога с точкой в начале имени в
`classname` появляются пустые части (`tests..<H>.<id>.test_x`). Каждая
пустая часть добавляет одну точку к началу следующей непустой части — так
разбор `parse_junit` (отчёт настоящего pytest во временной песочнице) и
`parse_forge_report` (отчёт задания CI с тем же `classname`) находят файл.

Имя скрытого каталога `<H>` — литерал `.artel-plank` и случайное
`.<6 букв>`; зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: разбор делит classname по каждой точке, пустая часть теряет точку — xunit2 даёт путём всё точечное имя, forge — модуль не найден
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

from orchestrator import config, project_profile
from orchestrator.advance_gates import acceptance as gate
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
    """Имя скрытого каталога: литерал как есть, `random` — `.<6 букв>`,
    `random2` — `..<6 букв>`."""
    if kind not in ("random", "random2"):
        return kind
    word = "".join(rng.choice(string.ascii_lowercase) for _ in range(6))
    return ("." if kind == "random" else "..") + word


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


def run_pytest(root: Path, rel: str, family: str = "xunit2") -> Path:
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


def junit_locations(report: Path, root: Path, comp: str) -> dict:
    """{имя теста отчёта: (путь, полное имя)} записей `parse_junit`."""
    records, reason = outcome.parse_junit(report, comp, "", root)
    assert records is not None, reason
    found = {}
    for record in records:
        _c, path, full, _n = project_profile.parse_test_id(record.id)
        found[full.rsplit("::", 1)[-1]] = (path, full)
    return found


def tree_files(root: Path) -> set:
    return {os.path.relpath(Path(d) / f, root).replace(os.sep, "/")
            for d, _dirs, files in os.walk(root) for f in files}


def forge_location(classname: str, name: str, root: Path, comp: str):
    """(путь, полное имя) записи `parse_forge_report` по ключу
    `<classname>::<name>`; `None` — ключ не разобран."""
    records, unresolved = outcome.parse_forge_report(
        {f"{classname}::{name}": "success"}, comp, "", tree_files(root))
    if unresolved or not records:
        return None
    _c, path, full, _n = project_profile.parse_test_id(records[0].id)
    return path, full


ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    components:
      {comp}:
        command: [pytest]
        report: junit-xml
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        plank_layout: {layout}
        weakening_scope: [tests/**]
        mutation_claim_scope: [tests/**]
"""


@pytest.mark.parametrize("kind", [".artel-plank", "random"])
def test_ac1_junit_xunit2_record_matched_to_plank_file(kind, tmp_root, tmp_path):
    """Запись настоящего отчёта xunit2 для `tests/<H>/<id>/test_x.py`.

    Песочница пульта: внешний проект с компонентом `junit-xml` и
    `plank_layout: tests/<H>/<id>` в `targets.yaml`; файл планки
    `test_x.py` в каталоге документов и тот же файл в выкладке песочницы
    кода; дочерний pytest (xunit2, без `file`) пишет отчёт, `parse_junit`
    его разбирает. Запись получает путь `tests/<H>/<id>/test_x.py` и имя
    `test_ok`, а `file_records` гейта FAIL_TO_PASS относит к файлу планки
    именно эту разобранную запись.

    Ловит мутацию: `_junit_location` делит `classname` по каждой точке
    (`split(".")`) — путь записи становится всем точечным именем
    `tests..<H>.<id>.test_x`, у файла планки в `file_records` записей нет.
    Ловит мутацию: склейка жёстко заданной строки `.artel-plank` — на
    случайном имени `.<6 букв>` путь записи снова всё точечное имя.
    """
    rng = rng_for("ac1", kind)
    hidden, tid = hidden_name(kind, rng), task_id(rng)
    name = "j" + "".join(rng.choice(string.ascii_lowercase) for _ in range(6))
    comp = "c" + "".join(rng.choice(string.ascii_lowercase) for _ in range(6))
    layout = f"tests/{hidden}/<id>"
    # `tmp_root` подменил `config.TARGETS` временным файлом песочницы.
    old = config.TARGETS.read_text(encoding="utf-8")
    config.TARGETS.write_text(old.rstrip("\n") + "\n" + ENTRY.format(
        name=name, comp=comp, layout=layout), encoding="utf-8")
    profiles = project_profile.component_profiles(name)
    assert [p.plank_layout for p in profiles] == [layout], f"зерно {SEED}"

    rel = f"tests/{hidden}/{tid}/test_x.py"
    root = sandbox(tmp_path, rel)
    tdir = tmp_path / "docs"
    (tdir / "acceptance_tests").mkdir(parents=True)
    (tdir / "acceptance_tests" / "test_x.py").write_text(TEST_TEXT,
                                                         encoding="utf-8")
    report = run_pytest(root, rel)
    records, reason = outcome.parse_junit(report, comp, "", root)
    assert records, f"зерно {SEED}: {reason}"
    ok = [r for r in records
          if project_profile.parse_test_id(r.id)[2] == "test_ok"]
    assert len(ok) == 1, f"зерно {SEED}: {[r.id for r in records]}"
    _c, path, full, _n = project_profile.parse_test_id(ok[0].id)
    assert (path, full) == (rel, "test_ok"), f"зерно {SEED}"

    files = gate.criterion_files(tid, tdir, root,
                                 project_profile.plank_rule(name), profiles,
                                 [], name)
    plank = [f for f in files if f.name == "test_x.py"]
    assert len(plank) == 1, f"зерно {SEED}: {files}"
    matched = gate.file_records(files, {comp: records})[plank[0]]
    assert ok[0] in matched, f"зерно {SEED}: {plank[0].rel} — {matched}"


@pytest.mark.parametrize("kind", [".artel-plank", "random"])
def test_ac2_forge_record_with_hidden_dir_found_in_tree(kind, tmp_path):
    """Запись отчёта задания CI с `classname` настоящего отчёта.

    Песочница с файлом `tests/<H>/<id>/test_x.py`; `classname` теста
    `test_ok` взят из отчёта настоящего pytest (xunit2), ключ
    `<classname>::test_ok` разобран `parse_forge_report` при дереве
    файлов песочницы: путь `tests/<H>/<id>/test_x.py`, имя `test_ok`.

    Ловит мутацию: `_forge_location` делит `classname` по каждой точке —
    кандидат `tests//<H без точки>/…` в дереве не найден, ключ уходит в
    неразобранные, записи нет.
    """
    rng = rng_for("ac2", kind)
    hidden, tid = hidden_name(kind, rng), task_id(rng)
    rel = f"tests/{hidden}/{tid}/test_x.py"
    root = sandbox(tmp_path, rel)
    classname = report_classname(run_pytest(root, rel), "test_ok")
    assert classname, f"зерно {SEED}"
    assert forge_location(classname, "test_ok", root, "c") == \
        (rel, "test_ok"), f"зерно {SEED}: {classname}"


@pytest.mark.parametrize("kind", [".artel-plank", "random"])
def test_ac3_classname_starting_with_dot_in_root(kind, tmp_path):
    """Файл `<H>/<id>/test_x.py` в корне песочницы: `classname` с точки.

    Отчёт настоящего pytest (xunit2) разобран `parse_junit`, его
    `classname` — `parse_forge_report`; оба дают путь `<H>/<id>/test_x.py`
    и имя `test_ok`.

    Ловит мутацию: пустая часть учитывается только в середине
    `classname` (`..`), а ведущая точка отбрасывается — путь записи
    `parse_junit` всё точечное имя, ключ CI не разобран.
    """
    rng = rng_for("ac3", kind)
    hidden, tid = hidden_name(kind, rng), task_id(rng)
    rel = f"{hidden}/{tid}/test_x.py"
    root = sandbox(tmp_path, rel)
    report = run_pytest(root, rel)
    assert junit_locations(report, root, "c").get("test_ok") == \
        (rel, "test_ok"), f"зерно {SEED}"
    classname = report_classname(report, "test_ok")
    assert forge_location(classname, "test_ok", root, "c") == \
        (rel, "test_ok"), f"зерно {SEED}: {classname}"


@pytest.mark.parametrize("kind", [".artel-plank", "random"])
def test_ac4_class_test_in_hidden_dir(kind, tmp_path):
    """Тест класса `TestK` файла `tests/<H>/<id>/test_x.py`.

    `classname` настоящего отчёта — `tests..<H>.<id>.test_x.TestK`;
    `parse_junit` и `parse_forge_report` дают путь
    `tests/<H>/<id>/test_x.py` и имя `TestK::test_in_class`.

    Ловит мутацию: найденный модуль отрезается от `classname` по числу
    частей без учёта склеенной точки — класс теряется или в имя попадает
    остаток пути (`<id>::test_x::TestK::…`) вместо `TestK::test_in_class`.
    """
    rng = rng_for("ac4", kind)
    hidden, tid = hidden_name(kind, rng), task_id(rng)
    rel = f"tests/{hidden}/{tid}/test_x.py"
    root = sandbox(tmp_path, rel)
    report = run_pytest(root, rel)
    assert junit_locations(report, root, "c").get("test_in_class") == \
        (rel, CLASS_NAME), f"зерно {SEED}"
    classname = report_classname(report, "test_in_class")
    assert classname.endswith(".TestK"), f"зерно {SEED}: {classname}"
    assert forge_location(classname, "test_in_class", root, "c") == \
        (rel, CLASS_NAME), f"зерно {SEED}: {classname}"


@pytest.mark.parametrize("kind", ["..x", "random2"])
@pytest.mark.parametrize("nested", [True, False])
def test_ac6_dir_name_with_two_leading_dots(kind, nested, tmp_path):
    """Каталог `..x` (две точки в начале): каждая пустая часть — одна точка.

    Файл `tests/..x/<id>/test_y.py` (`classname` `tests...x.<id>.test_y`)
    и, в отдельной песочнице, `..x/<id>/test_y.py` (`..x.<id>.test_y`);
    второе имя — `..<6 букв>`. Отчёт настоящего pytest разобран
    `parse_junit`, его `classname` — `parse_forge_report`: путь с
    каталогом ровно из двух точек, имя `test_ok` и `TestK::test_in_class`.

    Ловит мутацию: склейка только одной точки к следующей части — путь
    `tests/.x/…`, файла нет, запись `parse_junit` с путём всего точечного
    имени, ключ CI не разобран.
    """
    rng = rng_for("ac6", kind, nested)
    hidden, tid = hidden_name(kind, rng), task_id(rng)
    rel = f"{'tests/' if nested else ''}{hidden}/{tid}/test_y.py"
    root = sandbox(tmp_path, rel)
    report = run_pytest(root, rel)
    found = junit_locations(report, root, "c")
    assert found.get("test_ok") == (rel, "test_ok"), f"зерно {SEED}"
    assert found.get("test_in_class") == (rel, CLASS_NAME), f"зерно {SEED}"
    for name, full in (("test_ok", "test_ok"), ("test_in_class", CLASS_NAME)):
        classname = report_classname(report, name)
        assert forge_location(classname, name, root, "c") == (rel, full), \
            f"зерно {SEED}: {classname}"
