"""Строка `doctor` `target-failure-errors`: компоненты в границе отчёта без `failure_errors` — одна строка на все проекты сразу после строк проектов.

Группа: долгоживущий
Красен до реализации: среди строк `doctor.all_checks` нет строки `target-failure-errors`, а команды `target-set`, которой тест ставит поле, в диспетчере нет.

Связка, которую держит файл: «локальный слой под корнем песочницы —
`targets.load`/`project_profile.component_profiles` — `doctor.all_checks`
— команда `target-set` диспетчера `artel.main`». Песочница —
`tests.sandbox.InitializedTmpRootTest` (фикстура `initialized_tmp_root`:
пути `config` во временном каталоге, БД со схемой); строки `doctor` —
публичный `doctor.all_checks(conn)`, строка ищется по имени. Прочие
проверки `doctor` зовут CLI ролей, `gh` и сетевой git — им отвечает отказ
запуска (приём `tests/test_01m5scgsqn0at0b07h7m9803ra_doctor_layer.py`).
Файл локального слоя — `config.TARGETS.parent / ".artel" / "targets.yaml"`.
Строки проекта `<имя>` узнаются по имени строки `project-support-<имя>`,
которой открывается блок строк проекта, и по вхождению имени проекта в
имя строки. Имена проектов и компонентов — от зерна `random`; зерно
печатается и входит в текст провала.
"""
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, config, doctor, store
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
CHECK = "target-failure-errors"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
HINT = "target-set {name} description.components.{comp}.failure_errors '[AssertionError]'"


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


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value, random.Random(value)


def word(rng, size: int = 6) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(size))


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def component_record(name: str, comps: dict) -> str:
    """Запись в трёх разделах; `comps` — имя компонента → (есть ли `report`, `failure_errors` или None)."""
    lines = [f"  {name}:", "    description:", "      base: main",
             "      components:"]
    for comp, (reported, errors) in comps.items():
        lines += [f"        {comp}:", "          runner: pytest-own",
                  "          command: [python3, -m, pytest]"]
        if reported:
            lines.append("          report: junit-xml")
        if errors is not None:
            lines.append(f"          failure_errors: [{', '.join(errors)}]")
        lines.append(f"          paths: ^{comp}/")
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: operator", "    machine:", "      forge: github",
              f"      url: https://localhost/team/{name}",
              f"      token_slot: {name}-token"]
    return "\n".join(lines) + "\n"


def profile_record(name: str) -> str:
    """Запись с `test_profile` собственного раннера с `report` и без `failure_errors`."""
    return (f"  {name}:\n"
            f"    description:\n      base: main\n"
            f"      test_profile:\n        runner: pytest-own\n"
            f"        command: [python3, -m, pytest]\n"
            f"        report: junit-xml\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


def write_layers(local_text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_text, encoding="utf-8")


def run_cli(*argv) -> tuple:
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *argv]):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code
    return code in (0, None), code


def doctor_lines() -> tuple:
    checks = doctor.all_checks(store.db())
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    return checks, shown


def the_line(checks, shown, value):
    found = [c for c in checks if c.name == CHECK]
    assert len(found) == 1, f"зерно: {value}; строк {CHECK}: {len(found)}\n{shown}"
    return found[0]


def assert_after_project_lines(checks, shown, value, names) -> None:
    """Строка стоит после начала блока каждого проекта `names`, и ни одна строка с именем проекта не идёт после неё."""
    index = [c.name for c in checks].index(CHECK)
    opened = [i for i, c in enumerate(checks)
              if c.name in {f"project-support-{n}" for n in names}]
    assert len(opened) == len(names), f"зерно: {value}\n{shown}"
    assert max(opened) < index, f"зерно: {value}\n{shown}"
    later = [c.name for i, c in enumerate(checks)
             if i > index and any(n in c.name for n in names)]
    assert not later, f"зерно: {value}; {later}\n{shown}"


