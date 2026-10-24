"""AC-2, AC-3, AC-4, AC-5, AC-14 (дубли), AC-15, AC-16: таблицы
`mutation-run` «до» и «после» в PLAN и их согласованность с набором
патчей, строками падения, находками, удалёнными дублями, переносом тестов
и рабочей копией; фразы о зерне; числа тестов, строк и время до и после.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после», патчей и нового файла модуля ещё нет — прогонов mutation-run и свода не было, загрузчики _ctx бросают LookupError.

Планка сверяет форму и согласованность таблиц; подлинность таблиц,
исход повтора и независимость убийства от зерна по существу — работа
независимой проверки (требование 19 SPEC). Соглашения разбора PLAN —
докстринг `_plan.py`. «Функция, в которую перенесён тест» — функция-тест
его файла модуля с его именем (`_plan.moved_to`).
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
_SEED = re.compile(r"зерн", re.IGNORECASE)


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


class _Sites:
    """Проверка строк падения «до» (база) и «после» (HEAD): утверждение в
    теле убийцы (или в помощнике проверки `assert_fresh`, который он
    зовёт), не в `setUp`, фикстуре, помощнике подготовки и не утверждение
    подготовки (AC-4)."""

    def __init__(self):
        self.tests = _ctx.base_tests()
        self.base_trees = _ctx.base_trees()
        self.head_trees = _ctx.head_trees()
        self.prep_nodes = _plan.prep_line_nodes(self.base_trees)
        self.head_funcs = {p: _plan.module_functions(t) for p, t in self.head_trees.items()}

    def _prep_forms(self, test, canon) -> set:
        """Формы утверждений подготовки в теле исходного теста (по строкам
        `_plan.PREP_LINES`)."""
        lines = {n.lineno for n in self.prep_nodes.get(test.path, [])}
        return {_plan.normal_form(n, canon) for n in _plan.self_assertions(test.func)
                if n.lineno in lines}

    def before_ok(self, test, path: str, line: int) -> bool:
        if path != test.path:
            return False
        tree = self.base_trees[path]
        node = _plan.assertion_at(tree, line)
        if node is None or node.lineno in {p.lineno for p in self.prep_nodes.get(path, [])}:
            return False
        return _plan.site_ok(tree, line, test.func, ("setUp", *_plan.PREP_HELPERS))

    def after_ok(self, path: str, func_name: str, line: int, test=None) -> bool:
        tree = self.head_trees.get(path)
        func = self.head_funcs.get(path, {}).get(func_name)
        if tree is None or func is None:
            return False
        forms = set()
        canon = None
        if test is not None:
            base_c = _plan.base_canon(self.base_trees[test.path], test.path, test.cls)
            canon = _plan.new_canon(func, test.func, base_c)
            forms = self._prep_forms(test, base_c)
        return _plan.site_ok(tree, line, func, _plan.PREP_HELPERS, forms, canon)

    def origin_of(self, path: str, func_name: str):
        """Исходный тест, перенесённый в функцию; нет — None."""
        for test in self.tests.values():
            if test.target == path and func_name in {
                    f.name for f in _plan.moved_to(test.name,
                                                   _plan.module_tests(self.head_trees[path]))}:
                return test
        return None


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_five_wave_files_parts_and_every_patch():
    """Раздел «Мутации до»: таблицы `--ref base` на пяти файлах волны, части по ≤25 патчей, все патчи в них.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно пять файлов волны, строки
    «# патч … sha256 …», не больше 25 патчей; у каждой строки «# патч»
    шапки есть строка вывода, у каждой строки вывода — строка шапки; исход
    — из словаря команды; у «убита» узлы непусты и имеют вид
    `tests/<файл>::<Класс>::<метод>`. Каждый номер набора есть в таблицах.

    Ловит мутацию: роль перенесла только последнюю часть деления
    `--patches`, прогнала часть из 30 патчей, прогнала «до» с `--ref
    worktree` или без `tests/test_merge_after_declared.py` в `--tests`, или
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
    """Часть с патчем пути взятия окна или цикла `wait_for_window` — не больше 8 патчей, «до» и «после».

    Патч окна — патч, меняющий строки функций `merge_lock.acquire`,
    `_holder_is_dead`, `_is_own_process`, `run_window`,
    `merge_queue.wait_for_window`, `_head_task_id`, `_prune_dead_entries`,
    функций строк мьютекса и очереди `store` (`project_merge_lock_row`,
    `set_merge_lock`, `merge_queue_rows`, `project_merge_queue_rows`,
    `delete_merge_queue_row`, `task_target`) или проверки живости
    `liveness._age_seconds`/`_pid_alive` (строки старой стороны хунков по
    тексту модуля базы ветки). Таблица «до» или «после», в шапке которой
    есть такой патч, несёт не больше 8 патчей.

    Ловит мутацию: роль прогнала мутацию «голова очереди — первая запись
    всего пульта» (`_head_task_id`) вместе с 20 другими одной частью
    `--patches 1-21` — у части с патчем окна 21 патч, тест краснеет с
    номером таблицы.
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
    убийц «до» и ссылкой `tests/<файл волны>.py:<строка>`; для убитой
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
                            f"{sorted(killers)} и файл:строка файла волны")
    for number, nodes in sorted(after.items()):
        killers = _after_killers(nodes)
        if not any(number in _plan.refs(line) and _plan.after_refs(line) & killers
                   and any(p in _plan.MODULE_FILES for p, _n in _plan.file_lines(line))
                   for line in lines):
            problems.append(f"мутация {number} «после»: нет строки с убийцей из "
                            f"{sorted(killers)} и файл:строка файла модуля")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-4

def test_ac4_proof_kill_is_assertion_failure_outside_preparation():
    """Убитая мутация засчитана утверждением теста, а не сбором, исключением или подготовкой.

    Для каждой мутации с последним исходом «убита» есть строка PLAN со
    ссылкой на мутацию и убийцей, чья ссылка файл:строка лежит внутри
    утверждения в теле самого убийцы (или в `assert_fresh`, который он
    зовёт) — не в `setUp`, фикстуре, помощнике подготовки (`divide`,
    `declared_task`, `wait_texts`) и не утверждение подготовки (division
    :114, :119, :122; spec_gate_hint :175, :213; mutex_by_project :597,
    :326; declared :87 — «после» их перенесённые двойники той же формы):
    «до» — по базе ветки, «после» — по HEAD.

    Ловит мутацию: мутация «убита» только предпосылкой `test_ac5`
    (`assertIsNone(merge_lock.acquire(…))` :326) или `assertEqual("killed",
    …)` в `divide`, и роль привела эту строку — она подготовка, тест
    краснеет с номером.
    """
    plan = _ctx.plan_text()
    sites = _Sites()
    tests = sites.tests
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    after = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации после")))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        killers = _before_killers(nodes) & set(tests)
        ok = any(number in _plan.refs(line) and any(
            sites.before_ok(tests[key], path, n)
            for key in _plan.test_keys(line) & killers
            for path, n in _plan.file_lines(line))
            for line in lines)
        if not ok:
            problems.append(f"мутация {number} «до»: нет строки падения в "
                            f"утверждении убийцы из {sorted(killers)}")
    for number, nodes in sorted(after.items()):
        killers = _after_killers(nodes)
        ok = any(number in _plan.refs(line) and any(
            fpath == path and sites.after_ok(path, func, n, sites.origin_of(path, func))
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

    Ловит мутацию: мутацию «до» убил тест на удачном зерне (ветка
    «поле SPEC есть» `test_ac8`), а «после» зерно другое — «не убита»,
    тест краснеет с номером; либо утверждение ослаблено при переносе.
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


def test_ac5_each_mutation_of_seeded_tests_has_seed_phrase():
    """У каждой мутации тестов mutex_by_project, division, spec_gate_hint и тестов с ULID из `idgen` в PLAN есть фраза о зерне.

    Для мутации, сопоставленной в PLAN такому тесту или убитой им «до»,
    есть строка PLAN вне таблиц со ссылкой на мутацию и словом «зерн…»
    (почему её убийство не зависит от зерна). Тест с ULID — тот, чьё тело
    обращается к `idgen` или зовёт `self.insert(<состояние>)` без явного id.

    Ловит мутацию: роль объяснила зерно для мутаций mutex_by_project, а
    мутации `CheckTest::test_done_dependency_is_valid` (ULID из
    `merge_after_db_insert`) оставила без фразы — номер перечислен, тест
    краснеет.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    tests = _ctx.base_tests()
    seeded = {k for k, t in tests.items() if _plan.seeded_test(t)}
    mapped = _ctx.mapping(plan, set(names))
    numbers = set()
    for key in seeded:
        numbers |= mapped.get(key, set())
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    numbers |= {n for n, nodes in before.items() if _before_killers(nodes) & seeded}
    lines = [line for line in _plan.prose_lines(plan) if _SEED.search(line)]
    missing = sorted(n for n in numbers if not any(n in _plan.refs(line) for line in lines))
    assert numbers, "мутаций тестов со случайными входами в PLAN нет"
    assert not missing, f"мутации без фразы о зерне: {missing}"


