"""Команда `targets-migrate <имя>`: перенос записи внешнего проекта в локальный слой, отказы, отказ процессу роли; линт пути к локальному слою.

Группа: долгоживущий
Красен до реализации: команды `targets-migrate` в диспетчере `artel.py` нет — перенос не пишет `.artel/targets.yaml`, а `.artel/targets.yaml` и `config.TARGETS_LOCAL_REL` не внесены в имена живых файлов линта.

Связка, которую держит файл: «диспетчер `artel.main` — команда переноса —
загрузчик `targets.load`» в песочнице `tmp_root` (`tests.sandbox.TmpRootTest`:
`config.TARGETS` — `<tmp>/targets.yaml`, `config.PROJECTS` — под `<tmp>/.artel`,
признак процесса роли снят). Команда зовётся как из командной строки:
`sys.argv` подменён, `artel.main()`. Запись sled — литерал записи пина,
каталоги кэша `uv` в нём — под `config.PROJECTS` песочницы. Файл локального
слоя — `config.TARGETS.parent / ".artel" / "targets.yaml"`. Отказ — выход
`SystemExit` с ненулевым кодом; его текст — код выхода и вывод команды.

Свойства линта — модульные, без песочницы: `orchestrator.test_lint.findings`
над исходником образца. Имена проектов, компонентов, значения и порядок —
от зерна `random`; зерно печатается и входит в текст провала. Отказ под ролью
держит и прежнее поведение (закрытый белый список ролей).
"""
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, targets, test_lint, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NEXT_STEP = ("дальше: убери запись {name} из targets.yaml командой doc-commit, "
             "затем pin-update; до этого действует запись локального слоя")

# Запись sled пина; адрес репозитория — на localhost (в tests/ сетевых
# адресов нет, инвариант 35).
SLED_PIN = """  sled:
    forge: github
    url: https://localhost/sledproject/sled
    base: main
    token_slot: sled-github-token
    no_paths: [.claude/, .codex/, .agents/, CLAUDE.md, AGENTS.md, frontend/.claude/, frontend/CLAUDE.md, .devcontainer/, .github/, CODEOWNERS, .pre-commit-config.yaml, backend/pyproject.toml, backend/uv.lock, backend/.python-version, **/conftest.py, frontend/package.json, frontend/package-lock.json, frontend/vitest.config.js]
    project_skills: []
    merge_gate: operator
    test_profile:
      runner: pytest-own
      workdir: backend
      command: [uv, run, --frozen, pytest, -q]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
      report: junit-xml
      install: []
      full_suite_timeout_sec: 900
      env:
        DEBUG: "true"
        BASE_URL: http://localhost:8000
        CORS_ORIGINS: '["localhost"]'
        JWT__SECRET: test-only-jwt-secret-not-for-production-0123456789
        DB__HOST: 127.0.0.1
        DB__PORT: "1"
        DB__USER: test
        DB__PASSWORD: test
        DB__NAME: sled
        UV_CACHE_DIR: {cache}/uv
        UV_PYTHON_INSTALL_DIR: {cache}/uv-python
        PATH: /opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
"""

# Значения, которые без кавычек разбор прочёл бы иначе: строки окружения
# дописываются в конец блока `env` записи sled (отступ 8).
QUOTED_ENV = (
    '        NOTE: "a: b # c"\n'
    '        FLAG: "true"\n'
    '        NUM: "1"\n'
    '        LEAD: " x"\n'
    '        SQ: "\'single\'"\n'
    "        DQ: 'say \"hi\"'\n"
    '        HASH: "#x"\n'
    '        FLOW: "[x, y]"\n'
    '        EMPTY: ""\n'
)


class Seed:
    """Зерно сценария: печатается и входит в текст провала."""

    def __init__(self):
        self.value = random.randrange(1 << 30)
        print(f"зерно: {self.value}")
        self.rng = random.Random(self.value)

    def msg(self, text) -> str:
        return f"зерно: {self.value}; {text}"

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def name(self) -> str:
        return "p" + self.word()


@pytest.fixture
def seed():
    return Seed()


@pytest.fixture
def cli(tmp_root, capsys):
    """Песочница путей `config` и вызов команды как из командной строки."""

    def run(*argv) -> tuple:
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        out = capsys.readouterr()
        text = "\n".join(str(part) for part in (code, out.out, out.err))
        return (code in (0, None)), text

    return run


# ------------------------------------------------------------ файлы

def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def sled_pin(extra_env: str = "") -> str:
    cache = str(config.PROJECTS / "sled" / "cache")
    return SLED_PIN.replace("{cache}", cache) + extra_env


def write_repo(*entries: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry() + "".join(entries),
                              encoding="utf-8")


