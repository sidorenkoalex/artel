"""Гейт неослабления тестов видит правку данных фикстуры pytest, которой
пользуется залоченный тест (AC-10, AC-13, AC-14, AC-15 в части гейта).

Группа: долгоживущий

Красен до реализации: guard не прослеживает фикстуру, подставляемую по имени параметра, — правка её литерала не меняет записей теста, и общий вход гейтов `test_integrity.uncovered` находки по тесту не возвращает; для фикстуры в `tests/fixtures.py` `weakened_helpers` её не называет, и вызывающий вне диффа не сравнивается. Зелены с рождения маршрут мандата AC-10 (находок по файлу нет и сегодня) и AC-15 (находку сегодня даёт своё утверждение теста; метод держит отсутствие исключения рядом с записью фикстуры).

Песочница — `tests.sandbox.ConnRealGitSandbox`, связка «git — гейт —
журнал»: база — коммит на main, голова — ветка задачи `BRANCH`, мандат —
`ANSWER-1.md` на ветке документов `DOCS` коммитом ответа Оператора,
объявление «Меняемое поведение» — запись журнала
`test_integrity.DECLARED_CHANGE_ACTION` (её пишет approve гейта SPEC).
Гейт читается публичным входом `test_integrity.uncovered` (общий вход
перехода `in_dev -> verifying` и гейта мержа). Песочница заводится
собственной фикстурой файла (общие фикстуры А1 не используются). Имена
файлов, фикстур, тестов и значения литералов — из `random`; зерно
печатается и входит в текст провала.
"""
import random

import pytest

from orchestrator import config, store
from orchestrator.advance_gates import test_integrity
from tests.sandbox import ConnRealGitSandbox

TASK = "T001"
BRANCH = "task/t001-fikstury"
DOCS = "artifact/t001"
STATE = "review"
MARKER = test_integrity.TEST_WEAKENING_MANDATE_MARKER
ANSWER_SUBJECT = f"{TASK}: ANSWER-1 — ответ Оператора"
FIXTURES_PATH = "tests/fixtures.py"


@pytest.fixture
def gate():
    """Задача `TASK` в `STATE` в настоящем git-репозитории песочницы."""
    case = ConnRealGitSandbox()
    case.setUp()
    try:
        store.insert_task(case.conn, TASK, "Фикстуры", STATE, BRANCH,
                          config.DEFAULT_TARGET, 10.0)
        case.conn.commit()
        yield case
    finally:
        case.doCleanups()


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


def write(case, files):
    for rel, text in files.items():
        target = case.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def commit_diff(case, base, head):
    """База — коммит на main, голова — коммит ветки задачи."""
    write(case, base)
    case.git("add", "-A")
    case.git("commit", "-q", "-m", "база")
    case.checkout(BRANCH, create=True)
    write(case, head)
    case.git("add", "-A")
    case.git("commit", "-q", "-m", "голова")
    case.checkout(config.MAIN_BRANCH)


def add_mandate(case, elements):
    case.checkout(DOCS, create=True)
    write(case, {"/".join(("tasks", TASK, "ANSWER-1.md")):
                 f"# Ответ Оператора\n\n{MARKER} {elements}\n"
                 f"Основание: решение Оператора.\n"})
    case.git("add", "-A")
    case.git("commit", "-q", "-m", ANSWER_SUBJECT)
    case.checkout(config.MAIN_BRANCH)


def declare(case, line):
    store.journal(case.conn, TASK, "fsm", test_integrity.DECLARED_CHANGE_ACTION,
                  line)
    case.conn.commit()


def uncovered_lines(case, seed):
    found, git_detail = test_integrity.uncovered(case.conn, TASK, BRANCH, DOCS)
    assert found is not None, f"зерно {seed}: git не ответил: {git_detail}"
    return [f.line for f in found]


def fixture_module(name, body, test=""):
    lines = "".join(f"    {line}\n" for line in body.splitlines())
    return f"import pytest\n\n\n@pytest.fixture\ndef {name}():\n{lines}{test}"


