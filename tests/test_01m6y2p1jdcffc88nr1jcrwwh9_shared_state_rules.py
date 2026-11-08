"""Правила guard для общего состояния (ADR-0032 п. 4): фикстуры уровня модуля только через `shared_readonly`, `build` — помощник фикстуры, в модуле с общей фикстурой нет других песочниц, правила размера не трогают файлы планки.

Группа: долгоживущий
Красен до реализации: `pytest_style_errors_from_files` не знает `scope=` и `shared_readonly` и не принимает `sandbox_sources`, `_fixture_table` не видит присваивания общей фикстуры, а `long_lived_errors_from_files` даёт «нет метки размера» файлам планки — отказов про shared_readonly и песочницы нет, гейт неослабления правки `build` не называет, вызов с `sandbox_sources` падает на `TypeError`.

Свойства чистые — разбор исходников строками в памяти публичными входами
`scripts.guard` (`pytest_style_errors_from_files`, `assertion_changes`,
`long_lived_errors_from_files`, `long_lived_plank_errors`,
`sandbox_sources_from_dir`), песочница не нужна. Имена фикстур, функций,
тестов, классов, модулей песочниц и литералы берутся из `random` при каждом
запуске; зерно печатается и входит в текст провала.
"""
import random
import re

import pytest

from orchestrator import config
from scripts import guard

pytestmark = pytest.mark.size("small")

SCOPE_ADR = "только через shared_readonly (ADR-0032 п. 4)"
OTHER_CALL = ("иной вызов shared_readonly — только <имя> = "
              "shared_readonly(<класс>, <функция>) на уровне модуля "
              "(ADR-0032 п. 4)")
BUILD_NOT_LOCAL = "build общей фикстуры — функция этого файла"
ASSERT_IN_FIXTURE = "утверждение в фикстуре"
OTHER_SANDBOXES = "в модуле с общей фикстурой других песочниц нет"
SECOND_SHARED = "вторая общая фикстура в модуле"
NO_SIZE_MARK = "размер — нет метки размера"


def seeded():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def word(rng, length=7):
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def label_of(rng):
    return f"tests/test_{word(rng)}.py"


def style_errors(source, label, **kwargs):
    return guard.pytest_style_errors_from_files([(label, source)], **kwargs)


def having(errors, needle):
    return [line for line in errors if needle in line]


# ------------------------------------------------------------------ AC-1

def scope_source(rng, form, scope):
    """Исходник с фикстурой уровня `scope` (текст выражения или `None` —
    без аргумента) в форме `form`; отдаёт (исходник, имя фикстуры)."""
    name, test = f"fx_{word(rng)}", f"test_{word(rng)}"
    arg = "" if scope is None else f"scope={scope}"
    prefix = "pt" if form == "alias" else "pytest"
    head = "import pytest as pt\n" if form == "alias" else "import pytest\n"
    if scope is not None and re.fullmatch(r"[A-Z_]+", scope):
        head += f"\n{scope} = \"module\"\n"
    if form == "assign":
        raw = f"raw_{word(rng)}"
        body = (f"\n\ndef {raw}():\n    return {rng.randrange(1000)}\n\n\n"
                f"{name} = {prefix}.fixture({arg})({raw})\n")
    else:
        body = (f"\n\n@{prefix}.fixture({arg})\ndef {name}():\n"
                f"    return {rng.randrange(1000)}\n")
    return head + body + f"\n\ndef {test}({name}):\n    assert {name}\n", name


@pytest.mark.parametrize("form", ["decorator", "alias", "assign"])
@pytest.mark.parametrize("scope", ["module", "class", "package", "session"])
def test_ac1_wide_scope_literal_refused(form, scope):
    """Фикстура с литералом `scope=` шире функции получает отказ про shared_readonly.

    Сценарий: `@pytest.fixture(scope="<scope>")`, тот же декоратор через
    псевдоним `import pytest as pt` и присваивание `x =
    pytest.fixture(scope="<scope>")(f)` без декоратора; имена случайны.
    Среди ошибок `pytest_style_errors_from_files` есть строка «фикстура
    уровня <scope> — только через shared_readonly (ADR-0032 п. 4)».

    Ловит мутацию: `scope="module"` (или иной уровень из четырёх)
    пропускается; `scope=` читается только у `pytest.fixture`, без
    псевдонима модуля; проверяется только декоратор — присваивание
    `pytest.fixture(scope=…)(f)` пропускается: строки отказа нет.
    """
    seed, rng = seeded()
    source, _name = scope_source(rng, form, f'"{scope}"')
    errors = style_errors(source, label_of(rng))
    expected = f"фикстура уровня {scope} — {SCOPE_ADR}"
    assert having(errors, expected), f"зерно {seed}\n{source}\n{errors}"


@pytest.mark.parametrize("form", ["decorator", "alias", "assign"])
def test_ac1_non_literal_scope_refused_with_expression(form):
    """`scope=` не литералом — отказ, называющий выражение scope.

    Сценарий: `scope=<ИМЯ>`, где имя — случайная константа модуля; формы —
    декоратор, декоратор через псевдоним, присваивание. Среди ошибок есть
    строка «фикстура уровня `<ИМЯ>` — только через shared_readonly
    (ADR-0032 п. 4)» (обратные кавычки вокруг выражения допускаются).

    Ловит мутацию: отказ даётся только литералам из перечня — не литерал
    проходит без строки отказа; либо текст называет не выражение (пустое
    значение, `None`) — имени константы в строке нет.
    """
    seed, rng = seeded()
    level = f"LEVEL_{word(rng).upper()}"
    source, _name = scope_source(rng, form, level)
    errors = style_errors(source, label_of(rng))
    pattern = re.compile(rf"фикстура уровня `?{re.escape(level)}`? — "
                         rf"{re.escape(SCOPE_ADR)}")
    assert any(pattern.search(line) for line in errors), \
        f"зерно {seed}\n{source}\n{errors}"