def flow(items) -> str:
    return "[" + ", ".join(items) + "]"


def three_section_text(seed: Seed, name: str) -> str:
    """Годная запись в трёх разделах (отступ записи 2)."""
    return (f"  {name}:\n"
            f"    description:\n"
            f"      base: main\n"
            f"      test_profile:\n"
            f"        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"    policy:\n"
            f"      no_paths: [{seed.word()}/]\n"
            f"      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"    machine:\n"
            f"      forge: github\n"
            f"      url: https://localhost/{seed.word()}/{name}\n"
            f"      token_slot: {name}-token\n")


def two_components_text(name: str, comps: list, paths: dict, mode: str) -> str:
    """Запись прежнего вида с двумя компонентами со своими PATH."""
    lines = [f"  {name}:", "    forge: github",
             f"    url: https://localhost/team/{name}", "    base: main",
             f"    token_slot: {name}-token", "    no_paths: [secret/]",
             "    project_skills: []", "    merge_gate: operator",
             "    components:"]
    for i, comp in enumerate(comps):
        lines += [f"      {comp}:", "        runner: pytest-own",
                  "        command: [python3, -m, pytest]",
                  f"        paths: ^{comp}/",
                  f"        weakening_scope: [{comp}/tests/**/*.py]",
                  "        env:"]
        if i == 0:
            lines.append(f"          MODE: {mode}")
        lines.append(f"          PATH: {paths[comp]}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------ AC-12

def test_ac12_sled_pin_migrates_and_loads_same(cli):
    """Перенос записи sled пина: локальный слой написан, `load()` даёт ту же запись sled, вывод называет путь, разделы и следующий шаг.

    Сценарий: слой репозитория — артель и запись sled пина (литерал);
    `targets-migrate sled` завершается успешно; файл `.artel/targets.yaml`
    появился, его запись sled — ровно из разделов `description`, `policy`,
    `machine`. `load()["sled"]` равен записи до переноса — и при записи в
    обоих слоях, и после удаления sled из слоя репозитория (действует
    только локальная). Вывод несёт путь локального слоя, имена трёх
    разделов и строку следующего шага.

    Ловит мутацию: поле теряется при раскладке (запись после удаления из
    репозитория отличается или отказывает), каталог кэша не заменён на
    `<cache>` (отказ абсолютного пути), `env.PATH` не перенесён в
    `machine.path`; вывод без пути или следующего шага.
    """
    write_repo(sled_pin())
    before = targets.load()["sled"]
    ok, text = cli("targets-migrate", "sled")
    assert ok, text
    path = local_file()
    assert path.is_file(), text
    data = yamlmini.mapping(path.read_text(encoding="utf-8"))
    assert set(data["targets"]["sled"]) == {"description", "policy", "machine"}
    assert targets.load()["sled"] == before
    write_repo()
    assert targets.load()["sled"] == before
    assert str(path) in text
    for section in ("description", "policy", "machine"):
        assert section in text, text
    assert NEXT_STEP.format(name="sled") in text


def test_ac12_quoted_values_survive_round_trip(cli, seed):
    """Значения, требующие кавычек (`": "`, `#`, `true`, `1`, кавычки, скобки, пробелы, пустая строка), переживают круг «запись — разбор».

    Сценарий: к окружению записи sled добавлены строки, которые без
    кавычек разбор прочёл бы иначе. После `targets-migrate sled` и
    удаления записи из слоя репозитория `load()["sled"]` равен записи до
    переноса — каждое значение окружения той же строкой.

    Ловит мутацию: строка без кавычек читается другим значением —
    `"true"` становится булевым, `"1"` — числом, хвост после ` #`
    теряется как комментарий, ведущий пробел срезается.
    """
    write_repo(sled_pin(QUOTED_ENV))
    before = targets.load()["sled"]
    ok, text = cli("targets-migrate", "sled")
    assert ok, text
    write_repo()
    after = targets.load()["sled"]
    env_before, env_after = before["test_profile"]["env"], after["test_profile"]["env"]
    for key in seed.rng.sample(sorted(env_before), len(env_before)):
        assert env_after.get(key) == env_before[key], seed.msg(key)
    assert after == before


def test_ac12_two_components_with_different_paths(cli, seed):
    """Запись с двумя компонентами с разными PATH: путь компонента — в `machine.components.<имя>.path`, сведение возвращает прежнюю запись.

    Сценарий: слой репозитория — запись прежнего вида с двумя
    компонентами (имена и порядок от зерна), у каждого свой `env.PATH`,
    у первого ещё `MODE`. После `targets-migrate` в разделе `machine`
    записи есть `components` хотя бы с одним `<имя>.path`, а действующий
    путь каждого компонента (свой или общий `machine.path`) — его прежний
    PATH. После удаления записи из слоя репозитория `load()` даёт прежнюю
    запись, порядок компонентов — прежний.

    Ловит мутацию: разные PATH сведены в один `machine.path` — компонент
    получает чужой путь; порядок компонентов меняется при раскладке.
    """
    name = seed.name()
    comps = [seed.word(), seed.word()]
    while comps[0] == comps[1]:
        comps[1] = seed.word()
    paths = {comps[0]: f"/opt/{seed.word()}/bin:/usr/bin",
             comps[1]: f"/usr/local/{seed.word()}/bin:/bin"}
    write_repo(two_components_text(name, comps, paths, "m" + seed.word()))
    before = targets.load()[name]
    ok, text = cli("targets-migrate", name)
    assert ok, seed.msg(text)
    machine = yamlmini.mapping(local_file().read_text(encoding="utf-8"))[
        "targets"][name]["machine"]
    own = machine.get("components") or {}
    assert any(isinstance(v, dict) and "path" in v for v in own.values()), seed.msg(machine)
    for comp in comps:
        effective = (own.get(comp) or {}).get("path", machine.get("path"))
        assert effective == paths[comp], seed.msg((comp, machine))
    write_repo()
    after = targets.load()[name]
    assert list(after["components"]) == comps, seed.msg(after)
    assert after == before


def test_ac12_existing_layer_kept_verbatim(cli, seed):
    """Прежний локальный слой с комментариями и другой записью сохраняется дословно, новая запись дописана.

    Сценарий: в `.artel/targets.yaml` — комментарий над `targets:`,
    комментарий внутри раздела, годная запись другого проекта в трёх
    разделах и хвостовой комментарий. После `targets-migrate sled` новый
    текст начинается прежним текстом целиком, `load()` даёт прежнюю
    запись другого проекта и sled.

    Ловит мутацию: файл пересобран из разобранного словаря — комментарии
    прежнего файла теряются; новая запись вставлена в начало раздела.
    """
    other = seed.name()
    old = ("# локальный слой пульта " + seed.word() + "\n"
           "targets:\n"
           "  # запись " + seed.word() + "\n"
           + three_section_text(seed, other)
           + "  # хвост " + seed.word() + "\n")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(old, encoding="utf-8")
    write_repo(sled_pin())
    before = targets.load()
    ok, text = cli("targets-migrate", "sled")
    assert ok, seed.msg(text)
    new = path.read_text(encoding="utf-8")
    assert new.startswith(old), seed.msg(new)
    assert "sled:" in new[len(old):], seed.msg(new)
    after = targets.load()
    assert after[other] == before[other]
    assert after["sled"] == before["sled"]


def test_ac12_repeat_refused_file_unchanged(cli):
    """Повторный перенос — отказ «уже есть», файл локального слоя не изменён.

    Сценарий: `targets-migrate sled` успешен; второй вызов той же команды
    завершается ненулевым кодом с «уже есть» в тексте, байты файла —
    прежние.

    Ловит мутацию: проверка «запись уже есть в локальном слое» снята —
    запись дописывается второй раз или файл переписывается.
    """
    write_repo(sled_pin())
    ok, text = cli("targets-migrate", "sled")
    assert ok, text
    snapshot = local_file().read_bytes()
    ok, text = cli("targets-migrate", "sled")
    assert not ok, text
    assert "уже есть" in text
    assert local_file().read_bytes() == snapshot


@pytest.mark.parametrize("case", ["artel", "нет в репозитории"])
def test_ac12_artel_or_missing_refused_no_file(cli, seed, case):
    """`targets-migrate artel` и имя, которого нет в слое репозитория, — отказ, файла локального слоя нет.

    Сценарий: слой репозитория — артель и sled; команда зовётся с именем
    `artel` либо со случайным именем без записи. Код выхода ненулевой,
    текст называет имя, `.artel/targets.yaml` не создан.

    Ловит мутацию: запись артели переносится в локальный слой;
    отсутствующая запись даёт пустую запись или трейсбек вместо отказа.
    """
    write_repo(sled_pin())
    name = config.DEFAULT_TARGET if case == "artel" else seed.name()
    ok, text = cli("targets-migrate", name)
    assert not ok, seed.msg(text)
    assert name in text, seed.msg(text)
    assert not local_file().exists()


@pytest.mark.parametrize("values", [("/var/data",), ("/var/data", "~/logs")])
def test_ac12_foreign_absolute_env_refused(cli, seed, values):
    """Абсолютное значение `env`, не равное каталогу кэша, — отказ со списком полей, файл не пишется.

    Сценарий: к окружению записи sled добавлены одно или два абсолютных
    значения под случайными именами (`/…`, `~/…`). Код выхода ненулевой,
    текст называет каждое такое имя, `.artel/targets.yaml` не создан.

    Ловит мутацию: абсолютное значение переносится в `description` как
    есть и файл пишется; отказ называет только первое поле.
    """
    keys = [f"K{seed.word().upper()}" for _ in values]
    extra = "".join(f"        {key}: {value}\n" for key, value in zip(keys, values))
    write_repo(sled_pin(extra))
    ok, text = cli("targets-migrate", "sled")
    assert not ok, seed.msg(text)
    for key in keys:
        assert key in text, seed.msg(text)
    assert not local_file().exists()


def test_ac12_unrepresentable_value_refused_no_file(cli, seed):
    """Значение, которое после записи разбор прочёл бы иначе, — отказ с именем поля до записи файла.

    Сценарий (решение Оператора на гейте SPEC, пп. 1-2: сведение, теряющее
    поле, проверяется без подмены внутренних функций): у записи sled в
    окружении значение с обоими видами кавычек (`a'b"c` со случайными
    вставками): строка с кавычками пишется в кавычках, а экранирования
    внутри кавычек в подмножестве `yamlmini` нет — ни одна запись не
    вернёт разбором ту же строку. Код выхода ненулевой, текст называет
    имя поля, `.artel/targets.yaml` не создан.

    Ловит мутацию: сверка собранного текста с записью репозитория снята
    или идёт после записи файла — файл пишется со значением, которое
    читается иначе.
    """
    key = f"MIX{seed.word().upper()}"
    value = f"{seed.word()}'{seed.word()}\"{seed.word()}"
    write_repo(sled_pin(f"        {key}: {value}\n"))
    assert targets.load()["sled"]["test_profile"]["env"][key] == value
    ok, text = cli("targets-migrate", "sled")
    assert not ok, seed.msg(text)
    assert key in text, seed.msg(text)
    assert not local_file().exists()


# ------------------------------------------------------------ AC-15

def test_ac15_role_environment_refused_before_run(cli, monkeypatch):
    """`targets-migrate` из окружения роли (`ARTEL_ROLE`) — отказ до исполнения, файл локального слоя не создаётся.

    Сценарий: слой репозитория с записью sled, `ARTEL_ROLE` выставлен;
    `targets-migrate sled` завершается ненулевым кодом с текстом отказа
    процессу роли, названием команды и роли; `.artel/targets.yaml` нет.

    Ловит мутацию: команда внесена в белый список ролей
    (`_ROLE_ALLOWED_COMMANDS`) — роль переносит запись сама.
    """
    write_repo(sled_pin())
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
    ok, text = cli("targets-migrate", "sled")
    assert not ok, text
    assert "targets-migrate" in text and "недоступна процессу роли developer" in text
    assert not local_file().exists()


LINT_SOURCES = {
    "литерал": ('from pathlib import Path\n\n\ndef test_a():\n'
                '    Path(__file__).parent.parent / ".artel/targets.yaml"\n', True),
    "константа config": ('from pathlib import Path\nfrom orchestrator import config\n\n\n'
                         'def test_a():\n'
                         '    Path(__file__).parent.parent / config.TARGETS_LOCAL_REL\n', True),
    "путь песочницы": ('from orchestrator import config\n\n\ndef test_a():\n'
                       '    config.TARGETS.parent / config.TARGETS_LOCAL_REL\n', False),
}


@pytest.mark.parametrize("case", ["литерал", "константа config", "путь песочницы"])
def test_ac15_lint_live_local_layer_path(case):
    """Линт: путь от `__file__` к `.artel/targets.yaml` — находка «путь к живому файлу репозитория»; путь от `config.TARGETS` — нет.

    Сценарий: образец теста с `Path(__file__).parent.parent /
    ".artel/targets.yaml"` и с `Path(__file__).parent.parent /
    config.TARGETS_LOCAL_REL` даёт у `test_a` находку «путь к живому файлу
    репозитория»; образец с `config.TARGETS.parent /
    config.TARGETS_LOCAL_REL` находок не даёт.

    Ловит мутацию: `.artel/targets.yaml` не внесён в `LIVE_FILES` или
    `TARGETS_LOCAL_REL` — в `LIVE_FILE_CONFIG_ATTRS`; путь песочницы от
    `config.TARGETS` ошибочно считается живым.
    """
    source, expected = LINT_SOURCES[case]
    found = test_lint.findings(source, "tests/test_probe.py")
    hits = [hit for hits in found.values() for hit in hits
            if "путь к живому файлу репозитория" in hit]
    assert bool(hits) is expected, found
