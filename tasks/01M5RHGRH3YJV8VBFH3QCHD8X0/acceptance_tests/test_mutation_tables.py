"""AC-2, AC-3, AC-4, AC-5, AC-13 (дубли), AC-14, AC-15: таблицы
`mutation-run` «до» и «после» в PLAN и их согласованность с набором
патчей, строками падения, утверждениями подготовки, находками, удалёнными
дублями и переносом тестов; фразы о зерне; деревья ревизий, суммы патчей,
числа тестов, строк и время до и после.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после» и патчей ещё нет, тесты шести файлов не дописаны в модуль — прогонов mutation-run и свода не было, загрузчики _ctx бросают LookupError.

Планка сверяет форму и согласованность таблиц; подлинность таблиц,
исход повтора, отсутствие `Timeout` в логах и независимость убийства от
зерна по существу — работа независимой проверки (требование 17 SPEC).
Соглашения разбора PLAN — докстринг `_plan.py`. «Функция, в которую
перенесён тест» — функция-тест модуля с его именем (`_plan.moved_to`).
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
_AFTER_NODE = re.compile(r"^" + re.escape(_plan.MODULE) + r"::test\w*(?:\[.*\])?$")
_DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|секунд[а-я]*|s|мин|min)"
                       r"(?![A-Za-zА-Яа-яЁё])")
_SEED = re.compile(r"зерн", re.IGNORECASE)
_PARTIAL_SEED = re.compile(r"част[а-яё]*\s+з[её]рен", re.IGNORECASE)


def _before_killers(nodes) -> set:
    return {_plan.node_key(n) for n in nodes}


def _after_killers(nodes) -> set:
    return {_plan.after_node(n) for n in nodes}


def _moved(test, tree) -> set:
    """{(файл модуля, функция)} функций, в которые перенесён исходный тест."""
    return {(_plan.MODULE, f.name) for f in _plan.moved_to(test.name,
                                                           _plan.module_tests(tree))}


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


def _loop_patches(names: dict) -> set:
    """Номера патчей, меняющих строки узлов, способных зациклиться
    (`_plan.LOOP_NODES`; строки старой стороны по тексту базы ветки)."""
    found = set()
    for number, name in names.items():
        for path, lines in _plan.patch_old_lines(_ctx.patch_text(name)).items():
            wanted = _plan.LOOP_NODES.get(path)
            if not wanted:
                continue
            text = _ctx.base_text(path)
            if any(_plan.enclosing_names(text, n) & set(wanted) for n in lines):
                found.add(number)
    return found


class _Sites:
    """Проверка строк падения «до» (база) и «после» (HEAD): утверждение
    результата в теле убийцы либо в помощнике с утверждениями результата,
    который тело зовёт действием (не вызовом-подготовкой); не в `setUp`,
    фикстуре, помощнике подготовки или наблюдения и не утверждение
    подготовки, предпосылки или до действия теста (AC-4)."""

    def __init__(self):
        self.tests = _ctx.base_tests()
        self.base_trees = _ctx.base_trees()
        self.head = _ctx.head_tree()
        self.head_funcs = _plan.module_functions(self.head)

    # --- «до»

    def _base_prep_nodes(self, path: str) -> list:
        tree = self.base_trees[path]
        nodes = []
        for line in _plan.PREP_ASSERT_LINES.get(path, ()):
            node = _plan.assertion_at(tree, line)
            if node is None:
                raise LookupError(f"{path}:{line} в базе — не утверждение; база "
                                  f"прочитана не та")
            nodes.append(node)
        return nodes

    def _result_helper_of(self, path: str, line: int):
        """Метод-помощник результата файла `path`, в чьём утверждении стоит
        строка; нет — None."""
        tree = self.base_trees[path]
        for owner, method in sorted(_plan.RESULT_HELPERS):
            if owner != path:
                continue
            for cls in _plan.class_nodes(tree):
                node = _plan.class_method(tree, cls.name, method)
                if node is not None and _plan.covers(node, line):
                    return method
        return None

    def before_ok(self, test, places: list) -> bool:
        """Среди ссылок строки PLAN есть упавшее утверждение результата для
        убийцы `test` (и, у помощника, строка вызова-действия в теле теста)."""
        tree = self.base_trees[test.path]
        prep = {n.lineno for n in self._base_prep_nodes(test.path)}
        own = [n for p, n in places if p == test.path]
        for line in own:
            node = _plan.assertion_at(tree, line)
            if node is None or node.lineno in prep:
                continue
            if _plan.covers(test.func, line):
                return True
            method = self._result_helper_of(test.path, line)
            if method is None:
                continue
            prep_calls = set(_plan.PREP_CALL_LINES.get(test.path, ()))
            for call in _plan.calls_in_order(test.func, method, via_self=True):
                if any(_plan.covers(call, c) for c in own) and \
                        not any(_plan.covers(call, p) for p in prep_calls):
                    return True
        return False

    # --- «после»

    def _prep_forms(self, test, canon) -> set:
        lines = {n.lineno for n in self._base_prep_nodes(test.path)}
        return {_plan.normal_form(n, canon) for n in _plan.self_assertions(test.func)
                if n.lineno in lines}

    def _action_calls(self, test, func, helper: str, method: str) -> list:
        """Вызовы помощника `helper` в функции модуля, соответствующие
        вызовам-действиям `self.<method>` исходного теста (по порядку)."""
        base_calls = _plan.calls_in_order(test.func, method, via_self=True)
        new_calls = _plan.calls_in_order(func, helper, via_self=False)
        prep = set(_plan.PREP_CALL_LINES.get(test.path, ()))
        if len(base_calls) != len(new_calls):
            return []
        return [new for old, new in zip(base_calls, new_calls)
                if not any(_plan.covers(old, p) for p in prep)]

    def after_ok(self, func_name: str, places: list, test) -> bool:
        func = self.head_funcs.get(func_name)
        if func is None or test is None:
            return False
        base_c = _plan.base_canon(self.base_trees[test.path], test.path)
        canon = _plan.new_canon(func, test.func, base_c)
        prep_forms = self._prep_forms(test, base_c)
        own = [n for p, n in places if p == _plan.MODULE]
        helpers = {f"{_plan.PREFIX[p]}_{m}": m for p, m in _plan.RESULT_HELPERS
                   if p == test.path}
        for line in own:
            node = _plan.assertion_at(self.head, line)
            if node is None:
                continue
            chain = _plan.function_chain(self.head, line)
            if not chain or any(_plan.is_fixture(f) for f in chain):
                continue
            outer = chain[0]
            if outer is func:
                if _plan.normal_form(node, canon) in prep_forms:
                    continue
                return True
            if outer.name in helpers:
                for call in self._action_calls(test, func, outer.name,
                                               helpers[outer.name]):
                    if any(_plan.covers(call, c) for c in own):
                        return True
        return False

    def origin_of(self, func_name: str):
        """Исходный тест, перенесённый в функцию; нет — None."""
        for test in self.tests.values():
            if test.name == func_name:
                return test
        return None


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_six_wave_files_parts_and_every_patch():
    """Раздел «Мутации до»: таблицы `--ref base` на шести файлах волны, части по ≤25 патчей, все патчи в них.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно шесть файлов волны, строки
    «# патч … sha256 …», не больше 25 патчей; у каждой строки «# патч»
    шапки есть строка вывода, у каждой строки вывода — строка шапки; исход
    — из словаря команды; у «убита» узлы непусты и имеют вид
    `tests/<файл>::<Класс>::<метод>`. Каждый номер набора есть в таблицах.

    Отсутствие `Timeout` у засчитанного патча таблица не показывает: его
    держит строка падения в утверждении (AC-4, `test_ac4_…`) и независимая
    проверка по логам.

    Ловит мутацию: роль перенесла только последнюю часть деления
    `--patches`, прогнала часть из 30 патчей, прогнала «до» с `--ref
    worktree` или без `…new_declares_merge_after.py` в `--tests`, или
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