@pytest.mark.parametrize("form", ["decorator", "alias", "assign"])
@pytest.mark.parametrize("scope", ['"function"', "None", None])
def test_ac1_function_scope_not_refused(form, scope):
    """`scope="function"`, `scope=None` и вызов без `scope` отказа про shared_readonly не дают.

    Сценарий: те же три формы (декоратор, псевдоним, присваивание) с
    уровнем функции, `None` или без аргумента. Ни одна ошибка
    `pytest_style_errors_from_files` не содержит «только через
    shared_readonly».

    Ловит мутацию: отказ на любой `scope=` без разбора значения (в том числе
    `"function"`/`None`) либо на любом вызове `pytest.fixture(...)(f)` вне
    декоратора — появляется строка отказа.
    """
    seed, rng = seeded()
    source, _name = scope_source(rng, form, scope)
    errors = style_errors(source, label_of(rng))
    assert not having(errors, SCOPE_ADR), f"зерно {seed}\n{source}\n{errors}"


# ------------------------------------------------------------------ AC-2

# Форма импорта `shared_readonly` (требование 2): строки импорта и
# выражение вызова; {m}/{x} — случайные имена.
IMPORT_FORMS = {
    "from": ("from tests.sandbox import shared_readonly\n", "shared_readonly"),
    "from_as": ("from tests.sandbox import shared_readonly as {x}\n", "{x}"),
    "import": ("import tests.sandbox\n", "tests.sandbox.shared_readonly"),
    "import_as": ("import tests.sandbox as {m}\n", "{m}.shared_readonly"),
    "from_pkg": ("from tests import sandbox\n", "sandbox.shared_readonly"),
    "from_pkg_as": ("from tests import sandbox as {m}\n", "{m}.shared_readonly"),
}


class Shared:
    """Исходник файла с общей фикстурой `fx = <sr>(<класс>, <build>)`."""

    def __init__(self, rng, form="from", alias_class=False):
        names = {"m": f"m_{word(rng)}", "x": f"sr_{word(rng)}"}
        imports, call = IMPORT_FORMS[form]
        self.imports = imports.format(**names)
        self.sr = call.format(**names)
        if alias_class:
            self.cls = f"R{word(rng)}"
            self.imports += (f"from tests.sandbox import RealGitSandbox as "
                             f"{self.cls}\n")
        else:
            self.cls = "RealGitSandbox"
            self.imports += "from tests.sandbox import RealGitSandbox\n"
        self.fx = f"seeded_{word(rng)}"
        self.build = f"build_{word(rng)}"
        self.helper = f"helper_{word(rng)}"
        self.test = f"test_{word(rng)}"

    def source(self, build_body="return sb.root", helper_body=None,
               extra="", assignment=None):
        helper = "" if helper_body is None else \
            f"\n\ndef {self.helper}(sb):\n{indent(helper_body)}\n"
        line = assignment if assignment is not None else \
            f"{self.fx} = {self.sr}({self.cls}, {self.build})"
        return (f"import pytest\n\n{self.imports}{helper}\n\n"
                f"def {self.build}(sb):\n{indent(build_body)}\n\n\n{line}\n"
                f"{extra}\n\ndef {self.test}({self.fx}):\n"
                f"    assert {self.fx}.sandbox is not None\n")


def indent(body):
    return "\n".join(f"    {line}" for line in body.splitlines())


RELEVANT = (ASSERT_IN_FIXTURE, "shared_readonly", "build", "песочниц",
            "общая фикстура")


def relevant(errors):
    return [line for line in errors if any(n in line for n in RELEVANT)]


@pytest.mark.parametrize("alias_class", [False, True])
@pytest.mark.parametrize("form", list(IMPORT_FORMS))
@pytest.mark.parametrize("where", ["build", "helper"])
def test_ac2_assertion_in_build_or_its_helper_refused(where, form, alias_class):
    """Утверждение в `build` общей фикстуры или в его помощнике первого уровня — отказ «утверждение в фикстуре».

    Сценарий: `<имя> = shared_readonly(<класс>, <build>)` на уровне модуля
    в каждой форме импорта требования 2 и с классом песочницы под
    псевдонимом при импорте; `assert` стоит в `build` либо в функции файла,
    которую `build` вызывает. Среди ошибок есть «утверждение в фикстуре».

    Ловит мутацию: присваивание `shared_readonly` не считается фикстурой
    (или узнаётся только `from tests.sandbox import shared_readonly`, без
    `as`, `import tests.sandbox`, `from tests import sandbox`, псевдонима
    класса) — утверждение в `build` не отклоняется; помощник `build` не
    прослеживается — утверждение в помощнике не отклоняется.
    """
    seed, rng = seeded()
    sh = Shared(rng, form, alias_class)
    if where == "build":
        source = sh.source(build_body="assert sb is not None\nreturn sb.root")
    else:
        source = sh.source(build_body=f"return {sh.helper}(sb)",
                           helper_body="assert sb.root\nreturn sb.root")
    errors = style_errors(source, label_of(rng))
    assert having(errors, ASSERT_IN_FIXTURE), f"зерно {seed}\n{source}\n{errors}"


