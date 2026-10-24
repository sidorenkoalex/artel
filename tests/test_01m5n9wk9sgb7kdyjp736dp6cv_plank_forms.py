"""Отказы guard в файлах планки и долгоживущих файлах: скрытые пропуски,
скрытые варианты, утверждения в фикстурах, смешение стилей; исключение
`lint_base` для `amend-tests`; признак артели; счёт тестов (AC-3..AC-7,
AC-9 в части счёта).

Группа: долгоживущий

Красен до реализации: `long_lived_errors_from_files` знает только линт детерминизма и статику долгоживущих файлов — ни одна форма (а)–(з) требования 6 SPEC и ни смешение стилей отказа не дают. Чистые формы (AC-4), признак чужого проекта (AC-6) и счёт тестов (AC-9) держат сегодняшнее поведение и зелены с рождения.

Вход — публичные `guard.long_lived_errors_from_files` и
`guard.count_test_methods`. Строка отказа узнаётся по адресу
«<файл>::<функция>: строка N:» (требование 6); текст нарушения после
адреса тест не сверяет. Для формы (в) на уровне модуля адрес — «<модуль>»
(принимается и имя модуля файла: SPEC не уточняет, литерал это или имя).
Где номер строки однозначно не назван (декоратор над `def`), принимается
любая строка от декоратора до `def`. Метки файлов, имена функций, причины
и значения — из `random`; зерно печатается и входит в текст провала.
Группа файлов-входов — `разовый` либо без строки группы: проверка обязана
идти до фильтра по группе.
"""
import random
import tempfile
from pathlib import Path

import pytest

from scripts import guard

TASK_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00"
MODULE_LABEL = "<модуль>"


def seeded():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def word(rng, length=6):
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def header(rng, imports="import pytest\n"):
    group = rng.choice(('"""Файл-вход.\n\nГруппа: разовый\n"""\n',
                        '"""Файл-вход без строки группы."""\n'))
    return group + imports


def label_for(rng):
    return rng.choice((f"acceptance_tests/test_{word(rng)}.py",
                       f"tests/test_{word(rng)}.py"))


def line_of(source, needle, start=1):
    """Номер первой строки от `start`, содержащей `needle`."""
    for number, line in enumerate(source.splitlines(), start=1):
        if number >= start and needle in line:
            return number
    raise AssertionError(f"нет {needle!r} в тексте:\n{source}")


def errors(label, source, network=True, lint_base=None):
    return guard.long_lived_errors_from_files(
        [(label, source)], TASK_ID, network_addresses=network,
        lint_base=lint_base)


def addressed(found, label, names, lines):
    """Строки отказа с адресом «<label>::<имя>: строка N:» для имени из
    `names` и N из `lines`."""
    prefixes = [f"{label}::{name}: строка {n}:" for name in names
                for n in lines]
    return [e for e in found if any(e.startswith(p) for p in prefixes)]


def module_names(label):
    return (MODULE_LABEL, Path(label).stem)


class Form:
    """Нарушение одной формы: текст файла, имена и строки адреса."""

    def __init__(self, source, names, lines):
        self.source, self.names, self.lines = source, names, lines


def span(source, first_needle, def_needle):
    first = line_of(source, first_needle)
    return range(first, line_of(source, def_needle, first) + 1)


