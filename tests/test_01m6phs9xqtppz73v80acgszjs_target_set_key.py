"""Формы `target-set <проект> <раздел>.<поле> --key <ключ> <значение>` и `--drop-key <ключ>`: запись и снятие ключа поля-отображения `machine.submodule_tokens` локального слоя, отказы, копия, журнал, прежняя форма.

Группа: долгоживущий
Красен до реализации: новых форм `--key`/`--drop-key` у `target-set` нет — `--key <ключ> <значение>` отказывает прежней проверкой «значение — ровно один аргумент», `--drop-key <ключ>` уходит в прежнюю форму и отказывает «вложенное отображение» (или пишет строку `--drop-key`), `TARGET_SET_USAGE` новых форм не называет; тесты AC-11 зелены с рождения — они держат прежнее поведение; чисто отказные случаи (AC-3 отсутствующий ключ, AC-4, AC-9, отказы AC-12 кроме журнала) до реализации зелены тривиально — прежняя проверка числа аргументов тоже отказывает, не трогая файл; различающую силу они получают вместе с формой — проверено на временном стабе, где снятая проверка ключа или комментария красит их.

Связка, которую держит файл: «диспетчер `artel.main` — команда правки
`target-set` — загрузчик `targets.load`/`targets.target` — журнал пульта»
в песочнице `initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`:
пути `config` — `TARGETS`, `LOGS`, `DB`, `PROJECTS` — во временном
каталоге, БД со схемой, признак процесса роли снят). Настоящий локальный
слой пульта не читается и не пишется; имена проектов, ключей и слотов
вымышленные. Команда зовётся как из командной строки: `sys.argv` подменён,
`artel.main()`. Отказ — выход `SystemExit` с ненулевым кодом. Файл
локального слоя — `config.TARGETS.parent / ".artel" / "targets.yaml"`;
копии — `targets-*.yaml` в `config.LOGS`; записи журнала — строки
`steps` с действием `target-set`.

Слой песочницы записан в той форме, которую пишет пересборка команды
(без строк `#`, строки с `#` — в двойных кавычках, простые строки — без
кавычек): тогда побайтная сохранность прочих строк после успешной записи
— наблюдаемое свойство, а не артефакт пересборки.

Имена проектов, ключей и слотов — от зерна `random`; зерно печатается и
входит в текст провала.
"""
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, projects, store, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
PROJECT = "sandbox"
FIELD = "machine." + targets.SUBMODULE_TOKENS_FIELD
FIELD_LINE = f"      {targets.SUBMODULE_TOKENS_FIELD}:"


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

    def slot(self) -> str:
        return "s" + self.word() + "-token"


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


def journal_details() -> list:
    rows = store.db().execute(
        "SELECT detail FROM steps WHERE action = 'target-set' ORDER BY id").fetchall()
    return [row[0] for row in rows]


def record(name: str, tokens: dict | None = None, *, base: str = "main",
           extra_policy: str = "") -> str:
    """Запись в трёх разделах с `test_profile` в форме пересборки; `tokens` — `machine.submodule_tokens` (уже записанные литералы)."""
    text = (f"  {name}:\n"
            f"    description:\n      base: {base}\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"{extra_policy}"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")
    if tokens:
        text += FIELD_LINE + "\n" + "".join(
            f"        {key}: {slot}\n" for key, slot in tokens.items())
    return text


def other_record(name: str) -> str:
    """Другая запись слоя со значениями `a#b` и `a # b` (в двойных кавычках) — в полях и в её собственном `submodule_tokens`."""
    return record(name, {"x/y": '"a#b"', "z.w": '"a # b"'}, base='"a#b"',
                  extra_policy='      branch_template: "a # b"\n')


OTHER_VALUES = {"base": "a#b", "branch_template": "a # b",
                targets.SUBMODULE_TOKENS_FIELD: {"x/y": "a#b", "z.w": "a # b"}}


