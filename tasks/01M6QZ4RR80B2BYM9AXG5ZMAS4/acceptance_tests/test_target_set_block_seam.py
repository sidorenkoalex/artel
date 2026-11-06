"""Сверка формы `target-set … --from-file` через шов сборки `projects._render` (AC-10) и неизменность существующих тестов `target-set`/справки (AC-8).

Группа: разовый
Красен до реализации: формы `--from-file` у `target-set` нет — команда отказывает прежней проверкой («значение — ровно один аргумент») ещё до сборки текста, подменённая сборка не вызывается, проверка «подмена сработала» краснеет; тест неизменности существующих тестов (AC-8) зелен с рождения — он держит, что задача их не правит и они проходят.

Почему файл разовый: AC-10 называет шов подмены — закрытое имя
`projects._render` (`unittest.mock.patch`), а долгоживущему файлу `tests/`
подмена закрытых имён `orchestrator` запрещена; неизменность существующих
файлов `tests/` — факт этой задачи (дифф ветки от её базы, помощник пульта
`_pult.changed_paths`).

Песочница — `initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`):
пути `config` во временном каталоге, БД со схемой; настоящий локальный
слой не читается и не пишется. Команда — `artel.main()` с подменённым
`sys.argv`; файл блока — в подкаталоге `work/blocks` песочницы, текущий
каталог на время теста — `work` (возврат в `finally`).

Подмена сборки меняет только вызов сборки всего слоя — `_render` с
отступом 0, пустым префиксом и отображением с ключом `targets`; прочие
вызовы (рекурсивные, пробные `_render({key: None}, 0, "")`) идут к исходной
функции без изменений; вывод без правимой строки подмена не меняет.
Имена проектов — от зерна `random`; зерно печатается и входит в текст
провала.
"""
import os
import random
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

from orchestrator import artel, config, projects  # noqa: E402
from tests.sandbox import artel_target_entry  # noqa: E402

LETTERS = "abcdefghijkmnopqrstuvwxyz"
PROFILE = "description.test_profile"
EXISTING_TESTS = (
    "tests/test_projects_target_set.py",
    "tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py",
    "tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py",
    "tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py",
)
ORIGINAL_RENDER = projects._render


class Seed:
    """Зерно сценария: печатается и входит в текст провала."""

    def __init__(self):
        self.value = random.randrange(1 << 30)
        print(f"зерно: {self.value}")
        self.rng = random.Random(self.value)

    def msg(self, text) -> str:
        return f"зерно: {self.value}; {text}"

    def name(self) -> str:
        return "p" + "".join(self.rng.choice(LETTERS) for _ in range(6))


@pytest.fixture
def seed():
    return Seed()


@pytest.fixture
def cli(initialized_tmp_root, capsys):
    """Песочница путей `config` с БД пульта и вызов команды как из командной строки."""

    def run(*argv) -> tuple:
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        out = capsys.readouterr()
        return (code in (0, None)), "\n".join(str(p) for p in (code, out.out, out.err))

    return run


@pytest.fixture
def work_dir(initialized_tmp_root):
    """Текущий каталог процесса — подкаталог `work` песочницы с `blocks/`; прежний каталог возвращается."""
    work = initialized_tmp_root.root / "work"
    (work / "blocks").mkdir(parents=True)
    previous = os.getcwd()
    os.chdir(work)
    try:
        yield work
    finally:
        os.chdir(previous)


# ------------------------------------------------------------ слой

def local_file() -> Path:
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def copies() -> list:
    if not config.LOGS.is_dir():
        return []
    return sorted(config.LOGS.glob("targets-*.yaml"))