def test_ac2_patch_that_can_loop_shared_node_is_alone_in_its_part():
    """Патч, способный зациклить общий узел, — один в своей части, «до» и «после».

    Такой патч меняет строки `merge_after.check`, `_cycle_path`,
    `declared_from_tz`, `_mandate_items`, разбора строки «Порядок:»
    (`ORDER_LINE`, `_ORDER_LINE_RE`, `_ORDER_LIST_END`), разбора перечня
    `guard.merge_after_items` или поиска однозначного префикса
    `store.task_id_matches`/`resolve_task_id` (строки старой стороны хунков
    по тексту базы ветки). Таблица «до» или «после», в шапке которой есть
    такой патч, несёт ровно один патч.

    Ловит мутацию: роль прогнала мутацию «снять `seen.add` в
    `_cycle_path`» вместе с 20 другими одной частью `--patches 1-21` — у
    части с патчем общего узла 21 патч, тест краснеет с номером таблицы.
    """
    plan = _ctx.plan_text()
    loop = _loop_patches(_ctx.patch_names())
    problems = []
    for title in ("Мутации до", "Мутации после"):
        for table in _ctx.section_tables(plan, title):
            hit = sorted(set(table.patches) & loop)
            if hit and len(table.patches) > 1:
                problems.append(f"«{title}» таблица №{table.run_no}: патчей "
                                f"{len(table.patches)} при патчах общего узла {hit}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-3

def test_ac3_each_killed_mutation_names_failing_line_and_call_line_before_and_after():
    """У каждой убитой мутации PLAN называет строку падения «до» и «после»: утверждение и строку вызова в теле теста.

    Для мутации с последним исходом «до» «убита» есть строка PLAN вне
    таблиц со ссылкой на мутацию, ключом `<Класс>::<метод>` одного из её
    убийц «до» и ссылкой `tests/<файл волны>.py:<строка>`, причём одна из
    ссылок этого файла лежит внутри тела убийцы (строка вызова в теле
    теста). Для убитой «после» — строка со ссылкой на мутацию, ссылкой на
    функцию-убийцу и `tests/test_merge_after_module.py:<строка>` внутри
    тела этой функции.

    Ловит мутацию: роль привела строку падения только для таблицы «до» (или
    только строку утверждения в помощнике `answer_accepted` без строки
    вызова в теле теста, или только имя убившего теста без файл:строка) —
    у мутации нет такой строки, тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    head_funcs = _plan.module_functions(_ctx.head_tree())
    before = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    after = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации после")))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        killers = _before_killers(nodes) & set(tests)
        ok = any(number in _plan.refs(line) and any(
            any(p == tests[k].path and _plan.covers(tests[k].func, n)
                for p, n in _plan.file_lines(line))
            for k in _plan.test_keys(line) & killers) for line in lines)
        if not ok:
            problems.append(f"мутация {number} «до»: нет строки с убийцей из "
                            f"{sorted(killers)} и файл:строка в его теле")
    for number, nodes in sorted(after.items()):
        killers = _after_killers(nodes)
        ok = any(number in _plan.refs(line) and any(
            fname in head_funcs and any(
                p == _plan.MODULE and _plan.covers(head_funcs[fname], n)
                for p, n in _plan.file_lines(line))
            for _f, fname in _plan.after_refs(line) & killers) for line in lines)
        if not ok:
            problems.append(f"мутация {number} «после»: нет строки с убийцей из "
                            f"{sorted(killers)} и файл:строка в теле функции")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-4

def test_ac4_proof_kill_is_result_assertion_outside_preparation():
    """Убитая мутация засчитана утверждением результата, а не сбором, исключением, подготовкой, наблюдением или предпосылкой.

    Для каждой мутации с последним исходом «убита» есть строка PLAN со
    ссылкой на мутацию и убийцей, чья ссылка файл:строка — утверждение в
    теле убийцы либо в помощнике результата (`accepted`/`assert_refused`
    `answer`, `assert_refused` `spec_gate`, `declared`/
    `assert_refused_without_traces` `new_declares`), вызванном из тела
    действием, а не подготовкой (`accepted` :198, :233, :242, :261,
    `declared` :419). Не засчитываются: `approve_spec` :160 `plan`,
    `with_dependencies` :104, :108 и `status_line` :116 `status_show`,
    `status_line` :180 `new_declares`, предпосылки :160 `guard`, :276 и
    :305 `spec_gate`, `setUp`, фикстура, метод `git` песочницы (файл
    `tests/sandbox.py`). «До» — по базе ветки, «после» — по HEAD с теми же
    правилами для перенесённых двойников.

    Ловит мутацию: мутация «убита» только предпосылкой `test_ac4`
    (`assertEqual(self.deps(task_id), [dep])` :305) или утверждением
    `accepted` в вызове-подготовке :198, и роль привела эту строку — тест
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
            sites.before_ok(tests[key], _plan.file_lines(line))
            for key in _plan.test_keys(line) & killers)
            for line in lines)
        if not ok:
            problems.append(f"мутация {number} «до»: нет строки падения в "
                            f"утверждении результата убийцы из {sorted(killers)}")
    for number, nodes in sorted(after.items()):
        killers = _after_killers(nodes)
        ok = any(number in _plan.refs(line) and any(
            sites.after_ok(func, _plan.file_lines(line), sites.origin_of(func))
            for _f, func in _plan.after_refs(line) & killers)
            for line in lines)
        if not ok:
            problems.append(f"мутация {number} «после»: нет строки падения в "
                            f"утверждении результата убийцы из {sorted(killers)}")
    assert not problems, "\n".join(problems)


