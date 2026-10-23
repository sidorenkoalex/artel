"""Данные фикстур pytest в разборе утверждений guard: запись данных
фикстуры у запросившего её теста, `weakened_helpers` по телу фикстуры,
разрешение имени фикстуры, потребители записи (AC-1, AC-2, AC-10 в части
храповика, AC-11..AC-15 в части записей).

Группа: долгоживущий

Красен до реализации: guard прослеживает помощника только по вызову — фикстура, запрошенная параметром, `usefixtures` или `autouse`, в записи теста не попадает, поэтому правка её литерала записей теста не меняет, храповик убыли литералов фикстуры не видит, а `weakened_helpers` сравнивает только утверждения и тела фикстуры без утверждений не называет. Варианты AC-15 со своим утверждением теста зелены и сегодня: метод держит отсутствие исключения рядом с записью фикстуры.

Разбор читается публичными входами: `guard.test_assertions` (записи
`_assertion_records` без узла и происхождения: ключ записи и текст),
`guard.TestModules` (модуль `tests/fixtures.py` своей стороны),
`guard.weakened_helpers`, `guard.assertion_changes` и
`test_integrity.ratchet_finding`. Запись данных фикстуры узнаётся по
содержимому ключа (требование 3 SPEC): в нём есть имя фикстуры, её файл и
`ast.dump` литерала. Имена фикстур, тестов, классов и путей, значения
литералов и форма тела фикстуры (`return`/`yield`/присваивание) берутся из
`random` при каждом запуске; зерно печатается и входит в текст провала.
Свойства чистые, поэтому песочница не нужна.
"""
import random
from collections import Counter

import pytest

from orchestrator.advance_gates import test_integrity
from scripts import guard

FIXTURES_PATH = "tests/fixtures.py"
VALUE = "__VALUE__"

# Стиль импорта pytest (требование 2): строка импорта, декоратор фикстуры,
# декоратор фикстуры autouse, префикс меток.
STYLES = (
    ("import pytest\n", "@pytest.fixture()", "@pytest.fixture(autouse=True)",
     "pytest.mark"),
    ("import pytest\n", "@pytest.fixture", "@pytest.fixture(autouse=True)",
     "pytest.mark"),
    ("import pytest as pt\n", "@pt.fixture", "@pt.fixture(autouse=True)",
     "pt.mark"),
    ("from pytest import fixture, mark\n", "@fixture", "@fixture(autouse=True)",
     "mark"),
)


def seeded():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def word(rng, length=6):
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def two_values(rng):
    old = rng.randrange(10, 10_000)
    return old, old + rng.randrange(1, 10_000)


def fixture_text(decorator, name, body, params=""):
    lines = "".join(f"    {line}\n" for line in body.splitlines())
    return f"\n\n{decorator}\ndef {name}({params}):\n{lines}"


def value_body(rng):
    """Тело фикстуры с литералом `VALUE`: возвращаемым, отдаваемым `yield`
    либо присваиваемым (требование 3)."""
    return rng.choice((f"return {VALUE}", f"yield {VALUE}",
                       f"value = {VALUE}\nreturn value"))


def render(template, value):
    return None if template is None else template.replace(VALUE, str(value))


def records(test_source, path, shared=None):
    """Записи разбора утверждений по квалифицированному имени теста:
    `shared` — текст `tests/fixtures.py` этой стороны (`None` — модуля
    нет)."""
    texts = {path: test_source, FIXTURES_PATH: shared}
    modules = guard.TestModules(lambda p: texts.get(p))
    return guard.test_assertions(test_source, path, modules)


def multiset(items):
    return Counter(repr(item) for item in items)


def names_fixture(item, name, file, value):
    text = repr(item)
    return name in text and file in text and str(abs(value)) in text