def write_layers(local_text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_text, encoding="utf-8")


def layer(seed: Seed, tokens: dict | None = None) -> tuple:
    """(текст слоя, имя другой записи): `sandbox` с `tokens` и другая запись; порядок записей — от зерна."""
    other = seed.name()
    parts = [record(PROJECT, tokens), other_record(other)]
    seed.rng.shuffle(parts)
    return "targets:\n" + "".join(parts), other


def project_record() -> dict:
    return yamlmini.mapping(local_file().read_text(encoding="utf-8"))["targets"][PROJECT]


def without_field(text: str, name: str = PROJECT) -> list:
    """Строки текста слоя без строк поля `machine.submodule_tokens` записи `name` (заголовок поля и его ключи)."""
    lines = text.splitlines(keepends=True)
    kept, inside, in_field = [], False, False
    for line in lines:
        if re.match(r"^  \S", line):
            inside = line == f"  {name}:\n"
            in_field = False
        if inside and line.rstrip("\n") == FIELD_LINE:
            in_field = True
            continue
        if in_field and line.startswith(" " * 8):
            continue
        in_field = False
        kept.append(line)
    return kept


def check_other(other: str, seed: Seed) -> None:
    entry = targets.target(other)
    for field, want in OTHER_VALUES.items():
        assert entry[field] == want, seed.msg((field, entry.get(field)))


# ------------------------------------------------------------ AC-1

def test_ac1_key_creates_field_with_slash_and_dot_keys(cli, seed):
    """`--key` на записи без `submodule_tokens` заводит поле: ключи `a/b/c` и `a.b` записаны дословно, прочие поля записи прежние.

    Сценарий: локальный слой — `sandbox` без поля и другая запись.
    `target-set sandbox machine.submodule_tokens --key <г>/<п>/<м> <слот1>`,
    затем `--key <п>.<м> <слот2>`; обе успешны.
    `targets.target("sandbox")["submodule_tokens"]` равно
    `{"<г>/<п>/<м>": слот1, "<п>.<м>": слот2}`; разобранная запись
    `sandbox` без поля `machine.submodule_tokens` равна прежней записи.

    Ловит мутацию: ключ делится по точке (`a.b` пишется вложенным
    отображением `a: {b: …}` и загрузчик отказывает или даёт ключ `a`);
    ключ с `/` отвергнут проверкой ключа; при заведении поля пересборка
    теряет или меняет другое поле записи (например `token_slot`).
    """
    text, _other = layer(seed)
    write_layers(text)
    before = project_record()
    slash = f"{seed.word(3)}/{seed.word(3)}/{seed.word(3)}"
    dot = f"{seed.word(3)}.{seed.word(3)}"
    slot1, slot2 = seed.slot(), seed.slot()
    ok, out = cli("target-set", PROJECT, FIELD, "--key", slash, slot1)
    assert ok, seed.msg(out)
    ok, out = cli("target-set", PROJECT, FIELD, "--key", dot, slot2)
    assert ok, seed.msg(out)
    want = {slash: slot1, dot: slot2}
    assert targets.target(PROJECT)[targets.SUBMODULE_TOKENS_FIELD] == want, seed.msg(out)
    after = project_record()
    tokens = after["machine"].pop(targets.SUBMODULE_TOKENS_FIELD)
    assert tokens == want, seed.msg(tokens)
    assert after == before, seed.msg((before, after))


# ------------------------------------------------------------ AC-2