@pytest.mark.parametrize("alias_class", [False, True])
@pytest.mark.parametrize("form", list(IMPORT_FORMS))
def test_ac2_build_without_assertion_not_refused(form, alias_class):
    """Общая фикстура с `build` и помощником без утверждений отказов правил общего состояния не получает.

    Сценарий: каждая форма импорта требования 2, класс прямо или под
    псевдонимом; `build` вызывает помощника файла, ни там, ни там `assert`
    нет; тест берёт только общую фикстуру. Ни одна ошибка не называет
    утверждение в фикстуре, `shared_readonly`, `build` или песочницы.

    Ловит мутацию: утверждением считается любой вызов в `build`, либо
    законная форма (`as`, вызов через модуль, псевдоним класса) принята за
    «иной вызов shared_readonly», либо ссылка на класс первым аргументом —
    за создание песочницы: появляется строка отказа.
    """
    seed, rng = seeded()
    sh = Shared(rng, form, alias_class)
    source = sh.source(build_body=f"return {sh.helper}(sb)",
                       helper_body="return sb.root")
    errors = style_errors(source, label_of(rng))
    assert not relevant(errors), f"зерно {seed}\n{source}\n{errors}"


@pytest.mark.parametrize("kind", ["lambda", "imported"])
def test_ac2_build_not_local_function_refused(kind):
    """`build` — лямбда или импортированное имя — отказ «build общей фикстуры — функция этого файла».

    Сценарий: вторым аргументом `shared_readonly` передана `lambda sb:
    sb.root` либо имя, импортированное из другого модуля; форма импорта
    `shared_readonly` случайна. Среди ошибок есть строка отказа.

    Ловит мутацию: второй аргумент не сверяется с функциями файла — лямбда
    и чужое имя принимаются молча, строки отказа нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    if kind == "lambda":
        assignment = f"{sh.fx} = {sh.sr}({sh.cls}, lambda sb: sb.root)"
        extra_import = ""
    else:
        other = f"made_{word(rng)}"
        assignment = f"{sh.fx} = {sh.sr}({sh.cls}, {other})"
        extra_import = f"from tests.sandbox import capture as {other}\n"
    source = sh.source(assignment=assignment)
    source = source.replace("import pytest\n", "import pytest\n" + extra_import,
                            1)
    errors = style_errors(source, label_of(rng))
    assert having(errors, BUILD_NOT_LOCAL), f"зерно {seed}\n{source}\n{errors}"


@pytest.mark.parametrize("kind", ["keywords", "in_function", "in_class",
                                  "bare_call", "chained_names", "tuple_names"])
def test_ac2_other_shared_readonly_call_refused(kind):
    """Иной вызов `shared_readonly` — отказ с текстом единственной допустимой формы.

    Сценарий: ключевые аргументы, вызов в теле функции, в теле класса,
    вызов без присваивания, присваивание нескольким именам (`a = b = …` и
    `a, b = …`); форма импорта случайна. Среди ошибок есть «иной вызов
    shared_readonly — только <имя> = shared_readonly(<класс>, <функция>) на
    уровне модуля (ADR-0032 п. 4)».

    Ловит мутацию: распознаётся любое присваивание с вызовом
    `shared_readonly` (ключевые аргументы, несколько целей) или вызовы вне
    уровня модуля не просматриваются — строки отказа нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    call = f"{sh.sr}({sh.cls}, {sh.build})"
    other = f"other_{word(rng)}"
    assignment = {
        "keywords": f"{sh.fx} = {sh.sr}(sandbox_cls={sh.cls}, "
                    f"build={sh.build})",
        "in_function": f"def make_{word(rng)}():\n    return {call}",
        "in_class": f"class Holder{word(rng)}:\n    {sh.fx} = {call}",
        "bare_call": call,
        "chained_names": f"{sh.fx} = {other} = {call}",
        "tuple_names": f"{sh.fx}, {other} = {call}",
    }[kind]
    source = sh.source(assignment=assignment)
    errors = style_errors(source, label_of(rng))
    assert having(errors, OTHER_CALL), f"зерно {seed}\n{source}\n{errors}"


# ------------------------------------------------------------------ AC-3

def fixture_variant(rng, value):
    fx, test = f"fx_{word(rng)}", f"test_{word(rng)}"
    return (f"import pytest\n\n\n@pytest.fixture\ndef {fx}():\n"
            f"    return {value}\n\n\ndef {test}({fx}):\n    assert {fx}\n"), test


def change_for(source_of, old, new):
    base, head = source_of(old), source_of(new)
    label = "tests/test_sample.py"
    return guard.assertion_changes(base, head, paths=(label, label))


def test_ac3_build_literal_change_named_like_fixture_literal():
    """Правка литерала в `build` общей фикстуры называется у теста, берущего её, так же, как правка литерала фикстуры.

    Сценарий: два файла — с обычной фикстурой `@pytest.fixture`, отдающей
    литерал, и с общей фикстурой, чей `build` отдаёт тот же литерал (форма
    импорта случайна); тест берёт фикстуру параметром. Новая версия меняет
    литерал на другое случайное значение. `assertion_changes` называет тест
    в обоих случаях, вид изменения и пары значений совпадают.

    Ловит мутацию: присваивание `shared_readonly` не попадает в таблицу
    фикстур гейта неослабления — у теста общей фикстуры изменения нет
    (ответ пуст).
    """
    seed, rng = seeded()
    old = rng.randrange(10, 10_000)
    new = old + rng.randrange(1, 10_000)
    fx_rng = random.Random(seed)
    _src, fx_test = fixture_variant(random.Random(seed), old)
    expected = change_for(lambda v: fixture_variant(random.Random(seed), v)[0],
                          old, new)
    assert expected and fx_test in expected, f"зерно {seed}: {expected}"
    sh = Shared(fx_rng, fx_rng.choice(list(IMPORT_FORMS)))
    found = change_for(lambda v: sh.source(build_body=f"return {v}"), old, new)
    context = f"зерно {seed}\n{sh.source(build_body=f'return {new}')}\n{found}"
    assert found is not None and sh.test in found, context
    assert found[sh.test].kind == expected[fx_test].kind, context
    assert found[sh.test].pairs == expected[fx_test].pairs, context


