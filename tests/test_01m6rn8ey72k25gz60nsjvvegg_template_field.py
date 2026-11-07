"""Поле `policy.commit_message_template` записи проекта: проверка при загрузке и запись командой `target-set`.

Группа: долгоживущий
Красен до реализации: поля `commit_message_template` нет в перечне раздела `policy` (`targets.LOCAL_FIELDS`) — запись с ним отвергается отказом «неизвестное поле», годный шаблон не загружается, а `target-set` отказывает «поля commit_message_template нет в policy».

Связка, которую держит файл: «загрузчик записи проекта `targets.target`
— команда правки `target-set` (`artel.main`) — локальный слой» в
песочнице `initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`:
пути `config` во временном каталоге, БД со схемой). Настоящий локальный
слой пульта не читается и не пишется; запись проекта вымышленная, её имя,
система ссылок и литералы шаблонов — от зерна `random`, зерно печатается и
входит в текст провала.

Провалидировано временным стабом корректной реализации (удалён, не
закоммичен): поле в перечне `policy` и проверка значения в форме отказов
`_check_delivery` — все методы зелёные.

Отказ загрузки — исключение `targets.TargetsError`; отказ команды — выход
`SystemExit` с ненулевым кодом, его текст — код выхода и вывод команды.
"""
import contextlib
import io
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, targets, yamlmini

LETTERS = "abcdefghijkmnopqrstuvwxyz"
FIELD = "policy.commit_message_template"
FIELD_REFUSAL = f"поле '{FIELD}' — "
UNKNOWN_FIELD = "неизвестное поле"

ENTRY = """targets:
  {name}:
    description:
      base: main
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

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))


@pytest.fixture
def seed(initialized_tmp_root):
    return Seed()


def quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_record(name: str, *, system: str | None = None,
                 template: str | None = None) -> None:
    """Запись проекта `name` в локальном слое: `ref_required` и шаблон —
    по сценарию (None — поля нет)."""
    policy = ""
    if system is not None:
        policy += f"      ref_required: {system}\n"
    if template is not None:
        policy += f"      commit_message_template: {quoted(template)}\n"
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(ENTRY.format(name=name, policy=policy), encoding="utf-8")


def load_refusal(name: str) -> str | None:
    """Текст отказа загрузки записи `name`; None — запись загружена."""
    try:
        targets.target(name)
    except targets.TargetsError as exc:
        return str(exc)
    return None


def run(*argv) -> tuple[bool, str]:
    """(успех, текст) команды пульта как из командной строки."""
    buf = io.StringIO()
    ok = True
    with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            ok = exc.code in (0, None)
            if not ok:
                buf.write(f"\n{exc.code}")
    return ok, buf.getvalue()


INVALID = ["неизвестная подстановка", "пустая строка", "ref без ref_required"]


@pytest.mark.parametrize("case", INVALID)
def test_ac4_invalid_template_refused_by_field_name(seed, case):
    """Негодный шаблон — отказ загрузки с полным именем поля, не «неизвестное поле»; годный той же записи — загружается.

    Сценарий по `case`: «неизвестная подстановка» — шаблон
    `"{<случайное имя>}: x"` (подстановка вне `{id}`, `{ref}`, `{title}`,
    `{text}`) при заданном `ref_required`; «пустая строка» — `""`; «ref без
    ref_required» — шаблон с `{ref}` у записи без `policy.ref_required`.
    `targets.target` отказывает исключением, текст которого несёт
    `поле 'policy.commit_message_template' — ` и не несёт «неизвестное
    поле». Позитивный контроль на той же записи: `"{id}: {title}"` без
    `ref_required` и `"{ref}: {text}"` с ним загружаются без отказа.

    Ловит мутацию: поле добавлено в перечень раздела без проверки значения
    (негодный шаблон загружается — отказа нет); либо проверка подстановок
    берёт перечень сжатого коммита `{id}`, `{ref}`, `{text}` (годный
    `"{id}: {title}"` отвергается); либо `{ref}` без `ref_required` не
    проверяется (загрузка без отказа).
    """
    name = f"p{seed.word()}"
    system = f"sys{seed.word(4)}"
    if case == "неизвестная подстановка":
        bad = "{" + seed.word(5) + "}: x"
        write_record(name, system=system, template=bad)
    elif case == "пустая строка":
        write_record(name, system=system, template="")
    else:
        write_record(name, template="{ref}: {text}")
    refusal = load_refusal(name)
    assert refusal is not None, seed.msg(f"{case}: запись загружена без отказа")
    assert FIELD_REFUSAL in refusal, seed.msg(f"{case}: {refusal}")
    assert UNKNOWN_FIELD not in refusal, seed.msg(f"{case}: {refusal}")

    write_record(name, template="{id}: {title}")
    assert load_refusal(name) is None, seed.msg(
        f"годный {{id}}: {{title}} отвергнут: {load_refusal(name)}")
    write_record(name, system=system, template="{ref}: {text}")
    assert load_refusal(name) is None, seed.msg(
        f"годный {{ref}}: {{text}} отвергнут: {load_refusal(name)}")


def test_ac6_target_set_writes_valid_and_refuses_invalid(seed):
    """`target-set` пишет годный шаблон; негодный — отказ с полным именем поля, файл не записан.

    Сценарий: запись проекта в локальном слое с `policy.ref_required` и
    без шаблона. `target-set <проект> policy.commit_message_template
    "{<случайное имя>}"` — отказ, текст несёт `поле
    'policy.commit_message_template' — ` и не «неизвестное поле», файл
    побайтно прежний. `target-set … "{ref}: {title}"` — успех: в файле у
    записи `policy.commit_message_template` равно `{ref}: {title}`, запись
    загружается без отказа (позитивный контроль). Повторный негодный
    шаблон после записи — снова отказ, файл несёт годный шаблон побайтно.

    Ловит мутацию: поле не добавлено в перечень `policy` (команда
    отказывает «поля commit_message_template нет в policy» и годному
    шаблону); либо команда пишет файл без проверки загрузкой (негодный
    шаблон записан, файл изменился).
    """
    name = f"p{seed.word()}"
    write_record(name, system=f"sys{seed.word(4)}")
    local = targets.local_path()
    before = local.read_bytes()
    bad = "{" + seed.word(5) + "}"
    ok, text = run("target-set", name, FIELD, bad)
    assert not ok, seed.msg(f"негодный {bad!r} принят: {text}")
    assert FIELD_REFUSAL in text, seed.msg(text)
    assert UNKNOWN_FIELD not in text, seed.msg(text)
    assert local.read_bytes() == before, seed.msg("файл изменён отказом")

    ok, text = run("target-set", name, FIELD, "{ref}: {title}")
    assert ok, seed.msg(f"годный шаблон не записан: {text}")
    data = yamlmini.mapping(local.read_text(encoding="utf-8"))
    assert data["targets"][name]["policy"].get("commit_message_template") \
        == "{ref}: {title}", seed.msg(local.read_text(encoding="utf-8"))
    assert load_refusal(name) is None, seed.msg(load_refusal(name))

    written = local.read_bytes()
    ok, text = run("target-set", name, FIELD, bad)
    assert not ok, seed.msg(f"негодный {bad!r} принят после записи: {text}")
    assert FIELD_REFUSAL in text, seed.msg(text)
    assert local.read_bytes() == written, seed.msg("файл изменён отказом")