def test_ac2_key_replaces_value_other_key_intact(cli, seed):
    """`--key` на существующем ключе заменяет его значение, второй ключ поля цел.

    Сценарий: `sandbox` с `submodule_tokens` из двух ключей (`<к1>`, `<к2>`
    с косой чертой); `target-set sandbox machine.submodule_tokens --key
    <к1> <новый слот>` успешна; поле — `{<к1>: новый слот, <к2>: прежний}`.

    Ловит мутацию: `--key` подменяет всё поле отображением из одного
    ключа (второй ключ пропал); существующий ключ дописывается вторым
    вхождением или значение не меняется.
    """
    k1, k2 = seed.word(), f"{seed.word(3)}/{seed.word(3)}"
    s1, s2, new = seed.slot(), seed.slot(), seed.slot()
    text, _other = layer(seed, {k1: s1, k2: s2})
    write_layers(text)
    ok, out = cli("target-set", PROJECT, FIELD, "--key", k1, new)
    assert ok, seed.msg(out)
    got = targets.target(PROJECT)[targets.SUBMODULE_TOKENS_FIELD]
    assert got == {k1: new, k2: s2}, seed.msg(got)


# ------------------------------------------------------------ AC-3

def test_ac3_drop_key_and_last_key_drops_field(cli, seed):
    """`--drop-key` снимает ключ; снятие последнего ключа снимает поле целиком.

    Сценарий: `sandbox` с двумя ключами; `--drop-key <к1>` успешна — поле
    `{<к2>: слот2}`; затем `--drop-key <к2>` успешна — в разобранной записи
    `machine` нет `submodule_tokens`, и в `targets.target("sandbox")` поля
    нет.

    Ловит мутацию: снят последний ключ, а пустое отображение
    `submodule_tokens:` осталось (пересборка отказывает или пишет пустое
    поле); снимается не тот ключ или всё поле сразу.
    """
    k1, k2 = f"{seed.word(3)}.{seed.word(3)}", f"{seed.word(3)}/{seed.word(3)}"
    s1, s2 = seed.slot(), seed.slot()
    text, _other = layer(seed, {k1: s1, k2: s2})
    write_layers(text)
    ok, out = cli("target-set", PROJECT, FIELD, "--drop-key", k1)
    assert ok, seed.msg(out)
    assert targets.target(PROJECT)[targets.SUBMODULE_TOKENS_FIELD] == {k2: s2}, seed.msg(out)
    ok, out = cli("target-set", PROJECT, FIELD, "--drop-key", k2)
    assert ok, seed.msg(out)
    assert targets.SUBMODULE_TOKENS_FIELD not in project_record()["machine"], seed.msg(out)
    assert targets.SUBMODULE_TOKENS_FIELD not in targets.target(PROJECT), seed.msg(out)


@pytest.mark.parametrize("has_field", [True, False])
def test_ac3_drop_absent_key_refused(cli, seed, has_field):
    """`--drop-key` отсутствующего ключа — отказ с именем ключа, файл побайтно прежний.

    Сценарий: `sandbox` с полем из одного ключа либо без поля;
    `--drop-key <случайный другой ключ>`. Код выхода ненулевой, имя ключа
    в тексте отказа; байты файла прежние.

    Ловит мутацию: отсутствие ключа не проверяется — пишется пересобранный
    файл (копия, журнал) или `KeyError` вместо отказа с именем; при
    отсутствии поля целиком команда падает трейсбеком без имени ключа.
    """
    tokens = {seed.word(): seed.slot()} if has_field else None
    text, _other = layer(seed, tokens)
    write_layers(text)
    before = local_file().read_bytes()
    missing = "m" + seed.word()
    ok, out = cli("target-set", PROJECT, FIELD, "--drop-key", missing)
    assert not ok, seed.msg(out)
    assert missing in out, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)


# ------------------------------------------------------------ AC-4

