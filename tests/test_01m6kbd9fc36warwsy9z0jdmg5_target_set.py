"""Команда `target-set <проект> <путь> <значение>`: правка одного поля записи проекта в локальном слое `.artel/targets.yaml`, копия прежнего файла, запись журнала, отказы, `--show`, отказ процессу роли.

Группа: долгоживущий
Красен до реализации: команды `target-set` в диспетчере `artel.py` нет — вызов кончается отказом «неизвестная команда» (или трейсбеком), файл локального слоя не меняется, копии и записи журнала нет.

Связка, которую держит файл: «диспетчер `artel.main` — команда правки —
загрузчик `targets.load`/`project_profile.component_profiles` — журнал
пульта» в песочнице `initialized_tmp_root` (`tests.sandbox.
InitializedTmpRootTest`: пути `config` — `TARGETS`, `LOGS`, `DB`,
`PROJECTS` — во временном каталоге, БД со схемой, признак процесса роли
снят). Настоящий локальный слой пульта не читается и не пишется. Команда
зовётся как из командной строки: `sys.argv` подменён, `artel.main()`.
Отказ — выход `SystemExit` с ненулевым кодом; его текст — код выхода и
вывод команды. Файл локального слоя —
`config.TARGETS.parent / ".artel" / "targets.yaml"`; копии — файлы
`targets-*.yaml` в `config.LOGS`; записи журнала — строки таблицы `steps`
с действием `target-set`.

Имена проектов, имя второго компонента, порядок компонентов и значения —
от зерна `random`; зерно печатается и входит в текст провала.

До реализации часть отказных случаев (AC-3, AC-4, AC-7, AC-9 о
комментарии) уже зелена: неизвестную команду диспетчер тоже отвергает, не
трогая файл. Различающую силу они получают вместе с командой — их
проверяли на временном стабе реализации, где снятая проверка красит их.
"""
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, project_profile, projects, store, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
PROJECT = "sandbox"
COPY_NAME = re.compile(r"targets-[0-9][0-9TZ:_.\-]*?(-\d+)?\.yaml")
NO_COMPONENT = "компонента {comp} нет в записи; добавление компонентов не входит"


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
        text = "\n".join(str(part) for part in (code, out.out, out.err))
        return (code in (0, None)), text

    return run


# ------------------------------------------------------------ файлы

def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def copies() -> list:
    if not config.LOGS.is_dir():
        return []
    return sorted(config.LOGS.glob("targets-*.yaml"))


def journal_rows() -> list:
    conn = store.db()
    return conn.execute(
        "SELECT task_id, target, action, detail FROM steps "
        "WHERE action = 'target-set' ORDER BY id").fetchall()


def component_record(name: str, comps: list, *, policy_comp: str = "app",
                     reported=None) -> str:
    """Запись в трёх разделах с компонентами `comps`; блок `policy` — только
    у `policy_comp`, раздела `machine.components` нет."""
    reported = set(comps) if reported is None else set(reported)
    lines = [f"  {name}:", "    description:", "      base: main",
             "      components:"]
    for comp in comps:
        lines += [f"        {comp}:", "          runner: pytest-own",
                  "          command: [python3, -m, pytest]"]
        if comp in reported:
            lines.append("          report: junit-xml")
        lines.append(f"          paths: ^{comp}/")
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: operator", "      components:",
              f"        {policy_comp}:",
              f"          weakening_scope: [{policy_comp}/tests/**/*.py]",
              "    machine:", "      forge: github",
              f"      url: https://localhost/team/{name}",
              f"      token_slot: {name}-token"]
    return "\n".join(lines) + "\n"


def profile_record(name: str) -> str:
    """Запись в трёх разделах с `test_profile` — без `components` в `description`."""
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


def write_layers(local_text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_text, encoding="utf-8")


def standard_layer(seed: Seed) -> tuple:
    """Локальный слой: `sandbox` с компонентами `app` и случайным вторым (порядок от зерна) и запись другого проекта."""
    other_comp = "c" + seed.word()
    comps = ["app", other_comp]
    seed.rng.shuffle(comps)
    other = seed.name()
    text = ("targets:\n"
            + component_record(PROJECT, comps)
            + profile_record(other))
    return text, other_comp, other


def leaves(value, prefix=()) -> dict:
    """Листья разобранного отображения: путь → значение (список — лист)."""
    if isinstance(value, dict):
        found = {}
        for key, item in value.items():
            found.update(leaves(item, prefix + (key,)))
        return found
    return {prefix: value}