class Scenario:
    """Файл теста и (возможно) `tests/fixtures.py` с литералом `VALUE` в
    фикстуре `fixture`, запрошенной тестом `qual` способом `way`."""

    def __init__(self, rng, way, place, style):
        imports, plain, autouse, mark = style
        self.path = f"tests/test_{word(rng)}.py"
        self.fixture = f"fx_{word(rng)}"
        self.file = self.path if place == "own" else FIXTURES_PATH
        t = word(rng)
        decorator = autouse if way == "autouse" else plain
        own, shared = [], []
        (own if place == "own" else shared).append(
            fixture_text(decorator, self.fixture, value_body(rng)))
        top = ""
        if way == "param":
            test = f"\n\ndef test_{t}({self.fixture}):\n    assert {self.fixture}\n"
            self.qual = f"test_{t}"
        elif way == "usefixtures_test":
            test = (f"\n\n@{mark}.usefixtures(\"{self.fixture}\")\n"
                    f"def test_{t}():\n    pass\n")
            self.qual = f"test_{t}"
        elif way == "usefixtures_class":
            cls = f"Test{word(rng).capitalize()}"
            test = (f"\n\n@{mark}.usefixtures(\"{self.fixture}\")\n"
                    f"class {cls}:\n\n    def test_{t}(self):\n        pass\n")
            self.qual = f"{cls}{guard.TEST_NAME_SEP}test_{t}"
        elif way == "pytestmark":
            use = f"{mark}.usefixtures(\"{self.fixture}\")"
            top = f"\npytestmark = {rng.choice((use, f'[{use}]'))}\n"
            test = f"\n\ndef test_{t}():\n    pass\n"
            self.qual = f"test_{t}"
        elif way == "autouse":
            test = f"\n\ndef test_{t}():\n    pass\n"
            self.qual = f"test_{t}"
        elif way == "nested":
            outer = f"outer_{word(rng)}"
            own.append(fixture_text(plain, outer, f"return {self.fixture}",
                                    params=self.fixture))
            test = f"\n\ndef test_{t}({outer}):\n    assert {outer}\n"
            self.qual = f"test_{t}"
        else:
            raise ValueError(way)
        self.test = imports + top + "".join(own) + test
        self.shared = imports + "".join(shared) if shared else None

    def records(self, value):
        found = records(render(self.test, value), self.path,
                        render(self.shared, value))
        assert found is not None and self.qual in found, found
        return found[self.qual]


WAYS = (("param", "own"), ("param", "shared"),
        ("usefixtures_test", "own"), ("usefixtures_test", "shared"),
        ("usefixtures_class", "own"), ("usefixtures_class", "shared"),
        ("pytestmark", "own"), ("pytestmark", "shared"),
        ("autouse", "own"),
        ("nested", "own"), ("nested", "shared"))


@pytest.mark.parametrize("way,place", WAYS)
def test_ac2_every_request_way_gets_fixture_data_record(way, place):
    """Каждый способ запроса фикстуры даёт тесту запись её данных.

    Сценарий: фикстура со случайным литералом объявлена в файле теста или
    в `tests/fixtures.py` декоратором каждого стиля (`@pytest.fixture()`,
    `@pytest.fixture`, `@pt.fixture` после `import pytest as pt`,
    `@fixture` после `from pytest import fixture`); тест запрашивает её
    способом `way` (параметр, `usefixtures` на тесте, на классе, в
    `pytestmark`, `autouse`, через другую фикстуру). Смена литерала
    фикстуры меняет записи теста, и среди записей головы есть запись с
    именем фикстуры, её файлом и новым литералом.

    Ловит мутацию: фикстура не прослеживается (или прослеживается только
    по параметру, без `usefixtures`/`autouse`/вложенной фикстуры, или
    только `@pytest.fixture` без псевдонимов) — записи базы и головы
    совпадают, записи с именем фикстуры нет.
    """
    seed, rng = seeded()
    for style in STYLES:
        sc = Scenario(rng, way, place, style)
        old, new = two_values(rng)
        base, head = sc.records(old), sc.records(new)
        context = (f"зерно {seed}; стиль {style[1]}; файл теста:\n"
                   f"{render(sc.test, new)}\nfixtures.py:\n"
                   f"{render(sc.shared, new)}\nбаза: {base}\nголова: {head}")
        assert multiset(base) != multiset(head), context
        assert any(names_fixture(item, sc.fixture, sc.file, new)
                   for item in head), context