@pytest.mark.parametrize("shape", ["{w}:{w}", "#{w}", " {w}", "{w} "])
def test_ac4_unwritable_key_refused(cli, seed, shape):
    """Ключ с `:`, с ведущим `#`, с пробелом по краю при `--key` — отказ с именем ключа, файл не меняется.

    Сценарий: `sandbox` с полем из одного ключа; `--key <ключ> <слот>` с
    ключом формы `<w>:<w>`, `#<w>`, ` <w>`, `<w> `. Код выхода ненулевой,
    ключ в тексте отказа; байты файла прежние, копий нет.

    Ловит мутацию: проверка ключа снята — пересборка пишет `x:y: слот`
    (разбор даёт другой ключ), `#x: слот` (комментарий — ключ пропал) или
    ключ с обрезанным пробелом; отказ без имени ключа.
    """
    text, _other = layer(seed, {seed.word(): seed.slot()})
    write_layers(text)
    before = local_file().read_bytes()
    key = shape.replace("{w}", seed.word(), 1).replace("{w}", seed.word())
    ok, out = cli("target-set", PROJECT, FIELD, "--key", key, seed.slot())
    assert not ok, seed.msg(out)
    assert key in out, seed.msg((key, out))
    assert local_file().read_bytes() == before, seed.msg(out)
    assert copies() == [], seed.msg(out)


# ------------------------------------------------------------ AC-6

def test_ac6_field_outside_list_refused_with_list(cli, seed):
    """Поле вне перечня (`policy.no_paths --key x y`) — отказ с перечнем допустимых полей.

    Сценарий: `sandbox` без поля токенов; `target-set sandbox
    policy.no_paths --key <x> <y>`. Код выхода ненулевой; текст отказа
    называет `machine.submodule_tokens`.

    Ловит мутацию: перечень полей не проверяется — `--key` пишет ключ в
    `policy.no_paths` (список становится отображением); отказ без перечня.
    """
    text, _other = layer(seed)
    write_layers(text)
    ok, out = cli("target-set", PROJECT, "policy.no_paths", "--key",
                  seed.word(), seed.word())
    assert not ok, seed.msg(out)
    assert FIELD in out, seed.msg(out)


# ------------------------------------------------------------ AC-7

@pytest.mark.parametrize("has_field", [True, False])
def test_ac7_key_path_into_field_refused_with_list(cli, seed, has_field):
    """Путь `machine.submodule_tokens.<ключ>` с `--key` — отказ с перечнем допустимых полей, файл побайтно прежний.

    Сценарий: `sandbox` с полем или без; `target-set sandbox
    machine.submodule_tokens.<к> --key <к2> <слот>`. Код выхода ненулевой;
    в тексте отказа `machine.submodule_tokens` встречается не только как
    начало эха пути `machine.submodule_tokens.<к>` (то есть назван
    перечень); байты файла прежние.

    Ловит мутацию: путь режется по точке и `<к>` трактуется как поле
    отображения — ключ пишется вложенно; отказ лишь повторяет путь без
    перечня допустимых полей.
    """
    tokens = {seed.word(): seed.slot()} if has_field else None
    text, _other = layer(seed, tokens)
    write_layers(text)
    before = local_file().read_bytes()
    inner = "k" + seed.word()
    ok, out = cli("target-set", PROJECT, f"{FIELD}.{inner}", "--key",
                  seed.word(), seed.slot())
    assert not ok, seed.msg(out)
    listed = re.findall(re.escape(FIELD) + r"(?!\." + re.escape(inner) + ")", out)
    assert listed, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)


# ------------------------------------------------------------ AC-8