def function_test(t, name):
    return f"\n\ndef test_{t}({name}):\n    assert {name}\n"


def names_test(lines, path, qual):
    return [line for line in lines if line.startswith(f"{path}:") and
            qual in line]


@pytest.mark.parametrize("route", ("none", "mandate", "declared"))
def test_ac10_fixture_literal_edit_finding_and_its_removal(gate, route):
    """Правка литерала фикстуры залоченного теста — находка; снимает её только мандат на путь.

    Сценарий: файл тестов с фикстурой `return a` и классом с тестом,
    запрашивающим фикстуру параметром; в голове `return b`. Без
    объявления и мандата `uncovered` возвращает находку по тесту. С
    мандатом на путь файла находок по файлу нет. С объявлением правки
    `a` → `b` этого теста в «Меняемое поведение» (запись approve) и без
    мандата находка по тесту остаётся.

    Ловит мутацию: фикстура не прослеживается — находки нет без мандата;
    записи фикстуры дана роль равенства — объявленная пара `a` → `b`
    совпадает с фактической, и находка снимается объявлением.
    """
    seed, rng = seeded()
    path = f"tests/test_{word(rng)}.py"
    name, t, cls = f"fx_{word(rng)}", word(rng), f"Test{word(rng).capitalize()}"
    old, new = two_values(rng)
    test = (f"\n\nclass {cls}:\n\n    def test_{t}(self, {name}):\n"
            f"        assert {name}\n")
    commit_diff(gate, {path: fixture_module(name, f"return {old}", test)},
                {path: fixture_module(name, f"return {new}", test)})
    qual = f"{cls}::test_{t}"
    if route == "mandate":
        add_mandate(gate, path)
    elif route == "declared":
        declare(gate, f"- `{path}::{qual}`: `{old}` → `{new}` (требование 1)")
    lines = uncovered_lines(gate, seed)
    context = f"зерно {seed}; {route}; находки: {lines}"
    if route == "mandate":
        assert not [line for line in lines if line.startswith(f"{path}:")], \
            context
    else:
        assert names_test(lines, path, qual), context


def test_ac13_swapping_fixture_literals_is_a_finding(gate):
    """Обмен значениями двух литералов фикстуры залоченного теста — находка гейта.

    Сценарий: фикстура `limit = a; expected = b; return limit, expected`,
    в голове `limit = b; expected = a`; тест-функция запрашивает фикстуру
    параметром. `uncovered` без мандата возвращает находку по тесту.

    Ловит мутацию: ключ записи без порядкового номера литерала —
    мультимножества сторон совпадают, находки нет.
    """
    seed, rng = seeded()
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    a, b = two_values(rng)
    sides = [fixture_module(name, f"limit = {x}\nexpected = {y}\n"
                                  f"return limit, expected",
                            function_test(t, name))
             for x, y in ((a, b), (b, a))]
    commit_diff(gate, {path: sides[0]}, {path: sides[1]})
    lines = uncovered_lines(gate, seed)
    assert names_test(lines, path, f"test_{t}"), \
        f"зерно {seed}; находки: {lines}"


@pytest.mark.parametrize("form", ("call_argument", "sign", "helper"))
def test_ac14_fixture_data_edits_in_test_file_are_findings(gate, form):
    """`Config(limit=a)` → `b`, `return a` → `-a` и правка помощника фикстуры — находки гейта.

    Сценарий: файл тестов с фикстурой и тестом-функцией, запрашивающей её
    параметром; правка — аргумент вызова в `return`, знак возвращаемого
    числа либо литерал помощника `_expected`, которого фикстура зовёт
    (`return _expected()`, тело фикстуры не меняется). `uncovered` без
    мандата возвращает находку по тесту.

    Ловит мутацию: аргументы вызовов в запись не идут; знак не входит в
    литерал; константы помощника фикстуры в запись не идут — в каждом
    случае находки по тесту нет.
    """
    seed, rng = seeded()
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    old, new = two_values(rng)
    test = function_test(t, name)
    if form == "call_argument":
        cls = f"Config{word(rng).capitalize()}"
        sides = [fixture_module(name, f"return {cls}(limit={v})", test)
                 for v in (old, new)]
    elif form == "sign":
        sides = [fixture_module(name, f"return {v}", test)
                 for v in (old, -old)]
    else:
        sides = [fixture_module(name, "return _expected()",
                                f"\n\ndef _expected():\n    return {v}\n"
                                + test)
                 for v in (old, new)]
    commit_diff(gate, {path: sides[0]}, {path: sides[1]})
    lines = uncovered_lines(gate, seed)
    assert names_test(lines, path, f"test_{t}"), \
        f"зерно {seed}; {form}; голова:\n{sides[1]}\nнаходки: {lines}"