def _prep_places(base_trees) -> list:
    """[(файл, строка, ожидаемая функция модуля, вид)] утверждений и
    вызовов, не служащих доказательством (AC-4)."""
    places = []
    for path, lines in _plan.PREP_ASSERT_LINES.items():
        tree = base_trees[path]
        for line in lines:
            chain = _plan.function_chain(tree, line)
            name = chain[-1].name if chain else ""
            func = name if name.startswith("test") else f"{_plan.PREFIX[path]}_{name}"
            places.append((path, line, func, "assert"))
    for path, lines in _plan.PREP_CALL_LINES.items():
        tree = base_trees[path]
        for line in lines:
            chain = _plan.function_chain(tree, line)
            places.append((path, line, chain[-1].name if chain else "", "call"))
    return places


def test_ac4_preparation_assertion_lines_and_their_new_places_listed():
    """Строки утверждений-неупреждений «до» и их новые места «после» названы в PLAN.

    Для каждой строки перечня AC-4 (`accepted` :198, :233, :242, :261
    `answer`; `approve_spec` :160 `plan`; `with_dependencies` :104, :108 и
    `status_line` :116 `status_show`; `declared` :419 и `status_line` :180
    `new_declares`; :160 `guard`; :276, :305 `spec_gate`) в PLAN есть строка
    вне таблиц со ссылкой `tests/<файл волны>.py:<строка>` и ссылкой
    `tests/test_merge_after_module.py:<строка>`, лежащей в функции, куда
    перенесён объемлющий метод (тест — функцией с его именем, помощник —
    `<префикс>_<метод>`), на утверждении (для утверждений) или вызове
    помощника (для вызовов-подготовок).

    Ловит мутацию: PLAN перечислил строки «до», а новые места «после» не
    назвал (или назвал строку другой функции) — пары нет, тест краснеет со
    строкой.
    """
    plan = _ctx.plan_text()
    base_trees = _ctx.base_trees()
    head = _ctx.head_tree()
    funcs = _plan.module_functions(head)
    lines = _plan.prose_lines(plan)
    problems = []
    for path, line, func_name, kind in _prep_places(base_trees):
        func = funcs.get(func_name)
        ok = False
        for text in lines:
            refs = _plan.file_lines(text)
            if (path, line) not in refs:
                continue
            for p, n in refs:
                if p != _plan.MODULE or func is None or not _plan.covers(func, n):
                    continue
                if kind == "assert" and _plan.assertion_at(head, n) is not None:
                    ok = True
                if kind == "call" and any(
                        isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                        and c.func.id.startswith(_plan.PREFIX[path] + "_")
                        and _plan.covers(c, n) for c in ast.walk(func)):
                    ok = True
        if not ok:
            problems.append(f"{path}:{line}: в PLAN нет строки с новым местом в "
                            f"{_plan.MODULE} (функция {func_name})")
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

    Ловит мутацию: мутацию «до» убил тест на удачном зерне (сырой перенос
    префиксов при полном id), а «после» зерно другое — «не убита», тест
    краснеет с номером; либо утверждение ослаблено при переносе.
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


