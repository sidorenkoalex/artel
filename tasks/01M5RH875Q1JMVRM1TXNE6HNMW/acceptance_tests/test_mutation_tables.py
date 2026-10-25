"""AC-2, AC-3, AC-4, AC-5, AC-14, AC-15, AC-16, AC-17: таблицы
`mutation-run` «до» и «после» в PLAN и их согласованность с набором
патчей, копиями `--copy-table`, строками падения, находками, удалёнными
дублями, соответствием «до → после» и рабочей копией.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после», патчей и свода ещё нет — прогонов mutation-run и свода не было.

Планка сверяет форму и согласованность таблиц: части не длиннее 15
патчей, «до» — `--ref base` на файле волны, «после» — `--ref worktree` на
новом модуле теми же диапазонами и тем же числом рабочих процессов,
таблица в PLAN дословно равна копии `--copy-table`
(`mutation-run-<номер>.tsv` каталога документов), исход каждой мутации
одинаков во всех прогонах, убитую «до» тестом T «после» убивает функция, в
которую перенесён T, у каждой убитой мутации — строка падения «до» и
«после» в утверждении вне методов подготовки и фикстур. Подлинность
прогонов, `Timeout` в логе, «исключение без падения утверждения» и
непрошедшее предусловие сценария по логу — работа независимой проверки
(требование 25 SPEC). Соглашения разбора PLAN — докстринг `_plan.py`.
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT, TASK_ID  # noqa: E402

_DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|секунд[а-я]*|s|мин|min)"
                       r"(?![A-Za-zА-Яа-яЁё])")
_STATUS_CMD = "git status --porcelain -- orchestrator/"
_PORCELAIN_LINE = re.compile(r"^\s*[ MADRCU?!]{1,2}\s+\S*orchestrator/\S*")
_BEFORE, _AFTER = "Мутации до", "Мутации после"
_BEFORE_FILES = (_plan.SOURCE, _plan.MERGE_SANDBOX, _plan.OUTCOME_SANDBOX)
_AFTER_FILES = (_plan.MODULE, _plan.SANDBOX, _plan.MERGE_SANDBOX,
                _plan.OUTCOME_SANDBOX)
_BEFORE_NODE = re.compile("^" + re.escape(_plan.SOURCE) + r"::[A-Za-z_]\w*::test\w*$")
_AFTER_NODE = re.compile("^" + re.escape(_plan.MODULE) + r"::test\w*(?:\[.*\])?$")


def _texts(before: bool) -> dict:
    if before:
        return {p: _ctx.base_text(p) for p in _BEFORE_FILES}
    return {p: _ctx.head_text(p) for p in _AFTER_FILES}


def _assertion_at(tree, line: int):
    found = [n for n in ast.walk(tree) if _plan.is_assertion_node(n)
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


def _site(texts: dict, path: str, line: int, *, strict: bool = False):
    """(цепочка функций, литералы утверждения) для ссылки `path:line`,
    лежащей внутри утверждения; при `strict` — ещё и вне метода подготовки
    и фикстуры; иначе None."""
    text = texts.get(path)
    if text is None:
        return None
    inside, chain = _plan.assertion_site(text, line)
    if not (inside and chain):
        return None
    if strict and _plan.in_preparation(chain):
        return None
    node = _assertion_at(ast.parse(text), line)
    return chain, (_site_literals(node) if node is not None else set())


def _findings(plan: str) -> set:
    found = set()
    for line, hit in _plan.ref_lines(plan):
        if "находк" in line.casefold():
            found |= hit
    for text in _plan.sections(plan, "находк"):
        for _line, hit in _plan.ref_lines(text):
            found |= hit
    return found


def _tables(plan: str):
    return _ctx.section_tables(plan, _BEFORE), _ctx.section_tables(plan, _AFTER)


def _table_problems(found: list, *, ref: str, tests: str, node,
                    parts=None) -> tuple[list, set]:
    """(замечания, номера строк) по таблицам раздела: задача, ревизия,
    тесты, рабочие процессы, сплошной диапазон патчей не длиннее предела,
    строки «# патч» у каждой строки, исходы из словаря команды, узлы
    убийц; при `parts` — пара (диапазон, рабочие процессы) есть среди них."""
    problems, rows = [], set()
    for table in found:
        where = f"таблица №{table.run_no}"
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != ref:
            problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась {ref}")
        if table.tests != [tests]:
            problems.append(f"{where}: тесты {table.tests}, ожидались [{tests}]")
        if not table.workers:
            problems.append(f"{where}: в шапке нет строки «# рабочих процессов: …»")
        numbers = sorted(table.patches)
        if not numbers:
            problems.append(f"{where}: в шапке нет строк «# патч … sha256 …»")
        elif numbers != list(range(numbers[0], numbers[-1] + 1)):
            problems.append(f"{where}: патчи части не сплошной диапазон: {numbers}")
        if len(numbers) > _plan.MAX_PART:
            problems.append(f"{where}: в части {len(numbers)} патчей — больше "
                            f"{_plan.MAX_PART}")
        if parts is not None and (tuple(numbers), table.workers) not in parts:
            problems.append(f"{where}: диапазон {numbers} при рабочих процессах "
                            f"{table.workers!r} — такой части «до» нет")
        for number, outcome, nodes in table.rows:
            rows.add(number)
            if number not in table.patches:
                problems.append(f"{where}: строка мутации {number} без «# патч {number} …»")
            if outcome not in _plan.OUTCOMES:
                problems.append(f"{where}: мутация {number} — исход «{outcome}» не из "
                                f"вывода команды")
            if outcome == _plan.KILLED and (not nodes or any(not node.match(n)
                                                             for n in nodes)):
                problems.append(f"{where}: мутация {number} убита, узлы не вида "
                                f"{tests}::…: {nodes}")
    return problems, rows


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


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_parts_within_limit_every_mutation():
    """Раздел «Мутации до»: таблицы `--ref base` на файле волны частями-диапазонами не длиннее 15 патчей, каждая мутация есть.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно
    `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`,
    `# рабочих процессов: <n>`, строки «# патч … sha256 …». Патчи части —
    сплошной диапазон длиной не больше 15. У каждой строки есть строка
    «# патч» шапки; исход — из словаря команды; у «убита» узлы непусты и
    имеют вид `tests/<файл волны>::<Класс>::<метод>`. Каждая мутация набора
    есть строкой в таблицах раздела.

    Ловит мутацию: роль прогнала «до» одной частью `--patches 1-20`, или с
    `--ref worktree`, или на новом модуле — тест краснеет с таблицей.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    problems, rows = _table_problems(_ctx.section_tables(plan, _BEFORE), ref="base",
                                     tests=_plan.SOURCE, node=_BEFORE_NODE)
    absent = sorted(set(names) - rows)
    if absent:
        problems.append(f"мутаций нет строкой в таблицах «до»: {absent}")
    assert not problems, "\n".join(problems)


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

