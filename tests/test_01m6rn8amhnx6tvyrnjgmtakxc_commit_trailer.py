"""Поле `policy.commit_trailer` локального слоя записи проекта: пустое значение грузится штатно, негодные отказывают с именем поля, команда `target-set` его записывает.

Группа: долгоживущий
Красен до реализации: поля `commit_trailer` нет в `targets.LOCAL_FIELDS` — запись с ним отказывает «раздел 'policy': неизвестное поле 'commit_trailer'» без подстроки `policy.commit_trailer`, а `target-set` отказывает «поля commit_trailer нет в policy».

Текст сообщения коммита пульта (`gitcmd.pult_message`, AC-1, AC-2, AC-3)
проверяет файл планки задачи: долгоживущему файлу импорт
`orchestrator.gitcmd` закрыт guard (признак «git-модуль»).

Связки: AC-2, AC-4 — разбор записи (`targets.target`/`targets.merge_local`)
в песочнице `tmp_root` (пути `config` во временном каталоге, запись
вымышленного проекта — в файле локального слоя `targets.local_path()`,
загрузка штатная, без подмены записи). AC-5 — связка «диспетчер
`artel.main` — команда `target-set` — локальный слой — копия в
`config.LOGS`» в песочнице `initialized_tmp_root`. Настоящий локальный слой
пульта не читается и не пишется; git и сеть не нужны.

Имена проектов и случайная допустимая служебная строка — от зерна
`random`; зерно печатается и входит в текст провала.
"""
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefhkmnpqrsvwxyz"
KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
TRAILER = "Harness-Actor: orchestrator"
FIELD = "policy.commit_trailer"

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: []
      project_skills: []
      merge_gate: operator
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: github
      url: https://localhost/team/{name}
      token_slot: {name}-token
"""


class Seed:
    """Зерно сценария: печатается и входит в текст провала."""

    def __init__(self):
        self.value = random.randrange(1 << 30)
        print(f"зерно: {self.value}")
        self.rng = random.Random(self.value)

    def msg(self, text) -> str:
        return f"зерно: {self.value}; {text}"

    def name(self) -> str:
        return "q" + "".join(self.rng.choice(LETTERS) for _ in range(8))

    def trailer(self) -> str:
        """Случайная допустимая служебная строка `<Ключ>: <значение>`."""
        key = "".join(self.rng.choice(KEY_CHARS) for _ in range(self.rng.randint(1, 12)))
        value = "v" + "".join(self.rng.choice(LETTERS + " .<>@")
                              for _ in range(self.rng.randint(0, 15))).rstrip()
        return f"{key}: {value}"


@pytest.fixture
def seed():
    return Seed()


def quoted(value: str) -> str:
    """Литерал YAML строки в двойных кавычках (подмножество `yamlmini`)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def record_text(name: str, policy: dict | None = None) -> str:
    """Запись проекта в трёх разделах; значения `policy` — текст YAML."""
    lines = "".join(f"      {key}: {value}\n" for key, value in (policy or {}).items())
    return ENTRY.format(name=name, base=config.MAIN_BRANCH, policy=lines)


def write_local(name: str, policy: dict | None = None) -> None:
    """Единственная запись вымышленного локального слоя песочницы."""
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + record_text(name, policy), encoding="utf-8")


def load_error(name: str) -> str | None:
    """Текст отказа загрузки записи `name`; `None` — запись загрузилась."""
    try:
        targets.target(name)
    except targets.TargetsError as exc:
        return str(exc)
    return None


# ------------------------------------------------------------------- AC-2


@pytest.mark.parametrize("with_co_author", [False, True], ids=["без-co_author", "с-co_author"])
def test_ac2_empty_trailer_loads_into_entry(tmp_root, seed, with_co_author):
    """`commit_trailer: ""` в файле слоя грузится штатно, сведённая запись несёт поле со значением `""`.

    Сценарий: запись локального слоя со случайным именем и
    `commit_trailer: ""` (с `co_author` или без). `targets.target` отдаёт
    запись без отказа, в ней поле `commit_trailer` есть и равно `""`
    (явно: читатель записи в `pult_message` молча глотает отказ загрузки,
    и отказ иначе выглядел бы как запись без поля).

    Ловит мутацию: пустое приравнено к пробельному (отказ при
    `not value.strip()` — загрузка отказывает); пустое значение теряется
    при сведении записи (фильтр по истинности значения — поля в записи
    нет).
    """
    name = seed.name()
    policy = {"co_author": '"Co-authored-by: Соавтор <co@x.example>"'} if with_co_author else {}
    policy["commit_trailer"] = '""'
    write_local(name, policy)
    note = seed.msg(name)
    try:
        entry = targets.target(name)
    except targets.TargetsError as exc:
        pytest.fail(note + f"; отказ загрузки: {exc}")
    assert "commit_trailer" in entry and entry["commit_trailer"] == "", note + f"; {entry}"