def sections(name: str, scopes: bool) -> str:
    """`policy` (с необязательным листом `sandbox: s1`) и `machine` в форме пересборки."""
    return (f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n      sandbox: s1\n"
            + (f"      weakening_scope: [tests/**/*.py]\n"
               f"      mutation_claim_scope: [tests/test_*.py]\n" if scopes else "")
            + f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


def profile_record(name: str) -> str:
    return (f"  {name}:\n    description:\n      base: main\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"        runner: pytest-own\n"
            f"        env:\n          LANG: C\n          TZ: UTC\n"
            + sections(name, True))


def components_record(name: str, comps: list) -> str:
    body = "".join(f"        {comp}:\n          command: [python3, -m, pytest]\n"
                   f"          runner: pytest-own\n          paths: [^{comp}/]\n"
                   f"          env:\n            LANG: C\n" for comp in comps)
    return (f"  {name}:\n    description:\n      base: main\n      components:\n"
            + body + sections(name, False))


COMPOSE_BLOCK = ("runner: compose\ncompose_file: deploy/compose.yaml\n"
                 "compose_service: tests\ncompose_env_file: deploy/test.env\n"
                 "compose_env_template: deploy/test.env.example\n"
                 'compose_mount: "src:/work"\nworkdir: src\n'
                 "long_lived_dir: src/tests\n"
                 "long_lived_name: test_<id>_<name>.py\nreport: junit-xml\n")
APP_BLOCK = ("command: [python3, -m, pytest, -q]\nrunner: pytest-own\n"
             "paths: [^app/]\nenv:\n  LANG: C.UTF-8\n")


def write_layers(local_text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_text, encoding="utf-8")


# ------------------------------------------------------------ подмена сборки

def record_span(lines: list, name: str) -> tuple:
    """(начало, конец) строк записи `name` в собранных строках слоя; нет — (0, 0)."""
    head = f"  {name}:"
    if head not in lines:
        return 0, 0
    start = lines.index(head)
    end = start + 1
    while end < len(lines) and not (lines[end].startswith("  ")
                                    and not lines[end].startswith("   ")):
        end += 1
    return start, end


def replace_line(name: str, old: str, new: str | None, *, after: str | None = None):
    """Правка строк записи `name`: строка `old` заменяется `new` (None — снимается); при `after` — `new` вставляется после строки `after`. Строки нет — вывод прежний."""

    def edit(lines: list) -> list:
        start, end = record_span(lines, name)
        span = lines[start:end]
        anchor = after if after is not None else old
        if anchor not in span:
            return lines
        index = start + span.index(anchor)
        if after is not None:
            return lines[:index + 1] + [new] + lines[index + 1:]
        if new is None:
            return lines[:index] + lines[index + 1:]
        return lines[:index] + [new] + lines[index + 1:]

    return edit


def seam(edit, hits: list):
    """Замена `projects._render`: правит только сборку всего слоя; `hits` — сработавшие правки."""

    def fake(mapping, indent, prefix):
        lines = ORIGINAL_RENDER(mapping, indent, prefix)
        if (indent == 0 and prefix == "" and isinstance(mapping, dict)
                and "targets" in mapping):
            edited = edit(list(lines))
            if edited != lines:
                hits.append(True)
            return edited
        return lines

    return fake


# ------------------------------------------------------------ AC-10

CASES = {
    "своя запись: изменён policy.no_paths":
        ("profile", "own", ("      no_paths: []", "      no_paths: [zz]"), "no_paths"),
    "другая запись: изменён policy.merge_gate":
        ("profile", "other", ("      merge_gate: operator", "      merge_gate: target-human"),
         "merge_gate"),
    "своя запись: добавлен policy.branch_template":
        ("profile", "own", ("    policy:", "      branch_template: x", "after"),
         "branch_template"),
    "своя запись: снят policy.sandbox":
        ("profile", "own", ("      sandbox: s1", None), "sandbox"),
    "соседний компонент app2":
        ("components", "own", ("          paths: [^app2/]", "          paths: [^app2x/]"),
         "app2"),
    "блок читается иначе, чем файл":
        ("profile", "own", ("        compose_service: tests",
                            "        compose_service: other"), None),
}


@pytest.mark.parametrize("case", list(CASES))
def test_ac10_block_check_not_only_merge(cli, work_dir, seed, case):
    """Собранный текст, меняющий лист вне пути блока или дающий под путём блока не то значение, — отказ сверки, слой побайтно прежний, копии нет.

    Сценарий: слой — запись `<п>` (профиль `pytest-own` либо компоненты
    `app`, `app2`, `app3`) и другая запись с профилем; годный файл блока
    (`compose` для `description.test_profile`, `pytest-own` для
    `description.components.app`); `projects._render` подменён так, что
    сборка всего слоя (отступ 0, пустой префикс, ключ `targets`) правит одну
    строку: (а) меняет `policy.no_paths` своей записи, меняет
    `policy.merge_gate` другой записи, добавляет `policy.branch_template`
    своей записи, снимает `policy.sandbox` своей записи, меняет `paths`
    соседнего компонента `app2` при пути блока `description.components.app`;
    (б) меняет `compose_service` внутри заменяемого блока. Подмена
    сработала; код выхода ненулевой; в (а) вывод называет правленый лист;
    байты слоя прежние, копий нет.

    Ловит мутацию: сверка только через `_merge_mismatches` (своя запись с
    прежней не сравнивается — лишний, снятый или изменённый лист своей
    записи и не то значение блока проходят); «под путём блока» — строковый
    префикс (`…components.app` покрывает `…components.app2`); сверка не
    сравнивает значение блока с файлом.
    """
    layout, whose, edit_spec, leaf = CASES[case]
    own, other = seed.name(), seed.name()
    if layout == "profile":
        parts = [profile_record(own), profile_record(other)]
        path, block = PROFILE, COMPOSE_BLOCK
    else:
        parts = [components_record(own, ["app", "app2", "app3"]), profile_record(other)]
        path, block = "description.components.app", APP_BLOCK
    seed.rng.shuffle(parts)
    write_layers("targets:\n" + "".join(parts))
    before = local_file().read_bytes()
    (work_dir / "blocks" / "block.yaml").write_text(block, encoding="utf-8")
    name = own if whose == "own" else other
    if len(edit_spec) == 3:
        edit = replace_line(name, None, edit_spec[1], after=edit_spec[0])
    else:
        edit = replace_line(name, edit_spec[0], edit_spec[1])
    hits = []
    with mock.patch.object(projects, "_render", seam(edit, hits)):
        ok, out = cli("target-set", own, path, "--from-file", "./blocks/block.yaml")
    assert hits, seed.msg(("подменённая сборка всего слоя не вызвана", out))
    assert not ok, seed.msg(out)
    if leaf is not None:
        assert leaf in out, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)
    assert copies() == [], seed.msg(out)


# ------------------------------------------------------------ AC-8

def test_ac8_existing_target_set_tests_unedited_and_green():
    """Существующие тесты `target-set` и справки не правлены задачей и проходят.

    Сценарий: пути задачи (`changed_paths()` помощника пульта — дифф ветки
    от базы и неотслеживаемые файлы) не содержат ни одного из четырёх
    файлов AC-8; прогон этих файлов `python3 -m pytest` в корне рабочей
    копии (дочерний процесс в своей группе, с пределом времени) — код
    выхода 0.

    Зелёный с рождения: держит, что новая форма не ломает прежние тесты
    `target-set` и справки и что разработчик не подогнал их правкой.
    """
    touched = sorted(set(changed_paths()) & set(EXISTING_TESTS))
    assert touched == [], touched
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *EXISTING_TESTS],
        cwd=CODE_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=100)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        raise AssertionError(f"прогон существующих тестов не уложился в 100 с:\n{out[-3000:]}")
    assert proc.returncode == 0, out[-3000:]