def test_ac5_each_mutation_has_seed_phrase():
    """У каждой мутации набора в PLAN есть фраза о зерне.

    Входы всех шести стендов — от зерна, поэтому для каждого патча есть
    строка PLAN вне таблиц со ссылкой на мутацию и словом «зерн…» (почему
    её убийство не зависит от зерна).

    Ловит мутацию: роль объяснила зерно для мутаций `answer` и `plan`, а
    мутации `status_show` оставила без фразы — номер перечислен, тест
    краснеет.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    lines = [line for line in _plan.prose_lines(plan) if _SEED.search(line)]
    missing = sorted(n for n in names if not any(n in _plan.refs(line) for line in lines))
    assert not missing, f"мутации без фразы о зерне: {missing}"


def test_ac5_no_seed_fixed_in_new_module_code():
    """Зерно ни в одном перенесённом тесте, помощнике и фикстуре модуля не зафиксировано.

    В функциях модуля, которых нет в базе, нет `random.seed(…)`,
    `random.Random(<литерал>)` и присваивания литерала имени или атрибуту
    `seed`.

    Ловит мутацию: стенд `status_show_stand` получил `seed = 12345` (или
    `random.Random(0)`) ради стабильного убийства — узел найден, тест
    краснеет со строкой.
    """
    found = []
    for func in _ctx.new_functions():
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name == "random.seed" or (
                        name in ("random.Random", "Random") and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    found.append(f"{func.name}:{node.lineno}: {ast.unparse(node)}")
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    name = target.id if isinstance(target, ast.Name) else \
                        target.attr if isinstance(target, ast.Attribute) else ""
                    if name == "seed":
                        found.append(f"{func.name}:{node.lineno}: {ast.unparse(node)}")
    assert not found, "зерно зафиксировано:\n" + "\n".join(found)


def test_ac5_test_without_deterministic_kill_kept_and_named_finding():
    """Исходный тест, чью сопоставленную мутацию «до» не убил никто, не удалён и назван находкой.

    Для каждого исходного теста, все сопоставленные в PLAN мутации
    которого «до» — не «убита», функция с его именем есть в модуле, и тест
    (`<Класс>::<метод>`) назван в строке находок PLAN.

    Ловит мутацию: для `test_ac2_list_ends_at_parenthesis_or_dot` не нашлось
    мутации, убиваемой при любом зерне, и роль удалила тест (или оставила,
    не записав находку) — тест краснеет с его именем.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    tests = _ctx.base_tests()
    rows = _plan.last_rows(_ctx.section_tables(plan, "Мутации до"))
    proof = set(_plan.killed(rows))
    mapped = _ctx.mapping(plan, set(names))
    funcs = {f.name for f in _plan.module_tests(_ctx.head_tree())}
    keys = _plan.finding_keys(plan)
    problems = []
    for key, test in sorted(tests.items()):
        hit = mapped.get(key, set())
        killers_of = {n for n, nodes in _plan.killed(rows).items()
                      if key in _before_killers(nodes)}
        if hit and not (hit & proof) and not killers_of:
            if test.name not in funcs:
                problems.append(f"{key}: без убитой мутации — удалён")
            if key not in keys:
                problems.append(f"{key}: без убитой мутации — не назван находкой")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-13