def test_ac5_no_seed_fixed_in_module_files():
    """Зерно ни в одном тесте трёх файлов модулей не зафиксировано.

    В файлах модулей нет `random.seed(…)`, `random.Random(<литерал>)` и
    присваивания литерала имени или атрибуту `seed`.

    Ловит мутацию: стенд `project_mutex_stand` получил `seed = 12345`
    (или `random.Random(0)`) ради стабильного убийства — узел найден, тест
    краснеет со строкой.
    """
    found = []
    for path, tree in _ctx.head_trees().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = ast.unparse(node.func)
                if func == "random.seed" or (
                        func in ("random.Random", "Random") and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    found.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    name = target.id if isinstance(target, ast.Name) else \
                        target.attr if isinstance(target, ast.Attribute) else ""
                    if name == "seed":
                        found.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
    assert not found, "зерно зафиксировано:\n" + "\n".join(found)


# ------------------------------------------------------------------ AC-14

def test_ac14_untransferred_tests_are_listed_duplicates_meeting_conditions():
    """Неперенесённый исходный тест — удалённый дубль PLAN с мутациями и условиями (а), (б), (в).

    Исходный тест, для которого в его файле модуля нет функции с его
    именем, перечислен в разделе «…дубл…» PLAN со ссылками на мутации.
    Для каждого удалённого дубля: мутаций не меньше одной; каждую по
    таблице «до» убивает и другой сохраняемый тест того же прежнего файла
    (а); среди этих убийц есть тест, литералы и виды `self.assert*`
    которого покрывают литералы и виды удалённого (б). Ни одна мутация,
    убитая «до», не убита только удалёнными тестами (в).

    Ловит мутацию: при своде пропал `CheckTest::test_done_dependency_is_
    valid` без записи в PLAN, либо удалён дубль, чью мутацию «до» убивал
    кроме него только тест другого файла волны, — тест краснеет с именем.
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
        path = tests[key].path
        kept = None
        for number in sorted(numbers):
            others = {k for k in killers.get(number, set()) - set(removed)
                      if k in tests and tests[k].path == path}
            if not others:
                problems.append(f"{key}: мутацию {number} не убивает ни один "
                                f"сохраняемый тест того же файла (а)")
            kept = others if kept is None else kept & others
        lits = _plan.assertion_literals(tests[key].func)
        kinds = _plan.assertion_kinds(tests[key].func)
        covering = [k for k in sorted(kept or ())
                    if lits <= _plan.assertion_literals(tests[k].func)
                    and kinds <= _plan.assertion_kinds(tests[k].func)]
        if not covering:
            problems.append(f"{key}: среди сохраняемых убийц {sorted(numbers)} нет "
                            f"теста с его литералами и видами утверждений (б)")
    for number, who in sorted(killers.items()):
        if who and not (who - set(removed)):
            problems.append(f"мутацию {number} убивают только удалённые {sorted(who)} (в)")
    assert not problems, "\n".join(problems)


def test_ac14_test_whose_mutation_nobody_killed_or_claimed_here_is_not_removed():
    """Тест, чью сопоставленную мутацию «до» не убил никто, и тест без заявки в базе не удалены дублем.

    Ни один тест раздела «…дубл…» PLAN не сопоставлен (в строках PLAN вне
    таблиц) мутации, последний исход «до» которой — не «убита», и у
    каждого удалённого в базе была заявка «Ловит мутацию» (тест,
    получивший заявку в этой задаче, не удаляется).

    Ловит мутацию: роль удалила как дубль `MandateLineTest::
    test_none_word_mixed_with_ids_refused`, чья мутация осталась «не
    убита» находкой, — тест краснеет с его именем.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    tests = _ctx.base_tests()
    rows = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    proof = set(_plan.killed(rows))
    mapped = _ctx.mapping(plan, set(names))
    bad = [f"{key}: мутации {sorted(mapped.get(key, set()) - proof)} «до» не убиты"
           for key in sorted(_plan.removed_duplicates(plan))
           if mapped.get(key, set()) - proof]
    bad += [f"{key}: заявка получена в этой задаче — удалять нельзя"
            for key in sorted(_plan.removed_duplicates(plan))
            if key in tests and not tests[key].claim]
    assert not bad, "\n".join(bad)


# ------------------------------------------------------------------ AC-15

def test_ac15_after_tables_worktree_three_module_files_same_ranges_and_workers():
    """Раздел «Мутации после»: `--ref worktree` на трёх файлах модулей, те же диапазоны и `--workers`, что «до».

    Каждая таблица раздела — задача, `ревизия прогона: worktree <sha>`,
    тесты — ровно три файла модулей; её набор патчей и строка «# рабочих
    процессов» совпадают с набором и строкой одной из таблиц «до»; вывод
    полон (строка на каждый патч шапки); каждый патч набора есть в
    таблицах «после».

    Ловит мутацию: «после» прогнан одним диапазоном `--patches 1-40` при
    частях «до» 1-25 и 26-40, с `--workers 4` при умолчании «до», или без
    `tests/test_merge_after_module.py` — набор, строка процессов или тесты
    не те, тест краснеет.
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
    частью, или перед частью стоит ` M orchestrator/merge_after.py` —
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

def _same_assertion_line(line, number, test, sites, after_killers) -> bool:
    if number not in _plan.refs(line) or test.key not in _plan.test_keys(line):
        return False
    funcs = _plan.after_refs(line) & after_killers & _moved(test, sites.head_trees)
    if not funcs:
        return False
    base_tree = sites.base_trees[test.path]
    base_c = _plan.base_canon(base_tree, test.path, test.cls)
    places = _plan.file_lines(line)
    before_forms = []
    for path, n in places:
        if sites.before_ok(test, path, n):
            before_forms.append(_plan.normal_form(_plan.assertion_at(base_tree, n), base_c))
    for fpath, fname in funcs:
        tree = sites.head_trees[fpath]
        func = sites.head_funcs[fpath][fname]
        canon = _plan.new_canon(func, test.func, base_c)
        for path, n in places:
            if path == fpath and sites.after_ok(path, fname, n, test):
                node = _plan.assertion_at(tree, n)
                site_func = _plan.function_chain(tree, n)[0]
                site_canon = canon if site_func is func else \
                    _plan.Canon({a.arg for a in site_func.args.args}, {})
                if _plan.normal_form(node, site_canon) in before_forms:
                    return True
    return False


def test_ac16_killed_before_by_t_killed_after_by_its_function_same_assertion():
    """Мутацию, убитую «до» тестом T, «после» убивает функция T тем же утверждением.

    Для каждой мутации с последним исходом «до» «убита»: каждый её убийца
    T, не удалённый дублем, «после» представлен среди убийц функцией, в
    которую он перенесён; в PLAN есть строка со ссылкой на мутацию, с T,
    со ссылкой на его функцию и двумя файл:строка — утверждение T (база)
    и утверждение функции (HEAD) — одной формы по соответствию требования
    12 (`assertX(a, b)` ↔ `assert a <op> b`, `self.<помощник>` ↔ функция,
    `self` ↔ стенд; ожидания и литералы дословно).

    Ловит мутацию: «после» мутацию убил соседний тест, а функция T её
    пропустила, или функция T падает другим утверждением (`assert
    sleeps == []` вместо перенесённого `assert exited is None`) — нет
    убийцы или формы расходятся, тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    sites = _Sites()
    removed = set(_plan.removed_duplicates(plan))
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    after = _plan.last_rows(_ctx.section_tables(plan, "Мутации после"))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        outcome, after_nodes = after.get(number, ("<нет строки>", []))
        after_killers = _after_killers(after_nodes) if outcome == _plan.KILLED else set()
        kept = [sites.tests[k] for k in sorted(_before_killers(nodes))
                if k in sites.tests and k not in removed]
        for test in kept:
            if not (_moved(test, sites.head_trees) & after_killers):
                problems.append(f"мутация {number}: «до» убил {test.key}, «после» "
                                f"его функция не среди убийц ({outcome} {after_nodes})")
        if not any(_same_assertion_line(line, number, test, sites, after_killers)
                   for line in lines for test in kept):
            problems.append(f"мутация {number}: нет строки PLAN с T, его "
                            f"функцией и строками падения одной формы")
    assert not problems, "\n".join(problems)


def test_ac16_same_orchestrator_tree_across_all_header_revisions():
    """Дерево `orchestrator/` у ревизий всех шапок «до» и «после» одно.

    Для каждой пары различных ревизий из шапок таблиц обоих разделов
    `git diff --quiet <sha> <sha> -- orchestrator/` в рабочей копии
    завершается кодом 0.

    Ловит мутацию: «после» прогнан на ревизии с правкой `orchestrator/` (или
    «до» не повторён после подтяжки main с мержем 01M5QR7KGY) — `git diff`
    даёт код 1, тест краснеет с парой ревизий.
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
    """PLAN называет число тестов (замок, очередь, merge_after), строк и время до и после свода.

    «До» — по базе ветки: 37 тестов пяти файлов волны и их строки (сумма
    или число каждого файла); «после» — по HEAD: число функций-тестов
    каждого из трёх файлов модулей и их строки (сумма или каждого). Числа
    стоят в PLAN отдельными числами (разряды могут делиться пробелом);
    длительностей (`<n> с`/`мин`) не меньше двух.

    Ловит мутацию: роль записала числа только «до» (или число тестов
    «после» одной суммой без разбивки по замку, очереди и merge_after,
    или время только одного контрольного прогона) — числа или второй
    длительности нет, тест краснеет с ним.
    """
    plan = _ctx.plan_text()

    def named_total_or_each(values: list) -> bool:
        return _plan.number_named(plan, sum(values)) or \
            all(_plan.number_named(plan, v) for v in values)

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
    missing = [v for v in head_tests if not _plan.number_named(plan, v)]
    if missing:
        problems.append(f"число тестов «после» по файлам {head_tests} в PLAN не "
                        f"названо: {missing}")
    if not named_total_or_each(head_lines):
        problems.append(f"число строк «после» {head_lines} в PLAN не названо")
    if len(_DURATION.findall(plan)) < 2:
        problems.append("в PLAN нет двух длительностей контрольных прогонов — "
                        "до и после")
    assert not problems, "\n".join(problems)
