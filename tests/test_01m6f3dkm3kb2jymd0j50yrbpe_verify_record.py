"""Поле записи проекта `verify` — профиль проверок этапа `verifying`: что загрузка записи принимает и чему отказывает.

Группа: долгоживущий
Красен до реализации: раздел `description` записи локального слоя не знает поля `verify` — допустимое `verify: [human:<имя>]` отказывает «неизвестное поле», контрольные загрузки падают; в записи слоя репозитория `targets.yaml` поле `verify` проходит проверку молча.

Свойство — чистая проверка записи (`targets.target`/`targets.load` над
файлами слоёв песочницы `tmp_root`), без git и FSM. Каждый отказ по
значению проверяется в паре с контрольной загрузкой той же записи с
допустимым `verify: [human:<имя>]`: так отказ «неизвестное поле» до
реализации не сходит за отказ проверки значения. Имена проектов и проверок
порождаются модулем `random` при каждом запуске; зерно печатается и входит
в текст провала.

Провалидировано временным стабом реализации (удалён, не закоммичен): поле
`verify` в разделе `description` с проверкой каталога типов и отказом в
плоской записи и в слое репозитория — все методы файла зелёные.
"""
import random

import pytest

from orchestrator import config, targets
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NAME_CHARS = "abcdefghijkmnopqrstuvwxyz0123456789-"
C4_TEXT = "тип не реализован (пункт C4)"
UNKNOWN_FIELD = "неизвестное поле"


@pytest.fixture
def rng():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    gen = random.Random(seed)
    gen.seed_value = seed
    return gen


def word(rng, size: int = 7) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(size))


def check_name(rng) -> str:
    """Годное имя проверки по `[a-z0-9-]+`: первая — буква, дальше — любые
    символы набора."""
    return rng.choice(LETTERS) + "".join(rng.choice(NAME_CHARS)
                                         for _ in range(rng.randint(0, 8)))


def local_entry(name: str, description_extra: str = "", top_extra: str = "") -> str:
    """Запись локального слоя в трёх разделах; `description_extra` —
    строки раздела `description`, `top_extra` — строки вне разделов."""
    return (f"  {name}:\n"
            f"    description:\n      base: {config.MAIN_BRANCH}\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            + description_extra
            + f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n"
            + top_extra)


def write_local(text: str) -> None:
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + text, encoding="utf-8")


def load_local(name: str, verify: str | None):
    """(запись, None) — загрузилась; (None, текст отказа) — нет. `verify` —
    значение поля `verify` раздела `description` текстом YAML; None — поля
    нет."""
    extra = f"      verify: {verify}\n" if verify is not None else ""
    write_local(local_entry(name, extra))
    try:
        return targets.target(name), None
    except targets.TargetsError as exc:
        return None, str(exc)


def where(rng, text: str) -> str:
    return f"зерно {rng.seed_value}: {text}"


# (вариант, значение `verify` по годному имени `n` и случайному слову `w`,
# слова, которые обязан нести отказ сверх имени поля)
AC1_CASES = [
    ("ci", lambda n, w: "[ci]", ()),
    ("ci-рядом-с-human", lambda n, w: f"[human:{n}, ci]", ()),
    ("agent", lambda n, w: f"[agent:{w}]", (C4_TEXT,)),
    ("script", lambda n, w: f"[script:{w}]", (C4_TEXT,)),
    ("неизвестный-тип", lambda n, w: f"[robot{w}:{n}]", ()),
    ("тип-без-имени", lambda n, w: f"[{w}]", ()),
    ("повтор-имени", lambda n, w: f"[human:{n}, human:{n}]", ()),
    ("не-список-строка", lambda n, w: f"human:{n}", ()),
    ("не-список-число", lambda n, w: "5", ()),
    ("имя-с-заглавной", lambda n, w: f"[human:S{n}]", ()),
    ("пустое-имя", lambda n, w: "[human:]", ()),
    ("имя-с-пробелом", lambda n, w: f"[human:{n} {w}]", ()),
    ("имя-с-подчёркиванием", lambda n, w: f"[human:{n}_{w}]", ()),
]


@pytest.mark.parametrize("case,value,words", AC1_CASES,
                         ids=[c[0] for c in AC1_CASES])
def test_ac1_bad_verify_value_refused_naming_field(tmp_root, rng, case, value, words):
    """Недопустимое значение `verify` в разделе `description` — отказ загрузки с именем поля `verify`.

    Сценарий: запись локального слоя со случайным именем проекта сначала
    загружается с годным `verify: [human:<имя>]` (контроль), затем — с
    недопустимым значением варианта: объявление `ci` (одно и рядом с
    `human:*`), `agent:<имя>`/`script:<имя>` (текст отказа несёт «тип не
    реализован (пункт C4)»), неизвестный тип, элемент без типа, повтор
    имени `human:*`, значение не список (строка, число), имя вне
    `[a-z0-9-]+` — с заглавной буквой, пустое, с пробелом, с
    подчёркиванием. `targets.target` поднимает `TargetsError`, текст
    называет `verify` и не говорит «неизвестное поле».

    Ловит мутацию: `ci` в профиле молча принят (или принят рядом с
    `human:*`); `agent:*`/`script:*` приняты или отказ без текста «пункт
    C4»; неизвестный тип пропущен; повтор имени не сверяется; строка
    вместо списка принята как список из одного элемента; имя сверяется
    шаблоном шире `[a-z0-9-]+` (заглавные, `_`, пробел) или пустое имя
    принято; отказ не называет поле `verify`.
    """
    name = "r" + word(rng)
    good = check_name(rng)
    entry, error = load_local(name, f"[human:{good}]")
    assert error is None, where(rng, f"контрольная запись не загрузилась: {error}")
    bad = value(check_name(rng), word(rng, 4))
    entry, error = load_local(name, bad)
    assert entry is None, where(rng, f"verify: {bad} — запись загрузилась: {entry}")
    assert "verify" in error, where(rng, f"verify: {bad} — отказ без имени поля: {error}")
    assert UNKNOWN_FIELD not in error, where(rng, f"verify: {bad} — поле не объявлено: {error}")
    for text in words:
        assert text in error, where(rng, f"verify: {bad} — отказ без «{text}»: {error}")