def test_ac3_build_helper_literal_traced_unrelated_function_not():
    """Правка литерала в помощнике первого уровня `build` называется у теста общей фикстуры; та же правка в функции, которую `build` не вызывает, — нет.

    Сценарий: `build` вызывает помощника файла, тот отдаёт литерал; рядом —
    функция файла с тем же литералом, которую никто не вызывает. Правка
    литерала в помощнике — `assertion_changes` называет тест; правка того
    же литерала в несвязанной функции — теста в ответе нет.

    Ловит мутацию: помощник `build` не прослеживается — правка в помощнике
    не названа; либо прослеживаются все функции модуля — названа правка в
    несвязанной функции.
    """
    seed, rng = seeded()
    old = rng.randrange(10, 10_000)
    new = old + rng.randrange(1, 10_000)
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    unrelated = f"unused_{word(rng)}"

    def source(helper_value, unrelated_value):
        extra = (f"\n\ndef {unrelated}():\n    return {unrelated_value}\n")
        return sh.source(build_body=f"return {sh.helper}(sb)",
                         helper_body=f"return {helper_value}", extra=extra)

    traced = change_for(lambda v: source(v, old), old, new)
    assert traced is not None and sh.test in traced, \
        f"зерно {seed}\n{source(new, old)}\n{traced}"
    untouched = change_for(lambda v: source(old, v), old, new)
    assert untouched is not None and sh.test not in untouched, \
        f"зерно {seed}\n{source(old, new)}\n{untouched}"


# ------------------------------------------------------------------ AC-4

def root_sources():
    return guard.sandbox_sources_from_dir(config.ROOT)


def sandbox_module(base_import, base, cls):
    return f"{base_import}\n\n\nclass {cls}({base}):\n    pass\n"


def other_sandbox_errors(source, rng, **kwargs):
    return having(style_errors(source, label_of(rng), **kwargs),
                  OTHER_SANDBOXES)


TAKES_TMP_ROOT = {
    "param": "\n\ndef test_root_{w}(tmp_root):\n    assert tmp_root.root\n",
    "usefixtures": ("\n\n@pytest.mark.usefixtures(\"tmp_root\")\n"
                    "def test_root_{w}():\n    assert True\n"),
    "sandbox_class": "\n\nclass Local{w}(RealGitSandbox):\n    pass\n",
}


@pytest.mark.parametrize("way", list(TAKES_TMP_ROOT))
def test_ac4_other_sandbox_refused_only_with_shared_fixture(way):
    """Тест с `tmp_root` (параметром, `usefixtures`) или класс, наследующий `RealGitSandbox`, — отказ только в файле с общей фикстурой.

    Сценарий: в файл с общей фикстурой добавлен тест, берущий `tmp_root`
    параметром или `usefixtures`, либо класс файла, наследующий
    `RealGitSandbox`; форма импорта `shared_readonly` случайна. Есть строка
    «в модуле с общей фикстурой других песочниц нет». Тот же текст без
    присваивания общей фикстуры — строки нет.

    Ловит мутацию: в модуле с общей фикстурой `tmp_root` пропускается (или
    читается только параметр, без `usefixtures`), классы-наследники
    песочниц не проверяются — строки нет; либо правило действует во всех
    файлах — строка есть в файле без общей фикстуры.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    extra = TAKES_TMP_ROOT[way].format(w=word(rng))
    with_shared = sh.source(extra=extra)
    assert other_sandbox_errors(with_shared, rng), f"зерно {seed}\n{with_shared}"
    without = sh.source(extra=extra, assignment="")
    assert not other_sandbox_errors(without, rng), f"зерно {seed}\n{without}"


def test_ac4_own_sandbox_class_passed_to_shared_readonly_allowed():
    """Собственный класс песочницы, переданный первым аргументом `shared_readonly`, отказа не даёт.

    Сценарий: класс файла наследует `RealGitSandbox` и передан первым
    аргументом общей фикстуры; тест берёт только общую фикстуру. Строки «в
    модуле с общей фикстурой других песочниц нет» нет.

    Ловит мутацию: исключение для класса, переданного `shared_readonly`,
    не действует — его наследование `RealGitSandbox` даёт строку отказа.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    own = f"Own{word(rng)}"
    source = sh.source(
        extra="",
        assignment=(f"class {own}(RealGitSandbox):\n    pass\n\n\n"
                    f"{sh.fx} = {sh.sr}({own}, {sh.build})"))
    assert not other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