@pytest.mark.parametrize("place", ("own", "shared"))
def test_ac1_fixture_literal_edit_named_by_weakened_helpers_and_records(place):
    """Правка литерала фикстуры: `weakened_helpers` называет фикстуру, записи теста различаются.

    Сценарий `own`: фикстура в файле теста, правка литерала в ней —
    `weakened_helpers` по базе и голове файла теста называет фикстуру.
    Сценарий `shared`: фикстура в `tests/fixtures.py`, тело в базе и в
    голове различается, файл теста одинаков — `weakened_helpers` по базе и
    голове `tests/fixtures.py` называет фикстуру. В обоих сценариях записи
    теста стороны базы и стороны головы различаются, и запись головы
    называет фикстуру и её файл.

    Ловит мутацию: `weakened_helpers` сравнивает только утверждения (у
    фикстуры их нет) — имени фикстуры в ответе нет; данные фикстуры из
    `tests/fixtures.py` не читаются модулями своей стороны — записи
    вызывающего вне диффа одинаковы по обе стороны.
    """
    seed, rng = seeded()
    sc = Scenario(rng, "param", place, rng.choice(STYLES))
    old, new = two_values(rng)
    if place == "own":
        weakened = guard.weakened_helpers(render(sc.test, old),
                                          render(sc.test, new))
    else:
        assert render(sc.test, old) == render(sc.test, new)
        weakened = guard.weakened_helpers(render(sc.shared, old),
                                          render(sc.shared, new))
    base, head = sc.records(old), sc.records(new)
    context = (f"зерно {seed}; {place}; weakened_helpers: {weakened}\n"
               f"база: {base}\nголова: {head}")
    assert sc.fixture in weakened, context
    assert multiset(base) != multiset(head), context
    assert any(names_fixture(item, sc.fixture, sc.file, new)
               for item in head), context


def test_ac11_own_fixture_shadows_shared_one():
    """Одноимённая фикстура своего файла важнее фикстуры `tests/fixtures.py`.

    Сценарий: фикстура с одним именем и разными случайными литералами
    объявлена в файле теста и в `tests/fixtures.py`, тест запрашивает её
    параметром. Правка литерала своей фикстуры меняет записи теста; ни
    одна запись не называет `tests/fixtures.py`; правка литерала
    одноимённой фикстуры `tests/fixtures.py` записей теста не меняет.

    Ловит мутацию: имя ищется сначала в `tests/fixtures.py` (или в обоих
    модулях) — записи называют `tests/fixtures.py`, правка общей фикстуры
    меняет записи теста.
    """
    seed, rng = seeded()
    imports, plain, _autouse, _mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    own_old, own_new = two_values(rng)
    shared_old, shared_new = two_values(rng)
    shared_old, shared_new = shared_old + 20_000, shared_new + 20_000

    def test_source(value):
        return (imports + fixture_text(plain, name, f"return {value}")
                + f"\n\ndef test_{t}({name}):\n    assert {name}\n")

    def shared_source(value):
        return imports + fixture_text(plain, name, f"return {value}")

    qual = f"test_{t}"
    base = records(test_source(own_old), path, shared_source(shared_old))[qual]
    own_edit = records(test_source(own_new), path,
                       shared_source(shared_old))[qual]
    shared_edit = records(test_source(own_old), path,
                          shared_source(shared_new))[qual]
    context = (f"зерно {seed}\nбаза: {base}\nправка своей: {own_edit}\n"
               f"правка общей: {shared_edit}")
    assert multiset(base) != multiset(own_edit), context
    assert multiset(base) == multiset(shared_edit), context
    assert not any(FIXTURES_PATH in repr(item) for item in base + own_edit), \
        context


@pytest.mark.parametrize("place", ("own", "shared"))
def test_ac12_parametrize_argument_is_not_a_fixture(place):
    """Имя из аргументов `parametrize` теста фикстурой не считается.

    Сценарий: тест параметризован `parametrize` по имени, у которого есть
    одноимённая фикстура (в своём файле или в `tests/fixtures.py`); имена
    аргументов — строкой, строкой через запятую или кортежем. Правка
    литерала фикстуры записей теста не меняет, и ни одна запись не несёт
    литерала фикстуры. Контроль: тот же тест без `parametrize` от той же
    правки записи меняет — значит фикстура в сценарии прослеживается.

    Ловит мутацию: фикстура разрешается по имени параметра без сверки с
    именами аргументов `parametrize` — тест получает запись данных
    фикстуры, правка её литерала меняет записи.
    """
    seed, rng = seeded()
    imports, plain, _autouse, mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, other, t = f"fx_{word(rng)}", f"arg_{word(rng)}", word(rng)
    argnames = rng.choice((f'"{name}"', f'"{name},{other}"',
                           f'"{name}, {other}"', f'("{name}", "{other}")'))
    single = argnames == f'"{name}"'
    values = "[1, 2]" if single else "[(1, 2), (3, 4)]"
    params = name if single else f"{name}, {other}"
    fixture = fixture_text(plain, name, f"return {VALUE}")
    own = fixture if place == "own" else ""
    shared = imports + fixture if place == "shared" else None
    plain_test = f"\n\ndef test_{t}({params}):\n    assert {name}\n"
    marked = imports + own + (f"\n\n@{mark}.parametrize({argnames}, {values})"
                              + plain_test)
    control = imports + own + plain_test
    old, new = two_values(rng)
    qual = f"test_{t}"

    def side(template, value):
        return records(render(template, value), path,
                       render(shared, value))[qual]

    base, head = side(marked, old), side(marked, new)
    context = f"зерно {seed}; {argnames}\nбаза: {base}\nголова: {head}"
    assert multiset(base) == multiset(head), context
    assert not any(str(v) in repr(item) for item in base + head
                   for v in (old, new)), context
    assert multiset(side(control, old)) != multiset(side(control, new)), \
        f"контроль без parametrize: {context}"