def build_form(rng, kind, label):
    """Файл с единственным нарушением вида `kind` (требование 6)."""
    f, t, h = f"fx_{word(rng)}", f"test_{word(rng)}", f"_check_{word(rng)}"
    reason = word(rng)
    plain_test = f"\n\ndef {t}({f}):\n    assert {f}\n"

    def fixture_with(body, decorator="@pytest.fixture", imports=None):
        lines = "".join(f"    {line}\n" for line in body.splitlines())
        src = (header(rng) if imports is None else header(rng, imports)) + \
            f"\n\n{decorator}\ndef {f}():\n{lines}" + plain_test
        return src

    if kind == "a_assert":
        src = fixture_with(f"value = {rng.randrange(1, 99)}\nassert value\nreturn value")
        return Form(src, (f,), (line_of(src, "assert value"),))
    if kind == "a_pytest_fail":
        src = fixture_with(f"pytest.fail(\"{reason}\")\nreturn 1")
        return Form(src, (f,), (line_of(src, "pytest.fail("),))
    if kind == "a_assert_method":
        src = fixture_with("import unittest\ncase = unittest.TestCase()\n"
                           "case.assertEqual(1, 1)\nreturn case")
        return Form(src, (f,), (line_of(src, "case.assertEqual("),))
    if kind == "a_raises":
        src = fixture_with("with pytest.raises(ValueError):\n"
                           "    int(\"x\")\nreturn 1")
        return Form(src, (f,), (line_of(src, "pytest.raises("),))
    if kind == "a_helper":
        src = (header(rng) + f"\n\ndef {h}(value):\n    assert value\n"
               f"\n\n@pytest.fixture\ndef {f}():\n    return {h}(1)\n"
               + plain_test)
        return Form(src, (f, h), (line_of(src, "assert value"),
                                  line_of(src, f"return {h}(1)")))
    if kind in ("b_xfail", "b_importorskip"):
        call = ("pytest.xfail(\"%s\")" if kind == "b_xfail"
                else "pytest.importorskip(\"%s\")") % reason
        src = header(rng) + f"\n\ndef {t}():\n    {call}\n"
        return Form(src, (t,), (line_of(src, call),))
    if kind == "b_xfail_from_import":
        src = header(rng, "from pytest import xfail\n") + \
            f"\n\ndef {t}():\n    xfail(\"{reason}\")\n"
        return Form(src, (t,), (line_of(src, "    xfail("),))
    if kind == "b_xfail_alias":
        src = header(rng, "import pytest as pt\n") + \
            f"\n\ndef {t}():\n    pt.xfail(\"{reason}\")\n"
        return Form(src, (t,), (line_of(src, "pt.xfail("),))
    if kind in ("c_skip", "c_xfail", "c_importorskip"):
        name = {"c_skip": "skip", "c_xfail": "xfail",
                "c_importorskip": "importorskip"}[kind]
        src = fixture_with(f"pytest.{name}(\"{reason}\")\nreturn 1")
        return Form(src, (f,), (line_of(src, f"pytest.{name}("),))
    if kind in ("c_module_importorskip", "c_module_xfail", "c_module_skip"):
        call = {"c_module_importorskip": f"pytest.importorskip(\"{reason}\")",
                "c_module_xfail": f"pytest.xfail(\"{reason}\")",
                "c_module_skip": f"pytest.skip(\"{reason}\", "
                                 f"allow_module_level=True)"}[kind]
        src = header(rng) + f"\n{call}\n" + \
            f"\n\ndef {t}():\n    assert {t!r}\n"
        return Form(src, module_names(label), (line_of(src, call),))
    if kind in ("d_params", "d_params_alias"):
        imports, mod = (("import pytest\n", "pytest") if kind == "d_params"
                        else ("import pytest as pt\n", "pt"))
        src = fixture_with("return 1", f"@{mod}.fixture(params=[1, 2])",
                           imports)
        return Form(src, (f,), span(src, "params=", f"def {f}("))
    if kind == "e_indirect":
        src = header(rng) + (f"\n\n@pytest.fixture\ndef {f}(request):\n"
                             f"    return request.param\n"
                             f"\n\n@pytest.mark.parametrize(\"{f}\", [1, 2], "
                             f"indirect=True)\ndef {t}({f}):\n"
                             f"    assert {f}\n")
        return Form(src, (t,), span(src, "indirect=", f"def {t}("))
    if kind == "f_generate":
        src = header(rng) + ("\n\ndef pytest_generate_tests(metafunc):\n"
                             "    metafunc.parametrize(\"x\", [1, 2])\n"
                             f"\n\ndef {t}(x):\n    assert x\n")
        return Form(src, ("pytest_generate_tests",),
                    (line_of(src, "def pytest_generate_tests("),))
    if kind == "g_getfixturevalue":
        src = header(rng) + (f"\n\n@pytest.fixture\ndef {f}():\n    return 1\n"
                             f"\n\ndef {t}(request):\n"
                             f"    value = request.getfixturevalue(\"{f}\")\n"
                             f"    assert value\n")
        return Form(src, (t,), (line_of(src, "request.getfixturevalue("),))
    if kind == "h_name":
        src = fixture_with("return 1", f"@pytest.fixture(name=\"{word(rng)}\")")
        return Form(src, (f,), span(src, "name=", f"def {f}("))
    raise ValueError(kind)