def file_fixture_chain(rng, depth):
    """Фикстуры файла: первая берёт `tmp_root`, каждая следующая — прежнюю;
    тест берёт последнюю."""
    names = [f"prep_{word(rng)}" for _ in range(depth)]
    text, previous = "", "tmp_root"
    for name in names:
        text += (f"\n\n@pytest.fixture\ndef {name}({previous}):\n"
                 f"    return {previous}\n")
        previous = name
    return text + (f"\n\ndef test_chain_{word(rng)}({previous}):\n"
                   f"    assert {previous}\n")


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_ac4_file_fixture_taking_tmp_root_refused(depth):
    """Тест, берущий фикстуру файла, которая сама или транзитивно берёт `tmp_root`, — отказ.

    Сценарий: в файле с общей фикстурой цепочка фикстур файла длиной 1–3,
    первая берёт `tmp_root`; тест берёт последнюю. Есть строка «в модуле с
    общей фикстурой других песочниц нет».

    Ловит мутацию: проверяются только параметры самого теста — фикстура
    файла, берущая `tmp_root`, проходит; либо разбор не транзитивен —
    проходит цепочка длиной 2 и 3.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    source = sh.source(extra=file_fixture_chain(rng, depth))
    assert other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


SANDBOX_USES = {
    "construct_shared_class": "\n\ndef make_{w}():\n    return RealGitSandbox()\n",
    "local_chain": ("\n\nclass Base{w}(RealGitSandbox):\n    pass\n\n\n"
                    "class Child{w}(Base{w}):\n    pass\n"),
    "fixtures_attr": ("\n\nimport tests.fixtures\n\n\ndef make_{w}():\n"
                      "    return tests.fixtures._sandbox(RealGitSandbox)\n"),
    "fixtures_from": ("\n\nfrom tests.fixtures import _sandbox\n\n\n"
                      "def make_{w}():\n    return _sandbox(RealGitSandbox)\n"),
    "fixtures_module": ("\n\nfrom tests import fixtures as fx_{w}\n\n\n"
                        "def make_{w}():\n"
                        "    return fx_{w}._sandbox(RealGitSandbox)\n"),
}


@pytest.mark.parametrize("use", list(SANDBOX_USES))
def test_ac4_sandbox_construction_in_shared_module_refused(use):
    """Создание песочницы, вызов `tests.fixtures._sandbox` и цепочка локальных наследников в файле с общей фикстурой — отказ.

    Сценарий: файл с общей фикстурой над `RealGitSandbox` содержит вызов
    `RealGitSandbox()` (класс передан первым аргументом `shared_readonly`);
    либо `tests.fixtures._sandbox(RealGitSandbox)` через `import
    tests.fixtures`, `from tests.fixtures import _sandbox`, `from tests import
    fixtures as …`; либо локальный класс наследует локальный класс,
    наследующий `RealGitSandbox`. Есть строка «в модуле с общей фикстурой
    других песочниц нет».

    Ловит мутацию: вызов-создание класса, переданного `shared_readonly`,
    исключается вместе со ссылкой первым аргументом; вызов
    `tests.fixtures._sandbox` пропускается; наследование читается только
    напрямую от класса песочницы — строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    source = sh.source(extra=SANDBOX_USES[use].format(w=word(rng)))
    assert other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


def test_ac4_local_child_of_class_passed_to_shared_readonly_refused():
    """Локальный класс, наследующий класс, переданный `shared_readonly`, сам не переданный, — отказ.

    Сценарий: `Base(RealGitSandbox)` передан первым аргументом общей
    фикстуры, `Child(Base)` не передан. Есть строка «в модуле с общей
    фикстурой других песочниц нет» — источником может быть только `Child`.

    Ловит мутацию: исключение класса, переданного `shared_readonly`,
    распространяется на его наследников, или наследование через локальные
    классы не прослеживается — строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    base, child = f"Base{word(rng)}", f"Child{word(rng)}"
    source = sh.source(
        assignment=(f"class {base}(RealGitSandbox):\n    pass\n\n\n"
                    f"{sh.fx} = {sh.sr}({base}, {sh.build})\n\n\n"
                    f"class {child}({base}):\n    pass"))
    assert other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


def test_ac4_fake_proc_subclass_not_a_sandbox():
    """Класс файла, наследующий `FakeProc`, песочницей не считается.

    Сценарий: в файле с общей фикстурой класс наследует
    `tests.sandbox.FakeProc`. Строки «в модуле с общей фикстурой других
    песочниц нет» нет.

    Ловит мутацию: песочницей считается любой класс `tests/sandbox.py`, а
    не только наследники `TmpDirTest`/`TmpRootTest` — строка есть.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    source = sh.source(extra=(f"\n\nfrom tests.sandbox import FakeProc\n\n\n"
                              f"class Proc{word(rng)}(FakeProc):\n    pass\n"))
    assert not other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


def test_ac4_second_shared_fixture_refused():
    """Второе присваивание `shared_readonly` в том же файле — отказ «вторая общая фикстура в модуле».

    Сценарий: две общие фикстуры с разными именами над одним `build`.
    Среди ошибок есть строка «вторая общая фикстура в модуле».

    Ловит мутацию: число общих фикстур в модуле не считается — строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    second = f"again_{word(rng)}"
    source = sh.source(extra=f"\n{second} = {sh.sr}({sh.cls}, {sh.build})\n")
    errors = style_errors(source, label_of(rng))
    assert having(errors, SECOND_SHARED), f"зерно {seed}\n{source}\n{errors}"


def test_ac4_locked_file_gaining_shared_fixture_not_released():
    """Залоченный файл без общей фикстуры, в который добавлено присваивание `shared_readonly`, освобождения не получает.

    Сценарий: `lint_base` — залоченный текст с тестом, берущим `tmp_root`,
    без общей фикстуры; новая версия добавляет `<имя> = shared_readonly(…)`,
    тест не изменён. Есть строка «в модуле с общей фикстурой других
    песочниц нет».

    Ловит мутацию: освобождение `lint_base` по неизменённому тесту
    действует и для этого правила — строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    extra = TAKES_TMP_ROOT["param"].format(w=word(rng))
    label = label_of(rng)
    base = sh.source(extra=extra, assignment="")
    head = sh.source(extra=extra)
    errors = having(style_errors(head, label, lint_base={label: base}),
                    OTHER_SANDBOXES)
    assert errors, f"зерно {seed}\nбаза:\n{base}\nголова:\n{head}"


