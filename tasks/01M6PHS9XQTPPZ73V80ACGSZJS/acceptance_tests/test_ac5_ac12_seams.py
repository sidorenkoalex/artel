"""AC-5 и закрытые швы AC-12: текст проверки `targets._submodule_tokens_error` в отказе `--key`; прямой вызов новой сверки `projects._drop_key_mismatches`; связь веток `--key`/`--drop-key` со сверками через атрибуты модуля.

Группа: разовый
Красен до реализации: формы `--key`/`--drop-key` у `target-set` нет — `--key <ключ> <значение>` отказывает прежней проверкой числа аргументов без текста проверки `_submodule_tokens_error` и без текста подменённой сверки; функции `projects._drop_key_mismatches` нет — прямой вызов и её подмена падают `AttributeError`.

Почему файл в планке, а не в `tests/`: каждый тест опирается на закрытое
имя `orchestrator`, которое SPEC называет швом критерия: текст отказа
AC-5 — это текст `targets._submodule_tokens_error` (без вызова его не
получить, не зашив литерал); AC-12 требует прямого вызова
`projects._drop_key_mismatches` (решения 2 второго и 1 третьего
возврата) и подмены атрибутов модуля `projects._drop_key_mismatches`/
`projects._target_set_mismatches` (решения 2 третьего и 1 четвёртого
возврата). Долгоживущему файлу закрытые имена запрещены. Публичную часть
AC-12 (отказы прежней формы для новых форм, сохранность прочих строк)
держит долгоживущий файл задачи `tests/test_<id>_target_set_key.py`.

Песочница — `initialized_tmp_root` (`tests/fixtures.py`): пути `config`
(`TARGETS`, `LOGS`, `DB`) во временном каталоге, БД со схемой; настоящий
локальный слой пульта не читается и не пишется, имена вымышленные. Команда
зовётся как из командной строки: `sys.argv` подменён, `artel.main()`.
Подмены атрибутов — `monkeypatch`, только в памяти процесса теста.
Имена ключей и слотов — от зерна `random`, зерно печатается.
"""
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, projects, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
PROJECT = "sandbox"
OTHER = "neighbour"
FIELD = "machine." + targets.SUBMODULE_TOKENS_FIELD
FIELD_LINE = f"      {targets.SUBMODULE_TOKENS_FIELD}:\n"


@pytest.fixture
def rng():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    return random.Random(seed)


def word(rng, prefix: str = "") -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(6))


@pytest.fixture
def cli(initialized_tmp_root, capsys):
    """Вызов команды как из командной строки в песочнице `config`."""

    def run(*argv) -> tuple:
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        out = capsys.readouterr()
        return code in (0, None), f"{code}\n{out.out}\n{out.err}"

    return run


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def copies() -> list:
    if not config.LOGS.is_dir():
        return []
    return sorted(config.LOGS.glob("targets-*.yaml"))