def parsed(path) -> dict:
    return yamlmini.mapping(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------ AC-1

def test_ac1_failure_errors_set_copy_and_journal(cli, seed):
    """`target-set sandbox description.components.app.failure_errors [AssertionError]` меняет ровно одно поле, оставляет копию и запись журнала.

    Сценарий: локальный слой — запись `sandbox` с компонентами `app` (без
    `failure_errors`) и случайным вторым, плюс запись другого проекта.
    Команда успешна; разобранное отображение нового файла отличается от
    прежнего ровно одним листом — `targets.sandbox.description.components.
    app.failure_errors` со значением `[AssertionError]`;
    `project_profile.component_profiles("sandbox")` даёт у `app`
    `failure_errors == ("AssertionError",)`. В `config.LOGS` ровно одна
    копия `targets-<время>.yaml` с байтами прежнего файла, её путь — в
    выводе. В журнале ровно одна запись `target-set` без задачи с
    `target=sandbox`, читается «target-set: description.components.app.
    failure_errors: (нет) → [AssertionError]», и эта строка напечатана.

    Ловит мутацию: файл пересобран с потерей или изменением другого поля
    (лишний лист в разнице); значение записано строкой `"[AssertionError]"`
    вместо списка (профиль не видит `failure_errors`); копия не создаётся
    или пишется уже новым текстом; запись журнала без `target` либо с
    `<было>` вместо `(нет)` — пустым или `None`; запись не напечатана.
    """
    text = standard_layer(seed)[0]
    write_layers(text)
    before_bytes = local_file().read_bytes()
    before = parsed(local_file())
    field = "description.components.app.failure_errors"
    ok, out = cli("target-set", PROJECT, field, "[AssertionError]")
    assert ok, seed.msg(out)
    after = parsed(local_file())
    old_leaves, new_leaves = leaves(before), leaves(after)
    changed = {key for key in set(old_leaves) | set(new_leaves)
               if old_leaves.get(key, object()) != new_leaves.get(key, object())}
    key = ("targets", PROJECT, *field.split("."))
    assert changed == {key}, seed.msg(changed)
    assert new_leaves[key] == ["AssertionError"], seed.msg(new_leaves[key])
    profiles = {p.component: p for p in project_profile.component_profiles(PROJECT)}
    assert profiles["app"].failure_errors == ("AssertionError",), seed.msg(profiles["app"])
    found = copies()
    assert len(found) == 1, seed.msg(found)
    assert COPY_NAME.fullmatch(found[0].name), seed.msg(found[0].name)
    assert found[0].read_bytes() == before_bytes
    assert str(found[0]) in out, seed.msg(out)
    rows = journal_rows()
    assert len(rows) == 1, seed.msg([tuple(r) for r in rows])
    task_id, target, action, detail = tuple(rows[0])
    assert task_id is None, seed.msg(tuple(rows[0]))
    assert target == PROJECT, seed.msg(tuple(rows[0]))
    line = f"target-set: {field}: (нет) → [AssertionError]"
    assert f"{action}: {detail}" == line, seed.msg(tuple(rows[0]))
    assert line in out, seed.msg(out)


# ------------------------------------------------------------ AC-3

def refusal_case(case: str, seed: Seed) -> tuple:
    """(argv после `target-set`, правка прежнего текста или None, признак в тексте отказа)."""
    if case == "неизвестное поле":
        section = seed.rng.choice([
            "description", "policy", "machine", "description.components.app",
            "policy.components.app", "machine.components.app"])
        return ([PROJECT, f"{section}.zz{seed.word()}", seed.word()], None, section)
    if case == "вложенное отображение":
        path = seed.rng.choice([
            f"description.components.app.env.K{seed.word().upper()}",
            f"description.components.app.tools.t{seed.word()}"])
        return ([PROJECT, path, seed.word()], None, None)
    if case == "неверное значение":
        path = seed.rng.choice(["description.components.app.report",
                                "policy.merge_gate"])
        return ([PROJECT, path, "bad" + seed.word()], None, None)
    if case == "проект artel":
        return ([config.DEFAULT_TARGET, "description.base", seed.word()], None, None)
    if case == "необъявленный проект":
        return ([seed.name(), "policy.sandbox", seed.word()], None, None)
    if case == "несводимый слой":
        broken = (f"  {seed.name()}:\n    description:\n      base: main\n"
                  f"      test_profile:\n        command: [python3, -m, pytest]\n"
                  f"    policy:\n      no_paths: []\n      project_skills: []\n"
                  f"      merge_gate: operator\n")
        return ([PROJECT, "policy.sandbox", seed.word()],
                lambda text: text + broken, None)
    if case == "строка с #":
        return ([PROJECT, "policy.sandbox", seed.word()],
                lambda text: f"# {seed.word()}\n" + text, None)
    if case == "журнал недоступен":
        return ([PROJECT, "policy.sandbox", seed.word()], None, "journal")
    if case == "лишние аргументы":
        return ([PROJECT, "description.components.app.failure_errors",
                 "[AssertionError,", f"E{seed.word()}]"], None, "кавыч")
    raise AssertionError(case)


ALLOWED = {
    "description": lambda: list(targets.LOCAL_FIELDS["description"]),
    "policy": lambda: list(targets.LOCAL_FIELDS["policy"]),
    "machine": lambda: list(targets.LOCAL_FIELDS["machine"]),
    "description.components.app": lambda: [
        f for f in targets.COMPONENT_FIELDS if f not in targets.LOCAL_POLICY_SCOPES],
    "policy.components.app": lambda: list(targets.LOCAL_POLICY_SCOPES),
    "machine.components.app": lambda: list(targets.LOCAL_MACHINE_COMPONENT_FIELDS),
}


@pytest.mark.parametrize("case", [
    "неизвестное поле", "вложенное отображение", "неверное значение",
    "проект artel", "необъявленный проект", "несводимый слой", "строка с #",
    "журнал недоступен", "лишние аргументы"])
def test_ac3_refusals_leave_file_and_no_copy(cli, seed, case):
    """Каждый отказной случай — ненулевой код с причиной, файл локального слоя байт в байт прежний, копии нет.

    Сценарий: локальный слой — запись `sandbox` с компонентами и запись
    другого проекта; по случаю прежний текст дополняется (несводимая
    вторая запись без раздела `machine`; строка-комментарий `# …` в
    начале файла), БД пульта удаляется (журнал недоступен) или команда
    зовётся с отказным путём/значением/проектом/числом аргументов. Код
    выхода ненулевой, текст отказа непустой; байты файла и
    `targets.yaml` репозитория прежние; копий `targets-*.yaml` в
    `config.LOGS` нет. Отказ по неизвестному полю называет каждое
    допустимое поле раздела (перечни требования 2 SPEC); отказ по журналу
    несёт `projects.NO_JOURNAL`; по лишним аргументам — подсказку взять
    значение в кавычки.

    Ловит мутацию: проверка поля по перечню снята или перечень не
    печатается; путь `env.X`/`tools.X` пишется вложенным листом; значение
    не сверяется `targets.merge_local` и файл пишется; запись артели
    правится в локальном слое; необъявленный проект заводится новой
    записью; несводимый слой не проверяется до правки; строка-комментарий
    молча стирается пересборкой; журнал проверяется после записи файла
    (файл уже изменён); второй аргумент значения молча отброшен; копия
    создаётся до проверок.
    """
    text = standard_layer(seed)[0]
    argv, edit, needle = refusal_case(case, seed)
    if edit is not None:
        text = edit(text)
    write_layers(text)
    if case == "журнал недоступен":
        config.DB.unlink()
        assert not store.db_usable()
    repo_bytes = config.TARGETS.read_bytes()
    local_bytes = local_file().read_bytes()
    ok, out = cli("target-set", *argv)
    assert not ok, seed.msg(out)
    assert out.split("\n", 1)[1].strip(), seed.msg(out)
    assert local_file().read_bytes() == local_bytes, seed.msg(out)
    assert config.TARGETS.read_bytes() == repo_bytes, seed.msg(out)
    assert copies() == [], seed.msg(out)
    if case == "неизвестное поле":
        for allowed in ALLOWED[needle]():
            assert allowed in out, seed.msg((allowed, out))
    elif needle == "journal":
        assert projects.NO_JOURNAL in out, seed.msg(out)
    elif needle is not None:
        assert needle in out, seed.msg(out)


# ------------------------------------------------------------ AC-4

@pytest.mark.parametrize("path,value", [
    ("description.components.app.failure_errors", "[1.5]"),
    ("policy.sandbox", "{w}'{w}\"{w}"),
    ("policy.sandbox", "{w} # {w}"),
    ("policy.sandbox", '""'),
    ("description.components.app.failure_errors", "[AssertionError # {w}]"),
    ("description.components.app.failure_errors", "[a, b] # {w}"),
])
def test_ac4_value_read_otherwise_refused(cli, seed, path, value):
    """Значение, которое `yamlmini` прочитал бы иначе, чем задано (или пусто), — отказ, файл прежний.

    Сценарий: локальный слой — запись `sandbox`; аргумент значения —
    `[1.5]`, строка с кавычками обоих видов, `x # y` (хвост комментария
    теряется), `""` (пустое значение), списки `[AssertionError # x]` и
    `[a, b] # c` (разбор теряет часть списка); слова — от зерна. Код
    выхода ненулевой с причиной, байты файла локального слоя прежние,
    копий в `config.LOGS` нет.

    Ловит мутацию: значение пишется без сверки «записанное читается тем
    же» — файл получает `policy.sandbox: x` (потерян хвост), пустую строку,
    обрезанный список или строку, которую разбор вернёт другой.
    """
    write_layers(standard_layer(seed)[0])
    local_bytes = local_file().read_bytes()
    argument = value.replace("{w}", seed.word())
    ok, out = cli("target-set", PROJECT, path, argument)
    assert not ok, seed.msg(out)
    assert out.split("\n", 1)[1].strip(), seed.msg(out)
    assert local_file().read_bytes() == local_bytes, seed.msg(out)
    assert copies() == [], seed.msg(out)


# ------------------------------------------------------------ AC-5

def test_ac5_machine_path_changes(cli, seed):
    """Правка `machine.path` проходит: поле записано, отказа нет.

    Сценарий: локальный слой — запись `sandbox` без `machine.path`;
    `target-set sandbox machine.path /opt/<слово>/bin:/usr/bin` кончается
    успехом, разобранный файл несёт новое `machine.path`, сведённая
    запись `targets.load()["sandbox"]` годна.

    Ловит мутацию: `machine.path` ошибочно отнесён к абсолютным значениям
    (`/…`) и отвергнут, как у `targets-migrate` в разделах `description`/
    `policy`; поле записано не в раздел `machine`.
    """
    write_layers(standard_layer(seed)[0])
    value = f"/opt/{seed.word()}/bin:/usr/bin"
    ok, out = cli("target-set", PROJECT, "machine.path", value)
    assert ok, seed.msg(out)
    assert parsed(local_file())["targets"][PROJECT]["machine"]["path"] == value
    assert PROJECT in targets.load()


# ------------------------------------------------------------ AC-6

@pytest.mark.parametrize("path,expect", [
    ("description.components.app.report", ["junit-xml"]),
    ("policy.merge_gate", ["operator"]),
    ("machine", ["https://localhost/team/sandbox", "sandbox-token"]),
    (None, ["description", "policy", "machine", "merge_gate"]),
])
def test_ac6_show_prints_value_no_write(cli, seed, path, expect):
    """`target-set --show sandbox [<путь>]` печатает поле или раздел записи, файл не трогает.

    Сценарий: локальный слой — запись `sandbox`; `--show` с путём поля,
    путём раздела или без пути. Код выхода 0, вывод несёт значение поля
    либо поля раздела/записи; байты файла прежние; копий в `config.LOGS`
    нет.

    Ловит мутацию: `--show` проходит общий путь правки и переписывает
    файл (или делает копию); путь раздела не печатает его поля; без пути
    вывод пуст.
    """
    write_layers(standard_layer(seed)[0])
    local_bytes = local_file().read_bytes()
    argv = ["target-set", "--show", PROJECT] + ([path] if path else [])
    ok, out = cli(*argv)
    assert ok, seed.msg(out)
    for needle in expect:
        assert needle in out, seed.msg((needle, out))
    assert local_file().read_bytes() == local_bytes
    assert copies() == []


# ------------------------------------------------------------ AC-7

@pytest.mark.parametrize("show", [False, True])
def test_ac7_role_environment_refused(cli, seed, monkeypatch, show):
    """Под признаком роли (`ARTEL_ROLE`) `target-set` и `target-set --show` отказывают до исполнения.

    Сценарий: локальный слой — запись `sandbox`; `ARTEL_ROLE` выставлен;
    команда — правка `policy.sandbox` или `--show sandbox`. Код выхода
    ненулевой, текст — отказ процессу роли с названием команды; байты
    файла прежние, копий нет.

    Ловит мутацию: `target-set` внесён в `_ROLE_ALLOWED_COMMANDS` или
    `--show` выделен как читающий флаг, доступный роли.
    """
    write_layers(standard_layer(seed)[0])
    local_bytes = local_file().read_bytes()
    role = "r" + seed.word()
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, role)
    argv = (["target-set", "--show", PROJECT] if show
            else ["target-set", PROJECT, "policy.sandbox", seed.word()])
    ok, out = cli(*argv)
    assert not ok, seed.msg(out)
    assert "target-set" in out and f"недоступна процессу роли {role}" in out, seed.msg(out)
    assert local_file().read_bytes() == local_bytes
    assert copies() == []


