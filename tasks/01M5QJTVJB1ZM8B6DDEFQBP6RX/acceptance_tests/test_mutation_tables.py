"""AC-2, AC-3, AC-4, AC-5, AC-14 (дубли), AC-15, AC-16: таблицы
`mutation-run` «до» и «после» в PLAN и их согласованность с набором
патчей, строками падения, находками, удалёнными дублями, переносом тестов
и рабочей копией; числа тестов, строк и время до и после.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после», патчей и файлов модулей ещё нет — прогонов mutation-run и свода не было, загрузчики _ctx бросают LookupError.

Планка сверяет форму и согласованность таблиц; подлинность таблиц и
исход повтора — работа независимой проверки (требование 18 SPEC).
Соглашения разбора PLAN — докстринг `_plan.py`. «Функция, в которую
перенесён тест» — функция-тест его файла модуля с его именем
(`_plan.moved_to`).
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT, TASK_ID  # noqa: E402

_BEFORE_NODE = re.compile(
    r"^(?:" + "|".join(re.escape(p) for p in _plan.SOURCE_FILES)
    + r")::[A-Za-z_]\w*::test\w*$")
_AFTER_NODE = re.compile(
    r"^(?:" + "|".join(re.escape(p) for p in _plan.MODULE_FILES)
    + r")::test\w*(?:\[.*\])?$")
_DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|секунд[а-я]*|s|мин|min)"
                       r"(?![A-Za-zА-Яа-яЁё])")
_BEFORE_PREP = ("setUp", *_plan.HELPER_METHODS)


def _after_prep() -> tuple:
    names = set()
    for helpers in _plan.HELPERS.values():
        names |= set(helpers)
    return tuple(sorted(names))


def _before_killers(nodes) -> set:
    return {_plan.node_key(n) for n in nodes}


def _after_killers(nodes) -> set:
    return {_plan.after_node(n) for n in nodes}


def _moved(test, head_trees) -> set:
    """{(файл модуля, функция)} функций, в которые перенесён исходный тест."""
    funcs = _plan.module_tests(head_trees[test.target])
    return {(test.target, f.name) for f in _plan.moved_to(test.name, funcs)}


def _check_table_rows(table, where: str, node_re, problems: list) -> None:
    for number, outcome, nodes in table.rows:
        if number not in table.patches:
            problems.append(f"{where}: строка мутации {number} без строки "
                            f"«# патч {number} …» в шапке")
        if outcome not in _plan.OUTCOMES:
            problems.append(f"{where}: мутация {number} — исход «{outcome}» не "
                            f"из вывода команды")
        if outcome == _plan.KILLED and (not nodes or any(
                not node_re.match(n) for n in nodes)):
            problems.append(f"{where}: мутация {number} убита, узлы не того "
                            f"вида: {nodes}")
    listed = {n for n, _o, _nodes in table.rows}
    absent = sorted(set(table.patches) - listed)
    if absent:
        problems.append(f"{where}: строк мутаций шапки нет в выводе: {absent}")


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_three_source_files_parts_and_every_patch():
    """Раздел «Мутации до»: таблицы `--ref base` на трёх исходных файлах, части по ≤25 патчей, все патчи в них.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно три исходных файла,
    строки «# патч … sha256 …», не больше 25 патчей; у каждой строки
    «# патч» шапки есть строка вывода, у каждой строки вывода — строка
    шапки; исход — из словаря команды; у «убита» узлы непусты и имеют вид
    `tests/<файл>::<Класс>::<метод>`. Каждый номер набора есть в таблицах.

    Ловит мутацию: роль перенесла только последнюю часть деления
    `--patches`, прогнала часть из 30 патчей, прогнала «до» с `--ref
    worktree` или без `tests/test_merge_lock_by_project.py` в `--tests`, или
    обрезала вывод части — номер отсутствует, часть велика, ревизия или
    список тестов не те, тест краснеет.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    found = _ctx.section_tables(plan, "Мутации до")
    problems = []
    for table in found:
        where = f"таблица «до» №{table.run_no}"
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != "base":
            problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась base")
        if sorted(table.tests) != sorted(_plan.SOURCE_FILES):
            problems.append(f"{where}: тесты {table.tests}, ожидались "
                            f"{list(_plan.SOURCE_FILES)}")
        if not table.patches:
            problems.append(f"{where}: в шапке нет строк «# патч … sha256 …»")
        if len(table.patches) > _plan.MAX_PART:
            problems.append(f"{where}: патчей в части {len(table.patches)}, "
                            f"больше {_plan.MAX_PART}")
        _check_table_rows(table, where, _BEFORE_NODE, problems)
    absent = sorted(set(names) - set(_plan.last_rows(found)))
    if absent:
        problems.append(f"мутаций набора нет в таблицах «до»: {absent}")
    assert not problems, "\n".join(problems)