@pytest.mark.parametrize("tail", [
    ["--key"],
    ["--key", "{k}"],
    ["--drop-key"],
    ["--key", "{k}", "{v}", "{x}"],
    ["--drop-key", "{k}", "{x}"],
])
def test_ac8_wrong_arg_count_refused_with_usage(cli, seed, tail):
    """`--key`/`--drop-key` с неполным или лишним числом аргументов — отказ со строкой `TARGET_SET_USAGE`, в которой есть обе новые формы; файл прежний.

    Сценарий: `sandbox` с полем из ключа `<к>`; хвост команды после пути —
    `--key`, `--key <к>`, `--drop-key`, `--key <к> <слот> <лишний>`,
    `--drop-key <к> <лишний>`. Код выхода ненулевой; текст отказа несёт
    `projects.TARGET_SET_USAGE`, а та содержит `--key` и `--drop-key`;
    байты файла прежние.

    Ловит мутацию: лишний аргумент молча отброшен и ключ записан или снят;
    неполная форма уходит в прежнюю (`--drop-key` записан значением);
    отказ без строки формы вызова; `TARGET_SET_USAGE` не дополнена новыми
    формами.
    """
    key = seed.word()
    text, _other = layer(seed, {key: seed.slot()})
    write_layers(text)
    before = local_file().read_bytes()
    argv = [part.replace("{k}", key).replace("{v}", seed.slot())
            .replace("{x}", "x" + seed.word()) for part in tail]
    ok, out = cli("target-set", PROJECT, FIELD, *argv)
    assert not ok, seed.msg(out)
    assert projects.TARGET_SET_USAGE in out, seed.msg(out)
    assert "--key" in projects.TARGET_SET_USAGE, projects.TARGET_SET_USAGE
    assert "--drop-key" in projects.TARGET_SET_USAGE, projects.TARGET_SET_USAGE
    assert local_file().read_bytes() == before, seed.msg(out)


# ------------------------------------------------------------ AC-9

@pytest.mark.parametrize("value", ["", '""', "''", "  "])
def test_ac9_empty_value_refused(cli, seed, value):
    """Пустое значение при `--key` — отказ.

    Сценарий: `sandbox` без поля; `--key <к> <значение>` с пустым
    аргументом, `""`, `''` или пробелами. Код выхода ненулевой, и ключ в
    поле не появился.

    Ловит мутацию: проверка пустого значения снята для новой формы —
    пишется `<к>: ""` или `<к>: null`.
    """
    text, _other = layer(seed)
    write_layers(text)
    key = seed.word()
    ok, out = cli("target-set", PROJECT, FIELD, "--key", key, value)
    assert not ok, seed.msg(out)
    assert targets.SUBMODULE_TOKENS_FIELD not in project_record()["machine"], seed.msg(out)


# ------------------------------------------------------------ AC-10

def test_ac10_copy_journal_and_output_per_write(cli, seed):
    """Каждая запись `--key`/`--drop-key` — новая копия прежнего файла и строка журнала/вывода `<раздел>.<поле>[<ключ>]: <было> → <стало>`; повтор значения — «без изменений» без копии и журнала.

    Сценарий: `sandbox` без поля. Шаги: `--key <к> <с1>` — строка
    `machine.submodule_tokens[<к>]: (нет) → <с1>`; `--key <к> <с2>` —
    `… <с1> → <с2>`; `--key <к> <с2>` повтором — «без изменений»;
    `--drop-key <к>` — `… <с2> → (нет)`. После каждой записи копий в
    `config.LOGS` на одну больше и последняя копия — байты файла до этой
    записи; детали журнала `target-set` — ровно эти строки по порядку;
    строка `target-set: <деталь>` напечатана. Повтор не прибавляет ни
    копии, ни записи журнала.

    Ловит мутацию: копия не создаётся в ветке `--key`/`--drop-key` (или
    создаётся после записи — с новыми байтами); журнал пишет путь без
    `[<ключ>]` или `<было>` пустым; снятие пишет `→ None`; повтор того же
    значения переписывает файл и журналирует «с2 → с2».
    """
    text, _other = layer(seed)
    write_layers(text)
    key = f"{seed.word(3)}/{seed.word(3)}"
    s1, s2 = seed.slot(), seed.slot()
    label = f"{FIELD}[{key}]"
    steps = [(["--key", key, s1], f"{label}: (нет) → {s1}"),
             (["--key", key, s2], f"{label}: {s1} → {s2}"),
             (["--key", key, s2], None),
             (["--drop-key", key], f"{label}: {s2} → (нет)")]
    want_details = []
    for argv, detail in steps:
        before = local_file().read_bytes()
        n_copies = len(copies())
        ok, out = cli("target-set", PROJECT, FIELD, *argv)
        assert ok, seed.msg((argv, out))
        if detail is None:
            assert "без изменений" in out, seed.msg(out)
            assert len(copies()) == n_copies, seed.msg(out)
            assert local_file().read_bytes() == before, seed.msg(out)
        else:
            want_details.append(detail)
            found = copies()
            assert len(found) == n_copies + 1, seed.msg((argv, found))
            new = [c for c in found if c.read_bytes() == before]
            assert new, seed.msg((argv, found))
            assert f"target-set: {detail}" in out, seed.msg(out)
        assert journal_details() == want_details, seed.msg((argv, journal_details()))