# ------------------------------------------------------------ AC-9

@pytest.mark.parametrize("case", ["хвостовой", "строка с отступом"])
def test_ac9_comment_in_old_text_refused(cli, seed, case):
    """Комментарий в прежнем тексте (хвостовой после значения или строка с отступом) — отказ, файл прежний, копии нет.

    Сценарий: в записи `sandbox` после `merge_gate: operator` — хвостовой
    `  # <слово>` либо внутри раздела `policy` — строка `      # <слово>`.
    `target-set sandbox policy.sandbox <слово>` кончается ненулевым кодом
    с причиной; байты файла прежние; копий в `config.LOGS` нет.

    Ловит мутацию: проверка комментариев смотрит только строки,
    начинающиеся с `#` без отступа, — пересборка `projects._render` молча
    стирает хвостовой или вложенный комментарий.
    """
    text = standard_layer(seed)[0]
    word = seed.word()
    if case == "хвостовой":
        text = text.replace("      merge_gate: operator\n",
                            f"      merge_gate: operator  # {word}\n", 1)
    else:
        text = text.replace("    policy:\n", f"    policy:\n      # {word}\n", 1)
    assert word in text
    write_layers(text)
    local_bytes = local_file().read_bytes()
    ok, out = cli("target-set", PROJECT, "policy.sandbox", seed.word())
    assert not ok, seed.msg(out)
    assert out.split("\n", 1)[1].strip(), seed.msg(out)
    assert local_file().read_bytes() == local_bytes
    assert copies() == []


