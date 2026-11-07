"""Поле `policy.mr_title_template` локального слоя: проверка значения при загрузке записи и запись командой `target-set`.

Группа: долгоживущий
Красен до реализации: поля `mr_title_template` нет в `targets.LOCAL_FIELDS["policy"]` — загрузка любой записи с ним отказывает «неизвестное поле», а `target-set` — «поля mr_title_template нет в policy», без формы отказа `_check_delivery` и без записи файла.

Связка, которую держат методы `target-set`: «диспетчер `artel.main` —
команда `target-set` — загрузчик `targets.target` — копия прежнего файла в
`config.LOGS`» в песочнице `initialized_tmp_root` (пути `config` во
временном каталоге, БД после `init`). Методы загрузки — без команды: запись
кладётся в файл локального слоя песочницы (`targets.local_path()`) и
читается `targets.target`. Настоящий локальный слой пульта не читается и не
пишется; имена проектов и систем ссылок вымышленные и порождаются `random`,
зерно печатается и входит в текст провала.

Провалидировано временным стабом (удалён, не закоммичен): поле в
`LOCAL_FIELDS["policy"]` и `DELIVERY_POLICY_FIELDS`, проверка в
`_check_delivery` по образцу `branch_template` — все методы зелёные.
"""
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
FIELD = "policy.mr_title_template"
FIELD_REFUSAL = f"поле '{FIELD}'"
UNKNOWN_FIELD = "неизвестное поле"


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