FORMS = ("a_assert", "a_pytest_fail", "a_assert_method", "a_raises",
         "a_helper", "b_xfail", "b_importorskip", "b_xfail_from_import",
         "b_xfail_alias", "c_skip", "c_xfail", "c_importorskip",
         "c_module_importorskip", "c_module_xfail", "c_module_skip",
         "d_params", "d_params_alias", "e_indirect", "f_generate",
         "g_getfixturevalue", "h_name")


@pytest.mark.parametrize("kind", FORMS)
def test_ac3_each_form_refused_with_address(kind):
    """Каждая форма (а)–(з) отказывает строкой с адресом «<файл>::<функция>: строка N:».

    Сценарий: файл с единственным нарушением формы `kind` — утверждение
    в фикстуре (`assert`, `pytest.fail(`, `<x>.assertEqual(`,
    `pytest.raises`) и в помощнике, вызванном из фикстуры; `pytest.xfail(`
    и `pytest.importorskip(` в теле теста, в том числе `xfail(…)` после
    `from pytest import xfail` и `pt.xfail` после `import pytest as pt`;
    `pytest.skip/xfail/importorskip(` в фикстуре и на уровне модуля вне
    `pytestmark`; `@pytest.fixture(params=…)` и `@pt.fixture(params=…)`;
    `indirect=`; `pytest_generate_tests`; `request.getfixturevalue(`;
    `@pytest.fixture(name=…)`. При `network_addresses=True` среди ошибок
    есть строка с адресом функции нарушения (у модульной формы —
    «<модуль>») и строкой нарушения.

    Ловит мутацию: `pytest.xfail` пропущен (в теле теста, через
    `from pytest import xfail` или псевдоним); `fixture(params=)`
    пропущен; утверждение помощника фикстуры не прослеживается; модульная
    форма адресуется именем функции или не проверяется — строки с
    адресом нет.
    """
    seed, rng = seeded()
    label = label_for(rng)
    form = build_form(rng, kind, label)
    found = errors(label, form.source)
    context = (f"зерно {seed}; {kind}; ждём адрес {form.names} строки "
               f"{list(form.lines)}\n{form.source}\nошибки: {found}")
    assert addressed(found, label, form.names, form.lines), context


def clean_source(rng):
    reason = word(rng)
    f = f"fx_{word(rng)}"
    return header(rng, "import sys\n\nimport pytest\n") + (
        f"\n\n@pytest.fixture\ndef {f}():\n    value = {rng.randrange(1, 99)}\n"
        f"    return value\n"
        f"\n\n@pytest.mark.skipif(sys.platform == \"{word(rng)}\", "
        f"reason=\"{reason}\")\ndef test_{word(rng)}({f}):\n    assert {f}\n"
        f"\n\n@pytest.mark.parametrize(\"a,b\", [(1, 2), (3, 4)])\n"
        f"def test_{word(rng)}(a, b):\n    assert a < b\n")


def test_ac4_clean_forms_give_no_refusal():
    """`skipif` с причиной, `parametrize` литералами и фикстура без утверждений отказа не дают.

    Сценарий: файл с фикстурой без утверждений, тестом под
    `@pytest.mark.skipif(…, reason=…)`, запрашивающим её, и тестом с
    `parametrize` литералами. `long_lived_errors_from_files` при
    `network_addresses=True` ошибок не возвращает.

    Ловит мутацию: `skipif` с причиной принят за скрытый пропуск,
    `parametrize` литералами — за скрытые варианты (или `parametrize` без
    `indirect=` — за `indirect`), фикстура без утверждений — за фикстуру
    с утверждением — появляется строка отказа.
    """
    seed, rng = seeded()
    label = label_for(rng)
    source = clean_source(rng)
    found = errors(label, source)
    assert found == [], f"зерно {seed}\n{source}\nошибки: {found}"


def styles(rng):
    """(смешанный файл, только функции, только класс) — те же тесты."""
    fn, method = f"test_{word(rng)}", f"test_{word(rng)}"
    cls = f"Test{word(rng).capitalize()}"
    base = rng.choice(("", "unittest.TestCase"))
    function = f"\n\ndef {fn}():\n    assert {fn!r}\n"
    klass = (f"\n\nclass {cls}({base}):\n\n    def {method}(self):\n"
             f"        assert {method!r}\n")
    head = header(rng, "import unittest\n")
    return head + function + klass, head + function, head + klass


