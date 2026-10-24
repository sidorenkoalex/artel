"""AC-2, AC-3, AC-4, AC-5, AC-15, AC-16, AC-17, AC-18: таблицы
`mutation-run` «до» и «после» в PLAN и их согласованность с набором
патчей, группами, копиями `--copy-table`, строками падения, находками,
удалёнными дублями, соответствием «до → после» и рабочей копией.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после», патчей и свода ещё нет — прогонов mutation-run и свода не было.

Планка сверяет форму и согласованность таблиц: части не смешивают группы
и не длиннее предела, «после» — теми же диапазонами и тем же числом рабочих
процессов, таблица в PLAN дословно равна копии `--copy-table`
(`mutation-run-<номер>.tsv` каталога документов), исход каждой мутации
одинаков во всех прогонах, убитую «до» тестом T «после» убивает функция, в
которую перенесён T, у каждой убитой мутации — строка падения «до» и
«после» в утверждении вне подготовки и вне утверждений-предусловий.
Подлинность прогонов, `Timeout` в логе и «исключение без падения
утверждения» по логу — работа независимой проверки (требование 25 SPEC).
Соглашения разбора PLAN — докстринг `_plan.py`.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT, TASK_ID  # noqa: E402

_DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|секунд[а-я]*|s|мин|min)"
                       r"(?![A-Za-zА-Яа-яЁё])")
_STATUS_CMD = "git status --porcelain -- orchestrator/"
_PORCELAIN_LINE = re.compile(r"^\s*[ MADRCU?!]{1,2}\s+\S*orchestrator/\S*")
_BEFORE, _AFTER = "Мутации до", "Мутации после"
_BEFORE_FILES = (*_plan.SOURCE_FILES, _plan.OUTCOME_SANDBOX)
_AFTER_FILES = (*_plan.TARGETS, _plan.MERGE_SANDBOX)


def _node_re(path: str, before: bool):
    tail = r"::[A-Za-z_]\w*::test\w*$" if before else r"::test\w*(?:\[.*\])?$"
    return re.compile("^" + re.escape(path) + tail)


def _table_group(table, before: bool):
    """Группа таблицы по строке `# тесты:` — ровно один исходный файл
    («до») или один приёмник («после»); иначе None."""
    if len(table.tests) != 1:
        return None
    index = _plan.GROUP_OF_SOURCE if before else _plan.GROUP_OF_TARGET
    return index.get(table.tests[0])


def _texts(before: bool) -> dict:
    if before:
        return {p: _ctx.base_text(p) for p in _BEFORE_FILES}
    return {p: _ctx.head_text(p) for p in _AFTER_FILES}


def _assertion_at(tree, line: int):
    found = [n for n in ast.walk(tree) if _plan._is_assertion_node(n)
             and n.lineno <= line <= (n.end_lineno or n.lineno)]
    return min(found, key=lambda n: (n.end_lineno or n.lineno) - n.lineno,
               default=None)


def _site_literals(node) -> set:
    if isinstance(node, ast.Assert):
        return _plan.constants(node.test)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr.startswith("assert"):
        return set().union(*[_plan.constants(a)
                             for a in _plan.semantic_args(node)] or [set()])
    return set().union(*[_plan.constants(a) for a in node.args] or [set()])


def _site(texts: dict, path: str, line: int, *, strict: bool = False,
          preconditions: dict | None = None):
    """(цепочка функций, литералы утверждения) для ссылки `path:line`,
    лежащей внутри утверждения; при `strict` — ещё и вне метода подготовки,
    фикстуры и утверждения-предусловия; иначе None."""
    text = texts.get(path)
    if text is None:
        return None
    inside, chain = _plan.assertion_site(text, line)
    if not (inside and chain):
        return None
    tree = ast.parse(text)
    node = _assertion_at(tree, line)
    if strict:
        if _plan.in_preparation(chain):
            return None
        if node is not None and node.lineno in (preconditions or {}).get(path, set()):
            return None
    return chain, (_site_literals(node) if node is not None else set())


def _after_preconditions(plan: str) -> dict:
    """{приёмник: строки начала утверждений-предусловий} — ссылки
    `tests/test_merge_outcome_module.py:<n>` в строках PLAN, где названа
    старая строка предусловия."""
    head = ast.parse(_ctx.head_text(_plan.MERGE_MODULE))
    found = set()
    for line in _plan.prose_lines(plan):
        old = {n for p, n in _plan.file_lines(line) if p == _plan.MERGE_SOURCE}
        if not old & set(_plan.PRECONDITION_LINES):
            continue
        for path, n in _plan.file_lines(line):
            if path == _plan.MERGE_MODULE:
                node = _assertion_at(head, n)
                if node is not None:
                    found.add(node.lineno)
    return {_plan.MERGE_MODULE: found}


def _findings(plan: str) -> set:
    found = set()
    for line in _plan.prose_lines(plan):
        if "находк" in line.casefold():
            found |= _plan.refs(line)
    for text in _plan.sections(plan, "находк"):
        for line in _plan.prose_lines(text):
            found |= _plan.refs(line)
    return found


def _tables(plan: str):
    return _ctx.section_tables(plan, _BEFORE), _ctx.section_tables(plan, _AFTER)


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_one_group_parts_within_limit():
    """Раздел «Мутации до»: таблицы `--ref base` на исходном файле одной группы частями-диапазонами не длиннее предела, каждая мутация есть.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно исходный файл одной
    группы (`merge_outcome_gate` — М, `added_lines` — Д),
    `# рабочих процессов: <n>`, строки «# патч … sha256 …». Патчи части —
    сплошной диапазон длиной не больше 15 (при 4 рабочих процессах — 7 у
    группы М и 5 у группы Д), все — мутации той же группы по заявкам PLAN.
    У каждой строки есть строка «# патч» шапки; исход — из словаря
    команды; у «убита» узлы непусты и имеют вид
    `tests/<исходный файл группы>::<Класс>::<метод>`. Каждая мутация набора
    есть строкой в таблицах раздела своей группы.

    Ловит мутацию: роль прогнала «до» одной частью `--patches 1-25`
    вперемешку на обоих файлах, или повтор при `--workers 4` частью `1-10`,
    или «до» с `--ref worktree` — тест краснеет с таблицей.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    groups = _ctx.patch_groups(plan, set(names))
    found = _ctx.section_tables(plan, _BEFORE)
    problems, rows_by_group = [], {}
    for table in found:
        where = f"таблица №{table.run_no}"
        group = _table_group(table, before=True)
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != "base":
            problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась base")
        if group is None:
            problems.append(f"{where}: тесты {table.tests} — не исходный файл одной группы")
            continue
        if not table.workers:
            problems.append(f"{where}: в шапке нет строки «# рабочих процессов: …»")
        numbers = sorted(table.patches)
        if not numbers:
            problems.append(f"{where}: в шапке нет строк «# патч … sha256 …»")
        elif numbers != list(range(numbers[0], numbers[-1] + 1)):
            problems.append(f"{where}: патчи части не сплошной диапазон: {numbers}")
        limit = group.max_workers_4 if table.workers == "4" else _plan.MAX_PART
        if len(numbers) > limit:
            problems.append(f"{where}: в части {len(numbers)} патчей при рабочих "
                            f"процессах {table.workers!r} — больше {limit}")
        alien = [n for n in numbers if groups.get(n) != {group}]
        if alien:
            problems.append(f"{where}: группа {group.letter}, а мутации {alien} — "
                            f"не её по заявкам")
        node = _node_re(group.source, before=True)
        for number, outcome, nodes in table.rows:
            rows_by_group.setdefault(group.letter, set()).add(number)
            if number not in table.patches:
                problems.append(f"{where}: строка мутации {number} без «# патч {number} …»")
            if outcome not in _plan.OUTCOMES:
                problems.append(f"{where}: мутация {number} — исход «{outcome}» не из "
                                f"вывода команды")
            if outcome == _plan.KILLED and (not nodes or any(not node.match(n)
                                                             for n in nodes)):
                problems.append(f"{where}: мутация {number} убита, узлы не вида "
                                f"{group.source}::<Класс>::<метод>: {nodes}")
    for number in sorted(names):
        letters = {g.letter for g in groups.get(number, set())}
        if not any(number in rows_by_group.get(l, set()) for l in letters):
            problems.append(f"мутации {number} нет строкой в таблицах «до» её группы")
    assert not problems, "\n".join(problems)