# ------------------------------------------------------------ AC-11

def test_ac11_old_form_unchanged(cli, seed):
    """Прежняя форма `target-set <проект> <путь> <значение>` пишет поле, журнал и вывод — как прежде.

    Сценарий: `sandbox` с полем токенов; `target-set sandbox
    policy.sandbox <слово>` успешна; в файле `policy.sandbox` — слово,
    поле токенов прежнее; деталь журнала — `policy.sandbox: (нет) →
    <слово>`, строка `target-set: <деталь>` напечатана; одна копия.

    Ловит мутацию: разбор новой формы перехватывает и прежнюю (например,
    любой четвёртый аргумент или поле `machine.*` считается `--key`) —
    прежняя правка отказывает или журналирует путь в форме
    `<поле>[<ключ>]`.
    """
    tokens = {seed.word(): seed.slot()}
    text, _other = layer(seed, tokens)
    write_layers(text)
    value = "v" + seed.word()
    ok, out = cli("target-set", PROJECT, "policy.sandbox", value)
    assert ok, seed.msg(out)
    rec = project_record()
    assert rec["policy"]["sandbox"] == value, seed.msg(rec)
    assert rec["machine"][targets.SUBMODULE_TOKENS_FIELD] == tokens, seed.msg(rec)
    detail = f"policy.sandbox: (нет) → {value}"
    assert journal_details() == [detail], seed.msg(journal_details())
    assert f"target-set: {detail}" in out, seed.msg(out)
    assert len(copies()) == 1, seed.msg(copies())


@pytest.mark.parametrize("has_field", [True, False])
def test_ac11_old_form_nested_path_refused_as_before(cli, seed, has_field):
    """Прежняя форма с путём `machine.submodule_tokens.<ключ>` — прежний отказ «вложенное отображение», файл прежний.

    Сценарий: `sandbox` с полем (ключ `<к>`) или без; `target-set sandbox
    machine.submodule_tokens.<к> <слот>`. Код выхода ненулевой, текст —
    «target-set: путь machine.submodule_tokens.<к> ведёт во вложенное
    отображение — его поля командой не правятся; файл не записан»; байты
    файла прежние, копий нет.

    Ловит мутацию: путь `machine.submodule_tokens.<к>` прежней формы
    переведён на запись ключа (ключ записан) или отказ переписан новым
    текстом.
    """
    key = seed.word()
    text, _other = layer(seed, {key: seed.slot()} if has_field else None)
    write_layers(text)
    before = local_file().read_bytes()
    path = f"{FIELD}.{key}"
    ok, out = cli("target-set", PROJECT, path, seed.slot())
    assert not ok, seed.msg(out)
    refusal = (f"target-set: путь {path} ведёт во вложенное отображение — его "
               f"поля командой не правятся; файл не записан")
    assert refusal in out, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)
    assert copies() == [], seed.msg(out)


# ------------------------------------------------------------ AC-12

@pytest.mark.parametrize("form", ["key", "drop-key"])
@pytest.mark.parametrize("case", ["строка с #", "строка с # в отступе",
                                  "журнал недоступен", "проект artel",
                                  "записи нет"])
