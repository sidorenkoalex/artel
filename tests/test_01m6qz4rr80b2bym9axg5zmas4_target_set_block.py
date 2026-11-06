"""Форма `target-set <проект> <путь блока> --from-file <файл>`: замена блока `description.test_profile` или компонента `description.components.<имя>` локального слоя целиком из файла, её отказы, копия, журнал; прежние формы `target-set` и справка.

Группа: долгоживущий
Красен до реализации: формы `--from-file` у `target-set` нет — аргумент `--from-file` уходит в прежнюю форму (отказ «вложенное отображение»/«блок компонента, не поле»/`NO_COMPONENT` или «значение — ровно один аргумент»), блок не заменяется, литерала перечня путей блока и строки журнала «блок из <файл>» нет, `TARGET_SET_USAGE` и справка `artel.py` не называют `--from-file`; тесты прежних форм (AC-8) зелены с рождения — они держат прежнее поведение; часть отказных случаев (AC-5, AC-7, AC-11) до реализации зелена тривиально — прежняя форма тоже отказывает, не трогая файл; различающую силу они получают вместе с формой — проверено на временном стабе формы.

Связка, которую держит файл: «диспетчер `artel.main` — команда правки
`target-set` — загрузчик `targets.target` — журнал пульта» в песочнице
`initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`: пути
`config` — `ROOT`, `TARGETS`, `LOGS`, `DB` — во временном каталоге, БД со
схемой). Настоящий локальный слой пульта не читается и не пишется; имена
проектов и значения вымышленные. Команда зовётся как из командной строки:
`sys.argv` подменён, `artel.main()`. Отказ — выход `SystemExit` с
ненулевым кодом. Файл локального слоя — `config.TARGETS.parent / ".artel"
/ "targets.yaml"`; копии — `targets-*.yaml` в `config.LOGS`; записи
журнала — строки `steps` с действием `target-set`.

Файлы блоков лежат в подкаталоге `work/blocks` песочницы; текущий каталог
процесса на время теста — `work` (фикстура `work_dir`, возврат прежнего
каталога в `finally`), относительный аргумент `--from-file` читается от
него.

Слой песочницы записан в той форме, которую пишет пересборка команды
(без строк `#`, строки с `:`/`#` — в кавычках только там, где их ставит
пересборка).

Имена проектов и часть значений — от зерна `random`; зерно печатается и
входит в текст провала.
"""
import os
import random
import re
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, config, projects, store, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
PATHS_LITERAL = ("допустимые пути блока: description.test_profile, "
                 "description.components.<имя>")
PROFILE = "description.test_profile"
TOKENS = "machine." + targets.SUBMODULE_TOKENS_FIELD


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
        return (code in (0, None)), text, code

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