@pytest.mark.parametrize("chain", [1, 2])
def test_ac4_class_from_sandbox_module_sources_refused(chain):
    """Класс файла, наследующий класс модуля `tests/*_sandbox.py` (прямо или цепочкой модулей), — отказ.

    Сценарий: `sandbox_sources` — модули песочниц корня кода плюс модули
    со случайными именами: при `chain=1` `tests/<a>_sandbox.py` с классом,
    наследующим `RealGitSandbox`; при `chain=2` класс `tests/<a>_sandbox.py`
    наследует класс `tests/<b>_sandbox.py`, тот — `RealGitSandbox`. Класс
    файла с общей фикстурой наследует класс `tests/<a>_sandbox.py` — есть
    строка «в модуле с общей фикстурой других песочниц нет». Те же входы
    без модулей со случайными именами — строки нет.

    Ловит мутацию: класс песочницы из `tests/*_sandbox.py` не распознаётся
    (перечень строится только по `tests/sandbox.py`) или цепочка между
    модулями песочниц не прослеживается; `sandbox_sources` не читается —
    берутся модули `config.ROOT`, где таких классов нет: строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    a_mod, a_cls = f"zq{word(rng)}_sandbox", f"Zq{word(rng)}Sandbox"
    sources = dict(root_sources())
    if chain == 1:
        sources[f"tests/{a_mod}.py"] = sandbox_module(
            "from tests.sandbox import RealGitSandbox", "RealGitSandbox", a_cls)
    else:
        b_mod, b_cls = f"zq{word(rng)}_sandbox", f"Zq{word(rng)}Sandbox"
        sources[f"tests/{b_mod}.py"] = sandbox_module(
            "from tests.sandbox import RealGitSandbox", "RealGitSandbox", b_cls)
        sources[f"tests/{a_mod}.py"] = sandbox_module(
            f"from tests.{b_mod} import {b_cls}", b_cls, a_cls)
    source = sh.source(extra=(f"\n\nfrom tests.{a_mod} import {a_cls}\n\n\n"
                              f"class Local{word(rng)}({a_cls}):\n    pass\n"))
    found = other_sandbox_errors(source, rng, sandbox_sources=sources)
    assert found, f"зерно {seed}\n{source}\nмодули: {sorted(sources)}"
    plain = other_sandbox_errors(source, rng, sandbox_sources=root_sources())
    assert not plain, f"зерно {seed}\n{source}\n{plain}"


@pytest.mark.parametrize("use", ["call", "subclass"])
def test_ac4_sandbox_class_import_alias_refused(use):
    """`R()` и `class X(R)` при `from tests.sandbox import RealGitSandbox as R` в файле с общей фикстурой — отказ.

    Сценарий: общая фикстура над `RealGitSandbox`, в файле ещё и псевдоним
    класса при импорте со случайным именем; вызов псевдонима в функции
    файла или класс файла, наследующий псевдоним. Есть строка «в модуле с
    общей фикстурой других песочниц нет».

    Ловит мутацию: псевдоним класса песочницы при импорте не распознаётся —
    имя сверяется буквально с `RealGitSandbox`: строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    alias = f"R{word(rng)}"
    body = (f"\n\ndef make_{word(rng)}():\n    return {alias}()\n"
            if use == "call" else f"\n\nclass X{word(rng)}({alias}):\n    pass\n")
    source = sh.source(extra=(f"\n\nfrom tests.sandbox import RealGitSandbox "
                              f"as {alias}\n{body}"))
    assert other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


def test_ac4_shared_readonly_alias_with_tmp_root_refused():
    """Общая фикстура через `from tests.sandbox import shared_readonly as sr` и тест с `tmp_root` — отказ.

    Сценарий: `<имя> = <sr>(RealGitSandbox, build)` при псевдониме
    `shared_readonly` со случайным именем, рядом тест с `tmp_root`. Есть
    строка «в модуле с общей фикстурой других песочниц нет».

    Ловит мутацию: общая фикстура узнаётся только по буквальному имени
    `shared_readonly` — файл не считается модулем с общей фикстурой,
    строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, "from_as")
    source = sh.source(extra=TAKES_TMP_ROOT["param"].format(w=word(rng)))
    assert other_sandbox_errors(source, rng), f"зерно {seed}\n{source}"


def test_ac4_empty_sandbox_sources_no_sandbox_classes():
    """`sandbox_sources={}` — исключения нет, класс, наследующий `RealGitSandbox`, песочницей не считается.

    Сценарий: файл с общей фикстурой и классом файла, наследующим
    `RealGitSandbox`; `pytest_style_errors_from_files(…, sandbox_sources={})`
    возвращает список, строки «в модуле с общей фикстурой других песочниц
    нет» в нём нет. С модулями песочниц корня кода та же строка есть.

    Ловит мутацию: пустой словарь подменяется модулями `config.ROOT`
    (проверка `if not sandbox_sources` вместо `is None`) — строка есть;
    отсутствующий `tests/sandbox.py` в словаре даёт `KeyError`.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    source = sh.source(extra=TAKES_TMP_ROOT["sandbox_class"].format(w=word(rng)))
    assert not other_sandbox_errors(source, rng, sandbox_sources={}), \
        f"зерно {seed}\n{source}"
    assert other_sandbox_errors(source, rng, sandbox_sources=root_sources()), \
        f"зерно {seed}\n{source}"