def _copy_problems(plan: str, title: str) -> list:
    text = _ctx.section_text(plan, title)
    found, errors = _plan.tables(text)
    assert not errors, f"раздел «{title}»: " + "; ".join(errors)
    assert found, f"в разделе «{title}» нет таблиц mutation-run"
    problems = []
    for run_no in sorted({t.run_no for t in found}):
        name = f"mutation-run-{run_no}.tsv"
        copy = _ctx.artifact_text(name)
        if copy is None:
            problems.append(f"«{title}», таблица №{run_no}: копии {name} "
                            f"(--copy-table) в каталоге документов нет")
            continue
        block = copy.rstrip("\n").split("\n")
        if not _plan.contains_block(text, block):
            problems.append(f"«{title}», таблица №{run_no}: в разделе нет дословного "
                            f"текста копии {name} (шапка и все {len(block)} строк подряд)")
    return problems


def test_ac2_before_tables_verbatim_equal_copy_table():
    """Каждая таблица «до» в PLAN дословно, с шапкой и всеми строками, равна своей копии `--copy-table`.

    Ловит мутацию: роль перенесла вывод `--wait` без части строк «# патч»
    (или переписала исход «итог неизвестен» как «убита»), либо прогнала
    часть без `--copy-table` — текст раздела расходится с копией или копии
    нет, тест краснеет с номером прогона.
    """
    problems = _copy_problems(_ctx.plan_text(), _BEFORE)
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-3

