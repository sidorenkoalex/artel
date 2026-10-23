"""Разрешение фикстур pytest в разборе утверждений guard и отказы стиля —
свойства сверх долгоживущих файлов задачи 01M5N9WK9SGB7KDYJP736DP6CV:
`indirect=`, фикстура класса, переопределение одноимённой фикстуры
`tests/fixtures.py`, `indirect=` в `pytestmark`, `weakened_helpers` по
фикстуре, запросившей изменённую фикстуру."""
from collections import Counter

from scripts import guard

PATH = "tests/test_sample.py"


def records(source, shared=None):
    texts = {PATH: source, guard.FIXTURES_MODULE_PATH: shared}
    modules = guard.TestModules(lambda p: texts.get(p))
    return guard.test_assertions(source, PATH, modules)


def multiset(items):
    return Counter(repr(item) for item in items)


def test_indirect_parametrize_name_stays_a_fixture():
    """Имя `parametrize` с `indirect=True` отдаётся фикстуре — её данные
    идут тесту.

    Ловит мутацию: `indirect=` не учитывается, имя аргумента `parametrize`
    всегда исключается из фикстур — правка литерала фикстуры записей теста
    не меняет.
    """
    def source(value):
        return ("import pytest\n\n\n@pytest.fixture\ndef fx(request):\n"
                f"    return request.param + {value}\n\n\n"
                "@pytest.mark.parametrize(\"fx\", [1], indirect=True)\n"
                "def test_a(fx):\n    assert fx\n")

    assert multiset(records(source(7))["test_a"]) != \
        multiset(records(source(8))["test_a"])


def test_class_fixture_shadows_module_fixture_for_its_methods():
    """Фикстура тела класса важнее одноимённой фикстуры модуля для методов
    этого класса.

    Ловит мутацию: фикстуры тела класса не видны — тест получает данные
    фикстуры модуля, правка фикстуры класса записей не меняет.
    """
    def source(module_value, class_value):
        return ("import pytest\n\n\n@pytest.fixture\ndef fx():\n"
                f"    return {module_value}\n\n\nclass TestA:\n\n"
                "    @pytest.fixture\n    def fx(self):\n"
                f"        return {class_value}\n\n"
                "    def test_a(self, fx):\n        assert fx\n")

    name = f"TestA{guard.TEST_NAME_SEP}test_a"
    base = multiset(records(source(1, 2))[name])
    assert base != multiset(records(source(1, 3))[name])
    assert base == multiset(records(source(4, 2))[name])


def test_own_fixture_overriding_shared_one_traces_the_shared():
    """Своя фикстура, запросившая одноимённую, разрешается в фикстуру
    `tests/fixtures.py`, а не в саму себя.

    Ловит мутацию: вложенное имя разрешается в саму фикстуру — данных
    общей фикстуры в записях нет, её правка записей теста не меняет.
    """
    own = ("import pytest\n\n\n@pytest.fixture\ndef fx(fx):\n"
           "    return fx + 1\n\n\ndef test_a(fx):\n    assert fx\n")

    def shared(value):
        return f"import pytest\n\n\n@pytest.fixture\ndef fx():\n    return {value}\n"

    base = records(own, shared(10))["test_a"]
    assert multiset(base) != multiset(records(own, shared(11))["test_a"])
    assert any(guard.FIXTURES_MODULE_PATH in repr(item) for item in base)


def test_indirect_in_module_pytestmark_refused_at_module_address():
    """`indirect=` в `pytestmark` модуля — отказ с адресом «<модуль>».

    Ловит мутацию: `pytestmark` не проверяется на `indirect=` — строки
    отказа нет.
    """
    source = ('"""Файл."""\nimport pytest\n\npytestmark = [pytest.mark.'
              'parametrize("fx", [1], indirect=True)]\n\n\n'
              "@pytest.fixture\ndef fx(request):\n    return request.param\n"
              "\n\ndef test_a(fx):\n    assert fx\n")
    found = guard.pytest_style_errors_from_files([(PATH, source)])
    assert [e for e in found
            if e.startswith(f"{PATH}::{guard.PYTEST_STYLE_MODULE_LABEL}: "
                            f"строка 4:")], found


def test_weakened_helpers_names_fixture_requesting_changed_fixture():
    """Фикстура, запросившая фикстуру с изменённым телом, тоже названа.

    Ловит мутацию: `weakened_helpers` называет только изменённую фикстуру —
    тест, запросивший внешнюю фикстуру, вне диффа не ищется.
    """
    def source(value):
        return ("import pytest\n\n\n@pytest.fixture\ndef inner():\n"
                f"    return {value}\n\n\n@pytest.fixture\n"
                "def outer(inner):\n    return inner\n")

    assert {"inner", "outer"} <= guard.weakened_helpers(source(1), source(2))


HELPERS_PATH = "tests/helpers_sample.py"
IMPORTING = ("import pytest\nfrom tests.helpers_sample import make\n\n\n"
             "@pytest.fixture\ndef cfg():\n    return make()\n\n\n"
             "def test_a(cfg):\n    assert cfg\n")


def helpers_source(value):
    return f"def make():\n    return {value}\n"


def records_with_helpers(helpers):
    texts = {PATH: IMPORTING, HELPERS_PATH: helpers}
    modules = guard.TestModules(lambda p: texts.get(p))
    return guard._assertion_records(IMPORTING, PATH, modules)["test_a"]


def test_fixture_helper_imported_from_other_tests_module_is_traced():
    """Помощник фикстуры, импортированный из другого модуля `tests/`, —
    в записи данных фикстуры, с происхождением из файла помощника (ревью
    итерации 1, R1-F1).

    Ловит мутацию: помощник фикстуры ищется только в модуле фикстуры
    (`_HelperScope(module, None)`) — правка `5` → `500` в помощнике другого
    модуля записей теста не меняет.
    """
    base = records_with_helpers(helpers_source(5))
    head = records_with_helpers(helpers_source(500))
    assert multiset(item[:2] for item in base) != \
        multiset(item[:2] for item in head)
    assert {item[3][1] for item in base if item[3]} == {HELPERS_PATH}


def test_weakened_helpers_names_module_function_with_changed_literal():
    """Функция модуля с иным литералом названа, с теми же литералами — нет:
    по её имени находится файл фикстуры, которая зовёт её по импорту.

    Ловит мутацию: `weakened_helpers` называет функции модуля только по
    потере утверждений — помощник фикстуры другого файла не называется, и
    тест, запросивший фикстуру, вне диффа не сравнивается.
    """
    assert "make" in guard.weakened_helpers(helpers_source(5),
                                            helpers_source(500))
    assert "make" not in guard.weakened_helpers(
        helpers_source(5), "def make():\n    \"\"\"Пять.\"\"\"\n    return 5\n")
