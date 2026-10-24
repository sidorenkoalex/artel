"""AC-1: патчи мутаций `mutation-<nnn>.diff`, заявки «Ловит мутацию» всех 40
исходных тестов и их сопоставление патчам в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff, PLAN.md и файлов модулей ещё нет — загрузчики _ctx бросают LookupError.

Патчи и PLAN — ссылка документов задачи (`_pult.artifact_text`, перечень
первого уровня — `git ls-tree` ревизии выкладки); исходные файлы — база
ветки (`_pult.DIFF_BASE`), файлы модулей — HEAD. Соглашения разбора PLAN —
докстринг `_plan.py`: тест и мутация сопоставлены, когда в одной строке
PLAN (вне таблиц `mutation-run`) стоят `<Класс>::<метод>` теста и имя
патча `mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество заявок («одинаковые по смыслу — одна мутация») и
верность описания правки разбором не различимы; планка держит наблюдаемую
часть: каждый из 40 тестов сопоставлен патчу, у каждого патча есть
заявивший тест, у каждой перенесённой функции есть заявка, новая заявка
воплощена патчем кода `merge_lock.py`/`merge_queue.py`/`store.py`.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402


def test_ac1_patches_numbered_from_001_in_a_row_and_touch_only_orchestrator():
    """Патчи первого уровня: номера 001, 002, … без пропусков, каждый меняет только `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи начинается с 1 и не имеет пропусков; каждый патч несёт хотя бы
    один путь и одну изменённую строку, и все его пути — под
    `orchestrator/`.

    Ловит мутацию: роль пропустила номер при переписывании набора (001,
    002, 004), начала с 002 или положила в патч правку `tests/` — перечень
    или пути патча другие, тест краснеет с номерами или именем патча.
    """
    names = _ctx.patch_names()
    numbers = sorted(names)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"номера патчей не подряд с 001: {numbers}")
    problems = []
    for _number, name in sorted(names.items()):
        text = _ctx.patch_text(name)
        paths = _plan.patch_paths(text)
        outside = sorted(p for p in paths if not p.startswith("orchestrator/"))
        if not paths:
            problems.append(f"{name}: в патче нет ни одного пути")
        if outside:
            problems.append(f"{name}: меняет файлы вне orchestrator/: {outside}")
        if _plan.changed_line_count(text) < 1:
            problems.append(f"{name}: в патче нет изменённых строк")
    assert not problems, "\n".join(problems)


def test_ac1_every_one_of_40_source_tests_mapped_to_a_patch():
    """Каждый из 40 исходных тестов сопоставлен в PLAN патчу набора; прежних заявок — 19.

    В базе ветки у трёх исходных файлов 40 тестов, 19 из них со строкой
    «Ловит мутацию» в докстринге. Для каждого из 40 в PLAN есть строка вне
    таблиц, где `<Класс>::<метод>` теста стоит рядом со ссылкой на патч
    набора.

    Ловит мутацию: PLAN сопоставил мутации 19 прежним заявкам, а 21 новую
    (например `HeadTaskIdTest::test_empty_queue_has_no_head`) не назвал —
    перечень несопоставленных непуст, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    mapped = _ctx.mapping(plan, set(_ctx.patch_names()))
    tests = _ctx.base_tests()
    assert len(tests) == _plan.TEST_COUNT, (
        f"в исходных файлах базы тестов {len(tests)}, критерий называет "
        f"{_plan.TEST_COUNT} — база прочитана не та")
    claims = sum(1 for t in tests.values() if t.claim)
    assert claims == _plan.CLAIM_COUNT, (
        f"в исходных файлах базы заявок {claims}, критерий называет "
        f"{_plan.CLAIM_COUNT}")
    missing = [f"{t.path}::{t.key}" for t in tests.values() if not mapped.get(t.key)]
    assert not missing, ("исходные тесты без сопоставленного патча в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_patch_named_with_its_claiming_tests():
    """У каждого патча набора в PLAN названы заявившие его исходные тесты.

    Для каждого патча есть строка PLAN вне таблиц со ссылкой на него и
    хотя бы одним `<Класс>::<метод>` теста трёх исходных файлов базы;
    тесты одной мутации могут стоять списком в одной строке.

    Ловит мутацию: роль добавила патч в набор, но не назвала, чью заявку он
    воплощает (или сослалась на несуществующий тест `AcquireReleaseTest::
    test_acquire`) — у номера нет заявивших тестов, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    numbers = set(_ctx.patch_names())
    keys = set(_ctx.base_tests())
    named = set()
    for key, hit in _ctx.mapping(plan, numbers).items():
        if key in keys:
            named |= hit
    orphan = sorted(numbers - named)
    assert not orphan, f"патчи без заявивших исходных тестов в PLAN: {orphan}"


def test_ac1_new_claims_realised_by_patch_of_lock_queue_or_store_code():
    """Каждый из 21 теста без прежней заявки сопоставлен патчу кода `merge_lock.py`, `merge_queue.py` или `store.py`.

    Для исходного теста без строки «Ловит мутацию» в базе среди
    сопоставленных ему в PLAN патчей есть патч, все пути которого — из
    `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`,
    `orchestrator/store.py`.

    Ловит мутацию: новая заявка `RunWindowTest::test_mutex_is_released_even_
    when_the_body_raises` воплощена патчем `orchestrator/liveness.py` (или
    сопоставлена только патчу `orchestrator/config.py`) — у теста нет патча
    кода трёх модулей, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    mapped = _ctx.mapping(plan, set(names))
    paths = {n: _plan.patch_paths(_ctx.patch_text(name)) for n, name in names.items()}
    problems = []
    for test in _ctx.base_tests().values():
        if test.claim:
            continue
        good = [n for n in sorted(mapped.get(test.key, ()))
                if paths[n] and paths[n] <= set(_plan.CLAIM_CODE)]
        if not good:
            problems.append(f"{test.key}: патчи {sorted(mapped.get(test.key, ()))} "
                            f"не меняют только {list(_plan.CLAIM_CODE)}")
    assert not problems, "\n".join(problems)


def test_ac1_each_source_test_claim_lives_in_its_transferred_function():
    """Заявка каждого из 40 исходных тестов стоит в докстринге функции, в которую он перенесён.

    Для исходного теста, не названного в PLAN удалённым дублем, в его
    файле модуля (замок и `LegacyTouchHeartbeatTest` —
    `tests/test_merge_lock_module.py`, остальное —
    `tests/test_merge_queue.py`) есть функция-тест с его именем, и в её
    докстринге есть «Ловит мутацию»; у прежних 19 заявок — тоже.

    Ловит мутацию: новая заявка теста `HeadTaskIdTest::
    test_empty_queue_has_no_head` записана только в PLAN, а докстринг
    функции остался прежним однострочным — тест перечислен, тест краснеет.
    """
    plan = _ctx.plan_text()
    removed = set(_plan.removed_duplicates(plan))
    trees = _ctx.head_trees()
    problems = []
    for test in _ctx.base_tests().values():
        if test.key in removed:
            continue
        funcs = _plan.moved_to(test.name, _plan.module_tests(trees[test.target]))
        if not funcs:
            problems.append(f"{test.key}: в {test.target} нет функции с его именем")
        elif not any(_plan.CLAIM in (ast.get_docstring(f) or "") for f in funcs):
            problems.append(f"{test.key}: у {test.target}::{funcs[0].name} нет "
                            f"«{_plan.CLAIM}»")
    assert not problems, "\n".join(problems)