@pytest.mark.parametrize("side", ["до", "после"])
def test_ac3_each_killed_mutation_names_failed_assertion_line(side):
    """У каждой убитой мутации PLAN называет файл:строку упавшего утверждения «до» и «после».

    Для мутации с последним исходом «убита» в таблицах стороны есть строка
    PLAN вне таблиц со ссылкой на мутацию и ссылкой `tests/<файл>.py:<n>`,
    которая лежит внутри утверждения: «до» — в исходных файлах или
    `tests/outcome_gate_sandbox.py` базы, «после» — в приёмниках или
    `tests/merge_outcome_sandbox.py` на HEAD.

    Ловит мутацию: роль привела строку падения только для «до» (или номер
    строки исходного файла для «после», либо строку вне утверждения —
    заголовок функции из трассы) — у мутации нет годной строки, тест
    краснеет с номером.
    """
    plan = _ctx.plan_text()
    before = side == "до"
    tables = _ctx.section_tables(plan, _BEFORE if before else _AFTER)
    texts = _texts(before)
    lines = _plan.prose_lines(plan)
    missing = []
    for number in sorted(_plan.killed(_plan.last_rows(tables))):
        if not any(number in _plan.refs(line) and any(
                _site(texts, p, n) for p, n in _plan.file_lines(line)) for line in lines):
            missing.append(number)
    assert not missing, (f"убитые «{side}» мутации без файл:строки упавшего "
                         f"утверждения в PLAN: {missing}")


# ------------------------------------------------------------------ AC-4

def test_ac4_precondition_lines_named_in_old_and_new_file():
    """PLAN называет строки утверждений-предусловий (старые :715, :718, :749, :786, :801) в старом и новом файле.

    Для каждой старой строки есть строка PLAN вне таблиц со ссылкой
    `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:<n>` и
    ссылкой `tests/test_merge_outcome_module.py:<m>`, лежащей на HEAD
    внутри утверждения тестовой функции.

    Ловит мутацию: роль назвала новые строки только для трёх предусловий
    бывшего `Ac7MergeBaseTest` (или привела номера строк до последней
    правки модуля) — у старой строки нет пары, тест краснеет с ней.
    """
    plan = _ctx.plan_text()
    head = _ctx.head_text(_plan.MERGE_MODULE)
    missing = []
    for old in _plan.PRECONDITION_LINES:
        ok = False
        for line in _plan.prose_lines(plan):
            refs = _plan.file_lines(line)
            if (_plan.MERGE_SOURCE, old) not in refs:
                continue
            for path, n in refs:
                inside, chain = (_plan.assertion_site(head, n) if path == _plan.MERGE_MODULE
                                 else (False, []))
                if inside and chain and chain[0].name.startswith("test"):
                    ok = True
        if not ok:
            missing.append(old)
    assert not missing, (f"предусловия старых строк {missing} без строки нового "
                         f"файла в PLAN")