def test_ac13_swapping_two_fixture_literals_changes_records():
    """Обмен значениями двух литералов фикстуры меняет записи теста.

    Сценарий: фикстура `limit = a; expected = b; return limit, expected`
    со случайными различными `a`, `b`; в голове значения переставлены.
    Мультимножество записей теста в базе и в голове различается.

    Ловит мутацию: ключ записи — только `ast.dump` литерала без
    порядкового номера в теле фикстуры — мультимножества совпадают, обмен
    не виден.
    """
    seed, rng = seeded()
    imports, plain, _autouse, _mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    a, b = two_values(rng)
    test = f"\n\ndef test_{t}({name}):\n    assert {name}\n"
    sources = [fixture_file(imports, plain, name,
                            f"limit = {x}\nexpected = {y}\n"
                            f"return limit, expected", test)
               for x, y in ((a, b), (b, a))]
    base = records(sources[0], path)[f"test_{t}"]
    head = records(sources[1], path)[f"test_{t}"]
    context = f"зерно {seed}\n{sources[0]}\nбаза: {base}\nголова: {head}"
    assert multiset(base) != multiset(head), context


def fixture_file(imports, decorator, name, body, test=""):
    return imports + fixture_text(decorator, name, body) + test


@pytest.mark.parametrize("form", ("call_argument", "sign"))
def test_ac14_call_argument_and_sign_edits_change_records(form):
    """`Config(limit=a)` → `Config(limit=b)` и `return a` → `return -a` меняют записи теста.

    Сценарий: фикстура своего файла возвращает вызов с литералом в
    аргументе либо число; правка — новое значение аргумента либо смена
    знака. Записи теста в базе и в голове различаются.

    Ловит мутацию: в запись идут только литералы, стоящие прямо в
    `return`, без аргументов вызовов — правка `Config(limit=…)` не видна;
    знак не входит в литерал (пишется `Constant` под `UnaryOp`) — `a` и
    `-a` дают одну запись.
    """
    seed, rng = seeded()
    imports, plain, _autouse, _mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    old, new = two_values(rng)
    test = f"\n\ndef test_{t}({name}):\n    assert {name}\n"
    if form == "call_argument":
        cls = f"Config{word(rng).capitalize()}"
        bodies = (f"return {cls}(limit={old})", f"return {cls}(limit={new})")
    else:
        bodies = (f"return {old}", f"return -{old}")
    sources = [fixture_file(imports, plain, name, body, test) for body in bodies]
    base = records(sources[0], path)[f"test_{t}"]
    head = records(sources[1], path)[f"test_{t}"]
    context = f"зерно {seed}\n{sources[1]}\nбаза: {base}\nголова: {head}"
    assert multiset(base) != multiset(head), context


@pytest.mark.parametrize("place", ("own", "shared"))
def test_ac14_helper_called_by_fixture_is_traced_one_level(place):
    """Правка литерала в помощнике фикстуры меняет записи теста; `weakened_helpers` называет помощника.

    Сценарий: фикстура возвращает `_expected()`, помощник
    `def _expected(): return a`, правка в помощнике `a` → `b`, тело
    фикстуры не меняется. `own` — всё в файле теста: `weakened_helpers`
    по файлу теста называет `_expected`. `shared` — помощник и фикстура в
    `tests/fixtures.py`, файл теста одинаков: `weakened_helpers` по
    `tests/fixtures.py` называет и `_expected`, и фикстуру, которая его
    вызывает. В обоих случаях записи теста базы и головы различаются.

    Ловит мутацию: константы помощника фикстуры в запись не идут —
    записи совпадают; `weakened_helpers` не называет фикстуру, вызывающую
    изменённого помощника, — поиск вызывающих по имени помощника находит
    только `tests/fixtures.py`, и тест вне диффа не сравнивается.
    """
    seed, rng = seeded()
    imports, plain, _autouse, _mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    old, new = two_values(rng)

    def module(value):
        return (imports + f"\n\ndef _expected():\n    return {value}\n"
                + fixture_text(plain, name, "return _expected()"))

    test = f"\n\ndef test_{t}({name}):\n    assert {name}\n"
    qual = f"test_{t}"
    if place == "own":
        sources = [module(v) + test for v in (old, new)]
        weakened = guard.weakened_helpers(*sources)
        base = records(sources[0], path)[qual]
        head = records(sources[1], path)[qual]
        expected = {"_expected"}
    else:
        test_source = imports + test
        weakened = guard.weakened_helpers(module(old), module(new))
        base = records(test_source, path, module(old))[qual]
        head = records(test_source, path, module(new))[qual]
        expected = {"_expected", name}
    context = (f"зерно {seed}; weakened_helpers: {weakened}\nбаза: {base}\n"
               f"голова: {head}")
    assert expected <= weakened, context
    assert multiset(base) != multiset(head), context