def test_ac13_untransferred_tests_are_listed_duplicates_meeting_conditions():
    """Неперенесённый исходный тест — удалённый дубль PLAN с мутациями и условиями (а), (б), (в).

    Исходный тест, для которого в модуле нет функции с его именем,
    перечислен в разделе «…дубл…» PLAN со ссылками на мутации. Для каждого
    удалённого дубля: мутаций не меньше одной; каждую по таблице «до»
    убивает и другой сохраняемый тест того же прежнего файла (а); среди
    этих убийц есть тест, литералы и виды `self.assert*` которого
    покрывают литералы и виды удалённого (б). Ни одна мутация, убитая
    «до», не убита только удалёнными тестами (в).

    Ловит мутацию: при своде пропал `ShowDependenciesTest::
    test_ac14_show_without_dependencies_has_no_line` без записи в PLAN,
    либо удалён дубль, чью мутацию «до» убивал кроме него только тест
    другого файла волны, — тест краснеет с именем.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    tree = _ctx.head_tree()
    removed = _plan.removed_duplicates(plan)
    proof = _plan.killed(_plan.last_rows(_ctx.section_tables(plan, "Мутации до")))
    killers = {n: _before_killers(nodes) for n, nodes in proof.items()}
    problems = []
    for test in tests.values():
        if not _moved(test, tree) and test.key not in removed:
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


def test_ac13_test_whose_mutation_nobody_killed_or_claimed_here_is_not_removed():
    """Тест, чью сопоставленную мутацию «до» не убил никто, и тест без заявки в базе не удалены дублем.

    Ни один тест раздела «…дубл…» PLAN не сопоставлен (в строках PLAN вне
    таблиц) мутации, последний исход «до» которой — не «убита», и у
    каждого удалённого в базе была заявка «Ловит мутацию» (тест,
    получивший заявку в этой задаче, не удаляется).

    Ловит мутацию: роль удалила как дубль `StatusSuffixTest::
    test_ac13_no_suffix_without_field_or_all_done`, чья мутация осталась
    «не убита» находкой, — тест краснеет с его именем.
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