def test_ac5_mixed_styles_refused_unless_locked_text_mixed():
    """Тест-функция модуля рядом с классом тестовых методов — отказ; залоченный смешанный текст — без отказа.

    Сценарий: файл с тест-функцией и классом (pytest-класс либо
    `unittest.TestCase`) с тестовым методом; те же тесты по отдельности —
    только функция и только класс. При `network_addresses=True`
    смешанный файл получает ошибку с меткой файла, однородные — нет. При
    `lint_base`, где залоченный текст этого файла уже смешивал стили
    (голова — тот же текст с добавленной тест-функцией), ошибок нет.

    Ловит мутацию: смешение стилей не проверяется — у смешанного файла
    ошибок нет; исключение `lint_base` не применяется к смешению —
    залоченный смешанный файл получает отказ.
    """
    seed, rng = seeded()
    label = label_for(rng)
    mixed, functions, classes = styles(rng)
    context = f"зерно {seed}\n{mixed}"
    found = errors(label, mixed)
    assert found and all(label in e for e in found), \
        f"{context}\nошибки: {found}"
    assert errors(label, functions) == [], context
    assert errors(label, classes) == [], context
    extra = f"test_{word(rng)}"
    head = mixed + f"\n\ndef {extra}():\n    assert {extra!r}\n"
    assert errors(label, head, lint_base={label: mixed}) == [], context


@pytest.mark.parametrize("kind", FORMS)
def test_ac6_foreign_project_gets_no_refusal(kind):
    """При `network_addresses=False` ни форма (а)–(з), ни смешение стилей отказа не дают.

    Сценарий: те же файлы, что в AC-3, и смешанный файл AC-5, признак
    артели снят. `long_lived_errors_from_files` ошибок не возвращает.

    Ловит мутацию: новые проверки поставлены вне условия
    `network_addresses` — чужой проект получает отказ.
    """
    seed, rng = seeded()
    label = label_for(rng)
    form = build_form(rng, kind, label)
    found = errors(label, form.source, network=False)
    assert found == [], f"зерно {seed}; {kind}\n{form.source}\nошибки: {found}"
    mixed, _functions, _classes = styles(rng)
    found = errors(label, mixed, network=False)
    assert found == [], f"зерно {seed}; смешение\n{mixed}\nошибки: {found}"


LOCKED_FORMS = ("a_assert", "b_xfail", "c_skip", "d_params", "f_generate",
                "g_getfixturevalue", "h_name")


@pytest.mark.parametrize("kind", LOCKED_FORMS)
def test_ac7_locked_violation_excused_added_one_refused(kind):
    """`lint_base`: нарушение с тем же `ast.dump` в базе не отказывает, добавленное и изменённое — отказывают.

    Сценарий: залоченный текст — файл с нарушением формы `kind`; голова —
    тот же файл, сдвинутый пустыми строками и комментарием. С
    `lint_base` ошибок нет. Затем голова переименовывает функцию
    нарушения (в базе такого имени нет; кроме хука
    `pytest_generate_tests`, который после переименования хуком не
    остаётся) либо меняет её тело (иной `ast.dump`) — отказ с адресом
    функции головы.

    Ловит мутацию: исключение `lint_base` не применяется к новым формам —
    залоченный файл получает отказ; исключение по одному имени без
    сравнения `ast.dump` — изменённая функция отказа не получает.
    """
    seed, rng = seeded()
    label = label_for(rng)
    form = build_form(rng, kind, label)
    base = form.source
    shifted = base.replace("\n\n\n", f"\n\n\n# {word(rng)}\n\n", 1)
    context = f"зерно {seed}; {kind}\n{base}"
    assert errors(label, shifted, lint_base={label: base}) == [], context
    name = form.names[0]
    if kind != "f_generate":
        # Переименованный хук `pytest_generate_tests` хуком быть перестаёт.
        renamed_name = f"{name}_{word(rng)}"
        renamed = shifted.replace(f"def {name}(", f"def {renamed_name}(")
        found = errors(label, renamed, lint_base={label: base})
        assert [e for e in found
                if e.startswith(f"{label}::{renamed_name}: строка ")], \
            f"{context}\nпереименована:\n{renamed}\nошибки: {found}"
    marker = f"{word(rng)}_{rng.randrange(1000)}"
    lines = shifted.splitlines()
    index = next(i for i, line in enumerate(lines)
                 if line.startswith(f"def {name}("))
    lines.insert(index + 1, f"    {marker} = 1")
    changed = "\n".join(lines) + "\n"
    found = errors(label, changed, lint_base={label: base})
    assert [e for e in found if e.startswith(f"{label}::{name}: строка ")], \
        f"{context}\nизменена:\n{changed}\nошибки: {found}"