# ------------------------------------------------------------------- AC-4

# Значения поля текстом YAML файла слоя — каждое отказывает при загрузке.
FILE_REFUSALS = [
    ("число", "42"),
    ("список", "[x, y]"),
    ("пробелы", '"   "'),
    ("без-двоеточия", '"NoColon"'),
    ("двоеточие-без-пробела", '"Key:v"'),
    ("пробел-в-ключе", '"Key x: v"'),
    ("подчёркивание-в-ключе", '"Key_x: v"'),
    ("пустое-значение", '"Key: "'),
    ("пробельное-значение", '"Key:   "'),
]


@pytest.mark.parametrize("value", [row[1] for row in FILE_REFUSALS],
                         ids=[row[0] for row in FILE_REFUSALS])
def test_ac4_bad_value_in_layer_file_refused(tmp_root, seed, value):
    """Негодное значение `policy.commit_trailer` в файле слоя — отказ загрузки `TargetsError` с именем поля.

    Сценарий: запись локального слоя со случайным именем и значением поля
    по параметру (число, список, одни пробелы, без «: », `Key:v`, пробел
    или `_` в ключе, пустое или пробельное значение после «: »).
    `targets.target` поднимает `TargetsError`, текст которого содержит
    `policy.commit_trailer`.

    Ловит мутацию: проверка ищет `:`, а не `: ` (`Key:v` проходит); ключ
    проверяется `\\w` вместо `[A-Za-z0-9-]` (`Key_x: v` проходит); значение
    после «: » не обрезается (`Key:   ` проходит); значение целиком из
    пробелов читается как «строки нет»; не строка не отвергается.
    """
    name = seed.name()
    write_local(name, {"commit_trailer": value})
    text = load_error(name)
    note = seed.msg(f"{name}; {value}: {text}")
    assert text is not None, note
    assert FIELD in text, note


def test_ac4_two_lines_refused_by_merge_local(tmp_root, seed):
    """Значение из двух строк — `targets.merge_local` отказывает `TargetsError` с именем поля.

    Сценарий: запись случайного имени разбирается из текста слоя
    (`yamlmini.mapping`), в `policy` ставится `commit_trailer` из двух
    допустимых строк `<Ключ>: <значение>`, соединённых `\\n`; вызов
    `targets.merge_local(<имя>, <запись>)` поднимает `TargetsError`, текст
    содержит `policy.commit_trailer`.

    Ловит мутацию: формат проверяется по первой строке или поиском
    (`re.match`/`re.search` без привязки к концу) — значение из двух строк
    проходит.
    """
    name = seed.name()
    entry = yamlmini.mapping("targets:\n" + record_text(name))["targets"][name]
    value = seed.trailer() + "\n" + seed.trailer()
    entry["policy"]["commit_trailer"] = value
    note = seed.msg(f"{name}; {value!r}")
    with pytest.raises(targets.TargetsError) as caught:
        targets.merge_local(name, entry)
    assert FIELD in str(caught.value), note + f"; {caught.value}"


# ------------------------------------------------------------------- AC-5


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


def test_ac5_target_set_writes_field_with_backup(cli, seed):
    """`target-set <проект> policy.commit_trailer "Harness-Actor: orchestrator"` пишет поле в `policy`, оставляет копию прежнего слоя, запись грузится с ним.

    Сценарий: `targets.yaml` песочницы — запись артели; локальный слой —
    запись со случайным именем без поля. Команда успешна; в разобранном
    новом файле `targets.<имя>.policy.commit_trailer` равно
    `Harness-Actor: orchestrator`; в `config.LOGS` появилась копия
    `targets-*.yaml` с байтами прежнего файла; `targets.target(<имя>)`
    отдаёт поле с тем же значением.

    Ловит мутацию: поле не внесено в известные поля локального слоя
    (`target-set` отказывает «поля commit_trailer нет в policy», файл не
    меняется) или проверка значения отвергает допустимую строку с пробелом
    в значении.
    """
    name = seed.name()
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    write_local(name)
    local = targets.local_path()
    before = local.read_bytes()
    copies_before = set(config.LOGS.glob("targets-*.yaml")) if config.LOGS.is_dir() else set()
    ok, out = cli("target-set", name, FIELD, TRAILER)
    note = seed.msg(f"{name}; {out}")
    assert ok, note
    parsed = yamlmini.mapping(local.read_text(encoding="utf-8"))
    assert parsed["targets"][name]["policy"].get("commit_trailer") == TRAILER, note
    copies = set(config.LOGS.glob("targets-*.yaml")) - copies_before
    assert any(path.read_bytes() == before for path in copies), note + f"; {copies}"
    assert targets.target(name).get("commit_trailer") == TRAILER, note