def record(name: str, policy: str = "") -> str:
    """Запись в трёх разделах в форме пересборки `target-set`; `policy` — добавочные строки раздела `policy`."""
    return (f"  {name}:\n"
            f"    description:\n      base: {config.MAIN_BRANCH}\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"{policy}"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


def write_layers(local_text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_text, encoding="utf-8")


def policy_lines(system: str | None, template: str | None) -> str:
    """Строки `ref_required` и `mr_title_template` раздела `policy` (значение шаблона — в двойных кавычках)."""
    text = f"      ref_required: {system}\n" if system else ""
    if template is not None:
        text += f'      mr_title_template: "{template}"\n'
    return text


def copies() -> list:
    if not config.LOGS.is_dir():
        return []
    return sorted(config.LOGS.glob("targets-*.yaml"))


def refusal_on_load(name: str) -> str:
    """Текст отказа `targets.target(name)`; отказа нет — пустая строка."""
    try:
        targets.target(name)
    except targets.TargetsError as exc:
        return str(exc)
    return ""


# ------------------------------------------------------------ AC-3

@pytest.mark.parametrize("shape", ["{foo}", "{ref}: {foo}", "{{w}}: {title}",
                                   "{id} {{w}}"])
def test_ac3_unknown_placeholder_refused_with_field_name(initialized_tmp_root,
                                                         seed, shape):
    """Шаблон с неизвестной подстановкой — отказ загрузки записи в форме `_check_delivery` с полным именем поля.

    Сценарий: локальный слой с записью проекта (`ref_required` задан) и
    `policy.mr_title_template` вида `{foo}`, `{ref}: {foo}`, `{<слово>}:
    {title}`, `{id} {<слово>}` — неизвестная подстановка одна или рядом с
    допустимыми. `targets.target(<проект>)` отказывает `TargetsError`,
    текст которого несёт `поле 'policy.mr_title_template'` и не несёт
    «неизвестное поле».

    Ловит мутацию: неизвестная подстановка рядом с допустимыми не
    замечена (проверяется только наличие хотя бы одной из `{id}`, `{ref}`,
    `{title}`) — запись загружается без отказа; либо поле не заведено в
    `LOCAL_FIELDS["policy"]` — отказ «неизвестное поле»; либо отказ без
    имени раздела (`поле 'mr_title_template'`).
    """
    name = "p" + seed.word()
    template = shape.replace("{w}", "x" + seed.word())
    write_layers("targets:\n" + record(name, policy_lines("tracker", template)))
    text = refusal_on_load(name)
    assert FIELD_REFUSAL in text, seed.msg((template, text))
    assert UNKNOWN_FIELD not in text, seed.msg((template, text))


# ------------------------------------------------------------ AC-4

@pytest.mark.parametrize("system", ["tracker", None])
def test_ac4_empty_template_refused_with_field_name(initialized_tmp_root,
                                                    seed, system):
    """Пустая строка шаблона — отказ загрузки записи в форме `_check_delivery` с полным именем поля.

    Сценарий: запись проекта с `policy.mr_title_template: ""` (с
    `ref_required` и без). `targets.target(<проект>)` отказывает, текст
    несёт `поле 'policy.mr_title_template'` и не несёт «неизвестное поле».

    Ловит мутацию: проверка непустоты снята — пустой шаблон проходит
    проверку подстановок (в нём нет `{`), запись загружается, и заголовок
    MR стал бы пустым; либо пустое значение молча заменяется умолчанием.
    """
    name = "p" + seed.word()
    system = None if system is None else system + seed.word(3)
    write_layers("targets:\n" + record(name, policy_lines(system, "")))
    text = refusal_on_load(name)
    assert FIELD_REFUSAL in text, seed.msg(text)
    assert UNKNOWN_FIELD not in text, seed.msg(text)


# ------------------------------------------------------------ AC-5

@pytest.mark.parametrize("shape", ["{ref}: {title}", "{id} {ref}",
                                   "{w}-{ref}"])
def test_ac5_ref_without_ref_required_refused(initialized_tmp_root, seed, shape):
    """`{ref}` в шаблоне записи без `policy.ref_required` — отказ загрузки в форме `_check_delivery` с полным именем поля.

    Сценарий: запись без `ref_required`, шаблон с `{ref}` в разных
    позициях. `targets.target(<проект>)` отказывает, текст несёт
    `поле 'policy.mr_title_template'` и не несёт «неизвестное поле».
    Контроль: тот же шаблон в записи с `ref_required: <система>`
    загружается без отказа — отказ вызван именно отсутствием
    `ref_required`.

    Ловит мутацию: связь `{ref}` с `ref_required` не проверяется — запись
    без системы ссылок загружается, и заголовок по шаблону всегда шёл бы
    с пустым ключом; либо `{ref}` отвергается всегда (контроль с
    `ref_required` тоже отказывает).
    """
    name = "p" + seed.word()
    template = shape.replace("{w}", seed.word())
    write_layers("targets:\n" + record(name, policy_lines(None, template)))
    text = refusal_on_load(name)
    assert FIELD_REFUSAL in text, seed.msg((template, text))
    assert UNKNOWN_FIELD not in text, seed.msg((template, text))
    write_layers("targets:\n" + record(
        name, policy_lines("sys" + seed.word(3), template)))
    assert refusal_on_load(name) == "", seed.msg(refusal_on_load(name))


# ------------------------------------------------------------ AC-7

@pytest.mark.parametrize("value", ["{ref}: {title}", "{ref} {w}: {title}"])
def test_ac7_target_set_writes_field_and_keeps_copy(cli, seed, value):
    """`target-set <проект> policy.mr_title_template "{ref}: {title}"` пишет поле в локальный слой и кладёт копию прежнего файла в `config.LOGS`.

    Сценарий: локальный слой — проект с `ref_required` и без поля
    шаблона, рядом другая запись; `target-set <проект>
    policy.mr_title_template <значение>` успешна. В разобранном файле слоя
    у проекта `policy.mr_title_template` равно значению; запись
    загружается `targets.target` без отказа; в `config.LOGS` появилась
    копия `targets-*.yaml`, байты которой равны файлу до команды.

    Ловит мутацию: поле не заведено в `LOCAL_FIELDS["policy"]` — команда
    отказывает «поля нет в policy»; значение с `{`/`: ` пишется без
    кавычек и разбирается иначе (отображение вместо строки); копия не
    создаётся или создаётся уже с новыми байтами.
    """
    name, other = "p" + seed.word(), "q" + seed.word()
    template = value.replace("{w}", seed.word())
    parts = [record(name, policy_lines("tracker", None)), record(other)]
    seed.rng.shuffle(parts)
    write_layers("targets:\n" + "".join(parts))
    before = targets.local_path().read_bytes()
    ok, out = cli("target-set", name, FIELD, template)
    assert ok, seed.msg(out)
    data = yamlmini.mapping(targets.local_path().read_text(encoding="utf-8"))
    policy = data["targets"][name]["policy"]
    assert policy.get("mr_title_template") == template, seed.msg(policy)
    assert refusal_on_load(name) == "", seed.msg(refusal_on_load(name))
    found = copies()
    assert any(c.read_bytes() == before for c in found), seed.msg((found, out))


# ------------------------------------------------------------ AC-8

@pytest.mark.parametrize("shape", ["{foo}", "{ref}: {{w}}", "{id} {{w}}"])
def test_ac8_target_set_invalid_value_refused_file_intact(cli, seed, shape):
    """`target-set <проект> policy.mr_title_template` с недопустимым значением — отказ в форме `_check_delivery`, файл слоя побайтно прежний.

    Сценарий: проект с `ref_required`, без поля шаблона; значение `{foo}`,
    `{ref}: {<слово>}` или `{id} {<слово>}`. Код выхода ненулевой; текст
    отказа несёт `поле 'policy.mr_title_template'`, не несёт «неизвестное
    поле» и не несёт отказа перечня полей команды («нет в policy»); байты
    файла локального слоя прежние.

    Ловит мутацию: команда пишет файл до проверки записи (отказ есть, а
    файл уже переписан); поле не в перечне `LOCAL_FIELDS["policy"]` —
    отказ перечня команды вместо отказа проверки значения; проверка
    значения пропускает неизвестную подстановку — запись принята.
    """
    name = "p" + seed.word()
    write_layers("targets:\n" + record(name, policy_lines("tracker", None)))
    before = targets.local_path().read_bytes()
    value = shape.replace("{w}", "x" + seed.word())
    ok, out = cli("target-set", name, FIELD, value)
    assert not ok, seed.msg(out)
    assert FIELD_REFUSAL in out, seed.msg(out)
    assert UNKNOWN_FIELD not in out, seed.msg(out)
    assert "нет в policy" not in out, seed.msg(out)
    assert targets.local_path().read_bytes() == before, seed.msg(out)