def _killed_without_site(side: str, strict: bool) -> list:
    plan = _ctx.plan_text()
    before = side == "до"
    tables = _ctx.section_tables(plan, _BEFORE if before else _AFTER)
    texts = _texts(before)
    lines = _plan.ref_lines(plan)
    return [number for number in sorted(_plan.killed(_plan.last_rows(tables)))
            if not any(number in hit and any(
                _site(texts, p, n, strict=strict) for p, n in _plan.file_lines(line))
                for line, hit in lines)]


def test_ac3_each_killed_mutation_names_failed_assertion_line_before():
    """У каждой убитой «до» мутации PLAN называет файл:строку упавшего утверждения.

    Для мутации с последним исходом «убита» в таблицах «до» есть строка
    PLAN вне таблиц, ссылающаяся на мутацию, со ссылкой
    `tests/<файл>.py:<n>`, которая лежит внутри утверждения файла волны,
    `tests/merge_outcome_sandbox.py` или `tests/outcome_gate_sandbox.py`
    базы.

    Ловит мутацию: роль привела строку падения только для «после» (или
    строку вне утверждения — заголовок функции из трассы) — у мутации нет
    годной строки, тест краснеет с номером.
    """
    missing = _killed_without_site("до", strict=False)
    assert not missing, f"убитые «до» мутации без файл:строки утверждения: {missing}"


def test_ac3_each_killed_mutation_names_failed_assertion_line_after():
    """У каждой убитой «после» мутации PLAN называет файл:строку упавшего утверждения.

    Ссылка `tests/<файл>.py:<n>` лежит внутри утверждения нового модуля
    или песочниц (`tests/components_outcome_sandbox.py`,
    `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`) на
    HEAD.

    Ловит мутацию: роль привела для «после» номер строки старого файла
    волны (или не привела строку вовсе) — у мутации нет годной строки,
    тест краснеет с номером.
    """
    missing = _killed_without_site("после", strict=False)
    assert not missing, f"убитые «после» мутации без файл:строки утверждения: {missing}"


