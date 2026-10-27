"""Поля доставки записи проекта для состояния `awaiting_human`: `targets.delivery_policy` с умолчаниями, проверка `max_awaiting`/`awaiting_holds_zones` при загрузке, `mr_assignee` целым и строкой.

Группа: долгоживущий
Красен до реализации: функции `targets.delivery_policy` ещё нет (AttributeError), поля `max_awaiting`/`awaiting_holds_zones` раздела `policy` загрузка отказывает как «неизвестное поле», а `mr_assignee: 42` — как «не непустая строка».

Свойство — чистая проверка записи (`targets.target` над файлом локального
слоя песочницы `tmp_root`) и чтение её полей доставки, без git и FSM.
Отказ проверяется в паре с контрольной загрузкой той же записи с
допустимым значением: так отказ «неизвестное поле» до реализации не
сходит за отказ проверки значения. Имена проектов и числа порождаются
модулем `random` при каждом запуске; зерно печатается и входит в текст
провала.
"""
import random

import pytest

from orchestrator import config, targets

LETTERS = "abcdefghijkmnopqrstuvwxyz"


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def project_name(rng: random.Random) -> str:
    return "d" + "".join(rng.choice(LETTERS) for _ in range(7))


def write_record(name: str, policy: dict | None = None) -> None:
    """Файл локального слоя с одной записью проекта в трёх разделах;
    `policy` — дополнительные поля раздела `policy` строками YAML."""
    extra = "".join(f"      {key}: {value}\n"
                    for key, value in (policy or {}).items())
    entry = (f"  {name}:\n"
             f"    description:\n      base: {config.MAIN_BRANCH}\n"
             f"      test_profile:\n        command: [python3, -m, pytest]\n"
             f"        long_lived_dir: tests\n"
             f"        long_lived_name: test_<id>_<name>.py\n"
             f"    policy:\n      no_paths: []\n      project_skills: []\n"
             f"      merge_gate: operator\n"
             f"      weakening_scope: [tests/**/*.py]\n"
             f"      mutation_claim_scope: [tests/test_*.py]\n"
             + extra
             + f"    machine:\n      forge: github\n"
             f"      url: https://localhost/team/{name}\n"
             f"      token_slot: {name}-token\n")
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + entry, encoding="utf-8")


def load(name: str, policy: dict | None = None):
    """(плоская запись, None) — загрузилась; (None, текст отказа) — нет."""
    write_record(name, policy)
    try:
        return targets.target(name), None
    except targets.TargetsError as exc:
        return None, str(exc)


def test_ac1_delivery_policy_defaults_for_record_without_fields(tmp_root, seed):
    """Запись без полей доставки — `delivery_policy` отдаёт все пять умолчаний.

    Сценарий: запись локального слоя со случайным именем без
    `max_awaiting`, `awaiting_holds_zones`, `draft_mr`, `max_in_flight`,
    `mr_assignee` загружается; `targets.delivery_policy(запись)` даёт
    `max_awaiting` 3, `awaiting_holds_zones` True, `draft_mr` True,
    `max_in_flight` None, `mr_assignee` None.

    Ловит мутацию: умолчание `max_awaiting` — 1 или `None`;
    `awaiting_holds_zones` по умолчанию False (зоны отпускаются);
    `draft_mr` по умолчанию False; `max_in_flight` по умолчанию число
    вместо None; одного из ключей нет в выдаче (KeyError).
    """
    rng = random.Random(seed)
    name = project_name(rng)
    note = f"зерно: {seed}; проект {name}"
    entry, error = load(name)
    assert error is None, f"{note}: {error}"
    policy = targets.delivery_policy(entry)
    assert policy["max_awaiting"] == 3, f"{note}: {policy}"
    assert policy["awaiting_holds_zones"] is True, f"{note}: {policy}"
    assert policy["draft_mr"] is True, f"{note}: {policy}"
    assert policy["max_in_flight"] is None, f"{note}: {policy}"
    assert policy["mr_assignee"] is None, f"{note}: {policy}"