def test_ac2_parts_with_window_path_patches_hold_at_most_8():
    """Часть с патчем пути взятия окна — не больше 8 патчей, «до» и «после».

    Патч, после которого окно может не взяться, — патч, меняющий строки
    функций `merge_lock.acquire`, `_holder_is_dead`, `_is_own_process`,
    `run_window` или `merge_queue.wait_for_window`, `_head_task_id`,
    `_prune_dead_entries` (строки старой стороны хунков по тексту модуля
    базы ветки). Таблица «до» или «после», в шапке которой есть такой
    патч, несёт не больше 8 патчей.

    Ловит мутацию: роль прогнала мутацию «`acquire` всегда отказывает»
    вместе с 20 другими одной частью `--patches 1-21` — у части с патчем
    окна 21 патч, тест краснеет с номером таблицы.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    window = set()
    for number, name in names.items():
        for path, lines in _plan.patch_old_lines(_ctx.patch_text(name)).items():
            wanted = _plan.WINDOW_FUNCTIONS.get(path)
            if not wanted:
                continue
            text = _ctx.base_text(path)
            if any(set(_plan.enclosing_functions(text, n)) & set(wanted)
                   for n in lines):
                window.add(number)
    problems = []
    for title in ("Мутации до", "Мутации после"):
        for table in _ctx.section_tables(plan, title):
            hit = sorted(set(table.patches) & window)
            if hit and len(table.patches) > _plan.MAX_WINDOW_PART:
                problems.append(f"«{title}» таблица №{table.run_no}: патчей "
                                f"{len(table.patches)} при патчах окна {hit}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-3

def test_ac3_each_killed_mutation_names_failing_file_line_before_and_after():
    """У каждой убитой мутации PLAN называет строку падения файл:строка «до» и «после».

    Для мутации с последним исходом «до» «убита» есть строка PLAN вне
    таблиц со ссылкой на мутацию, ключом `<Класс>::<метод>` одного из её
    убийц «до» и ссылкой `tests/<исходный файл>.py:<строка>`; для убитой
    «после» — строка со ссылкой на мутацию, ссылкой на функцию-убийцу
    «после» и `tests/<файл модуля>.py:<строка>`.

    Ловит мутацию: роль привела строку падения только для таблицы «до» (или
    только имя убившего теста без файл:строка) — у мутации нет строки
    «после», тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    after = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации после")))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        killers = _before_killers(nodes)
        if not any(number in _plan.refs(line) and _plan.test_keys(line) & killers
                   and any(p in _plan.SOURCE_FILES for p, _n in _plan.file_lines(line))
                   for line in lines):
            problems.append(f"мутация {number} «до»: нет строки с убийцей из "
                            f"{sorted(killers)} и файл:строка исходного файла")
    for number, nodes in sorted(after.items()):
        killers = _after_killers(nodes)
        if not any(number in _plan.refs(line) and _plan.after_refs(line) & killers
                   and any(p in _plan.MODULE_FILES for p, _n in _plan.file_lines(line))
                   for line in lines):
            problems.append(f"мутация {number} «после»: нет строки с убийцей из "
                            f"{sorted(killers)} и файл:строка файла модуля")
    assert not problems, "\n".join(problems)