def test_ac4_long_lived_errors_pass_sandbox_sources_to_style_check():
    """`long_lived_errors_from_files` проверяет стиль по своим `sandbox_sources`.

    Сценарий (указание Оператора на гейте SPEC, 2): `sandbox_sources` —
    модули песочниц корня кода плюс `tests/<имя>_sandbox.py` со случайным
    именем и классом, наследующим `RealGitSandbox`, которого нет в
    `config.ROOT`. Класс файла с общей фикстурой наследует этот класс —
    среди ошибок `long_lived_errors_from_files` есть «в модуле с общей
    фикстурой других песочниц нет».

    Ловит мутацию: `sandbox_sources` не пробрасывается в проверку стиля —
    перечень берётся из `config.ROOT`, класса там нет, строки нет.
    """
    seed, rng = seeded()
    sh = Shared(rng, rng.choice(list(IMPORT_FORMS)))
    mod, cls = f"zq{word(rng)}_sandbox", f"Zq{word(rng)}Sandbox"
    sources = dict(root_sources())
    sources[f"tests/{mod}.py"] = sandbox_module(
        "from tests.sandbox import RealGitSandbox", "RealGitSandbox", cls)
    source = sh.source(extra=(f"\n\nfrom tests.{mod} import {cls}\n\n\n"
                              f"class Local{word(rng)}({cls}):\n    pass\n"))
    task_id = random_task_id(rng)
    errors = guard.long_lived_errors_from_files(
        [(label_of(rng), source)], task_id, sandbox_sources=sources)
    assert having(errors, OTHER_SANDBOXES), f"зерно {seed}\n{source}\n{errors}"


# ------------------------------------------------------------------ AC-6

LONG_LIVED_SAMPLE = '''"""Образец долгоживущего файла.

Группа: долгоживущий
"""


def test_sample():
    """Образец.

    Ловит мутацию: образец.
    """
    assert len("abc") == 3
'''


def random_task_id(rng):
    return "01" + "".join(rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                          for _ in range(24))


def plank_label(rng, task_id, kind):
    name = f"test_{word(rng)}.py"
    if kind == "relative":
        return f"acceptance_tests/{name}"
    return "/".join(("tasks", task_id, "acceptance_tests", name))


@pytest.mark.parametrize("kind", ["relative", "snapshot"])
def test_ac6_plank_file_has_no_size_line_but_keeps_move_refusal(kind):
    """Файл планки с «Группа: долгоживущий» без метки размера строки «размер — нет метки размера» не получает, отказ «перенеси файл» остаётся.

    Сценарий: метка файла `acceptance_tests/test_<…>.py` или
    `<каталог задач>/<id>/acceptance_tests/test_<…>.py` (метка снимка
    `amend-tests`, id задачи случаен), текст —
    долгоживущий образец без `pytestmark`. В ошибках
    `long_lived_errors_from_files(…, size_marks=True)` нет «размер — нет
    метки размера»; `long_lived_plank_errors` на том же входе даёт «перенеси
    файл в tests/…».

    Ловит мутацию: правила размера применяются к файлам планки (строка
    размера у файла планки) либо фильтр узнаёт только одну из двух форм
    метки — строка есть.
    """
    seed, rng = seeded()
    task_id = random_task_id(rng)
    files = [(plank_label(rng, task_id, kind), LONG_LIVED_SAMPLE)]
    errors = guard.long_lived_errors_from_files(files, task_id, size_marks=True)
    assert not having(errors, NO_SIZE_MARK), f"зерно {seed}: {files[0][0]}\n{errors}"
    moved = guard.long_lived_plank_errors(files, task_id)
    assert having(moved, "перенеси файл в tests/"), f"зерно {seed}: {moved}"


def test_ac6_long_lived_file_with_inner_acceptance_tests_segment_keeps_size():
    """Долгоживущий файл `tests/acceptance_tests/test_<id>_<имя>.py` без метки размера получает «размер — нет метки размера».

    Сценарий: та же долгоживущая заготовка без `pytestmark`, метка — путь
    с сегментом `acceptance_tests` в середине; id задачи и имя случайны.
    Среди ошибок `long_lived_errors_from_files(…, size_marks=True)` есть
    строка «размер — нет метки размера».

    Ловит мутацию: размер снят с любого пути с сегментом `acceptance_tests`
    (поиск подстроки вместо привязки к началу метки) — строки нет.
    """
    seed, rng = seeded()
    task_id = random_task_id(rng)
    label = f"tests/acceptance_tests/test_{task_id.lower()}_{word(rng)}.py"
    errors = guard.long_lived_errors_from_files(
        [(label, LONG_LIVED_SAMPLE)], task_id, size_marks=True)
    assert having(errors, NO_SIZE_MARK), f"зерно {seed}: {label}\n{errors}"


# ------------------------------------------------------------------ AC-7

def pair_scope_module(rng):
    refused = style_errors(scope_source(rng, "decorator", '"module"')[0],
                           label_of(rng))
    allowed = style_errors(scope_source(rng, "decorator", '"function"')[0],
                           label_of(rng))
    return bool(having(refused, SCOPE_ADR)), bool(having(allowed, SCOPE_ADR))


def pair_scope_assign(rng):
    refused = style_errors(scope_source(rng, "assign", '"module"')[0],
                           label_of(rng))
    allowed = style_errors(scope_source(rng, "assign", None)[0], label_of(rng))
    return bool(having(refused, SCOPE_ADR)), bool(having(allowed, SCOPE_ADR))


def pair_fixture_table(rng):
    sh = Shared(rng)
    old, new = rng.randrange(10, 1000), rng.randrange(1000, 2000)
    found = change_for(lambda v: sh.source(build_body=f"return {v}"), old, new)
    same = change_for(lambda v: sh.source(build_body="return 7"), old, new)
    return bool(found) and sh.test in found, bool(same) and sh.test in same


def pair_build_helper(rng):
    sh = Shared(rng)
    old, new = rng.randrange(10, 1000), rng.randrange(1000, 2000)

    def source(v):
        return sh.source(build_body=f"return {sh.helper}(sb)",
                         helper_body=f"return {v}")
    found = change_for(source, old, new)
    same = change_for(lambda v: source(old), old, new)
    return bool(found) and sh.test in found, bool(same) and sh.test in same


