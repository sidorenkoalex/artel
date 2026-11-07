"""Путь блока `machine.commit_author` формы `target-set <проект> <путь блока> --from-file <файл>`: заведение и замена поля автора коммитов пульта целиком из файла, отказ проверки формы `commit_author`, отказ прочих путей `machine.*` с дописанным перечнем путей блока.

Группа: долгоживущий
Красен до реализации: путь `machine.commit_author` не входит в виды пути блока — `_block_keys` отказывает перечнем без `machine.commit_author`, поле не заводится и не заменяется, сведённая запись `targets.target` несёт прежнего автора, отказ формы не несёт «нужно {name, email}», литерала перечня с `machine.commit_author` в выводе нет; проверено на временном стабе третьей ветки пути блока — все тесты зелены.

Связка, которую держит файл: «диспетчер `artel.main` — команда правки
`target-set` — сведение `targets.merge_local` — сведённая запись
`targets.target` (поле `commit_author`, его читает автор коммитов пульта)
— журнал пульта» в песочнице `initialized_tmp_root`
(`tests.sandbox.InitializedTmpRootTest`: пути `config` — `ROOT`,
`TARGETS`, `LOGS`, `DB` — во временном каталоге, БД со схемой). Настоящий
локальный слой пульта не читается и не пишется; имена проектов, авторов и
почты вымышленные (домен `example.invalid`), сети нет. Команда зовётся как
из командной строки: `sys.argv` подменён, `artel.main()`. Отказ — выход
`SystemExit` с ненулевым кодом. Файл локального слоя —
`config.TARGETS.parent / ".artel" / "targets.yaml"`; копии —
`targets-*.yaml` в `config.LOGS`; записи журнала — строки `steps` с
действием `target-set`.

Файлы блоков лежат в подкаталоге `work/blocks` песочницы; текущий каталог
процесса на время теста — `work` (фикстура `work_dir`, возврат прежнего
каталога в `finally`).

Имена проектов, авторов и почты — от зерна `random`; зерно печатается и
входит в текст провала.
"""
import os
import random
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, config, store, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
PATH = "machine.commit_author"
PATHS_LITERAL = ("допустимые пути блока: description.test_profile, "
                 "description.components.<имя>, machine.commit_author")
SHAPE_REFUSAL = "нужно {name, email}"


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

    def author(self) -> tuple:
        """(имя, почта) вымышленного автора."""
        first = self.word().capitalize()
        return f"Bot {first}", f"{first.lower()}.{self.word(4)}@example.invalid"


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


def journal_details() -> list:
    rows = store.db().execute(
        "SELECT detail FROM steps WHERE action = 'target-set' ORDER BY id").fetchall()
    return [row[0] for row in rows]


def record(name: str, seed: Seed, author: tuple | None) -> str:
    """Запись проекта в форме пересборки; `author` — (имя, почта) поля `machine.commit_author` или None — поля нет."""
    text = (f"  {name}:\n    description:\n      base: main\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"        runner: pytest-own\n"
            f"        env:\n          LANG: C\n"
            f"          PYTHONPATH: {seed.word()}\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")
    if author is not None:
        text += (f"      commit_author:\n        name: {author[0]}\n"
                 f"        email: {author[1]}\n")
    return text


def layer(seed: Seed, author: tuple | None, other_author: tuple | None) -> tuple:
    """(текст слоя, проект, другая запись): запись `<п>` с полем `author` и другая запись с `other_author`; порядок — от зерна."""
    name, other = seed.name(), seed.name()
    parts = [record(name, seed, author), record(other, seed, other_author)]
    seed.rng.shuffle(parts)
    return "targets:\n" + "".join(parts), name, other


def write_layers(local_text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_text, encoding="utf-8")


def parsed_layer() -> dict:
    return yamlmini.mapping(local_file().read_text(encoding="utf-8"))


def leaves(value: object, prefix: tuple = ()) -> dict:
    """Листья разобранного отображения: путь → значение (список — один лист)."""
    if isinstance(value, dict):
        found = {}
        for key, item in value.items():
            found.update(leaves(item, prefix + (key,)))
        return found
    return {prefix: value}


def outside(data: dict, prefix: tuple) -> dict:
    """Листья разобранного слоя вне кортежа-префикса `prefix`."""
    return {key: value for key, value in leaves(data).items()
            if key[:len(prefix)] != prefix}