@pytest.mark.parametrize("side", ["до", "после"])
def test_ac4_proof_mutation_fails_outside_preparation_and_preconditions(side):
    """Убитая мутация доказана падением утверждения вне подготовки и вне утверждений-предусловий.

    Для мутации с последним исходом «убита» стороны есть строка PLAN со
    ссылкой на неё и `файл:строкой`, лежащей в утверждении, которое не
    внутри метода подготовки (`setUp`, `direct_task`, `verifying_task`,
    `rewrite_passed`, `in_dev_task`, `artel_in_dev_task`,
    `operator_mandate`) или фикстуры и не утверждение-предусловие (старые
    :715, :718, :749, :786, :801; новые — по строкам PLAN критерия).

    Ловит мутацию: патч ломает `workspace.ensure`, все тесты падают на
    `assertIsNone(error, …)` в `direct_task` (:220), роль записала эту
    строку и не переписала патч — годной строки нет, тест краснеет с
    номером.
    """
    plan = _ctx.plan_text()
    before = side == "до"
    tables = _ctx.section_tables(plan, _BEFORE if before else _AFTER)
    texts = _texts(before)
    pre = ({_plan.MERGE_SOURCE: set(_plan.PRECONDITION_LINES)} if before
           else _after_preconditions(plan))
    lines = _plan.prose_lines(plan)
    lonely = []
    for number in sorted(_plan.killed(_plan.last_rows(tables))):
        if not any(number in _plan.refs(line) and any(
                _site(texts, p, n, strict=True, preconditions=pre)
                for p, n in _plan.file_lines(line)) for line in lines):
            lonely.append(number)
    assert not lonely, (f"мутации «{side}» без падения утверждения вне подготовки и "
                        f"предусловий: {lonely}")


def test_ac4_collection_error_never_counted_killed():
    """Мутация с последним исходом «ошибка сбора, импорта или setup» не засчитана доказательством.

    Для мутации, чья последняя строка «до» или «после» — этот исход (патч не
    переписан), PLAN называет её находкой.

    Ловит мутацию: патч ломает импорт `orchestrator.fsm_merge_gate`, строка
    таблицы — «ошибка сбора, импорта или setup», роль сослалась на неё как
    на убитую и не переписала патч — тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    before, after = _tables(plan)
    collection = sorted({n for found in (before, after)
                         for n, (outcome, _nodes) in _plan.last_rows(found).items()
                         if outcome == _plan.COLLECTION})
    unlisted = sorted(set(collection) - _findings(plan))
    assert not unlisted, (f"мутации с последним исходом «{_plan.COLLECTION}» не "
                          f"переписаны и не названы находками: {unlisted}")


def test_ac4_survived_before_listed_as_findings():
    """Мутации, не убитые «до» никем, перечислены в PLAN находками.

    Ловит мутацию: роль молча оставила в наборе патч, который «до» никто не
    убил, и не записала его находкой — тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    rows = _plan.last_rows(_ctx.section_tables(plan, _BEFORE))
    survived = sorted(n for n, (outcome, _nodes) in rows.items()
                      if outcome == _plan.SURVIVED)
    unlisted = sorted(set(survived) - _findings(plan))
    assert not unlisted, f"мутации, не убитые «до», не названы находками: {unlisted}"