def test_ac7_module_level_statement_excused_by_same_dump():
    """Модульный `pytest.importorskip(…)` с тем же `ast.dump` в базе не отказывает, добавленный — отказывает.

    Сценарий: залоченный текст несёт модульный `pytest.importorskip("a")`
    вне `pytestmark`; голова — тот же оператор, сдвинутый вниз. С
    `lint_base` ошибок нет. Голова с добавленным модульным
    `pytest.importorskip("b")` получает отказ с адресом «<модуль>» на
    строке нового оператора и без отказа на строке старого.

    Ловит мутацию: ключ исключения модульной формы — номер строки, а не
    `ast.dump` оператора — сдвинутый оператор получает отказ; исключение
    по одному ключу «<модуль>» без сравнения операторов — добавленный
    оператор отказа не получает.
    """
    seed, rng = seeded()
    label = label_for(rng)
    old_mod, new_mod, t = word(rng), word(rng), f"test_{word(rng)}"
    old_call = f"pytest.importorskip(\"{old_mod}\")"
    new_call = f"pytest.importorskip(\"{new_mod}_x\")"
    base = header(rng) + f"\n{old_call}\n\n\ndef {t}():\n    assert {t!r}\n"
    shifted = base.replace(f"\n{old_call}\n", f"\n# {word(rng)}\n\n{old_call}\n")
    context = f"зерно {seed}\n{base}"
    assert errors(label, shifted, lint_base={label: base}) == [], context
    added = shifted.replace(f"{old_call}\n", f"{old_call}\n{new_call}\n")
    found = errors(label, added, lint_base={label: base})
    names = module_names(label)
    new_line = line_of(added, new_call)
    old_line = line_of(added, old_call)
    assert addressed(found, label, names, (new_line,)), \
        f"{context}\nголова:\n{added}\nошибки: {found}"
    assert not addressed(found, label, names, (old_line,)), \
        f"{context}\nголова:\n{added}\nошибки: {found}"


def test_ac9_variants_do_not_change_test_count():
    """Тест-функция с фикстурой `params=` и тест с `parametrize` считаются по одному.

    Сценарий: во временном каталоге `acceptance_tests/test_x.py` —
    случайное число тест-функций, каждая либо запрашивает фикстуру с
    `params=[…]` случайной длины, либо параметризована `parametrize`
    случайным числом вариантов. `count_test_methods` равен числу функций.

    Ловит мутацию: счёт тестов идёт по вариантам (длина `params`/списка
    `parametrize`) — число больше числа функций.
    """
    seed, rng = seeded()
    count = rng.randrange(1, 5)
    parts = ["import pytest\n"]
    for i in range(count):
        values = list(range(rng.randrange(2, 6)))
        if rng.random() < 0.5:
            parts.append(f"\n\n@pytest.fixture(params={values})\n"
                         f"def fx_{i}(request):\n    return request.param\n"
                         f"\n\ndef test_{word(rng)}_{i}(fx_{i}):\n"
                         f"    assert fx_{i} is not None\n")
        else:
            parts.append(f"\n\n@pytest.mark.parametrize(\"v\", {values})\n"
                         f"def test_{word(rng)}_{i}(v):\n    assert v >= 0\n")
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / "acceptance_tests"
        tests_dir.mkdir()
        (tests_dir / f"test_{word(rng)}.py").write_text("".join(parts),
                                                        encoding="utf-8")
        counted = guard.count_test_methods(Path(tmp))
    assert counted == count, f"зерно {seed}\n{''.join(parts)}\nсчёт: {counted}"