# ------------------------------------------------------------------ AC-4

def test_ac4_proof_mutation_fails_outside_preparation_before_and_after():
    """Убитая мутация доказана падением утверждения вне методов подготовки и фикстур — и «до», и «после».

    Для мутации с последним исходом «убита» стороны есть строка PLAN,
    ссылающаяся на неё, с `файл:строкой` в утверждении, которое не внутри
    метода подготовки (`setUp`, `writing_task`, `component_task`,
    `in_dev_task`, `artel_in_dev_task`, `operator_mandate`, `direct_task`,
    `verifying_task`, `rewrite_passed`, `git`) или фикстуры. Утверждение
    помощника исхода `mandate_answer` доказательством считается.

    Ловит мутацию: патч ломает `workspace.ensure`, все тесты падают на
    `assertIsNone(error, …)` в `writing_task`, роль записала эту строку и
    не переписала патч — годной строки нет, тест краснеет с номером.
    """
    lonely = {side: _killed_without_site(side, strict=True) for side in ("до", "после")}
    assert not any(lonely.values()), (
        f"мутации без падения утверждения вне подготовки: {lonely}")


def test_ac4_collection_error_never_counted_killed():
    """Мутация с последним исходом «ошибка сбора, импорта или setup» не засчитана доказательством.

    Для мутации, чья последняя строка «до» или «после» — этот исход (патч не
    переписан), PLAN называет её находкой.

    Ловит мутацию: патч ломает импорт `orchestrator.fsm_advance`, строка
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

    Ловит мутацию: мутацию бывшего `Ac13Ac14GateMandateTest` убивает только
    жребий `broken` — «до» она «не убита», роль повторила часть и записала
    второй прогон («убита»), или «после» она выжила — тест краснеет с
    номером и исходами.
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


# ------------------------------------------------------------------ AC-14

def test_ac14_removed_duplicates_killed_by_kept_test_with_its_literals():
    """Удалённый дубль: его мутации убивает сохраняемый тест того же файла с теми же утверждениями; тест без убитых мутаций не удалён.

    Раздел «…дубл…» PLAN перечисляет удалённые тесты файла волны с
    мутациями. Для каждого: мутаций не меньше одной; каждую из них и каждую
    мутацию, сопоставленную ему в PLAN, «до» кто-то убил; каждую по таблице
    «до» убивает и сохраняемый тест (условие (а)); среди них есть тест,
    убивающий их все, у которого литералы и виды `self.assert*` (по базе
    ветки) покрывают литералы и виды удалённого (условие (б)). Раздела нет
    — дублей нет, проверять нечего.

    Ловит мутацию: удалён как дубль бывший `Ac25TrainingProjectTest`, чью
    мутацию «перепутаны компоненты» «до» убивал только он (у
    `Ac19ForeignPlankTest` нет `assertNotIn`), — тест краснеет с именем дубля.
    """
    plan = _ctx.plan_text()
    removed = _ctx.removed_keys(plan)
    if not removed:
        return
    rows = _plan.last_rows(_ctx.section_tables(plan, _BEFORE))
    proof = _plan.killed(rows)
    tests = _ctx.base_tests()
    killers = {n: {_plan.node_key(x) for x in nodes} for n, nodes in proof.items()}
    claimed = _ctx.mapping(plan, set(_ctx.patch_names()))
    problems = []
    for key, numbers in sorted(removed.items()):
        if key not in tests:
            problems.append(f"{key}: в исходном файле базы такого теста нет")
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
            others = {k for k in killers[number] - {key} - set(removed) if k in tests}
            kept = others if kept is None else kept & others
            if not others:
                problems.append(f"{key}: мутацию {number} не убивает ни один сохраняемый тест")
        lits = _plan.assertion_literals(tests[key].func)
        kinds = _plan.assertion_kinds(tests[key].func)
        covering = [k for k in sorted(kept or ())
                    if lits <= _plan.assertion_literals(tests[k].func)
                    and kinds <= _plan.assertion_kinds(tests[k].func)]
        if not covering:
            problems.append(f"{key}: среди сохраняемых тестов, убивающих {sorted(numbers)}, "
                            f"нет теста с его литералами и видами {sorted(kinds)}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-15

def test_ac15_after_tables_worktree_module_same_ranges_and_workers():
    """Раздел «Мутации после»: `--ref worktree` на новом модуле, те же диапазоны и рабочие процессы, что «до», каждая мутация есть.

    Каждая таблица раздела — задача, `ревизия прогона: worktree <sha>`,
    тесты — ровно `tests/test_outcome_components_module.py`; пара (диапазон
    патчей, `# рабочих процессов`) есть среди пар таблиц «до»; у строк —
    строка «# патч» шапки, исход из словаря команды, у «убита» узлы вида
    `tests/test_outcome_components_module.py::<функция>`. Каждая мутация
    набора есть строкой «после».

    Ловит мутацию: «после» прогнан одной частью `1-20` при частях «до»
    `1-15`/`16-20`, либо с `--workers 4` при «до» по умолчанию, либо на
    старом файле — тест краснеет с таблицей.
    """
    plan = _ctx.plan_text()
    before, after = _tables(plan)
    parts = {(tuple(sorted(t.patches)), t.workers) for t in before}
    problems, rows = _table_problems(after, ref="worktree", tests=_plan.MODULE,
                                     node=_AFTER_NODE, parts=parts)
    absent = sorted(set(_ctx.patch_names()) - rows)
    if absent:
        problems.append(f"мутаций нет в таблицах «после»: {absent}")
    assert not problems, "\n".join(problems)


def test_ac15_after_tables_verbatim_equal_copy_table():
    """Каждая таблица «после» в PLAN дословно, с шапкой и всеми строками, равна своей копии `--copy-table`.

    Ловит мутацию: роль свела в PLAN две части «после» в одну таблицу с
    общей шапкой (или дописала исход руками) — текст раздела не содержит
    копии `mutation-run-<номер>.tsv` подряд, тест краснеет с номером.
    """
    problems = _copy_problems(_ctx.plan_text(), _AFTER)
    assert not problems, "\n".join(problems)


def test_ac15_empty_orchestrator_status_shown_before_each_after_part():
    """Перед каждой таблицей «после» PLAN приводит пустой вывод `git status --porcelain -- orchestrator/`.

    В разделе «Мутации после» между концом предыдущей таблицы (или началом
    раздела) и шапкой каждой таблицы стоит команда `git status --porcelain
    -- orchestrator/`, и между её последним вхождением и шапкой нет строки
    вывода porcelain с путём `orchestrator/…`.

    Ловит мутацию: роль привела проверку только перед первой частью
    «после», или перенесла вывод ` M orchestrator/fsm_advance.py` — тест
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