def merged_author(name: str) -> tuple | None:
    """(имя, почта) поля `commit_author` сведённой записи `targets.target(<проект>)` — того, что читает автор коммитов пульта; None — поля нет."""
    author = targets.target(name).get("commit_author")
    return None if author is None else (author["name"], author["email"])


def block_file(work: Path, name: str, text: str) -> str:
    """Файл блока в `work/blocks`; аргумент `--from-file` — относительный."""
    (work / "blocks" / name).write_text(text, encoding="utf-8")
    return f"./blocks/{name}"


def author_block(author: tuple) -> str:
    """Файл блока `commit_author`: `name` и `email`, порядок ключей — прямой."""
    return f"name: {author[0]}\nemail: {author[1]}\n"


def refusal_kept(ok: bool, out: str, before: bytes, seed: Seed) -> None:
    assert not ok, seed.msg(out)
    assert "Traceback" not in out, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)
    assert copies() == [], seed.msg(out)


# ------------------------------------------------------------ AC-1

def test_ac1_commit_author_added_from_file(cli, work_dir, seed):
    """Запись без `machine.commit_author` получает поле целиком из файла блока; пульт читает новую пару автора.

    Сценарий: слой — запись `<п>` без `commit_author` и другая запись со
    своим `commit_author`; файл блока — `name` и `email` вымышленного
    автора. `target-set <п> machine.commit_author --from-file <файл>`
    успешна. Разобранное `machine.commit_author` записи `<п>` равно
    отображению файла; `merged_author(<п>)` — пара (name, email)
    файла, у другой записи — её прежняя пара; листья слоя вне
    `targets.<п>.machine.commit_author` прежние; одна копия — байты
    прежнего файла; журнал и вывод — `machine.commit_author: блок из
    <аргумент> (листов было (нет) → стало 2)`.

    Ловит мутацию: путь `machine.commit_author` не принят `_block_keys`
    (отказ перечнем — поле не заведено, `merged_author` — None);
    блок записан не под `machine`, а рядом с записью или под `description`;
    правка задевает другую запись или прочие поля `machine`; копия не
    создана; в журнале «было 0» вместо `(нет)` или число ключей не листов.
    """
    author, other_author = seed.author(), seed.author()
    text, name, other = layer(seed, None, other_author)
    write_layers(text)
    before_bytes = local_file().read_bytes()
    before = parsed_layer()
    assert merged_author(name) is None, seed.msg(text)
    block = author_block(author)
    arg = block_file(work_dir, "author.yaml", block)
    ok, out = cli("target-set", name, PATH, "--from-file", arg)
    assert ok, seed.msg(out)
    after = parsed_layer()
    want = yamlmini.mapping(block)
    got = after["targets"][name]["machine"].get("commit_author")
    assert got == want, seed.msg((got, want))
    assert merged_author(name) == author, seed.msg(out)
    assert merged_author(other) == other_author, seed.msg(out)
    prefix = ("targets", name, "machine", "commit_author")
    assert outside(after, prefix) == outside(before, prefix), seed.msg(out)
    detail = f"{PATH}: блок из {arg} (листов было (нет) → стало 2)"
    assert journal_details() == [detail], seed.msg(journal_details())
    assert detail in out, seed.msg(out)
    found = copies()
    assert len(found) == 1 and found[0].read_bytes() == before_bytes, seed.msg(found)


# ------------------------------------------------------------ AC-2