def sections(name: str, *, scopes: bool = True) -> str:
    """Разделы `policy` и `machine` записи в форме пересборки; `scopes` — области гейтов профиля (только у записи с `test_profile`)."""
    return (f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            + (f"      weakening_scope: [tests/**/*.py]\n"
               f"      mutation_claim_scope: [tests/test_*.py]\n" if scopes else "")
            + f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


def profile_record(name: str, seed: Seed) -> str:
    """Запись с `test_profile` раннера `pytest-own`: вложенное `env` из двух ключей."""
    return (f"  {name}:\n    description:\n      base: main\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"        runner: pytest-own\n"
            f"        env:\n          LANG: C\n"
            f"          PYTHONPATH: {seed.word()}\n"
            + sections(name))


def component_lines(comp: str, seed: Seed) -> str:
    """Компонент раннера `pytest-own` с вложенными `env` и `tools` (по два ключа)."""
    return (f"        {comp}:\n"
            f"          command: [python3, -m, pytest]\n"
            f"          runner: pytest-own\n"
            f"          paths: [^{comp}/]\n"
            f"          env:\n            LANG: C\n"
            f"            TZ: {seed.word()}\n"
            f"          tools:\n            uv: \"0.4\"\n"
            f"            ruff: \"0.{seed.rng.randrange(1, 9)}\"\n")


def components_record(name: str, comps: list, seed: Seed) -> str:
    return (f"  {name}:\n    description:\n      base: main\n"
            f"      components:\n"
            + "".join(component_lines(comp, seed) for comp in comps)
            + sections(name, scopes=False))


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


def block_file(work: Path, name: str, text: str) -> str:
    """Файл блока в `work/blocks`; аргумент `--from-file` — относительный, через `..`."""
    (work / "blocks" / name).write_text(text, encoding="utf-8")
    return f"./blocks/../blocks/{name}"


def compose_block(seed: Seed, *, mount: bool = True) -> str:
    """Блок `test_profile` раннера `compose`: все поля `COMPOSE_REQUIRED`, `workdir`, `long_lived_*` под левой частью `compose_mount`, `report: junit-xml`."""
    lines = ["runner: compose",
             "compose_file: deploy/compose.yaml",
             f"compose_service: s{seed.word()}",
             "compose_env_file: deploy/test.env",
             "compose_env_template: deploy/test.env.example"]
    if mount:
        lines.append('compose_mount: "src:/work"')
    lines += ["workdir: src",
              "long_lived_dir: src/tests",
              "long_lived_name: test_<id>_<name>.py",
              "report: junit-xml"]
    return "".join(line + "\n" for line in lines)


def profile_layer(seed: Seed) -> tuple:
    """(текст слоя, проект, другая запись): запись с профилем `pytest-own` и другая запись; порядок — от зерна."""
    name, other = seed.name(), seed.name()
    parts = [profile_record(name, seed), profile_record(other, seed)]
    seed.rng.shuffle(parts)
    return "targets:\n" + "".join(parts), name, other


def components_layer(seed: Seed, comps: list) -> tuple:
    """(текст слоя, проект): запись с компонентами `comps` и запись с профилем."""
    name, other = seed.name(), seed.name()
    parts = [components_record(name, comps, seed), profile_record(other, seed)]
    seed.rng.shuffle(parts)
    return "targets:\n" + "".join(parts), name


def component_block(seed: Seed, comp: str) -> str:
    """Блок компонента `pytest-own` — иной, чем в слое: другая команда, `env` из двух ключей, без `tools`."""
    return (f"command: [python3, -m, pytest, -q]\n"
            f"runner: pytest-own\n"
            f"paths: [^{comp}/]\n"
            f"env:\n  LANG: C.UTF-8\n  HOME_{seed.word().upper()}: x\n")


def refusal_kept(ok: bool, out: str, before: bytes, seed: Seed) -> None:
    assert not ok, seed.msg(out)
    assert "Traceback" not in out, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)
    assert copies() == [], seed.msg(out)


# ------------------------------------------------------------ AC-1