def test_ac12_old_refusals_hold_for_new_forms(cli, seed, form, case):
    """Отказы прежней формы действуют для `--key` и `--drop-key`: комментарий в слое, недоступный журнал, проект артели, нет записи — файл прежний, копии нет.

    Сценарий: `sandbox` с полем из ключа `<к>`; по случаю — строка
    `# <слово>` в начале файла или с отступом внутри `machine`, удалённая
    БД пульта, проект `artel` или незнакомое имя проекта. Команда —
    `--key <новый ключ> <слот>` или `--drop-key <к>`. Код выхода
    ненулевой; байты файла локального слоя прежние; копий нет; у
    недоступного журнала текст несёт `projects.NO_JOURNAL`.

    Ловит мутацию: ветка новой формы минует проверку комментария
    (пересборка стирает строку `#`), проверку журнала (файл записан, а
    журнал нет) или проверку проекта (запись артели или новая запись
    заводится в локальном слое); копия создаётся до отказа.
    """
    key = seed.word()
    text, _other = layer(seed, {key: seed.slot()})
    name = PROJECT
    if case == "строка с #":
        text = f"# {seed.word()}\n" + text
    elif case == "строка с # в отступе":
        text = text.replace(f"  {PROJECT}:\n    description:\n",
                            f"  {PROJECT}:\n    description:\n      # {seed.word()}\n", 1)
        assert "      # " in text
    elif case == "проект artel":
        name = config.DEFAULT_TARGET
    elif case == "записи нет":
        name = seed.name()
    write_layers(text)
    if case == "журнал недоступен":
        config.DB.unlink()
        assert not store.db_usable()
    before = local_file().read_bytes()
    argv = (["--key", "n" + seed.word(), seed.slot()] if form == "key"
            else ["--drop-key", key])
    ok, out = cli("target-set", name, FIELD, *argv)
    assert not ok, seed.msg(out)
    assert local_file().read_bytes() == before, seed.msg(out)
    assert copies() == [], seed.msg(out)
    if case == "журнал недоступен":
        assert projects.NO_JOURNAL in out, seed.msg(out)


def test_ac12_other_lines_and_hash_values_preserved(cli, seed):
    """После успешных `--key`/`--drop-key` все строки слоя, кроме строк правимого поля, побайтно прежние; значения `a#b` и `a # b` другой записи прежние.

    Сценарий: слой в форме пересборки — `sandbox` без поля и другая
    запись с `base: "a#b"`, `branch_template: "a # b"` и своим
    `submodule_tokens` со слотами `"a#b"`/`"a # b"`. Шаги: `--key <к1>`,
    `--key <к2>`, `--drop-key <к1>`, `--drop-key <к2>` — все успешны.
    После каждого строки файла без строк поля `machine.submodule_tokens`
    записи `sandbox` равны таким же строкам исходного файла; поля другой
    записи по `targets.target(<другая>)` — `a#b`, `a # b` и прежнее
    отображение токенов.

    Ловит мутацию: пересборка в ветке новой формы пишет значения иначе
    (кавычки сняты — `a#b` читается как `a`; одинарные кавычки или
    переставленные поля — строки не те); правка задевает
    `submodule_tokens` другой записи (ключ того же имени снят или записан
    не в ту запись).
    """
    text, other = layer(seed)
    write_layers(text)
    original = without_field(text)
    k1, k2 = f"{seed.word(3)}/{seed.word(3)}", f"{seed.word(3)}.{seed.word(3)}"
    for argv in (["--key", k1, seed.slot()], ["--key", k2, seed.slot()],
                 ["--drop-key", k1], ["--drop-key", k2]):
        ok, out = cli("target-set", PROJECT, FIELD, *argv)
        assert ok, seed.msg((argv, out))
        now = local_file().read_text(encoding="utf-8")
        assert without_field(now) == original, seed.msg((argv, now))
        check_other(other, seed)