def test_ac8_warn_then_ok_after_target_set(pult, seed, capsys):
    """Два компонента в границе отчёта без `failure_errors` — одна строка `warn` с подсказкой на каждый; после `target-set` обоих полей — `ok`.

    Сценарий: локальный слой — запись проекта (имя от зерна) с тремя
    компонентами: двое с `report: junit-xml` без `failure_errors`, третий
    без `report` и без `failure_errors`; плюс запись с `test_profile`,
    у которого `report` задан. В `all_checks` ровно одна строка
    `target-failure-errors`: `warn`, текст несёт подсказку
    `target-set <проект> description.components.<к>.failure_errors
    '[AssertionError]'` для обоих компонентов с `report`, не называет
    компонент без `report` и запись с `test_profile`; строка стоит сразу
    после строк проектов. После `target-set` поля `failure_errors` у
    обоих компонентов строка — `ok`.

    Ловит мутацию: строка по проекту вместо одной общей; в перечень входят
    компоненты вне границы отчёта (без `report`) или запись `test_profile`;
    назван только первый компонент; подсказка без кавычек вокруг
    значения; поле, поставленное `target-set`, не видно строке (читает не
    тот слой); строка добавлена не за циклом проектов.
    """
    value, rng = seed
    name, plain = "p" + word(rng), "q" + word(rng)
    comps = ["a" + word(rng), "b" + word(rng), "c" + word(rng)]
    rng.shuffle(comps)
    first, second, silent = comps
    record = component_record(name, {first: (True, None), second: (True, None),
                                     silent: (False, None)})
    write_layers("targets:\n" + record + profile_record(plain))
    checks, shown = doctor_lines()
    line = the_line(checks, shown, value)
    assert line.status == "warn", f"зерно: {value}\n{shown}"
    for comp in (first, second):
        assert HINT.format(name=name, comp=comp) in line.detail, f"зерно: {value}; {line}"
    assert f"components.{silent}." not in line.detail, f"зерно: {value}; {line}"
    assert plain not in line.detail, f"зерно: {value}; {line}"
    assert_after_project_lines(checks, shown, value, [name, plain])
    for comp in (first, second):
        ok, code = run_cli("target-set", name,
                           f"description.components.{comp}.failure_errors",
                           "[AssertionError]")
        assert ok, f"зерно: {value}; код {code}; {capsys.readouterr()}"
    checks, shown = doctor_lines()
    line = the_line(checks, shown, value)
    assert line.status == "ok", f"зерно: {value}\n{shown}"


def test_ac8_two_projects_one_line(pult, seed):
    """Компоненты без `failure_errors` в двух проектах — одна строка на все проекты, оба названы.

    Сценарий: две записи с компонентами (имена от зерна), у каждой по
    одному компоненту с `report` без `failure_errors` и по одному с
    заданным `failure_errors`. Строка `target-failure-errors` одна,
    `warn`, несёт подсказки для обоих проектов и не называет компоненты с
    заданным полем.

    Ловит мутацию: строка по проекту (две строки) или перечень только
    последнего проекта; компонент с непустым `failure_errors` тоже в
    перечне.
    """
    value, rng = seed
    names = ["p" + word(rng), "q" + word(rng)]
    bare = {n: "a" + word(rng) for n in names}
    done = {n: "d" + word(rng) for n in names}
    text = "targets:\n" + "".join(
        component_record(n, {bare[n]: (True, None),
                             done[n]: (True, ["AssertionError"])}) for n in names)
    write_layers(text)
    checks, shown = doctor_lines()
    line = the_line(checks, shown, value)
    assert line.status == "warn", f"зерно: {value}\n{shown}"
    for n in names:
        assert HINT.format(name=n, comp=bare[n]) in line.detail, f"зерно: {value}; {line}"
        assert f"components.{done[n]}." not in line.detail, f"зерно: {value}; {line}"
    # Записи одной формы дают блоки строк одной длины: строка стоит ровно
    # через длину блока после начала блока последнего проекта.
    first_block, last_block = sorted(
        i for i, c in enumerate(checks)
        if c.name in {f"project-support-{n}" for n in names})
    index = [c.name for c in checks].index(CHECK)
    assert index == last_block + (last_block - first_block), f"зерно: {value}\n{shown}"


@pytest.mark.parametrize("case", ["test_profile с report", "компонент без report"])
def test_ac8_out_of_bounds_gives_no_warn(pult, seed, case):
    """Запись с `test_profile` и `report` либо компонент без `report` с пустым `failure_errors` — строка `ok`, не `warn`.

    Сценарий: единственная внешняя запись — `test_profile` собственного
    раннера с `report` без `failure_errors` либо запись с компонентом без
    `report` и без `failure_errors` (и вторым компонентом с заданным
    полем). Строка `target-failure-errors` одна и в статусе `ok`.

    Ловит мутацию: граница отчёта считается по `report` без признака
    компонента (`test_profile` даёт `warn`) или не считается вовсе
    (компонент без `report` даёт `warn`).
    """
    value, rng = seed
    name = "p" + word(rng)
    if case == "test_profile с report":
        record = profile_record(name)
    else:
        record = component_record(name, {"a" + word(rng): (False, None),
                                         "d" + word(rng): (True, ["AssertionError"])})
    write_layers("targets:\n" + record)
    checks, shown = doctor_lines()
    line = the_line(checks, shown, value)
    assert line.status == "ok", f"зерно: {value}\n{shown}"


def test_ac8_broken_local_layer_skip(pult, seed):
    """Незагружаемый локальный слой — строка `target-failure-errors` в `all_checks` есть, статус `skip` с причиной.

    Сценарий: слой репозитория годен, `.artel/targets.yaml` с табуляцией в
    отступе (строки проектов из-за этого не выводятся). Строка одна,
    `skip`, текст причины непустой.

    Ловит мутацию: строка добавлена в ветку `else` успешного
    `targets.load()` — при сломанном слое её нет; сбой загрузки роняет
    `all_checks` или даёт `ok`.
    """
    value, rng = seed
    write_layers(f"targets:\n\tp{word(rng)}:\n")
    checks, shown = doctor_lines()
    line = the_line(checks, shown, value)
    assert line.status == "skip", f"зерно: {value}\n{shown}"
    assert line.detail.strip(), f"зерно: {value}\n{shown}"