def test_ac2_verify_outside_description_refused(tmp_root, rng):
    """Поле `verify` в плоской записи локального слоя (вне раздела `description`) — отказ загрузки, текст называет `verify`.

    Сценарий: запись локального слоя со случайным именем: контроль — та же
    запись с `verify: [human:<имя>]` в разделе `description` загружается;
    затем поле переносится на уровень разделов записи (рядом с
    `description`/`policy`/`machine`): `targets.target` поднимает
    `TargetsError`, текст называет `verify`.

    Ловит мутацию: `verify` принимается на любом уровне записи (поиск поля
    по всей записи, а не в разделе `description`) — запись загрузилась.
    """
    name = "f" + word(rng)
    good = check_name(rng)
    entry, error = load_local(name, f"[human:{good}]")
    assert error is None, where(rng, f"контрольная запись не загрузилась: {error}")
    write_local(local_entry(name, top_extra=f"    verify: [human:{good}]\n"))
    with pytest.raises(targets.TargetsError) as caught:
        targets.target(name)
    assert "verify" in str(caught.value), where(rng, f"отказ без имени поля: {caught.value}")


@pytest.mark.parametrize("record", ["артель", "внешний проект"])
def test_ac2_verify_in_repo_layer_refused(tmp_root, rng, record):
    """Поле `verify` в записи слоя репозитория (`targets.yaml`) — отказ загрузки, текст называет `verify`.

    Сценарий: `config.TARGETS` песочницы — запись артели с профилем тестов
    и плоская запись внешнего проекта со случайным именем; по параметру
    поле `verify: [human:<имя>]` дописано в запись артели либо в запись
    внешнего проекта. Контроль: те же записи без поля загружаются
    (`targets.load`). С полем `targets.load` поднимает `TargetsError`,
    текст называет `verify`.

    Ловит мутацию: проверка `verify` только в локальном слое — запись
    репозитория с полем загружается молча (поле затем читается как
    профиль); отказ только для артели или только для внешней записи.
    """
    name = "x" + word(rng)
    good = check_name(rng)
    external = (f"  {name}:\n    forge: github\n"
                f"    url: https://localhost/team/{name}\n"
                f"    base: {config.MAIN_BRANCH}\n    token_slot: {name}-token\n"
                f"    no_paths: []\n    project_skills: []\n"
                f"    merge_gate: operator\n")
    line = f"    verify: [human:{good}]\n"
    config.TARGETS.write_text("targets:\n" + artel_target_entry() + external,
                              encoding="utf-8")
    loaded = targets.load()
    assert name in loaded, where(rng, f"контроль: записи {name} нет: {list(loaded)}")
    if record == "артель":
        text = artel_target_entry() + line + external
    else:
        text = artel_target_entry() + external + line
    config.TARGETS.write_text("targets:\n" + text, encoding="utf-8")
    with pytest.raises(targets.TargetsError) as caught:
        targets.load()
    assert "verify" in str(caught.value), where(rng, f"отказ без имени поля: {caught.value}")


@pytest.mark.parametrize("count", [0, 1, 3])
def test_ac3_record_with_or_without_verify_loads(tmp_root, rng, count):
    """Запись локального слоя с `verify: [human:<имя>, …]` в разделе `description` и запись без поля `verify` загружаются.

    Сценарий: запись локального слоя со случайным именем; по параметру —
    без поля `verify` (0) либо с одной или тремя проверками `human:*` с
    различными случайными годными именами (`[a-z0-9-]+`, в том числе с
    цифрами и дефисом). `targets.target` отдаёт запись проекта без отказа.

    Ловит мутацию: шаблон имени уже `[a-z0-9-]+` (дефис или цифра
    отказывают); несколько проверок `human:*` считаются повтором; запись
    без поля `verify` отказывает (поле стало обязательным).
    """
    name = "o" + word(rng)
    names: list = []
    while len(names) < count:
        candidate = check_name(rng) + rng.choice("0123456789") + "-" + rng.choice(LETTERS)
        if candidate not in names:
            names.append(candidate)
    value = f"[{', '.join(f'human:{n}' for n in names)}]" if count else None
    entry, error = load_local(name, value)
    assert error is None, where(rng, f"verify: {value} — отказ: {error}")
    assert entry is not None, where(rng, f"verify: {value} — записи нет")