@pytest.mark.parametrize("order", ["name, email", "email, name"])
def test_ac2_commit_author_replaced_whole(cli, work_dir, seed, order):
    """Заданное `machine.commit_author` заменяется целиком значениями файла; журнал несёт листов было 2 → стало 2.

    Сценарий: слой — запись `<п>` с `commit_author` (прежняя пара) и
    другая запись со своим; файл блока — другие `name` и `email` (в
    прямом или обратном порядке ключей). Команда успешна; разобранное
    поле равно отображению файла, прежних значений в нём нет;
    `merged_author(<п>)` — новая пара, у другой записи — прежняя;
    листья вне пути блока прежние; одна копия — байты прежнего файла;
    журнал и вывод — `machine.commit_author: блок из <аргумент> (листов
    было 2 → стало 2)`.

    Ловит мутацию: заменён только один ключ (прежний `email` остался);
    существующее поле принято за отсутствующее (`было (нет)`); путь принят
    только для заведения поля, замена отказывает; задета другая запись.
    """
    old, new, other_author = seed.author(), seed.author(), seed.author()
    text, name, other = layer(seed, old, other_author)
    write_layers(text)
    before_bytes = local_file().read_bytes()
    before = parsed_layer()
    assert merged_author(name) == old, seed.msg(text)
    block = (author_block(new) if order == "name, email"
             else f"email: {new[1]}\nname: {new[0]}\n")
    arg = block_file(work_dir, "author.yaml", block)
    ok, out = cli("target-set", name, PATH, "--from-file", arg)
    assert ok, seed.msg(out)
    after = parsed_layer()
    got = after["targets"][name]["machine"]["commit_author"]
    assert got == yamlmini.mapping(block), seed.msg(got)
    assert old[0] not in got.values() and old[1] not in got.values(), seed.msg(got)
    assert merged_author(name) == new, seed.msg(out)
    assert merged_author(other) == other_author, seed.msg(out)
    prefix = ("targets", name, "machine", "commit_author")
    assert outside(after, prefix) == outside(before, prefix), seed.msg(out)
    detail = f"{PATH}: блок из {arg} (листов было 2 → стало 2)"
    assert journal_details() == [detail], seed.msg(journal_details())
    assert detail in out, seed.msg(out)
    found = copies()
    assert len(found) == 1 and found[0].read_bytes() == before_bytes, seed.msg(found)


# ------------------------------------------------------------ AC-3

@pytest.mark.parametrize("present, case", [
    (False, "только name"),
    (False, "лишний login"),
    (True, "только name"),
    (True, "лишний login"),
])
def test_ac3_bad_commit_author_shape_refused(cli, work_dir, seed, present, case):
    """Файл блока только с `name` или с лишним ключом `login` — отказ проверки формы `commit_author`, слой побайтно прежний, копии нет.

    Сценарий: слой — запись `<п>` без поля или с заданным полем и другая
    запись; файл блока — только `name` либо `name`, `email` и `login`.
    Код выхода ненулевой, трассировки нет; вывод несёт «нужно {name,
    email}»; байты слоя прежние; копий в `config.LOGS` нет; журнала
    `target-set` нет.

    Ловит мутацию: сверка `merge_local` нового текста не делается для пути
    `machine.*` (неполное поле записано); лишний ключ отброшен молча и
    блок записан; копия создаётся до сверки; отказ без текста проверки
    формы (например, перечнем путей блока — путь не принят).
    """
    author = seed.author()
    text, name, _other = layer(seed, seed.author() if present else None,
                               seed.author())
    write_layers(text)
    before = local_file().read_bytes()
    block = (f"name: {author[0]}\n" if case == "только name"
             else author_block(author) + f"login: {seed.word()}\n")
    arg = block_file(work_dir, "author.yaml", block)
    ok, out = cli("target-set", name, PATH, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    assert SHAPE_REFUSAL in out, seed.msg(out)
    assert journal_details() == [], seed.msg(journal_details())


# ------------------------------------------------------------ AC-4

@pytest.mark.parametrize("path", [
    "machine.submodule_tokens",
    "machine.url",
    "machine.token_slot",
    "machine.commit_author.name",
])
def test_ac4_other_machine_paths_refused_with_paths_list(cli, work_dir, seed, path):
    """Прочие пути `machine.*` с `--from-file` — отказ с перечнем путей блока, где дописан `machine.commit_author`; слой прежний.

    Сценарий: слой — запись `<п>` с `commit_author` и другая запись; файл
    блока — годный блок `name`/`email`; путь — `machine.submodule_tokens`,
    `machine.url`, `machine.token_slot` или `machine.commit_author.name`.
    Код выхода ненулевой; вывод несёт литерал `допустимые пути блока:
    description.test_profile, description.components.<имя>,
    machine.commit_author`; байты слоя прежние, копий нет.

    Ловит мутацию: принят любой путь `machine.*` (или префикс
    `machine.commit_author`), и блок записан; перечень `BLOCK_PATHS` не
    дописан или новый путь вставлен не в конец.
    """
    text, name, _other = layer(seed, seed.author(), None)
    write_layers(text)
    before = local_file().read_bytes()
    arg = block_file(work_dir, "author.yaml", author_block(seed.author()))
    ok, out = cli("target-set", name, path, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    assert PATHS_LITERAL in out, seed.msg(out)