# ------------------------------------------------------------------ AC-14

def test_ac14_after_tables_worktree_module_same_ranges_and_workers():
    """Раздел «Мутации после»: `--ref worktree` на `tests/test_merge_after_module.py`, те же диапазоны и `--workers`, что «до».

    Каждая таблица раздела — задача, `ревизия прогона: worktree <sha>`,
    тесты — ровно модуль; её набор патчей и строка «# рабочих процессов»
    совпадают с набором и строкой одной из таблиц «до»; вывод полон
    (строка на каждый патч шапки); каждый патч набора есть в таблицах
    «после».

    Ловит мутацию: «после» прогнан одним диапазоном `--patches 1-40` при
    частях «до» 1-25 и 26-40, с `--workers 4` при умолчании «до», или со
    старыми шестью файлами в `--tests` — набор, строка процессов или тесты
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
        if table.tests != [_plan.MODULE]:
            problems.append(f"{where}: тесты {table.tests}, ожидался {_plan.MODULE}")
        if (frozenset(table.patches), table.workers) not in parts:
            problems.append(f"{where}: патчи {sorted(table.patches)} при рабочих "
                            f"процессах «{table.workers}» — нет такой части «до»")
        _check_table_rows(table, where, _AFTER_NODE, problems)
    absent = sorted(set(names) - set(_plan.last_rows(after)))
    if absent:
        problems.append(f"мутаций набора нет в таблицах «после»: {absent}")
    assert not problems, "\n".join(problems)


def test_ac14_empty_orchestrator_scripts_status_before_each_after_part():
    """Перед каждой частью «после» — пустой вывод `git status --porcelain -- orchestrator/ scripts/`.

    В разделе «Мутации после» между концом предыдущей таблицы и шапкой
    каждой таблицы есть строка с командой `git status --porcelain --
    orchestrator/ scripts/`, и после неё до шапки нет строк вывода
    porcelain (`XY <путь>`) с путём под `orchestrator/` или `scripts/`.

    Ловит мутацию: роль привела вывод `git status` только перед первой
    частью, проверила только `orchestrator/`, или перед частью стоит
    ` M scripts/guard.py` — тест краснеет с шапкой части.
    """
    plan = _ctx.plan_text()
    texts = _plan.sections(plan, "Мутации после")
    assert texts, "в PLAN нет раздела «Мутации после»"
    command = "git status --porcelain -- orchestrator/ scripts/"
    porcelain = re.compile(r"^[ MADRCUT?!]{2} \"?(?:orchestrator|scripts)/")
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


# ------------------------------------------------------------------ AC-15

def _same_assertion_line(line, number, test, sites, after_killers) -> bool:
    if number not in _plan.refs(line) or test.key not in _plan.test_keys(line):
        return False
    funcs = _plan.after_refs(line) & after_killers & _moved(test, sites.head)
    if not funcs:
        return False
    base_tree = sites.base_trees[test.path]
    base_c = _plan.base_canon(base_tree, test.path)
    places = _plan.file_lines(line)
    if not sites.before_ok(test, places):
        return False
    before_forms = [_plan.normal_form(_plan.assertion_at(base_tree, n), base_c)
                    for p, n in places if p == test.path
                    and _plan.assertion_at(base_tree, n) is not None]
    for _fpath, fname in funcs:
        func = sites.head_funcs[fname]
        if not sites.after_ok(fname, places, test):
            continue
        canon = _plan.new_canon(func, test.func, base_c)
        for p, n in places:
            if p != _plan.MODULE:
                continue
            node = _plan.assertion_at(sites.head, n)
            if node is None:
                continue
            site_func = _plan.function_chain(sites.head, n)[0]
            if site_func is func:
                candidates = [canon]
            else:
                # Помощник модуля: стенд — первый параметр; локальные имена,
                # переименованные по требованию 9 (`_plan.LOCALS_TO_RENAME`),
                # сводятся к прежнему имени (amend-tests 25.10, ложный отказ
                # mutation-024: `journal` → `entries` в `spec_gate_assert_refused`).
                stands = {site_func.args.args[0].arg} if site_func.args.args else set()
                local_names = {n.id for n in ast.walk(site_func)
                               if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                candidates = [_plan.Canon(stands, {})] + [
                    _plan.Canon(stands, {}, locals_={name: old})
                    for name in sorted(local_names) for old in _plan.LOCALS_TO_RENAME
                    if name != old]
            if any(_plan.normal_form(node, c) in before_forms for c in candidates):
                return True
    return False


def test_ac15_killed_before_by_t_killed_after_by_its_function_same_assertion():
    """Мутацию, убитую «до» тестом T при любом зерне, «после» убивает функция T тем же утверждением.

    Для каждой мутации с последним исходом «до» «убита»: каждый её убийца
    T, не удалённый дублем и не названный в PLAN убийцей лишь на части
    зёрен (строка с мутацией, T и словами «на части зёрен»), «после» представлен
    среди убийц функцией, в которую он перенесён; хотя бы для одного такого
    T в PLAN есть строка со ссылкой на мутацию, с T, со ссылкой на его
    функцию и строками падения — утверждение T (база) и утверждение
    функции (HEAD) одной формы по соответствию требования 11
    (`assertX(a, b)` ↔ `assert a <op> b`, `self.<помощник>` ↔ функция,
    `self` ↔ стенд; ожидания и литералы дословно).

    Ловит мутацию: «после» мутацию убил соседний тест, а функция T её
    пропустила, или функция T падает другим утверждением (`assert
    new_declares_deps(stand, task_id) == []` вместо перенесённого `assert
    task_id is None`) — нет убийцы или формы расходятся, тест краснеет с
    номером.
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
        partial = {k for line in lines if number in _plan.refs(line)
                   and _PARTIAL_SEED.search(line) for k in _plan.test_keys(line)}
        kept = [sites.tests[k] for k in sorted(_before_killers(nodes))
                if k in sites.tests and k not in removed and k not in partial]
        if not kept:
            problems.append(f"мутация {number}: нет убийцы «до», убивающего при "
                            f"любом зерне")
            continue
        for test in kept:
            if not (_moved(test, sites.head) & after_killers):
                problems.append(f"мутация {number}: «до» убил {test.key}, «после» "
                                f"его функция не среди убийц ({outcome} {after_nodes})")
        if not any(_same_assertion_line(line, number, test, sites, after_killers)
                   for line in lines for test in kept):
            problems.append(f"мутация {number}: нет строки PLAN с T, его "
                            f"функцией и строками падения одной формы")
    assert not problems, "\n".join(problems)