def test_ac4_void_outcome_neither_killed_nor_survived():
    """Мутация с последним исходом «итог неизвестен», «патч не применяется», «патч трогает тесты», «не прогнана» или «оборвана по пределу» не засчитана выжившей.

    Для мутации, чья последняя строка «до» или «после» — такой исход, PLAN
    не называет её находкой (выжившей); убитой она не считается по разбору
    таблиц (доказательство — только последний исход «убита»).

    Ловит мутацию: прогон «до» оборвался по пределу, роль записала
    оборванную мутацию находкой («никто не убил») и не перепрогнала её
    меньшим диапазоном — тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    before, after = _tables(plan)
    void = sorted({n for found in (before, after)
                   for n, (outcome, _nodes) in _plan.last_rows(found).items()
                   if outcome in _plan.VOID_OUTCOMES})
    as_findings = sorted(set(void) & _findings(plan))
    assert not as_findings, (f"мутации с исходом «итог неизвестен»/предела/патча "
                             f"названы находками: {as_findings}")


# ------------------------------------------------------------------ AC-5

def test_ac5_outcome_same_in_before_after_and_every_repeat():
    """Исход «убита / не убита» каждой мутации одинаков во всех прогонах её патча — «до», «после» и повторах.

    Берутся все строки всех таблиц разделов «Мутации до»/«Мутации после» и
    всех копий `mutation-run-<n>.tsv` каталога документов; строка относится
    к патчу по паре (номер, sha256 из шапки), sha256 патча — из последней
    шапки «до». Среди исходов «убита»/«не убита» строк одного патча — одно
    значение; последний исход «до» и «после» каждой мутации — оба из этих
    двух.

    Ловит мутацию: мутацию бывшего `Ac11` убивает только жребий стороны —
    «до» она «не убита», роль повторила часть и записала второй прогон
    («убита»), или «после» она выжила — тест краснеет с номером и исходами.
    """
    plan = _ctx.plan_text()
    before, after = _tables(plan)
    final = _plan.last_patch_sha(before)
    outcomes = {}
    for number, sha, outcome in _plan.all_outcomes(before + after + _ctx.copy_tables()):
        if final.get(number) == sha and outcome in (_plan.KILLED, _plan.SURVIVED):
            outcomes.setdefault(number, set()).add(outcome)
    problems = [f"мутация {n}: исходы {sorted(o)}" for n, o in sorted(outcomes.items())
                if len(o) > 1]
    last_b, last_a = _plan.last_rows(before), _plan.last_rows(after)
    for number in sorted(_ctx.patch_names()):
        b = last_b.get(number, ("<нет строки>",))[0]
        a = last_a.get(number, ("<нет строки>",))[0]
        if b not in (_plan.KILLED, _plan.SURVIVED) or a not in (_plan.KILLED, _plan.SURVIVED):
            problems.append(f"мутация {number}: последний исход «до» «{b}», «после» «{a}»")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-15

def test_ac15_removed_duplicates_killed_by_kept_test_with_its_literals():
    """Удалённый дубль: его мутации убивает сохраняемый тест того же исходного файла с теми же утверждениями; тест без убитых мутаций не удалён.

    Раздел «…дубл…» PLAN перечисляет удалённые тесты исходных файлов с
    мутациями. Для каждого: мутаций не меньше одной; каждую из них и каждую
    мутацию, сопоставленную ему в PLAN, «до» кто-то убил; каждую по таблице
    «до» убивает и сохраняемый тест того же исходного файла (условие (а));
    среди них есть тест, убивающий их все, у которого литералы и виды
    `self.assert*` (по базе ветки) покрывают литералы и виды удалённого
    (условие (б)).

    Ловит мутацию: удалён как дубль бывший `Ac6LegacyRecordTest`, чью
    мутацию «до» убивал только он, или тест `added_lines` с литералом,
    которого нет у оставленного соседа, — тест краснеет с именем дубля.
    """
    plan = _ctx.plan_text()
    rows = _plan.last_rows(_ctx.section_tables(plan, _BEFORE))
    proof = _plan.killed(rows)
    removed = _ctx.removed_keys(plan)
    tests = _ctx.base_tests()
    killers = {n: {_plan.node_key(x) for x in nodes} for n, nodes in proof.items()}
    claimed = _ctx.mapping(plan, set(_ctx.patch_names()))
    problems = []
    for key, numbers in sorted(removed.items()):
        if key not in tests:
            problems.append(f"{key}: в исходных файлах базы такого теста нет")
            continue
        if not numbers:
            problems.append(f"{key}: удалён без перечня своих мутаций")
            continue
        unkilled = sorted(n for n in claimed.get(key, set()) | numbers if n not in proof)
        if unkilled:
            problems.append(f"{key}: удалён, а его мутации {unkilled} «до» не убиты никем")
            continue
        kept = None
        for number in numbers:
            others = {k for k in killers[number] - {key} - set(removed)
                      if k in tests and tests[k].path == tests[key].path}
            kept = others if kept is None else kept & others
            if not others:
                problems.append(f"{key}: мутацию {number} не убивает ни один сохраняемый "
                                f"тест того же файла")
        lits = _plan.assertion_literals(tests[key].func)
        kinds = _plan.assertion_kinds(tests[key].func)
        covering = [k for k in sorted(kept or ())
                    if lits <= _plan.assertion_literals(tests[k].func)
                    and kinds <= _plan.assertion_kinds(tests[k].func)]
        if not covering:
            problems.append(f"{key}: среди сохраняемых тестов, убивающих {sorted(numbers)}, "
                            f"нет теста с его литералами и видами {sorted(kinds)}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-16

def test_ac16_after_tables_worktree_target_same_ranges_and_workers():
    """Раздел «Мутации после»: `--ref worktree` на приёмнике группы, те же диапазоны и рабочие процессы, что «до», каждая мутация есть.

    Каждая таблица раздела — задача, `ревизия прогона: worktree <sha>`,
    тесты — ровно приёмник одной группы (`tests/test_merge_outcome_module.py`
    — М, `tests/test_outcome_gate_module.py` — Д); пара (диапазон патчей,
    `# рабочих процессов`) есть среди пар таблиц «до» той же группы; у строк
    — строка «# патч» шапки, исход из словаря команды, у «убита» узлы вида
    `tests/<приёмник>::<функция>[<вариант>]`. Каждая мутация набора есть
    строкой «после».

    Ловит мутацию: «после» группы Д прогнан на `tests/test_merge_outcome_module.py`,
    одной частью `1-19` при частях «до» `1-15`/`16-19`, либо с `--workers 4`
    при «до» по умолчанию — тест краснеет с таблицей.
    """
    plan = _ctx.plan_text()
    before, after = _tables(plan)
    parts = {(id(_table_group(t, True)), tuple(sorted(t.patches)), t.workers)
             for t in before}
    problems = []
    for table in after:
        where = f"таблица «после» №{table.run_no}"
        group = _table_group(table, before=False)
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != "worktree":
            problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась worktree")
        if group is None:
            problems.append(f"{where}: тесты {table.tests} — не приёмник одной группы")
            continue
        part = (id(group), tuple(sorted(table.patches)), table.workers)
        if part not in parts:
            problems.append(f"{where}: диапазон {list(part[1])} при рабочих процессах "
                            f"{part[2]!r} — такой части «до» группы {group.letter} нет")
        node = _node_re(group.target, before=False)
        for number, outcome, nodes in table.rows:
            if number not in table.patches:
                problems.append(f"{where}: строка мутации {number} без «# патч {number} …»")
            if outcome not in _plan.OUTCOMES:
                problems.append(f"{where}: мутация {number} — исход «{outcome}» не из "
                                f"вывода команды")
            if outcome == _plan.KILLED and (not nodes or any(not node.match(n)
                                                             for n in nodes)):
                problems.append(f"{where}: мутация {number} убита, узлы не вида "
                                f"{group.target}::<функция>: {nodes}")
    absent = sorted(set(_ctx.patch_names()) - set(_plan.last_rows(after)))
    if absent:
        problems.append(f"мутаций нет в таблицах «после»: {absent}")
    assert not problems, "\n".join(problems)


def test_ac16_after_tables_verbatim_equal_copy_table():
    """Каждая таблица «после» в PLAN дословно, с шапкой и всеми строками, равна своей копии `--copy-table`.

    Ловит мутацию: роль свела в PLAN две части «после» в одну таблицу с
    общей шапкой (или дописала исход руками) — текст раздела не содержит
    копии `mutation-run-<номер>.tsv` подряд, тест краснеет с номером.
    """
    problems = _copy_problems(_ctx.plan_text(), _AFTER)
    assert not problems, "\n".join(problems)


def test_ac16_empty_orchestrator_status_shown_before_each_after_part():
    """Перед каждой таблицей «после» PLAN приводит пустой вывод `git status --porcelain -- orchestrator/`.

    В разделе «Мутации после» между концом предыдущей таблицы (или началом
    раздела) и шапкой каждой таблицы стоит команда `git status --porcelain
    -- orchestrator/`, и между её последним вхождением и шапкой нет строки
    вывода porcelain с путём `orchestrator/…`.

    Ловит мутацию: роль привела проверку только перед первой частью
    «после», или перенесла вывод ` M orchestrator/fsm_merge_gate.py` — тест
    краснеет с номером таблицы.
    """
    text = _ctx.section_text(_ctx.plan_text(), _AFTER)
    found, errors = _plan.tables(text)
    assert not errors, f"раздел «{_AFTER}»: " + "; ".join(errors)
    assert found, f"в разделе «{_AFTER}» нет таблиц mutation-run"
    lines = text.split("\n")
    problems, prev_end = [], 0
    for table in sorted(found, key=lambda t: t.start):
        lead = lines[prev_end:table.start]
        at = [i for i, line in enumerate(lead) if _STATUS_CMD in line]
        if not at:
            problems.append(f"перед таблицей «после» №{table.run_no} нет команды "
                            f"«{_STATUS_CMD}»")
        else:
            dirty = [line for line in lead[at[-1] + 1:] if _PORCELAIN_LINE.match(line)]
            if dirty:
                problems.append(f"перед таблицей «после» №{table.run_no} вывод непуст: "
                                f"{dirty}")
        prev_end = table.start + len(table.lines)
    assert not problems, "\n".join(problems)


def test_ac16_same_orchestrator_tree_across_all_header_revisions():
    """Дерево `orchestrator/` у ревизий всех шапок «до» и «после» одно.

    Ловит мутацию: «после» прогнан на ревизии с правкой `orchestrator/`
    (или «до» не повторён после подтяжки main с правкой `orchestrator/`) —
    `git diff --quiet` даёт код 1, тест краснеет с парой ревизий.
    """
    before, after = _tables(_ctx.plan_text())
    shas = sorted({t.sha for t in before + after})
    problems = []
    for i, left in enumerate(shas):
        for right in shas[i + 1:]:
            res = _plan.git(CODE_ROOT, "diff", "--quiet", left, right, "--", "orchestrator/")
            if res.returncode != 0:
                problems.append(f"git diff --quiet {left} {right} -- orchestrator/ — "
                                f"код {res.returncode} {res.stderr.strip()}")
    assert not problems, "\n".join(problems)


def test_ac16_patch_sha256_same_in_before_and_after_headers():
    """sha256 каждого патча в шапке «до» совпадает с его sha256 в шапке «после».

    Ловит мутацию: роль переписала патч между прогонами «до» и «после» и не
    повторила «до» — sha256 номера в шапках расходится, тест краснеет с
    номером и обоими значениями.
    """
    before, after = _tables(_ctx.plan_text())
    names = _ctx.patch_names()
    b_shas, a_shas = _plan.last_patch_sha(before), _plan.last_patch_sha(after)
    assert set(names) <= set(b_shas), (
        f"патчи без строки «# патч» в шапках «до»: {sorted(set(names) - set(b_shas))}")
    problems = [f"патч {n}: sha256 «до» {b_shas[n]} ≠ «после» {a_shas.get(n)}"
                for n in sorted(b_shas) if a_shas.get(n) != b_shas[n]]
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-17

def _functions_of(key: str, tests: dict, transfer: dict) -> set:
    """{(приёмник, функция)} перенесённого теста: по имени и по PLAN."""
    test = tests[key]
    group = _plan.GROUP_OF_SOURCE[test.path]
    funcs = (_plan.module_functions(_ctx.head_tree(group.target)) if group is _plan.GROUP_M
             else _ctx.new_functions(group.target))
    return {(group.target, f.name)
            for f in _ctx.matches(funcs, group.target, test.cls, test.func.name, transfer)}


def test_ac17_mutation_killed_before_by_t_killed_after_by_function_of_t():
    """Мутацию, убитую «до» тестом T, «после» убивает функция, в которую перенесён T.

    Каждый тест исходных файлов базы, не перечисленный удалённым дублем,
    сопоставлен функции своего приёмника на HEAD (по имени или по
    соответствию «до → после» PLAN). Для каждой мутации с последним исходом
    «до» «убита» и каждого её убийцы «до» T (не удалённого дублем) последний
    исход «после» — «убита», и среди убийц «после» есть узел функции T.

    Ловит мутацию: бывший `Ac3MergePrepareTest` при своде потерял подслучай
    «ключ None» — мутацию, которую «до» убивал он, «после» никто не убил
    (или убила только соседняя функция) — тест краснеет с номером и T.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    removed = set(_ctx.removed_keys(plan))
    transfer = _plan.transfer_map(plan)
    problems = []
    funcs_of = {}
    for key in sorted(tests):
        if key in removed:
            continue
        funcs_of[key] = _functions_of(key, tests, transfer)
        if not funcs_of[key]:
            problems.append(f"{key}: функции приёмника нет (ни по имени, ни по PLAN)")
    before, after = _tables(plan)
    after_rows = _plan.last_rows(after)
    for number, nodes in sorted(_plan.killed(_plan.last_rows(before)).items()):
        outcome, after_nodes = after_rows.get(number, ("<нет строки>", []))
        killers = {_plan.after_node_parts(n)[:2] for n in after_nodes} \
            if outcome == _plan.KILLED else set()
        for key in sorted({_plan.node_key(n) for n in nodes}):
            if key in removed or key not in funcs_of:
                continue
            if not funcs_of[key] & killers:
                problems.append(f"мутация {number}: «до» её убил {key}, «после» его "
                                f"функции {sorted(funcs_of[key])} не среди убийц "
                                f"«{outcome}» {sorted(killers)}")
    assert not problems, "\n".join(problems)