def record(name: str, tokens: dict | None) -> str:
    """Запись в форме пересборки с `test_profile`; `tokens` — `machine.submodule_tokens`."""
    text = (f"  {name}:\n"
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
    if tokens:
        text += FIELD_LINE + "".join(
            f"        {key}: {slot}\n" for key, slot in tokens.items())
    return text


def write_layer(tokens: dict | None) -> str:
    text = "targets:\n" + record(PROJECT, tokens) + record(OTHER, None)
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


# ------------------------------------------------------------ AC-5

@pytest.mark.parametrize("raw,value", [("123", 123), ("[a, b]", ["a", "b"])])
def test_ac5_non_string_value_refused_with_check_text(cli, rng, raw, value):
    """Значение `123` или `[a, b]` при `--key` — отказ с текстом проверки `_submodule_tokens_error`, файл побайтно прежний.

    Сценарий: `sandbox` с полем из ключа `<к1>`; `target-set sandbox
    machine.submodule_tokens --key <к2> 123` либо `… '[a, b]'`. Код выхода
    ненулевой; в тексте отказа — `targets._submodule_tokens_error({<к2>:
    <значение>})` (у числа — «слот пути <к2> — 123, не непустая строка»);
    байты файла прежние, копий нет.

    Ловит мутацию: значение не проверяется до записи — файл пишется, и
    загрузка слоя после этого отказывает; отказ есть, но со своим текстом
    вместо текста проверки загрузчика; число записано строкой `"123"`.
    """
    write_layer({word(rng, "k"): word(rng, "s")})
    before = local_file().read_bytes()
    key = word(rng, "n")
    ok, out = cli("target-set", PROJECT, FIELD, "--key", key, raw)
    assert not ok, out
    reason = targets._submodule_tokens_error({key: value})
    assert reason and reason in out, (reason, out)
    assert local_file().read_bytes() == before, out
    assert copies() == [], out


# ------------------------------------------------------------ AC-12

@pytest.mark.parametrize("sole", [False, True])
@pytest.mark.parametrize("variant", ["ровно лист", "лист и ещё поле",
                                     "лист не снят"])
def test_ac12_drop_key_mismatches_direct(initialized_tmp_root, rng, sole, variant):
    """Прямой вызов `_drop_key_mismatches(data, text, name, keys, path)`: текст без ровно снимаемого листа — `[]`; текст с иным отличием — непустой список строк.

    Сценарий: слой — `sandbox` с полем из одного или двух ключей и другая
    запись; `data` — разобранный прежний текст, `keys` —
    `["machine", "submodule_tokens", <к>]`, `path` — `targets.local_path()`.
    Собранный текст строится из прежнего: снята строка ключа (и заголовок
    поля, если ключ единственный) — ожидается `[]`; дополнительно изменён
    `url` записи `sandbox` — непустой список строк; строка ключа не снята
    (текст прежний) — непустой список строк.

    Ловит мутацию: сверка снятия сравнивает только наличие снятого листа и
    не видит лишнего изменённого поля; сверка не замечает, что лист не
    снят; при снятии единственного ключа исчезнувшее отображение
    принимается за лишнее расхождение (`[]` не получается); возвращается
    не список строк.
    """
    key = word(rng, "k") + "/" + word(rng)
    tokens = {key: word(rng, "s")}
    if not sole:
        tokens[word(rng, "j") + "." + word(rng)] = word(rng, "s")
    old = write_layer(tokens)
    data = yamlmini.mapping(old)
    key_line = f"        {key}: {tokens[key]}\n"
    assert old.count(key_line) == 1
    text = old.replace((FIELD_LINE + key_line) if sole else key_line, "", 1)
    if variant == "лист и ещё поле":
        url = f"url: https://localhost/team/{PROJECT}\n"
        assert old.count(url) == 1
        text = text.replace(url, f"url: https://localhost/team/{PROJECT}x\n", 1)
    elif variant == "лист не снят":
        text = old
    keys = ["machine", targets.SUBMODULE_TOKENS_FIELD, key]
    got = projects._drop_key_mismatches(data, text, PROJECT, keys,
                                        targets.local_path())
    assert isinstance(got, list), got
    if variant == "ровно лист":
        assert got == [], got
    else:
        assert got and all(isinstance(item, str) and item for item in got), got


def test_ac12_drop_key_branch_uses_module_check(cli, rng, monkeypatch):
    """Подменённая `projects._drop_key_mismatches` с непустым результатом — `--drop-key` существующего ключа отказывает её текстом, файл прежний, копии нет.

    Сценарий: `sandbox` с полем из ключа `<к>`; атрибут модуля
    `projects._drop_key_mismatches` подменён функцией, возвращающей
    `[<случайная строка>]`; `target-set sandbox machine.submodule_tokens
    --drop-key <к>`. Код выхода ненулевой, строка расхождения в тексте
    отказа; байты файла прежние; копий в `config.LOGS` нет.

    Ловит мутацию: ветка `--drop-key` не вызывает сверку или вызывает её
    по прямой ссылке, захваченной до подмены, — команда пишет файл;
    сверка вызывается после резервной копии — копия есть.
    """
    key = word(rng, "k")
    write_layer({key: word(rng, "s")})
    before = local_file().read_bytes()
    problem = "расхождение-" + word(rng)
    monkeypatch.setattr(projects, "_drop_key_mismatches",
                        lambda *args, **kwargs: [problem])
    ok, out = cli("target-set", PROJECT, FIELD, "--drop-key", key)
    assert not ok, out
    assert problem in out, out
    assert local_file().read_bytes() == before, out
    assert copies() == [], out


def test_ac12_key_branch_uses_module_check(cli, rng, monkeypatch):
    """Подменённая `projects._target_set_mismatches` с непустым результатом — `--key` с допустимыми ключом и значением отказывает её текстом, файл прежний, копии нет.

    Сценарий: `sandbox` с полем из ключа `<к1>`; атрибут модуля
    `projects._target_set_mismatches` подменён функцией, возвращающей
    `[<случайная строка>]`; `target-set sandbox machine.submodule_tokens
    --key <к2> <слот>`. Код выхода ненулевой, строка расхождения в тексте
    отказа; байты файла прежние; копий нет.

    Ловит мутацию: ветка `--key` проверяет значение напрямую в обход
    сверки или зовёт свою копию сверки — команда пишет файл; сверка после
    резервной копии — копия есть.
    """
    write_layer({word(rng, "k"): word(rng, "s")})
    before = local_file().read_bytes()
    problem = "расхождение-" + word(rng)
    monkeypatch.setattr(projects, "_target_set_mismatches",
                        lambda *args, **kwargs: [problem])
    ok, out = cli("target-set", PROJECT, FIELD, "--key", word(rng, "n"),
                  word(rng, "s"))
    assert not ok, out
    assert problem in out, out
    assert local_file().read_bytes() == before, out
    assert copies() == [], out