def test_ac15_same_orchestrator_and_scripts_tree_across_all_header_revisions():
    """Деревья `orchestrator/` и `scripts/` у ревизий всех шапок «до» и «после» одни.

    Для каждой пары различных ревизий из шапок таблиц обоих разделов
    `git diff --quiet <sha> <sha> -- orchestrator/ scripts/` в рабочей
    копии завершается кодом 0.

    Ловит мутацию: «после» прогнан на ревизии с правкой `scripts/guard.py`
    (или «до» не повторён после подтяжки main с правкой
    `orchestrator/merge_after.py`) — `git diff` даёт код 1, тест краснеет
    с парой ревизий.
    """
    plan = _ctx.plan_text()
    shas = sorted({t.sha for t in _ctx.section_tables(plan, "Мутации до")}
                  | {t.sha for t in _ctx.section_tables(plan, "Мутации после")})
    problems = []
    for i, left in enumerate(shas):
        for right in shas[i + 1:]:
            res = _plan.git(CODE_ROOT, "diff", "--quiet", left, right, "--",
                            "orchestrator/", "scripts/")
            if res.returncode != 0:
                problems.append(f"git diff --quiet {left} {right} -- orchestrator/ "
                                f"scripts/ — код {res.returncode} {res.stderr.strip()}")
    assert not problems, "\n".join(problems)