def test_ac9_hash_inside_quotes_not_comment(cli, seed):
    """`#` только внутри кавычек значения (`base: "a # b"`) — не комментарий: правка другого поля проходит, `description.base` прежнее.

    Сценарий: запись `sandbox` с `base: "<слово> # <слово>"`;
    `target-set sandbox policy.sandbox <слово>` успешна; в новом файле
    `policy.sandbox` — новое значение, `description.base` — прежняя строка
    с ` # `; сведённая запись `targets.load()["sandbox"]["base"]` — та же.

    Ловит мутацию: правило комментария ищет `#` в сырой строке без учёта
    кавычек — правка отказывает; пересборка пишет `base` без кавычек, и
    разбор теряет хвост ` # …`.
    """
    base = f"{seed.word()} # {seed.word()}"
    text = standard_layer(seed)[0]
    text = text.replace("      base: main\n", f'      base: "{base}"\n', 1)
    write_layers(text)
    value = "s" + seed.word()
    ok, out = cli("target-set", PROJECT, "policy.sandbox", value)
    assert ok, seed.msg(out)
    record = parsed(local_file())["targets"][PROJECT]
    assert record["policy"]["sandbox"] == value, seed.msg(record)
    assert record["description"]["base"] == base, seed.msg(record)
    assert targets.load()[PROJECT]["base"] == base