def test_ac15_same_orchestrator_tree_across_all_header_revisions():
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


def test_ac15_patch_sha256_same_in_before_and_after_headers():
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


# ------------------------------------------------------------------ AC-16

def _functions_of(key: str, tests: dict, funcs: dict, transfer: dict) -> set:
    test = tests[key]
    return {f.name for f in _ctx.matches(funcs, test.cls, test.func.name, transfer)}


def test_ac16_mutation_killed_before_by_t_killed_after_by_function_of_t():
    """Мутацию, убитую «до» тестом T, «после» убивает функция, в которую перенесён T.

    Каждый тест файла волны, не перечисленный удалённым дублем,
    сопоставлен функции нового модуля на HEAD (по имени или по
    соответствию «до → после» PLAN). Для каждой мутации с последним исходом
    «до» «убита» и каждого её убийцы «до» T (не удалённого дублем) последний
    исход «после» — «убита», и среди убийц «после» есть узел функции T.

    Ловит мутацию: бывший `test_ac17_first_refusal_names_component` при
    своде потерял `assert broken in refused[-1], …` — мутацию, которую «до»
    убивал он, «после» никто не убил (или убила только соседняя функция) —
    тест краснеет с номером и T.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    removed = set(_ctx.removed_keys(plan))
    transfer = _plan.transfer_map(plan)
    funcs = _ctx.module_functions()
    problems, funcs_of = [], {}
    for key in sorted(tests):
        if key in removed:
            continue
        funcs_of[key] = _functions_of(key, tests, funcs, transfer)
        if not funcs_of[key]:
            problems.append(f"{key}: функции нового модуля нет (ни по имени, ни по PLAN)")
    before, after = _tables(plan)
    after_rows = _plan.last_rows(after)
    for number, nodes in sorted(_plan.killed(_plan.last_rows(before)).items()):
        outcome, after_nodes = after_rows.get(number, ("<нет строки>", []))
        killers = {_plan.after_node_parts(n)[1] for n in after_nodes} \
            if outcome == _plan.KILLED else set()
        for key in sorted({_plan.node_key(n) for n in nodes}):
            if key in removed or key not in funcs_of:
                continue
            if not funcs_of[key] & killers:
                problems.append(f"мутация {number}: «до» её убил {key}, «после» его "
                                f"функции {sorted(funcs_of[key])} не среди убийц "
                                f"«{outcome}» {sorted(killers)}")
    assert not problems, "\n".join(problems)


def test_ac16_plan_maps_failure_line_before_to_after_with_same_check():
    """Для каждой убитой «до» мутации PLAN даёт соответствие «файл:строка до → файл:строка после» перенесённого утверждения.

    Есть строка PLAN вне таблиц, ссылающаяся на мутацию, со ссылкой «до»
    (файл волны базы) внутри утверждения теста T — одного из её убийц «до»
    — или помощника исхода `mandate_answer`, и ссылкой «после» (новый
    модуль на HEAD) внутри утверждения функции, в которую перенесён T, или
    функции `mandate_answer`; литералы проверяемой части утверждения
    «после» содержат литералы утверждения «до».

    Ловит мутацию: роль назвала строкой «после» утверждение чужой функции
    (`assert box.state(t) == "verifying"` вместо перенесённого
    `assert box.records(rows, BROKEN_ACTION) == []`), или не привела пары
    строк — тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    tests = _ctx.base_tests()
    transfer = _plan.transfer_map(plan)
    funcs = _ctx.module_functions()
    before, _after = _tables(plan)
    btexts = {_plan.SOURCE: _ctx.base_text(_plan.SOURCE)}
    atexts = {_plan.MODULE: _ctx.head_text(_plan.MODULE)}
    lines = _plan.ref_lines(plan)
    problems = []
    for number, nodes in sorted(_plan.killed(_plan.last_rows(before)).items()):
        killers = {_plan.node_key(n) for n in nodes} & set(tests)
        ok = False
        for line, hit in lines:
            if number not in hit:
                continue
            refs = _plan.file_lines(line)
            for key in killers:
                targets = _functions_of(key, tests, funcs, transfer)
                method = tests[key].func.name
                for bp, bn in refs:
                    bsite = _site(btexts, bp, bn)
                    if not bsite or bsite[0][-1].name not in (method, *_plan.OUTCOME_HELPERS):
                        continue
                    for ap, an in refs:
                        asite = _site(atexts, ap, an)
                        if asite and asite[0][0].name in targets | set(_plan.OUTCOME_HELPERS) \
                                and bsite[1] <= asite[1]:
                            ok = True
        if not ok:
            problems.append(f"мутация {number}: нет строки PLAN «файл:строка до → "
                            f"файл:строка после» перенесённого утверждения её убийцы")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-17