def test_ac15_patch_sha256_same_in_before_and_after_headers():
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


def test_ac15_plan_names_test_count_lines_and_time_before_and_after():
    """PLAN называет число тестов и строк модуля и шести файлов до и после свода и время прогонов.

    «До» — по базе ветки: 33 теста шести файлов волны и их строки (сумма
    или число каждого файла), 20 тестов прежнего модуля и его строки;
    «после» — по HEAD: число функций-тестов модуля и его строки. Числа
    стоят в PLAN отдельными числами (разряды могут делиться пробелом);
    длительностей (`<n> с`/`мин`) не меньше двух.

    Ловит мутацию: роль записала числа только «до» (или не назвала строки
    модуля после свода, или время только одного контрольного прогона) —
    числа или второй длительности нет, тест краснеет с ним.
    """
    plan = _ctx.plan_text()

    def named_total_or_each(values: list) -> bool:
        return _plan.number_named(plan, sum(values)) or \
            all(_plan.number_named(plan, v) for v in values)

    base = _ctx.base_texts()
    base_tests = [len(_plan.base_tests(p, t)) for p, t in base.items()]
    base_lines = [t.count("\n") for t in base.values()]
    old_module = _ctx.base_module_text()
    new_module = _ctx.head_module_text()
    checks = [
        (named_total_or_each(base_tests), f"число тестов шести файлов «до» {base_tests}"),
        (named_total_or_each(base_lines), f"число строк шести файлов «до» {base_lines}"),
        (_plan.number_named(plan, len(_plan.module_tests(ast.parse(old_module)))),
         "число тестов модуля «до»"),
        (_plan.number_named(plan, old_module.count("\n")), "число строк модуля «до»"),
        (_plan.number_named(plan, len(_plan.module_tests(ast.parse(new_module)))),
         "число тестов модуля «после»"),
        (_plan.number_named(plan, new_module.count("\n")), "число строк модуля «после»"),
    ]
    problems = [f"{what} в PLAN не названо" for ok, what in checks if not ok]
    if len(_DURATION.findall(plan)) < 2:
        problems.append("в PLAN нет двух длительностей контрольных прогонов — "
                        "до и после")
    assert not problems, "\n".join(problems)
