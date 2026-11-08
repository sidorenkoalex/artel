"""Общая фикстура `shared_readonly` в guard — свойства сверх долгоживущих
файлов задачи 01M6Y2P1JDCFFC88NR1JCRWWH9: `weakened_helpers` называет общую
фикстуру по правке `build`, его помощника и присваивания; залоченный файл с
тем же присваиванием и неизменённым тестом освобождается от правила «других
песочниц нет»; общая фикстура не тянет параметр `build` как фикстуру."""
from scripts import guard

LABEL = "tests/test_sample.py"


def source(build_value=1, helper_value=2, sandbox_cls="RealGitSandbox"):
    return ("import pytest\n\n"
            "from tests.sandbox import RealGitSandbox, shared_readonly\n\n\n"
            f"def helper(sb):\n    return {helper_value}\n\n\n"
            f"def build(sb):\n    return helper(sb) + {build_value}\n\n\n"
            f"seeded = shared_readonly({sandbox_cls}, build)\n\n\n"
            "def test_a(seeded):\n    assert seeded.built\n\n\n"
            "def test_b(tmp_root):\n    assert tmp_root\n")


def test_weakened_helpers_names_shared_fixture_on_build_change():
    """Правка литерала `build`, его помощника или класса в присваивании
    называет имя общей фикстуры — по нему гейт ищет тесты вне диффа.

    Ловит мутацию: `_changed_fixture_names` не знает общих фикстур — в
    ответе нет `seeded`, тест другого файла, берущий её, не найдётся.
    """
    base = source()
    assert "seeded" in guard.weakened_helpers(base, source(build_value=5))
    assert "seeded" in guard.weakened_helpers(base, source(helper_value=5))
    assert "seeded" in guard.weakened_helpers(
        base, source(sandbox_cls="OtherSandbox"))
    assert "seeded" not in guard.weakened_helpers(base, source())


def test_locked_file_with_same_shared_fixture_is_released():
    """Залоченный файл, где уже были и общая фикстура, и неизменённый тест с
    `tmp_root`, отказа «других песочниц нет» не получает.

    Ловит мутацию: освобождение `lint_base` для правила общего состояния не
    действует вовсе (требует того, чего база дать не может) — строка
    отказа есть и у неизменённого залоченного файла.
    """
    text = source()
    found = guard.pytest_style_errors_from_files([(LABEL, text)])
    assert any(guard.STYLE_OTHER_SANDBOXES in line for line in found)
    released = guard.pytest_style_errors_from_files(
        [(LABEL, text)], lint_base={LABEL: text})
    assert not any(guard.STYLE_OTHER_SANDBOXES in line for line in released)


def test_build_parameter_is_not_traced_as_fixture():
    """Параметр `sb` функции `build` не разрешается фикстурой: одноимённая
    фикстура файла в записи теста общей фикстуры не попадает.

    Ловит мутацию: у общей фикстуры прослеживаются параметры `build` как
    вложенные фикстуры — правка литерала фикстуры `sb` меняет записи теста.
    """
    def text(value):
        return source() + (f"\n\n@pytest.fixture\ndef sb():\n"
                           f"    return {value}\n")

    def records(value):
        return [key for key, _text in
                guard.test_assertions(text(value), LABEL)["test_a"]]

    assert records(3) == records(4)


def test_long_lived_empty_sandbox_sources_reads_root_sandboxes():
    """`long_lived_errors_from_files(…, sandbox_sources={})` — так его зовут
    выход из `tests_writing`, `preflight` и `amend-tests` при профиле без
    правил размера — классы песочниц берёт из `config.ROOT`: наследник
    `RealGitSandbox` в модуле с общей фикстурой получает отказ.

    Ловит мутацию: пустой словарь `sandbox_sources` уходит проверке стиля
    как есть — перечень классов песочниц пуст, строки отказа нет.
    """
    text = source().replace("def test_b(tmp_root):\n    assert tmp_root\n",
                            "class Local(RealGitSandbox):\n    pass\n")
    errors = guard.long_lived_errors_from_files(
        [(LABEL, text)], "01M6Y2P1JDCFFC88NR1JCRWWH9", sandbox_sources={})
    assert any(guard.STYLE_OTHER_SANDBOXES in line for line in errors)


def test_bare_package_import_names_shared_fixture_and_sandbox():
    """`import tests` (и `import tests.fixtures`, `import tests as p`):
    вызов `tests.sandbox.shared_readonly(…)` — общая фикстура, а
    `tests.sandbox.RealGitSandbox()` в её модуле — отказ «других песочниц
    нет».

    Ловит мутацию: имя пакета из `import tests` не ведёт к его модулям —
    общая фикстура не распознана, утверждение в `build` и создание
    песочницы проходят без отказа.
    """
    def text(header, package):
        return (f"{header}\n\n\n"
                f"def build(sb):\n    assert sb\n\n\n"
                f"seeded = {package}.sandbox.shared_readonly("
                f"{package}.sandbox.RealGitSandbox, build)\n\n\n"
                f"def test_a(seeded):\n"
                f"    assert {package}.sandbox.RealGitSandbox()\n")

    for header, package in (("import tests", "tests"),
                            ("import tests.fixtures", "tests"),
                            ("import tests as p", "p")):
        found = guard.pytest_style_errors_from_files(
            [(LABEL, text(header, package))])
        assert any(guard.STYLE_OTHER_SANDBOXES in line for line in found), \
            (header, found)
        assert any(guard.STYLE_ASSERTION_IN_FIXTURE in line
                   for line in found), (header, found)