def test_ac10_fixture_records_count_in_ratchet():
    """Убыль литералов фикстуры — убыль храповика; мандат на путь её снимает.

    Сценарий: фикстура своего файла возвращает кортеж из двух-четырёх
    случайных литералов, в голове из него убран один литерал; утверждения
    самого теста не меняются. `ratchet_finding` без мандата даёт находку,
    с мандатом на путь файла — нет.

    Ловит мутацию: записи данных фикстуры не входят в счёт утверждений
    храповика — счёт по обе стороны одинаков, находки нет.
    """
    seed, rng = seeded()
    imports, plain, _autouse, _mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    values = [rng.randrange(10, 10_000) + 10_000 * i
              for i in range(rng.randrange(2, 5))]
    test = f"\n\ndef test_{t}({name}):\n    assert {name}\n"
    base = fixture_file(imports, plain, name,
                        f"return {tuple(values)!r}", test)
    head = fixture_file(imports, plain, name,
                        f"return {tuple(values[:-1])!r}", test)
    found = test_integrity.ratchet_finding({path: base}, {path: head}, {})
    covered = test_integrity.ratchet_finding({path: base}, {path: head},
                                             {path: "ANSWER-1"})
    context = f"зерно {seed}\nбаза:\n{base}\nголова:\n{head}"
    assert found is not None, context
    assert covered is None, context


@pytest.mark.parametrize("own", ("unmatched", "removed", "none"))
def test_ac15_fixture_record_passes_consumers_without_errors(own):
    """Запись фикстуры проходит `assertion_changes` и храповик без исключения, рядом со своим утверждением без пары.

    Сценарий: литерал фикстуры изменён; у теста рядом либо своё
    утверждение, сменившее форму (`assert x == a` → `assert x`, пары нет),
    либо удалённое утверждение, либо своих утверждений нет.
    `assertion_changes` возвращает для теста `AssertionChange` известного
    вида с признаками-строками (их читает двусторонний прогон), а
    `ratchet_finding` отрабатывает без исключения.

    Ловит мутацию: запись фикстуры несёт узел, у которого нет `func`
    (литерал), а `_other_change_sign`/`_assertion_kind` обращаются к нему
    как к вызову — `AttributeError`; запись фикстуры не доходит до
    `assertion_changes` — теста в ответе нет при варианте `none`.
    """
    seed, rng = seeded()
    imports, plain, _autouse, _mark = rng.choice(STYLES)
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    old, new = two_values(rng)
    check = rng.randrange(1, 9)
    base_body = {"unmatched": f"assert {name} == {check}",
                 "removed": f"assert {name} == {check}", "none": "pass"}[own]
    head_body = {"unmatched": f"assert {name}", "removed": "pass",
                 "none": "pass"}[own]
    base = fixture_file(imports, plain, name, f"return {old}",
                        f"\n\ndef test_{t}({name}):\n    {base_body}\n")
    head = fixture_file(imports, plain, name, f"return {new}",
                        f"\n\ndef test_{t}({name}):\n    {head_body}\n")
    context = f"зерно {seed}\nбаза:\n{base}\nголова:\n{head}"
    changes = guard.assertion_changes(base, head, (path, path))
    assert changes is not None and f"test_{t}" in changes, \
        f"{context}\nответ: {changes}"
    change = changes[f"test_{t}"]
    assert change.kind in (guard.ASSERTION_CHANGE_EXPECTATION,
                           guard.ASSERTION_CHANGE_OTHER), context
    assert all(isinstance(sign, str) for sign in change.signs), context
    test_integrity.ratchet_finding({path: base}, {path: head}, {})