def test_ac17_plan_maps_failure_line_before_to_after_with_same_check():
    """Для каждой убитой «до» мутации PLAN даёт соответствие «файл:строка до → файл:строка после» перенесённого утверждения.

    Есть строка PLAN вне таблиц со ссылкой на мутацию, ссылкой «до»
    (исходный файл или `tests/outcome_gate_sandbox.py` базы) внутри
    утверждения теста T — одного из её убийц «до» — или помощника исхода
    `no_gate_refusal`, и ссылкой «после» (приёмник на HEAD) внутри
    утверждения функции, в которую перенесён T, или функции
    `no_gate_refusal`; литералы проверяемой части утверждения «после»
    содержат литералы утверждения «до».

    Ловит мутацию: роль назвала строкой «после» утверждение чужой функции
    (`assert box.state(t) == "done"` вместо перенесённого
    `assert box.ci_calls == []`), или не привела пары строк — тест краснеет
    с номером.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    transfer = _plan.transfer_map(plan)
    before, _after = _tables(plan)
    btexts, atexts = _texts(True), _texts(False)
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(_plan.killed(_plan.last_rows(before)).items()):
        killers = {_plan.node_key(n) for n in nodes} & set(tests)
        ok = False
        for line in lines:
            if number not in _plan.refs(line):
                continue
            refs = _plan.file_lines(line)
            for key in killers:
                funcs = {f for _p, f in _functions_of(key, tests, transfer)}
                method = tests[key].func.name
                for bp, bn in refs:
                    bsite = _site(btexts, bp, bn)
                    if not bsite or bsite[0][0].name not in (method, *_plan.OUTCOME_HELPERS):
                        continue
                    for ap, an in refs:
                        asite = _site(atexts, ap, an)
                        if asite and asite[0][0].name in funcs | set(_plan.OUTCOME_HELPERS) \
                                and bsite[1] <= asite[1]:
                            ok = True
        if not ok:
            problems.append(f"мутация {number}: нет строки PLAN «файл:строка до → "
                            f"файл:строка после» перенесённого утверждения её убийцы")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-18

def test_ac18_plan_names_counts_lines_and_control_run_time():
    """PLAN называет число тестов и строк до и после свода по трём приёмникам и время контрольных прогонов «до» и «после».

    «До» — по базе ветки: число тестов и строк каждого исходного файла
    (19 и 6 тестов) и модуля гейта исходов. «После» — по HEAD: число
    тестовых функций и строк `tests/test_merge_outcome_module.py` и
    `tests/test_outcome_gate_module.py`, число строк
    `tests/merge_outcome_sandbox.py`. Каждое число стоит в PLAN отдельным
    числом; в строках PLAN со словом «контрольн…» длительностей (`<n> с` /
    `мин`) не меньше двух.

    Ловит мутацию: роль записала числа только «до» (или строки модуля до
    последней правки), либо время адресного прогона под ролью вместо
    контрольных прогонов `mutation-run` — тест краснеет с недостающим.
    """
    plan = _ctx.plan_text()

    def named(number: int) -> bool:
        return re.search(rf"(?<![\d.,]){number}(?![\d])", plan) is not None

    def lines(text: str) -> int:
        return text.count("\n")

    wanted = {}
    for path in (*_plan.SOURCE_FILES, _plan.GATE_MODULE):
        text = _ctx.base_text(path)
        tree = ast.parse(text)
        tests = (len(_plan.base_tests(path, text)) if path in _plan.SOURCE_FILES
                 else len(_plan.module_tests(tree)))
        wanted[f"тестов «до» {path}"] = tests
        wanted[f"строк «до» {path}"] = lines(text)
    for path in _plan.TARGETS:
        text = _ctx.head_text(path)
        wanted[f"тестов «после» {path}"] = len(_plan.module_tests(ast.parse(text)))
        wanted[f"строк «после» {path}"] = lines(text)
    wanted[f"строк «после» {_plan.MERGE_SANDBOX}"] = lines(_ctx.head_text(_plan.MERGE_SANDBOX))
    problems = [f"{what} — {n}: в PLAN не названо" for what, n in wanted.items()
                if not named(n)]
    control = [line for line in _plan.prose_lines(plan) if "контрольн" in line.casefold()]
    if sum(len(_DURATION.findall(line)) for line in control) < 2:
        problems.append("в строках PLAN о контрольных прогонах нет двух длительностей "
                        "(«<n> с» / «<n> мин») — «до» и «после»")
    assert not problems, "\n".join(problems)