# ------------------------------------------------------------ AC-10

@pytest.mark.parametrize("section", ["description", "policy", "machine"])
def test_ac10_missing_component_refused(cli, seed, section):
    """Путь к компоненту, которого нет в `description.components`, — отказ «компонента <к> нет в записи…», файл прежний.

    Сценарий: запись `sandbox` с компонентами; путь
    `<раздел>.components.<случайное имя>.<допустимое поле>`. Код выхода
    ненулевой, текст — «компонента <к> нет в записи; добавление
    компонентов не входит»; байты файла прежние, копий нет.

    Ловит мутацию: блок незнакомого компонента создаётся (добавление
    компонента через правку поля); существование компонента сверяется по
    блоку `policy`/`machine`, а не по `description.components`.
    """
    write_layers(standard_layer(seed)[0])
    local_bytes = local_file().read_bytes()
    comp = "z" + seed.word()
    field, value = {"description": ("report", "junit-xml"),
                    "policy": ("weakening_scope", f"[{comp}/tests/**/*.py]"),
                    "machine": ("path", f"/opt/{seed.word()}/bin")}[section]
    ok, out = cli("target-set", PROJECT, f"{section}.components.{comp}.{field}", value)
    assert not ok, seed.msg(out)
    assert NO_COMPONENT.format(comp=comp) in out, seed.msg(out)
    assert local_file().read_bytes() == local_bytes
    assert copies() == []