def test_ac1_delivery_policy_reads_given_values(tmp_root, seed):
    """Заданные в записи поля доставки `delivery_policy` отдаёт как есть, не умолчанием.

    Сценарий: запись со случайным `max_awaiting` (целое > 0, не 3),
    `awaiting_holds_zones: false`, `draft_mr: false` и случайным
    `max_in_flight` загружается; `delivery_policy` отдаёт именно эти
    значения. Контроль к проверке умолчаний: функция, всегда отдающая
    умолчания, на нём краснеет.

    Ловит мутацию: `delivery_policy` возвращает словарь умолчаний, не
    глядя в запись; поля `max_awaiting`/`awaiting_holds_zones` объявлены и
    проверены, но не перенесены в плоскую запись — `delivery_policy`
    видит умолчание 3/True.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    awaiting = rng.choice([1, 2, 4, 5, 7, 11, 40])
    in_flight = rng.randrange(1, 50)
    note = f"зерно: {seed}; проект {name}; max_awaiting {awaiting}"
    entry, error = load(name, {"max_awaiting": awaiting,
                               "awaiting_holds_zones": "false",
                               "draft_mr": "false",
                               "max_in_flight": in_flight})
    assert error is None, f"{note}: {error}"
    policy = targets.delivery_policy(entry)
    assert policy["max_awaiting"] == awaiting, f"{note}: {policy}"
    assert policy["awaiting_holds_zones"] is False, f"{note}: {policy}"
    assert policy["draft_mr"] is False, f"{note}: {policy}"
    assert policy["max_in_flight"] == in_flight, f"{note}: {policy}"


# (вариант, поле, плохое значение YAML, допустимое значение YAML)
REFUSALS = [
    ("max-awaiting-zero", "max_awaiting", "0", "3"),
    ("max-awaiting-negative", "max_awaiting", "-2", "3"),
    ("max-awaiting-string", "max_awaiting", '"3"', "3"),
    ("max-awaiting-word", "max_awaiting", "many", "3"),
    ("holds-zones-word", "awaiting_holds_zones", "yes", "true"),
    ("holds-zones-int", "awaiting_holds_zones", "1", "false"),
    ("holds-zones-string", "awaiting_holds_zones", '"true"', "true"),
]


@pytest.mark.parametrize("case,field,bad,good", REFUSALS,
                         ids=[c[0] for c in REFUSALS])
def test_ac1_bad_awaiting_field_refuses_load_with_field_name(tmp_root, seed, case,
                                                            field, bad, good):
    """Негодное значение `max_awaiting`/`awaiting_holds_zones` — отказ загрузки с именем поля.

    Сценарий: запись со случайным именем и допустимым значением поля
    загружается (контроль: поле объявлено); та же запись с `max_awaiting`
    0, отрицательным, строкой, словом или с `awaiting_holds_zones` словом,
    целым, строкой — `TargetsError`, текст называет поле и не говорит
    «неизвестное поле».

    Ловит мутацию: `max_awaiting` сравнивается `>= 0` — 0 пройдёт;
    проверки типа нет — строка `"3"` пройдёт; `awaiting_holds_zones`
    приводится `bool(...)` — `yes`/`1` пройдут; отказ называет не то поле.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    note = f"зерно: {seed}; {case}; проект {name}"
    entry, error = load(name, {field: good})
    assert error is None, f"{note}: контрольная запись не загрузилась: {error}"
    entry, error = load(name, {field: bad})
    assert entry is None, f"{note}: запись загрузилась: {entry}"
    assert field in error, f"{note}: отказ не называет поле {field}: {error}"
    assert "неизвестное" not in error, f"{note}: поле не объявлено: {error}"


def test_ac1_random_non_positive_max_awaiting_refused(tmp_root, seed):
    """Случайное целое ≤ 0 в `max_awaiting` — отказ загрузки с именем поля.

    Сценарий: для нескольких случайных целых от -1000 до 0 запись с
    `max_awaiting: <число>` не загружается, текст отказа называет
    `max_awaiting`; та же запись со случайным целым > 0 загружается.

    Ловит мутацию: граница сдвинута (`< 0` вместо `<= 0`, `< -1`) —
    одно из чисел пройдёт загрузку.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    for value in [0] + [rng.randrange(-1000, 0) for _ in range(3)]:
        note = f"зерно: {seed}; проект {name}; max_awaiting {value}"
        entry, error = load(name, {"max_awaiting": value})
        assert entry is None, f"{note}: запись загрузилась: {entry}"
        assert "max_awaiting" in error, f"{note}: {error}"
    good = rng.randrange(1, 1000)
    entry, error = load(name, {"max_awaiting": good})
    assert error is None, f"зерно: {seed}; max_awaiting {good}: {error}"


def test_ac2_mr_assignee_string_and_integer_load(tmp_root, seed):
    """`mr_assignee` строкой `alice` и целым 42 — запись загружается без отказа.

    Сценарий: запись со случайным именем и `policy.mr_assignee: alice`
    загружается; та же запись с `mr_assignee: 42` и со случайным
    положительным целым — тоже.

    Ловит мутацию: проверка загрузки оставлена прежней («не непустая
    строка») — целое 42 отказано; целое допущено, но строка — нет.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    for value in ("alice", 42, rng.randrange(1, 10 ** 6)):
        note = f"зерно: {seed}; проект {name}; mr_assignee {value!r}"
        entry, error = load(name, {"mr_assignee": value})
        assert error is None, f"{note}: {error}"


def test_ac2_delivery_policy_reads_digits_as_id_and_name_as_string(tmp_root, seed):
    """Целое и строка цифр в `mr_assignee` — один и тот же id исполнителя; `alice` — строка как есть.

    Сценарий: случайное положительное целое N; запись с
    `mr_assignee: N` и запись с `mr_assignee: "N"` (строка цифр в
    кавычках) дают в `delivery_policy` одно и то же значение
    `mr_assignee`, и оно не строка `"N"` как есть (толкование как id, а
    не как имя); запись с `mr_assignee: alice` даёт строку `"alice"`.

    Ловит мутацию: строка цифр не толкуется как id и уходит строкой как
    есть — значения для N и `"N"` разойдутся; `alice` толкуется как id
    или подменяется (None, пустое) — значение не `"alice"`.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    number = rng.randrange(1, 10 ** 6)
    note = f"зерно: {seed}; проект {name}; N {number}"
    by_int, error = load(name, {"mr_assignee": number})
    assert error is None, f"{note}: {error}"
    by_digits, error = load(name, {"mr_assignee": f'"{number}"'})
    assert error is None, f"{note}: {error}"
    by_name, error = load(name, {"mr_assignee": "alice"})
    assert error is None, f"{note}: {error}"
    as_int = targets.delivery_policy(by_int)["mr_assignee"]
    as_digits = targets.delivery_policy(by_digits)["mr_assignee"]
    assert as_int == as_digits, f"{note}: {as_int!r} != {as_digits!r}"
    assert as_digits != str(number), f"{note}: строка цифр не истолкована: {as_digits!r}"
    assert str(number) in repr(as_int), f"{note}: id потерян: {as_int!r}"
    assert targets.delivery_policy(by_name)["mr_assignee"] == "alice", note