def test_ac1_profile_block_replaced_from_relative_file(cli, work_dir, seed):
    """Блок `test_profile` `pytest-own` заменяется блоком `compose` из файла, заданного относительным путём через `..` от текущего каталога.

    Сценарий: слой — запись `<п>` с профилем `pytest-own` (вложенное `env`
    из двух ключей) и другая запись. Текущий каталог — `work` песочницы
    (не `config.ROOT` и не каталог слоя); файл блока — только в
    `work/blocks`. `target-set <п> description.test_profile --from-file
    ./blocks/../blocks/profile.yaml` успешна. Разобранный блок слоя равен
    отображению файла (полей `command`, `env` прежнего профиля нет);
    `targets.target(<п>)` сводится, `runner` — `compose`; листья слоя вне
    `targets.<п>.description.test_profile` прежние; одна копия — байты
    прежнего файла; журнал и вывод — `description.test_profile: блок из
    ./blocks/../blocks/profile.yaml (листов было <N> → стало <M>)`, где N и M
    — листья блока до и после (список — один лист), N ≠ число ключей
    верхнего уровня прежнего блока.

    Ловит мутацию: N/M считаются числом ключей верхнего уровня (`было 5`
    вместо `6`); путь `--from-file` в журнале разрешён `resolve`/`absolute`;
    файл читается от `config.ROOT` или каталога слоя (файл не найден —
    отказ); блок сливается с прежним, а не заменяется (`env` остался);
    правка задевает другую запись или другой раздел.
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    before_bytes = local_file().read_bytes()
    before = parsed_layer()
    assert Path.cwd().resolve() == work_dir.resolve()
    assert Path.cwd().resolve() not in (config.ROOT.resolve(),
                                        config.TARGETS.parent.resolve(),
                                        local_file().parent.resolve())
    block = compose_block(seed)
    arg = block_file(work_dir, "profile.yaml", block)
    ok, out, _code = cli("target-set", name, PROFILE, "--from-file", arg)
    assert ok, seed.msg(out)
    after = parsed_layer()
    want = yamlmini.mapping(block)
    got = after["targets"][name]["description"]["test_profile"]
    assert got == want, seed.msg((got, want))
    assert "env" not in got and "command" not in got, seed.msg(got)
    assert targets.target(name)["test_profile"]["runner"] == "compose", seed.msg(out)
    prefix = ("targets", name, "description", "test_profile")
    assert outside(after, prefix) == outside(before, prefix), seed.msg(out)
    old_block = before["targets"][name]["description"]["test_profile"]
    n, m = len(leaves(old_block)), len(leaves(want))
    assert n != len(old_block), seed.msg(old_block)
    detail = f"{PROFILE}: блок из {arg} (листов было {n} → стало {m})"
    assert journal_details() == [detail], seed.msg(journal_details())
    assert detail in out, seed.msg(out)
    found = copies()
    assert len(found) == 1 and found[0].read_bytes() == before_bytes, seed.msg(found)


# ------------------------------------------------------------ AC-2

def test_ac2_compose_without_mount_refused(cli, work_dir, seed):
    """Тот же блок `compose` без `compose_mount` — отказ проверки `compose` про отсутствующее поле, слой побайтно прежний, копии нет.

    Сценарий: слой AC-1; файл блока без строки `compose_mount`. Код выхода
    ненулевой; текст отказа несёт «нет поля» и `compose_mount`; байты слоя
    прежние; копий в `config.LOGS` нет.

    Ловит мутацию: сведение `merge_local` нового текста не проверяется
    (блок записан с неполной записью `compose`); копия создаётся до сверки;
    отказ без причины проверки `compose`.
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    before = local_file().read_bytes()
    arg = block_file(work_dir, "profile.yaml", compose_block(seed, mount=False))
    ok, out, _code = cli("target-set", name, PROFILE, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    assert "нет поля" in out and "compose_mount" in out, seed.msg(out)


# ------------------------------------------------------------ AC-3

def test_ac3_component_added_and_replaced_in_place(cli, work_dir, seed):
    """Новый компонент добавляется в конец, существующий средний заменяется целиком на своём месте.

    Сценарий: слой — запись `<п>` с тремя компонентами `pytest-own`
    (вложенные `env` и `tools`) и запись с профилем; текущий каталог —
    `work`. Шаг 1: `--from-file ./blocks/../blocks/new.yaml` на
    `description.components.<новое>` — компонент равен файлу, порядок —
    прежний список и новое имя в конце, листья вне пути блока прежние,
    журнал и вывод — `description.components.<новое>: блок из <аргумент>
    (листов было (нет) → стало <M>)`. Шаг 2: `--from-file` на средний
    компонент — он равен файлу (`tools` снят), порядок компонентов прежний,
    листья вне пути прежние, деталь — `… (листов было <N> → стало <M>)`,
    N ≠ числу ключей верхнего уровня прежнего блока.

    Ловит мутацию: заменённый компонент снимается и вставляется заново
    (уходит в конец); новый компонент вставлен не в конец; поля прежнего
    компонента, которых нет в файле, остались (слияние); N/M — число
    ключей верхнего уровня; путь `--from-file` разрешён в журнале; файл
    читается от `config.ROOT` или каталога слоя; задет соседний компонент.
    """
    comps = [f"a{seed.word(4)}", f"b{seed.word(4)}", f"c{seed.word(4)}"]
    text, name = components_layer(seed, comps)
    write_layers(text)
    assert Path.cwd().resolve() not in (config.ROOT.resolve(),
                                        config.TARGETS.parent.resolve(),
                                        local_file().parent.resolve())
    new = f"n{seed.word(4)}"
    new_block = (f"command: [python3, -m, pytest]\nrunner: pytest-own\n"
                 f"paths: [^{new}/]\ntools:\n  uv: \"0.5\"\n")
    steps = [(new, "new.yaml", new_block, [*comps, new]),
             (comps[1], "mid.yaml", component_block(seed, comps[1]), [*comps, new])]
    details = []
    for comp, file_name, block, order in steps:
        before = parsed_layer()
        arg = block_file(work_dir, file_name, block)
        path = f"description.components.{comp}"
        ok, out, _code = cli("target-set", name, path, "--from-file", arg)
        assert ok, seed.msg((path, out))
        after = parsed_layer()
        got_comps = after["targets"][name]["description"]["components"]
        want = yamlmini.mapping(block)
        assert got_comps[comp] == want, seed.msg((got_comps[comp], want))
        assert list(got_comps) == order, seed.msg(list(got_comps))
        prefix = ("targets", name, "description", "components", comp)
        assert outside(after, prefix) == outside(before, prefix), seed.msg(path)
        old_comps = before["targets"][name]["description"]["components"]
        if comp in old_comps:
            old_block = old_comps[comp]
            n = len(leaves(old_block))
            assert n != len(old_block), seed.msg(old_block)
            was = str(n)
        else:
            was = "(нет)"
        detail = f"{path}: блок из {arg} (листов было {was} → стало {len(leaves(want))})"
        details.append(detail)
        assert detail in out, seed.msg(out)
        assert journal_details() == details, seed.msg(journal_details())
    assert "tools" not in parsed_layer()["targets"][name]["description"]["components"][comps[1]]


# ------------------------------------------------------------ AC-4

@pytest.mark.parametrize("path, unwritable", [
    ("policy.no_paths", False),
    ("description.test_profile.runner", False),
    (TOKENS, False),
    ("description.components.{existing}.runner", False),
    ("description.components.", True),
    ("description.components.a:b", True),
    ("description.components.#x", True),
])
def test_ac4_wrong_block_path_refused_with_paths_list(cli, work_dir, seed, path, unwritable):
    """Путь вне двух видов блока или с неписуемым именем компонента — отказ с литералом перечня видов пути, слой прежний.

    Сценарий: слой — запись с тремя компонентами; годный файл блока
    компонента; путь — `policy.no_paths`, `description.test_profile.runner`,
    `machine.submodule_tokens`, `description.components.<существующий>.runner`,
    `description.components.`, `description.components.a:b`,
    `description.components.#x`. Код выхода ненулевой; вывод несёт литерал
    `допустимые пути блока: description.test_profile,
    description.components.<имя>`; для неписуемых имён в выводе нет «не
    записать»; байты слоя прежние, копий нет, компонента с точкой в имени
    нет.

    Ловит мутацию: путь из четырёх сегментов принят и компонент
    `<к>.runner` заведён (`_render` пропускает точку); неписуемое имя
    отвергается только сборкой `_rendered` («не записать») или пишется;
    `policy.*`/`machine.*` приняты как путь блока; отказ без перечня.
    """
    comps = [f"a{seed.word(4)}", f"b{seed.word(4)}", f"c{seed.word(4)}"]
    text, name = components_layer(seed, comps)
    write_layers(text)
    before = local_file().read_bytes()
    arg = block_file(work_dir, "comp.yaml", component_block(seed, "zz"))
    path = path.replace("{existing}", comps[1])
    ok, out, _code = cli("target-set", name, path, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    assert PATHS_LITERAL in out, seed.msg(out)
    if unwritable:
        assert "не записать" not in out, seed.msg(out)
    got = parsed_layer()["targets"][name]["description"]["components"]
    assert not [comp for comp in got if "." in comp], seed.msg(list(got))


# ------------------------------------------------------------ AC-5

def duplicate_top(seed: Seed) -> tuple:
    """Блок `compose` с повтором `compose_service` на верхнем уровне: (текст, ключ, строка второго вхождения)."""
    lines = compose_block(seed).splitlines()
    lines.insert(6, f"compose_service: t{seed.word()}")
    return "\n".join(lines) + "\n", "compose_service", 7


def duplicate_nested(seed: Seed) -> tuple:
    """Блок компонента с повтором `LANG` во вложенном `env`: (текст, ключ, строка второго вхождения)."""
    text = (f"command: [python3, -m, pytest]\nrunner: pytest-own\n"
            f"paths: [^zz/]\nenv:\n  LANG: C\n  TZ: {seed.word()}\n"
            f"  LANG: C.UTF-8\n")
    return text, "LANG", 7


@pytest.mark.parametrize("case", [
    "ошибка разбора", "пустой текст", "только пустые строки", "список",
    "строка-комментарий", "хвостовой комментарий", "несуществующий",
    "не UTF-8", "значение не записать",
])
def test_ac5_bad_block_file_refused(cli, work_dir, seed, case):
    """Негодный файл блока `test_profile` — отказ с причиной, слой побайтно прежний, копии нет.

    Сценарий: слой AC-1; файл — годный блок `compose` с дефектом по
    случаю: строка с неожиданным отступом; пустой текст; только пустые
    строки (отказ со словом «пуст»); блочный список `- a` (причина разбора
    `yamlmini`); строка `# <слово>` целиком; `runner: compose  # x`;
    файла нет; байты не UTF-8 (отказ текстом, не трассировкой); значение
    `compose_service` с обеими кавычками (отказ «не записать»). Код выхода
    ненулевой, трассировки нет, байты слоя прежние, копий нет.

    Ловит мутацию: комментарий файла не проверяется — `yamlmini` молча
    отбрасывает его и блок записан; пустой файл отказывает без слова
    «пуст» или после сборки; не UTF-8 даёт `UnicodeDecodeError`
    трассировкой; ошибка разбора или неписуемое значение проходят мимо
    отказа; копия создаётся до отказа.
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    before = local_file().read_bytes()
    good = compose_block(seed)
    target = work_dir / "blocks" / "bad.yaml"
    arg = "./blocks/bad.yaml"
    if case == "ошибка разбора":
        target.write_text(good.replace("workdir: src\n", "workdir: src\n   x: y\n"),
                          encoding="utf-8")
    elif case == "пустой текст":
        target.write_text("", encoding="utf-8")
    elif case == "только пустые строки":
        target.write_text("\n  \n\n", encoding="utf-8")
    elif case == "список":
        target.write_text("- runner\n- compose\n", encoding="utf-8")
    elif case == "строка-комментарий":
        lines = good.splitlines(keepends=True)
        lines.insert(2, f"# {seed.word()}\n")
        target.write_text("".join(lines), encoding="utf-8")
    elif case == "хвостовой комментарий":
        target.write_text(good.replace("runner: compose\n", "runner: compose  # x\n"),
                          encoding="utf-8")
    elif case == "несуществующий":
        arg = "./blocks/missing.yaml"
    elif case == "не UTF-8":
        target.write_bytes(good.encode("utf-8") + b"compose_env_template: \xff\xfe\n")
    elif case == "значение не записать":
        target.write_text(good.replace("compose_service: ", "compose_service: a\"b'"),
                          encoding="utf-8")
    ok, out, code = cli("target-set", name, PROFILE, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    assert isinstance(code, str), seed.msg(out)
    if case in ("пустой текст", "только пустые строки"):
        assert "пуст" in out, seed.msg(out)
    if case == "значение не записать":
        assert "не записать" in out, seed.msg(out)
    if case == "список":
        assert "блочные списки" in out, seed.msg(out)


@pytest.mark.parametrize("kind", ["верхний уровень", "вложенное отображение"])
def test_ac5_duplicate_key_refused_with_line(cli, work_dir, seed, kind):
    """Повтор ключа на одном уровне файла блока — отказ с именем ключа и номером строки второго вхождения.

    Сценарий: повтор `compose_service` верхнего уровня в блоке `compose`
    (второе вхождение — строка 7) на записи с профилем, либо повтор `LANG`
    во вложенном `env` блока компонента `pytest-own` (строка 7) на записи
    с компонентами. Без проверки повтора `yamlmini` оставил бы последнее
    значение, и блок был бы годен. Код выхода ненулевой; вывод несёт имя
    ключа и число 7 отдельным словом; байты слоя прежние, копий нет.

    Ловит мутацию: повтор ключа не проверяется (последнее значение молча
    записано); проверяется только верхний уровень; номер строки — первого
    вхождения или счёт с 0.
    """
    if kind == "верхний уровень":
        text, name, _other = profile_layer(seed)
        path = PROFILE
        block, key, line = duplicate_top(seed)
    else:
        comps = [f"a{seed.word(4)}", f"b{seed.word(4)}", f"c{seed.word(4)}"]
        text, name = components_layer(seed, comps)
        path = f"description.components.{comps[1]}"
        block, key, line = duplicate_nested(seed)
    write_layers(text)
    before = local_file().read_bytes()
    assert block.splitlines()[line - 1].strip().startswith(f"{key}:"), block
    arg = block_file(work_dir, "dup.yaml", block)
    ok, out, _code = cli("target-set", name, path, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    assert key in out, seed.msg(out)
    assert re.search(rf"(?<![\w./-]){line}(?![\w./-])", out), seed.msg(out)


def test_ac5_same_key_under_different_parents_accepted(cli, work_dir, seed):
    """Одно имя ключа у разных родительских отображений — не повтор: команда проходит, блок слоя равен файлу.

    Сценарий: слой с тремя компонентами `pytest-own`; файл блока среднего
    компонента — `runner` верхнего уровня и `runner` внутри `env`, `LANG`
    и в `env`, и в `tools`. Команда успешна; разобранный компонент слоя
    равен отображению файла.

    Ловит мутацию: отказ при любом повторе имени ключа в файле без учёта
    родителя (`runner` у блока и у `env`, `LANG` у `env` и `tools`).
    """
    comps = [f"a{seed.word(4)}", f"b{seed.word(4)}", f"c{seed.word(4)}"]
    text, name = components_layer(seed, comps)
    write_layers(text)
    block = (f"runner: pytest-own\ncommand: [python3, -m, pytest]\n"
             f"paths: [^{comps[1]}/]\nenv:\n  runner: {seed.word()}\n  LANG: C\n"
             f"tools:\n  LANG: \"1.0\"\n")
    arg = block_file(work_dir, "same.yaml", block)
    path = f"description.components.{comps[1]}"
    ok, out, _code = cli("target-set", name, path, "--from-file", arg)
    assert ok, seed.msg(out)
    got = parsed_layer()["targets"][name]["description"]["components"][comps[1]]
    assert got == yamlmini.mapping(block), seed.msg(got)


# ------------------------------------------------------------ AC-6

def test_ac6_repeat_reports_no_changes(cli, work_dir, seed):
    """Повтор той же команды на уже применённом файле — «без изменений», новой копии и записи журнала нет.

    Сценарий: слой AC-1; команда AC-1 успешна (одна копия, одна запись
    журнала); тот же вызов повторно успешен, вывод несёт «без изменений»,
    копий по-прежнему одна, записей журнала одна, байты слоя прежние.

    Ловит мутацию: сравнение блока с файлом перед записью снято — повтор
    переписывает слой, создаёт копию и журналирует «было M → стало M».
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    arg = block_file(work_dir, "profile.yaml", compose_block(seed))
    ok, out, _code = cli("target-set", name, PROFILE, "--from-file", arg)
    assert ok, seed.msg(out)
    applied = local_file().read_bytes()
    ok, out, _code = cli("target-set", name, PROFILE, "--from-file", arg)
    assert ok, seed.msg(out)
    assert "без изменений" in out, seed.msg(out)
    assert len(copies()) == 1, seed.msg(copies())
    assert len(journal_details()) == 1, seed.msg(journal_details())
    assert local_file().read_bytes() == applied, seed.msg(out)


# ------------------------------------------------------------ AC-7

@pytest.mark.parametrize("tail", [[], ["{file}", "{extra}"]])
def test_ac7_from_file_wrong_arg_count_refused_with_usage(cli, work_dir, seed, tail):
    """`--from-file` третьим аргументом без файла или с лишним аргументом — отказ со строкой `TARGET_SET_USAGE`, слой прежний.

    Сценарий: слой AC-1, годный файл блока; `target-set <п>
    description.test_profile --from-file` и `… --from-file <файл>
    <лишний>`. Код выхода ненулевой; вывод несёт
    `projects.TARGET_SET_USAGE`; байты слоя прежние, копий нет.

    Ловит мутацию: лишний аргумент молча отброшен и блок записан;
    `--from-file` без файла уходит в прежнюю форму со значением
    `--from-file`; отказ без строки формы вызова.
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    before = local_file().read_bytes()
    arg = block_file(work_dir, "profile.yaml", compose_block(seed))
    argv = [part.replace("{file}", arg).replace("{extra}", "x" + seed.word())
            for part in tail]
    ok, out, _code = cli("target-set", name, PROFILE, "--from-file", *argv)
    refusal_kept(ok, out, before, seed)
    assert projects.TARGET_SET_USAGE in out, seed.msg(out)


# ------------------------------------------------------------ AC-8

def test_ac8_value_key_and_show_forms_unchanged(cli, seed):
    """Прежние формы значения, `--key`, `--drop-key`, `--show` пишут и выводят как прежде.

    Сценарий: слой AC-1. `target-set <п> policy.sandbox <слово>` — деталь
    `policy.sandbox: (нет) → <слово>`; `--key <к> <слот>` и `--drop-key <к>`
    на `machine.submodule_tokens` — детали `…[<к>]: (нет) → <слот>` и
    `…[<к>]: <слот> → (нет)`; три копии; журнал — эти три строки;
    `target-set --show <п> description.test_profile` печатает блок с
    отступом два пробела — ровно строки профиля слоя.

    Ловит мутацию: разбор новой формы перехватывает прежние (четвёртый
    аргумент или путь `description.*` считается блоком) — прежняя правка
    отказывает, журналирует «блок из …» или `--show` печатает иначе.
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    value, key, slot = "v" + seed.word(), "k" + seed.word(), "s" + seed.word()
    label = f"{TOKENS}[{key}]"
    steps = [(["policy.sandbox", value], f"policy.sandbox: (нет) → {value}"),
             ([TOKENS, "--key", key, slot], f"{label}: (нет) → {slot}"),
             ([TOKENS, "--drop-key", key], f"{label}: {slot} → (нет)")]
    for argv, detail in steps:
        ok, out, _code = cli("target-set", name, *argv)
        assert ok, seed.msg((argv, out))
        assert f"target-set: {detail}" in out, seed.msg(out)
    assert journal_details() == [detail for _argv, detail in steps], seed.msg(journal_details())
    assert len(copies()) == 3, seed.msg(copies())
    record = local_file().read_text(encoding="utf-8").split(f"  {name}:\n", 1)[1]
    block = record.split("      test_profile:\n", 1)[1].split("    policy:\n", 1)[0]
    want = "description.test_profile:\n" + "".join(
        line[6:] + "\n" for line in block.splitlines())
    ok, out, _code = cli("target-set", "--show", name, PROFILE)
    assert ok, seed.msg(out)
    assert want in out, seed.msg((want, out))


def test_ac8_old_refusals_unchanged(cli, seed):
    """Отказы прежней формы «вложенное отображение», `NO_COMPONENT` и «значение — ровно один аргумент» — побайтно прежние тексты.

    Сценарий: слой с компонентами и записью с профилем.
    `target-set <п> description.test_profile.runner compose` — текст
    «target-set: путь description.test_profile.runner ведёт во вложенное
    отображение — его поля командой не правятся; файл не записан»;
    `target-set <к> description.components.<нет>.runner pytest-own` —
    «target-set: компонента <нет> нет в записи; добавление компонентов не
    входит; файл не записан»; `target-set <п> policy.sandbox a b` — прежний
    текст про один аргумент. Байты слоя прежние.

    Ловит мутацию: путь `description.test_profile.<поле>` или компонента
    прежней формы переведён на новую форму или отказ переписан (перечень
    путей блока, иной текст); отсутствующий компонент заводится.
    """
    comps = [f"a{seed.word(4)}", f"b{seed.word(4)}", f"c{seed.word(4)}"]
    text, comp_name = components_layer(seed, comps)
    profile_name = next(entry for entry in yamlmini.mapping(text)["targets"]
                        if entry != comp_name)
    write_layers(text)
    before = local_file().read_bytes()
    missing = "m" + seed.word()
    cases = [
        ([profile_name, "description.test_profile.runner", "compose"],
         "target-set: путь description.test_profile.runner ведёт во вложенное "
         "отображение — его поля командой не правятся; файл не записан"),
        ([comp_name, f"description.components.{missing}.runner", "pytest-own"],
         f"target-set: компонента {missing} нет в записи; добавление "
         f"компонентов не входит; файл не записан"),
        ([profile_name, "policy.sandbox", "a", "b"],
         "target-set: значение — ровно один аргумент, получено 2: a b — возьми "
         "значение в кавычки, например '[a, b]'; файл не записан"),
    ]
    for argv, refusal in cases:
        ok, out, code = cli("target-set", *argv)
        assert not ok, seed.msg(out)
        assert code == refusal, seed.msg((argv, code))
        assert local_file().read_bytes() == before, seed.msg(out)


@pytest.mark.parametrize("argv, head", [
    (["{p}", "policy.sandbox"], "target-set: нужны проект, путь поля и значение"),
    (["{p}", TOKENS, "--key", "k"], "target-set: --key — неверное число аргументов"),
    (["{p}", TOKENS, "--drop-key"], "target-set: --drop-key — неверное число аргументов"),
    (["--show"], "target-set --show: нужен проект и, возможно, путь"),
    (["--show", "{p}", "a", "b"], "target-set --show: нужен проект и, возможно, путь"),
])
def test_ac8_usage_tail_refusals(cli, seed, argv, head):
    """Отказы прежних форм с вшитой строкой формы вызова: текст без хвоста прежний, хвост — `projects.TARGET_SET_USAGE`.

    Сценарий: слой AC-1; неполная форма значения, неверное число
    аргументов `--key`/`--drop-key`, неверные аргументы `--show`. Текст
    отказа — `<прежняя голова>\\n<TARGET_SET_USAGE>`: голова побайтно
    прежняя, хвост равен текущему `projects.TARGET_SET_USAGE`; байты слоя
    прежние.

    Ловит мутацию: голова отказа переписана при дополнении справки;
    хвост — устаревшая копия строки формы вызова, а не
    `TARGET_SET_USAGE`; неполная форма уходит в новую форму.
    """
    text, name, _other = profile_layer(seed)
    write_layers(text)
    before = local_file().read_bytes()
    ok, out, code = cli("target-set", *[part.replace("{p}", name) for part in argv])
    assert not ok, seed.msg(out)
    assert isinstance(code, str), seed.msg(out)
    got_head, sep, tail = code.partition("\n")
    assert sep and got_head == head, seed.msg(code)
    assert tail == projects.TARGET_SET_USAGE, seed.msg(code)
    assert local_file().read_bytes() == before, seed.msg(out)


# ------------------------------------------------------------ AC-9

def help_block() -> list:
    """Строки блока «Команды:» справки `artel.py` до первой пустой строки."""
    lines = artel.__doc__.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "Команды:")
    block = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        block.append(line)
    return block


def test_ac9_usage_and_help_name_from_file():
    """`TARGET_SET_USAGE` и справка `artel.py` называют форму `--from-file` альтернативой, начинающейся словом `target-set`.

    Сценарий: каждая альтернатива `TARGET_SET_USAGE` (разделитель ` | `)
    начинается `target-set`, одна из них несёт `--from-file`. В блоке
    «Команды:» справки строки с отступом ровно два пробела — начала
    команд, прочие — продолжения с отступом больше двух; альтернатива
    справки (команда со всеми продолжениями, разбитая по `|`), несущая
    `--from-file`, начинается словом `target-set`.

    Ловит мутацию: новая форма не дописана в `TARGET_SET_USAGE` или в
    справку; продолжение справки с отступом два пробела (слово `--from-file`
    или `<проект>` читается как команда); альтернатива без слова
    `target-set`.
    """
    usage = [part.strip() for part in projects.TARGET_SET_USAGE.split(" | ")]
    assert all(part.split()[0] == "target-set" for part in usage), usage
    assert any("--from-file" in part for part in usage), usage
    commands = []
    for line in help_block():
        indent = len(line) - len(line.lstrip(" "))
        assert indent >= 2, line
        if indent == 2:
            commands.append(line.strip())
        else:
            commands[-1] += " " + line.strip()
    alternatives = [part.strip() for command in commands
                    for part in command.split("|") if part.strip()]
    named = [part for part in alternatives if "--from-file" in part]
    assert named, commands
    assert all(part.split()[0] == "target-set" for part in named), named


# ------------------------------------------------------------ AC-11

@pytest.mark.parametrize("case", ["проект artel", "записи нет", "строка с #",
                                  "журнал недоступен"])
def test_ac11_load_refusals_hold_for_from_file(cli, work_dir, seed, case):
    """Отказы загрузки слоя и недоступного журнала действуют для `--from-file`: слой побайтно прежний, копии нет.

    Сценарий: слой AC-1 и годный файл блока `compose` (отличается от
    текущего блока); по случаю — проект `config.DEFAULT_TARGET`,
    незнакомое имя проекта, строка `# <слово>` в начале слоя или удалённая
    БД пульта (`store.db_usable()` ложно). Код выхода ненулевой; байты
    слоя прежние; копий нет; у недоступного журнала текст несёт
    `projects.NO_JOURNAL`.

    Ловит мутацию: ветка новой формы минует `_target_set_load` (запись
    артели или новая запись заводится, пересборка стирает строку `#`) или
    проверку журнала (слой записан, а журнал нет); копия до отказа.
    """
    text, name, _other = profile_layer(seed)
    if case == "проект artel":
        name = config.DEFAULT_TARGET
    elif case == "записи нет":
        name = seed.name()
    elif case == "строка с #":
        text = f"# {seed.word()}\n" + text
    write_layers(text)
    if case == "журнал недоступен":
        config.DB.unlink()
        assert not store.db_usable()
    before = local_file().read_bytes()
    arg = block_file(work_dir, "profile.yaml", compose_block(seed))
    ok, out, _code = cli("target-set", name, PROFILE, "--from-file", arg)
    refusal_kept(ok, out, before, seed)
    if case == "журнал недоступен":
        assert projects.NO_JOURNAL in out, seed.msg(out)