@pytest.mark.parametrize("edited", ("helper", "fixture"))
def test_ac14_shared_fixture_edit_reaches_test_outside_diff(gate, edited):
    """Правка помощника или фикстуры в `tests/fixtures.py` — находка по тесту вне диффа.

    Сценарий: в `tests/fixtures.py` помощник `_expected` и фикстура,
    которая возвращает `_expected()`; файл теста, запрашивающего фикстуру
    параметром, в базе и в голове одинаков. Правка — литерал помощника
    (тело фикстуры не меняется) либо литерал самой фикстуры
    (`return _expected() + a` → `+ b`). `uncovered` без мандата
    возвращает находку по тесту из неизменённого файла.

    Ловит мутацию: `weakened_helpers` не называет фикстуру, вызывающую
    изменённого помощника, — поиск вызывающих по имени помощника находит
    только `tests/fixtures.py`, тест вне диффа не сравнивается, находки
    нет; данные фикстуры из `tests/fixtures.py` не читаются модулями
    своей стороны — записи теста по обе стороны одинаковы.
    """
    seed, rng = seeded()
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    old, new = two_values(rng)
    shift = rng.randrange(1, 9)

    def shared(helper_value, fixture_value):
        return fixture_module(name, f"return _expected() + {fixture_value}",
                              f"\n\ndef _expected():\n    return "
                              f"{helper_value}\n")

    base = shared(old, shift)
    head = shared(new, shift) if edited == "helper" else shared(old, shift + 10)
    test = "import pytest\n" + function_test(t, name)
    commit_diff(gate, {FIXTURES_PATH: base, path: test}, {FIXTURES_PATH: head})
    lines = uncovered_lines(gate, seed)
    assert names_test(lines, path, f"test_{t}"), \
        f"зерно {seed}; {edited}; находки: {lines}"


@pytest.mark.parametrize("own", ("unmatched", "removed"))
def test_ac15_gate_handles_fixture_record_next_to_unmatched_assertion(gate, own):
    """Запись фикстуры рядом со своим утверждением теста без пары проходит гейт без исключения.

    Сценарий: литерал фикстуры изменён, а своё утверждение теста сменило
    форму (`assert x == c` → `assert x`) либо удалено. `uncovered`
    (сравнение, различение и храповик) отрабатывает без исключения и
    возвращает находку по тесту.

    Ловит мутацию: признак иной смены (`_other_change_sign`) берёт вид
    утверждения у записи фикстуры как у вызова — `AttributeError` из
    `uncovered`.
    """
    seed, rng = seeded()
    path = f"tests/test_{word(rng)}.py"
    name, t = f"fx_{word(rng)}", word(rng)
    old, new = two_values(rng)
    check = rng.randrange(1, 9)
    head_body = f"assert {name}" if own == "unmatched" else "pass"
    base = fixture_module(name, f"return {old}",
                          f"\n\ndef test_{t}({name}):\n"
                          f"    assert {name} == {check}\n")
    head = fixture_module(name, f"return {new}",
                          f"\n\ndef test_{t}({name}):\n    {head_body}\n")
    commit_diff(gate, {path: base}, {path: head})
    lines = uncovered_lines(gate, seed)
    assert names_test(lines, path, f"test_{t}"), \
        f"зерно {seed}; {own}; находки: {lines}"