@pytest.mark.parametrize("section", ["description", "policy", "machine"])
def test_ac10_no_components_mapping_refused(cli, seed, section):
    """Запись без отображения `components` в `description` (`test_profile`) — путь к компоненту отказывает «компонента <к> нет в записи…».

    Сценарий: локальный слой — запись с `test_profile` (случайное имя);
    путь `<раздел>.components.<к>.<поле>`. Код выхода ненулевой, текст
    отказа о компоненте; байты файла прежние, копий нет.

    Ловит мутацию: при отсутствии `description.components` отображение
    заводится заново и компонент добавляется; отказ падает трейсбеком
    `KeyError`/`TypeError` вместо причины.
    """
    name = seed.name()
    write_layers("targets:\n" + profile_record(name))
    local_bytes = local_file().read_bytes()
    comp = "k" + seed.word()
    field, value = {"description": ("report", "junit-xml"),
                    "policy": ("weakening_scope", "[x/tests/**/*.py]"),
                    "machine": ("path", f"/opt/{seed.word()}/bin")}[section]
    ok, out = cli("target-set", name, f"{section}.components.{comp}.{field}", value)
    assert not ok, seed.msg(out)
    assert NO_COMPONENT.format(comp=comp) in out, seed.msg(out)
    assert local_file().read_bytes() == local_bytes
    assert copies() == []


@pytest.mark.parametrize("section", ["policy", "machine"])
def test_ac10_component_block_created(cli, seed, section):
    """Компонент есть в `description.components`, но без своего блока в `policy`/`machine` — блок создаётся с одним полем.

    Сценарий: запись `sandbox`: блок `policy.components` есть только у
    `app`, раздела `machine.components` нет вовсе; путь —
    `policy.components.<второй>.weakening_scope` либо
    `machine.components.<второй>.path`. Команда успешна; в новом файле
    блок второго компонента в разделе — ровно `{поле: значение}`.

    Ловит мутацию: существование блока компонента требуется в самом
    разделе (отказ «компонента нет»); отсутствие `machine.components`
    роняет команду; блок создаётся с лишними полями.
    """
    text, other_comp, _ = standard_layer(seed)
    write_layers(text)
    if section == "policy":
        field, value, want = ("weakening_scope", f"[{other_comp}/tests/**/*.py]",
                              [f"{other_comp}/tests/**/*.py"])
    else:
        want = value = f"/opt/{seed.word()}/bin:/usr/bin"
        field = "path"
    ok, out = cli("target-set", PROJECT, f"{section}.components.{other_comp}.{field}", value)
    assert ok, seed.msg(out)
    record = parsed(local_file())["targets"][PROJECT]
    assert record[section]["components"][other_comp] == {field: want}, seed.msg(record)


# ------------------------------------------------------------ AC-11

@pytest.mark.parametrize("path,value", [
    ("description.components.app.report", "junit-xml"),
    ("policy.merge_gate", "operator"),
    ("description.base", "main"),
])
def test_ac11_same_value_no_change(cli, seed, path, value):
    """Значение, равное текущему, — «без изменений», код 0, файл прежний, копии и записи журнала нет.

    Сценарий: запись `sandbox`; `target-set` поля его текущим значением.
    Код выхода 0, в выводе «без изменений»; байты файла прежние; копий
    `targets-*.yaml` в `config.LOGS` нет; записей журнала `target-set` не
    прибавилось.

    Ловит мутацию: равенство значений не проверяется — файл переписан,
    копия создана, в журнал ушла запись «main → main»; равенство отдано
    отказом с ненулевым кодом.
    """
    write_layers(standard_layer(seed)[0])
    local_bytes = local_file().read_bytes()
    rows = len(journal_rows())
    ok, out = cli("target-set", PROJECT, path, value)
    assert ok, seed.msg(out)
    assert "без изменений" in out, seed.msg(out)
    assert local_file().read_bytes() == local_bytes
    assert copies() == []
    assert len(journal_rows()) == rows