def test_ac3_failing_line_in_pause_substitute_is_its_raise_assertion_error():
    """Строка падения в подмене паузы `fake_sleep` by_project — её `raise AssertionError`.

    Каждая ссылка PLAN `tests/test_merge_lock_by_project.py:<строка>`,
    попадающая в тело `fake_sleep` (база ветки), указывает на строку
    `raise AssertionError("задача P ушла в паузу очереди")`; каждая ссылка
    на файл модуля внутри вложенной `fake_sleep`, поднимающей
    `AssertionError`, — на её строку `raise`.

    Ловит мутацию: роль назвала строкой падения `def fake_sleep` (:104) или
    вызов `merge_queue.wait_for_window` вместо `raise AssertionError` —
    ссылка не на строку `raise`, тест краснеет с ней.
    """
    plan = _ctx.plan_text()
    base_trees = _ctx.base_trees()
    head_trees = _ctx.head_trees()
    problems = []
    for line in _plan.prose_lines(plan):
        for path, number in _plan.file_lines(line):
            if path == _plan.BY_PROJECT_SOURCE:
                tree = base_trees[path]
            elif path in head_trees:
                base_tree = base_trees.get(path)
                if base_tree is not None and \
                        _plan.assertion_at(base_tree, number) is not None:
                    continue  # ссылка на утверждение исходного файла очереди
                tree = head_trees[path]
            else:
                continue
            for func in ast.walk(tree):
                if not (isinstance(func, ast.FunctionDef)
                        and func.name == "fake_sleep"
                        and func.lineno <= number <= func.end_lineno):
                    continue
                raises = [n.lineno for n in ast.walk(func)
                          if _plan.is_assertion_error_raise(n)]
                if raises and number not in raises:
                    problems.append(f"{path}:{number} — в fake_sleep, но не "
                                    f"строка raise AssertionError {raises}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-4

def test_ac4_proof_kill_is_assertion_failure_outside_preparation():
    """Убитая мутация засчитана утверждением теста, а не сбором, исключением или подготовкой.

    Для каждой мутации с последним исходом «убита» есть строка PLAN с
    ссылкой на мутацию и убийцей, чья ссылка файл:строка лежит внутри
    утверждения (`assert`, `self.assert*`, `pytest.raises`/`fail`, `raise
    AssertionError`) в теле самого убившего теста — не в `setUp`,
    помощнике подготовки (`row`, `seed`, `enqueue`, …) или фикстуре:
    «до» — по базе ветки, «после» — по HEAD.

    Ловит мутацию: мутация «убита» исключением `sqlite3.OperationalError` в
    `store.insert_task` фикстуры (или по таймауту на строке
    `merge_queue.wait_for_window(...)`), и роль привела эту строку — она
    не в утверждении теста, тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    base_trees = _ctx.base_trees()
    head_trees = _ctx.head_trees()
    tests = _ctx.base_tests()
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    after = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации после")))
    lines = _plan.prose_lines(plan)
    prep = _after_prep()
    problems = []
    for number, nodes in sorted(before.items()):
        killers = _before_killers(nodes) & set(tests)
        ok = any(
            number in _plan.refs(line) and any(
                tests[key].path == path and _plan.site_ok(
                    base_trees[path], n, tests[key].name, _BEFORE_PREP)
                for key in _plan.test_keys(line) & killers
                for path, n in _plan.file_lines(line))
            for line in lines)
        if not ok:
            problems.append(f"мутация {number} «до»: нет строки падения в "
                            f"утверждении убийцы из {sorted(killers)}")
    for number, nodes in sorted(after.items()):
        killers = _after_killers(nodes)
        ok = any(
            number in _plan.refs(line) and any(
                fpath == path and _plan.site_ok(head_trees.get(path), n, func, prep)
                for fpath, func in _plan.after_refs(line) & killers
                for path, n in _plan.file_lines(line))
            for line in lines)
        if not ok:
            problems.append(f"мутация {number} «после»: нет строки падения в "
                            f"утверждении убийцы из {sorted(killers)}")
    assert not problems, "\n".join(problems)


def test_ac4_not_killed_and_collection_only_before_listed_as_findings():
    """Мутации, которые «до» не убил никто (в том числе «убитые» только сбором), — находки PLAN.

    Для мутации с последним исходом «до» «не убита» или «ошибка сбора,
    импорта или setup» в PLAN есть ссылка на неё в строке со словом
    «находк…» либо в разделе, в заголовке которого оно есть.

    Ловит мутацию: роль оставила в наборе патч, который «до» никто не убил
    (или чей прогон упал сбором), и не записала его находкой — номер не
    найден среди находок, тест краснеет.
    """
    plan = _ctx.plan_text()
    rows = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    survived = {n for n, (outcome, _nodes) in rows.items()
                if outcome in (_plan.SURVIVED, _plan.COLLECTION)}
    unlisted = sorted(survived - _plan.finding_refs(plan))
    assert not unlisted, f"мутации, не убитые «до», не названы находками: {unlisted}"


def test_ac4_inconclusive_outcome_neither_killed_nor_survived():
    """Мутация с исходом «итог неизвестен», «патч не применяется», «патч трогает тесты», «не прогнана» не названа находкой.

    Мутация, чья последняя строка «до» или «после» — один из этих исходов
    (или «оборвана по пределу»), убитой по разбору таблиц не считается;
    PLAN не называет её находкой (выжившей).

    Ловит мутацию: часть оборвалась по пределу, роль записала оборванную
    мутацию находкой «никто не убил» и не перепрогнала её — номер найден
    среди находок, тест краснеет.
    """
    plan = _ctx.plan_text()
    before = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    after = _plan.last_rows(_ctx.section_tables(plan, "Мутации после"))
    unclear = {n for rows in (before, after) for n, (outcome, _nodes) in rows.items()
               if outcome in _plan.INCONCLUSIVE}
    as_findings = sorted(unclear & _plan.finding_refs(plan))
    assert not as_findings, f"мутации без итога названы находками: {as_findings}"


# ------------------------------------------------------------------ AC-5

def test_ac5_killed_or_not_killed_same_before_and_after():
    """Исход «убита / не убита» каждой мутации в «до» и «после» один.

    Для каждой мутации, у которой последний исход и «до», и «после» — из
    пары «убита»/«не убита», они совпадают.

    Ловит мутацию: мутацию «до» убил тест, утверждение которого при
    переносе ослаблено, — «после» она «не убита», тест краснеет с номером;
    либо роль перепрогоняла часть «после», пока гонка не убила мутацию.
    """
    plan = _ctx.plan_text()
    before = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    after = _plan.last_rows(_ctx.section_tables(plan, "Мутации после"))
    pair = (_plan.KILLED, _plan.SURVIVED)
    differ = [f"мутация {n}: «до» {before[n][0]}, «после» {after[n][0]}"
              for n in sorted(set(before) & set(after))
              if before[n][0] in pair and after[n][0] in pair
              and before[n][0] != after[n][0]]
    assert not differ, "\n".join(differ)


def test_ac5_concurrent_acquire_mutations_killed_before_and_after_by_it():
    """Мутации `ConcurrentAcquireTest` убиты им «до» и его функцией «после».

    Каждая мутация, сопоставленная в PLAN тесту
    `ConcurrentAcquireTest::test_concurrent_acquire_on_free_lock_exactly_one_wins`,
    «до» убита с этим узлом среди убийц, «после» — с функцией
    `tests/test_merge_lock_module.py::test_concurrent_acquire_on_free_lock_exactly_one_wins`
    среди убийц; такая мутация есть.

    Ловит мутацию: заявка теста — мутация гонки `BEGIN IMMEDIATE`, которую
    восемь потоков убивают не каждый раз, — «после» убийцей тест не
    назван (или мутация «не убита»), тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    tests = _ctx.base_tests()
    key = "ConcurrentAcquireTest::test_concurrent_acquire_on_free_lock_exactly_one_wins"
    numbers = sorted(_ctx.mapping(plan, set(names)).get(key, ()))
    assert numbers, f"в PLAN нет мутации, сопоставленной {key}"
    moved = _moved(tests[key], _ctx.head_trees())
    assert moved, f"функции, в которую перенесён {key}, в файле модуля нет"
    before = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    after = _plan.last_rows(_ctx.section_tables(plan, "Мутации после"))
    problems = []
    for number in numbers:
        outcome, nodes = before.get(number, ("<нет строки>", []))
        if outcome != _plan.KILLED or key not in _before_killers(nodes):
            problems.append(f"мутация {number} «до»: {outcome} {nodes}")
        outcome, nodes = after.get(number, ("<нет строки>", []))
        if outcome != _plan.KILLED or not (_after_killers(nodes) & moved):
            problems.append(f"мутация {number} «после»: {outcome} {nodes}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-14

def test_ac14_untransferred_tests_are_listed_duplicates_meeting_both_conditions():
    """Неперенесённый исходный тест — удалённый дубль PLAN с мутациями и условиями (а), (б).

    Исходный тест, для которого в его файле модуля нет функции с его
    именем, перечислен в разделе «…дубл…» PLAN со ссылками на мутации.
    Для каждого удалённого дубля: мутаций не меньше одной; каждую по
    таблице «до» убивает и другой сохраняемый тест (а); среди сохраняемых
    убийц всех его мутаций есть тест, литералы и виды `self.assert*`
    которого (по базе ветки) покрывают литералы и виды удалённого (б).

    Ловит мутацию: при своде пропал `RunWindowTest::
    test_mutex_is_released_even_when_the_body_raises` без записи в PLAN,
    либо удалён дубль, чью мутацию «до» убивал только он, или дубль с
    литералом `"sess-holder"`, которого нет у оставленного соседа, — тест
    краснеет с именем.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    trees = _ctx.head_trees()
    removed = _plan.removed_duplicates(plan)
    proof = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    killers = {n: _before_killers(nodes) for n, nodes in proof.items()}
    problems = []
    for test in tests.values():
        if not _moved(test, trees) and test.key not in removed:
            problems.append(f"{test.key}: не перенесён и не назван удалённым дублем")
    for key, numbers in sorted(removed.items()):
        if key not in tests:
            problems.append(f"{key}: такого исходного теста в базе нет")
            continue
        if not numbers:
            problems.append(f"{key}: удалён без перечня своих мутаций")
            continue
        kept = None
        for number in sorted(numbers):
            others = killers.get(number, set()) - set(removed)
            if not others:
                problems.append(f"{key}: мутацию {number} не убивает ни один "
                                f"сохраняемый тест (а)")
            kept = others if kept is None else kept & others
        lits = _plan.assertion_literals(tests[key].func)
        kinds = _plan.assertion_kinds(tests[key].func)
        covering = [k for k in sorted(kept or ()) if k in tests
                    and lits <= _plan.assertion_literals(tests[k].func)
                    and kinds <= _plan.assertion_kinds(tests[k].func)]
        if not covering:
            problems.append(f"{key}: среди сохраняемых убийц {sorted(numbers)} нет "
                            f"теста с его литералами и видами утверждений (б)")
    assert not problems, "\n".join(problems)


def test_ac14_test_whose_mutation_nobody_killed_is_not_removed():
    """Тест, чью сопоставленную мутацию «до» не убил никто, не удалён дублем.

    Ни один тест раздела «…дубл…» PLAN не сопоставлен (в строках PLAN вне
    таблиц) мутации, последний исход «до» которой — не «убита».

    Ловит мутацию: роль удалила как дубль `HeadTaskIdTest::
    test_empty_queue_has_no_head`, чья мутация осталась «не убита»
    находкой, — тест краснеет с его именем.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    rows = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    proof = set(_plan.killed(rows))
    mapped = _ctx.mapping(plan, set(names))
    bad = [f"{key}: мутации {sorted(mapped.get(key, set()) - proof)} «до» не убиты"
           for key in sorted(_plan.removed_duplicates(plan))
           if mapped.get(key, set()) - proof]
    assert not bad, "\n".join(bad)


# ------------------------------------------------------------------ AC-15

def test_ac15_after_tables_worktree_two_module_files_same_ranges_and_workers():
    """Раздел «Мутации после»: `--ref worktree` на двух файлах модулей, те же диапазоны и `--workers`, что «до».

    Каждая таблица раздела — задача, `ревизия прогона: worktree <sha>`,
    тесты — ровно `tests/test_merge_lock_module.py` и
    `tests/test_merge_queue.py`; её набор патчей и строка «# рабочих
    процессов» совпадают с набором и строкой одной из таблиц «до»; вывод
    полон (строка на каждый патч шапки); каждый патч набора есть в
    таблицах «после».

    Ловит мутацию: «после» прогнан одним диапазоном `--patches 1-40` при
    частях «до» 1-25 и 26-40, с `--workers 4` при умолчании «до», или на
    `tests/test_merge_lock.py` — набор, строка процессов или тесты не те,
    тест краснеет.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    before = _ctx.section_tables(plan, "Мутации до")
    after = _ctx.section_tables(plan, "Мутации после")
    parts = {(frozenset(t.patches), t.workers) for t in before}
    problems = []
    for table in after:
        where = f"таблица «после» №{table.run_no}"
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != "worktree":
            problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась worktree")
        if sorted(table.tests) != sorted(_plan.MODULE_FILES):
            problems.append(f"{where}: тесты {table.tests}, ожидались "
                            f"{list(_plan.MODULE_FILES)}")
        if (frozenset(table.patches), table.workers) not in parts:
            problems.append(f"{where}: патчи {sorted(table.patches)} при рабочих "
                            f"процессах «{table.workers}» — нет такой части «до»")
        _check_table_rows(table, where, _AFTER_NODE, problems)
    absent = sorted(set(names) - set(_plan.last_rows(after)))
    if absent:
        problems.append(f"мутаций набора нет в таблицах «после»: {absent}")
    assert not problems, "\n".join(problems)


def test_ac15_empty_orchestrator_status_before_each_after_part():
    """Перед каждой частью «после» — пустой вывод `git status --porcelain -- orchestrator/`.

    В разделе «Мутации после» между концом предыдущей таблицы и шапкой
    каждой таблицы есть строка с командой `git status --porcelain --
    orchestrator/`, и после неё до шапки нет строк вывода porcelain
    (`XY <путь>`) с путём под `orchestrator/`.

    Ловит мутацию: роль привела вывод `git status` только перед первой
    частью, или перед частью стоит ` M orchestrator/merge_lock.py` —
    тест краснеет с шапкой части.
    """
    plan = _ctx.plan_text()
    texts = _plan.sections(plan, "Мутации после")
    assert texts, "в PLAN нет раздела «Мутации после»"
    command = "git status --porcelain -- orchestrator/"
    porcelain = re.compile(r"^[ MADRCUT?!]{2} \"?orchestrator/")
    problems, heads = [], 0
    for text in texts:
        lines = text.split("\n")
        boundary = 0
        for i, line in enumerate(lines):
            if not _plan.HEAD_RE.match(line):
                if _plan.ROW_RE.match(line) or line == _plan.COLUMNS:
                    boundary = i + 1
                continue
            heads += 1
            window = lines[boundary:i]
            marks = [k for k, w in enumerate(window) if command in w]
            if not marks:
                problems.append(f"перед «{line}» нет вывода «{command}»")
            elif any(porcelain.match(w.strip("`")) for w in window[marks[-1] + 1:]):
                problems.append(f"перед «{line}» вывод «{command}» не пуст")
            boundary = i + 1
    assert heads, "в разделе «Мутации после» нет таблиц mutation-run"
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-16

def test_ac16_killed_before_by_t_killed_after_by_its_function_same_assertion():
    """Мутацию, убитую «до» тестом T, «после» убивает функция T тем же утверждением.

    Для каждой мутации с последним исходом «до» «убита»: каждый её убийца
    T, не удалённый дублем, «после» представлен среди убийц функцией, в
    которую он перенесён; в PLAN есть строка со ссылкой на мутацию, с T,
    со ссылкой на его функцию и двумя файл:строка — утверждение в теле T
    (база) и утверждение в теле функции (HEAD) — с одной нормальной формой
    (`assertX(a, b)` ↔ `assert a <op> b`, `self.<помощник>` ↔ функция,
    `self.<КОНСТАНТА>` ↔ константа; для `raise AssertionError` — тот же
    текст).

    Ловит мутацию: «после» мутацию убил соседний тест, а функция T её
    пропустила, или функция T падает другим утверждением
    (`assert row["pid"] == …` вместо перенесённого `assert refusal is None`)
    — нет убийцы или формы расходятся, тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    base_trees = _ctx.base_trees()
    head_trees = _ctx.head_trees()
    removed = set(_plan.removed_duplicates(plan))
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    after = _plan.last_rows(_ctx.section_tables(plan, "Мутации после"))
    lines = _plan.prose_lines(plan)
    prep = _after_prep()
    problems = []
    for number, nodes in sorted(before.items()):
        outcome, after_nodes = after.get(number, ("<нет строки>", []))
        after_killers = _after_killers(after_nodes) if outcome == _plan.KILLED else set()
        kept = [tests[k] for k in sorted(_before_killers(nodes))
                if k in tests and k not in removed]
        for test in kept:
            if not (_moved(test, head_trees) & after_killers):
                problems.append(f"мутация {number}: «до» убил {test.key}, «после» "
                                f"его функция не среди убийц ({outcome} {after_nodes})")
        if not any(_same_assertion_line(line, number, test, base_trees, head_trees,
                                        after_killers, prep)
                   for line in lines for test in kept):
            problems.append(f"мутация {number}: нет строки PLAN с T, его "
                            f"функцией и строками падения одной нормальной формы")
    assert not problems, "\n".join(problems)


def _same_assertion_line(line, number, test, base_trees, head_trees, after_killers,
                         prep) -> bool:
    if number not in _plan.refs(line) or test.key not in _plan.test_keys(line):
        return False
    funcs = _plan.after_refs(line) & after_killers & _moved(test, head_trees)
    if not funcs:
        return False
    base_tree = base_trees[test.path]
    sites = _plan.file_lines(line)
    before_forms = []
    for path, n in sites:
        if path == test.path and _plan.site_ok(base_tree, n, test.name, _BEFORE_PREP):
            node = _plan.assertion_at(base_tree, n)
            before_forms.append(_plan.normal_form(
                node, _plan.canon_for(base_tree, test.func, test.cls)))
    for fpath, fname in funcs:
        tree = head_trees[fpath]
        func = _plan.module_functions(tree)[fname]
        for path, n in sites:
            if path == fpath and _plan.site_ok(tree, n, fname, prep):
                node = _plan.assertion_at(tree, n)
                renames = _plan.helper_renames(tree, fpath)
                if _plan.normal_form(node, _plan.canon_for(tree, func, None, renames)) \
                        in before_forms:
                    return True
    return False


def test_ac16_same_orchestrator_tree_across_all_header_revisions():
    """Дерево `orchestrator/` у ревизий всех шапок «до» и «после» одно.

    Для каждой пары различных ревизий из шапок таблиц обоих разделов
    `git diff --quiet <sha> <sha> -- orchestrator/` в рабочей копии
    завершается кодом 0.

    Ловит мутацию: «после» прогнан на ревизии с правкой `orchestrator/` (или
    «до» не повторён после подтяжки main с правкой `orchestrator/`) —
    `git diff` даёт код 1, тест краснеет с парой ревизий.
    """
    plan = _ctx.plan_text()
    shas = sorted({t.sha for t in _ctx.section_tables(plan, "Мутации до")}
                  | {t.sha for t in _ctx.section_tables(plan, "Мутации после")})
    problems = []
    for i, left in enumerate(shas):
        for right in shas[i + 1:]:
            res = _plan.git(CODE_ROOT, "diff", "--quiet", left, right, "--",
                            "orchestrator/")
            if res.returncode != 0:
                problems.append(f"git diff --quiet {left} {right} -- orchestrator/ "
                                f"— код {res.returncode} {res.stderr.strip()}")
    assert not problems, "\n".join(problems)


def test_ac16_patch_sha256_same_in_before_and_after_headers():
    """sha256 каждого патча в шапке «до» совпадает с его sha256 в шапке «после».

    Ловит мутацию: роль переписала патч между прогонами «до» и «после» и не
    повторила «до» — sha256 номера в шапках расходится, тест краснеет с
    номером и обоими значениями.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    b_shas = _plan.last_patch_sha(_ctx.section_tables(plan, "Мутации до"))
    a_shas = _plan.last_patch_sha(_ctx.section_tables(plan, "Мутации после"))
    assert set(names) <= set(b_shas), (
        f"патчи без строки «# патч» в шапках «до»: {sorted(set(names) - set(b_shas))}")
    problems = [f"патч {n}: sha256 «до» {b_shas[n]} ≠ «после» {a_shas.get(n)}"
                for n in sorted(b_shas) if a_shas.get(n) != b_shas[n]]
    assert not problems, "\n".join(problems)


def test_ac16_plan_names_test_count_lines_and_time_before_and_after():
    """PLAN называет число тестов, строк и время до и после свода.

    «До» — по базе ветки: 40 тестов трёх исходных файлов и их строки (сумма
    или число каждого файла); «после» — по HEAD: число функций-тестов двух
    файлов модулей (сумма или каждого) и их строки. Каждое число стоит в
    PLAN отдельным числом; длительностей (`<n> с`/`мин`) не меньше двух.

    Ловит мутацию: роль записала числа только «до» (или время только одного
    контрольного прогона) — числа «после» или второй длительности нет,
    тест краснеет с ним.
    """
    plan = _ctx.plan_text()

    def named(number: int) -> bool:
        return re.search(rf"(?<![\d.,]){number}(?![\d])", plan) is not None

    def named_total_or_each(values: list) -> bool:
        return named(sum(values)) or all(named(v) for v in values)

    base = _ctx.base_texts()
    base_tests = [len(_plan.base_tests(p, t)) for p, t in base.items()]
    base_lines = [t.count("\n") for t in base.values()]
    head = {p: _ctx.head_text(p) for p in _plan.MODULE_FILES}
    head_tests = [len(_plan.module_tests(ast.parse(t))) for t in head.values()]
    head_lines = [t.count("\n") for t in head.values()]
    problems = []
    if not named_total_or_each(base_tests):
        problems.append(f"число тестов «до» {base_tests} в PLAN не названо")
    if not named_total_or_each(base_lines):
        problems.append(f"число строк «до» {base_lines} в PLAN не названо")
    if not named_total_or_each(head_tests):
        problems.append(f"число тестов «после» {head_tests} в PLAN не названо")
    if not named_total_or_each(head_lines):
        problems.append(f"число строк «после» {head_lines} в PLAN не названо")
    if len(_DURATION.findall(plan)) < 2:
        problems.append("в PLAN нет двух длительностей контрольных прогонов — "
                        "до и после")
    assert not problems, "\n".join(problems)