def pair_assert_in_build(rng):
    sh = Shared(rng)
    refused = style_errors(sh.source(build_body="assert sb\nreturn sb"),
                           label_of(rng))
    allowed = style_errors(sh.source(), label_of(rng))
    return (bool(having(refused, ASSERT_IN_FIXTURE)),
            bool(having(allowed, ASSERT_IN_FIXTURE)))


def pair_tmp_root(rng):
    sh = Shared(rng)
    extra = TAKES_TMP_ROOT["param"].format(w=word(rng))
    return (bool(other_sandbox_errors(sh.source(extra=extra), rng)),
            bool(other_sandbox_errors(sh.source(extra=extra, assignment=""),
                                      rng)))


def pair_sandbox_module(rng):
    sh = Shared(rng)
    mod, cls = f"zq{word(rng)}_sandbox", f"Zq{word(rng)}Sandbox"
    sources = dict(root_sources())
    sources[f"tests/{mod}.py"] = sandbox_module(
        "from tests.sandbox import RealGitSandbox", "RealGitSandbox", cls)
    source = sh.source(extra=(f"\n\nfrom tests.{mod} import {cls}\n\n\n"
                              f"class Local{word(rng)}({cls}):\n    pass\n"))
    return (bool(other_sandbox_errors(source, rng, sandbox_sources=sources)),
            bool(other_sandbox_errors(source, rng,
                                      sandbox_sources=root_sources())))


def pair_class_alias(rng):
    sh = Shared(rng)
    alias = f"R{word(rng)}"
    used = sh.source(extra=(f"\n\nfrom tests.sandbox import RealGitSandbox "
                            f"as {alias}\n\n\nclass X{word(rng)}({alias}):\n"
                            f"    pass\n"))
    unused = sh.source(extra=(f"\n\nfrom tests.sandbox import RealGitSandbox "
                              f"as {alias}\n"))
    return (bool(other_sandbox_errors(used, rng)),
            bool(other_sandbox_errors(unused, rng)))


def pair_fixtures_sandbox(rng):
    sh = Shared(rng)
    w = word(rng)
    used = sh.source(extra=SANDBOX_USES["fixtures_attr"].format(w=w))
    unused = sh.source(extra=f"\n\nimport tests.fixtures\n")
    return (bool(other_sandbox_errors(used, rng)),
            bool(other_sandbox_errors(unused, rng)))


def size_line(rng, label_of_task):
    task_id = random_task_id(rng)
    label = label_of_task(task_id)
    errors = guard.long_lived_errors_from_files(
        [(label, LONG_LIVED_SAMPLE)], task_id, size_marks=True)
    return bool(having(errors, NO_SIZE_MARK))


def pair_plank_size(rng):
    plank = size_line(rng, lambda tid: plank_label(rng, tid, "relative"))
    long_lived = size_line(
        rng, lambda tid: f"tests/test_{tid.lower()}_{word(rng)}.py")
    return long_lived, plank


def pair_inner_segment(rng):
    inner = size_line(rng, lambda tid: (f"tests/acceptance_tests/"
                                        f"test_{tid.lower()}_{word(rng)}.py"))
    plank = size_line(rng, lambda tid: plank_label(rng, tid, "snapshot"))
    return inner, plank


# Мутация AC-7 -> парная проверка: (исход на входе, где мутация снимает
# правило; исход на входе-двойнике без нарушения) — ожидается (True, False).
MUTATION_PAIRS = {
    "scope_module_skipped": pair_scope_module,
    "shared_assign_not_in_fixture_table": pair_fixture_table,
    "assert_in_build_allowed": pair_assert_in_build,
    "tmp_root_in_shared_module_skipped": pair_tmp_root,
    "size_line_on_plank_file": pair_plank_size,
    "build_helper_not_traced": pair_build_helper,
    "fixture_scope_assignment_skipped": pair_scope_assign,
    "sandbox_module_class_unknown": pair_sandbox_module,
    "sandbox_class_alias_unknown": pair_class_alias,
    "fixtures_sandbox_call_skipped": pair_fixtures_sandbox,
    "inner_acceptance_tests_segment_loses_size": pair_inner_segment,
}


@pytest.mark.parametrize("mutation", list(MUTATION_PAIRS))
def test_ac7_each_named_mutation_flips_a_pair(mutation):
    """Каждая статическая мутация AC-7 меняет исход парной проверки: нарушение замечено, двойник без нарушения чист.

    Сценарий: для мутации — два входа, различающиеся ровно условием,
    которое мутация снимает: `scope="module"` против `"function"`;
    присваивание `pytest.fixture(scope="module")(f)` против вызова без
    `scope`; смена литерала в `build` (в помощнике `build`) против
    неизменного `build`; `assert` в `build` против `build` без него; тест с
    `tmp_root` в файле с общей фикстурой против файла без неё; класс
    модуля `tests/<имя>_sandbox.py` при его исходнике в `sandbox_sources`
    против `sandbox_sources` без него; класс-наследник псевдонима
    `RealGitSandbox` против неиспользованного псевдонима; вызов
    `tests.fixtures._sandbox` против одного импорта `tests.fixtures`;
    размер у долгоживущего файла `tests/` против файла планки и у
    `tests/acceptance_tests/…` против метки снимка
    `<каталог задач>/<id>/acceptance_tests/…`.
    Исход — (True, False). Мутация «конструктор вне try» — в файле
    прогона подпроцессом (`…_construct_failure.py`).

    Ловит мутацию: каждую из названных в AC-7 статических — первый вход
    перестаёт давать отказ (изменение), исход (False, False); правило,
    срабатывающее без разбора условия, — исход (True, True).
    """
    seed, rng = seeded()
    outcome = MUTATION_PAIRS[mutation](rng)
    assert outcome == (True, False), f"зерно {seed}; {mutation}: {outcome}"