def test_ac17_plan_names_counts_lines_and_control_run_time():
    """PLAN называет число тестов и строк до и после свода и время контрольных прогонов «до» и «после».

    «До» — по базе ветки: число тестов (17) и строк файла волны. «После» —
    по HEAD: число тестовых функций и строк
    `tests/test_outcome_components_module.py`. Каждое число стоит в PLAN
    отдельным числом; в строках PLAN со словом «контрольн…» длительностей
    (`<n> с` / `мин`) не меньше двух.

    Ловит мутацию: роль записала числа только «до» (или строки модуля до
    последней правки), либо время адресного прогона под ролью вместо
    контрольных прогонов `mutation-run` — тест краснеет с недостающим.
    """
    plan = _ctx.plan_text()

    def named(number: int) -> bool:
        return re.search(rf"(?<![\d.,]){number}(?![\d])", plan) is not None

    source = _ctx.base_text(_plan.SOURCE)
    module = _ctx.head_text(_plan.MODULE)
    wanted = {
        f"тестов «до» {_plan.SOURCE}": len(_plan.base_tests(_plan.SOURCE, source)),
        f"строк «до» {_plan.SOURCE}": source.count("\n"),
        f"тестов «после» {_plan.MODULE}": len(_plan.module_tests(ast.parse(module))),
        f"строк «после» {_plan.MODULE}": module.count("\n"),
    }
    problems = [f"{what} — {n}: в PLAN не названо" for what, n in wanted.items()
                if not named(n)]
    control = [line for line in _plan.prose_lines(plan) if "контрольн" in line.casefold()]
    if sum(len(_DURATION.findall(line)) for line in control) < 2:
        problems.append("в строках PLAN о контрольных прогонах нет двух длительностей "
                        "(«<n> с» / «<n> мин») — «до» и «после»")
    assert not problems, "\n".join(problems)
