"""AC-2, AC-3, AC-4, AC-11, AC-12, AC-13: таблицы `mutation-run` «до» и
«после» в PLAN и их согласованность с набором патчей, копиями
`--copy-table`, отметками падений подготовки, упавшими утверждениями,
находками, удалёнными дублями, соответствием имён «до → после» и рабочей
копией.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после», патчей и свода в tests/test_outcome_gate_module.py ещё нет — прогонов mutation-run и свода не было.

Планка сверяет форму и согласованность таблиц: каждая мутация в таблицах
обеих сторон, части не длиннее предела, «после» — теми же диапазонами и
тем же числом рабочих процессов, таблица в PLAN дословно равна копии
`--copy-table` (`mutation-run-<номер>.tsv` каталога документов), убитую
«до» тестом T «после» убивает функция, в которую перенесён T, у каждой
убитой мутации — строка падения «до» и «после» (решение Оператора
ANSWER-1, п. 2). Подлинность прогонов и верность отметки «убита только
падением подготовки» — работа независимой проверки (требование 17 SPEC).
Соглашения разбора PLAN — докстринг `_plan.py`.
"""
import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, artifact_text)

_BEFORE_NODE = re.compile(
    r"^(?:" + "|".join(re.escape(p) for p in _plan.SOURCE_FILES)
    + r")::[A-Za-z_]\w*::test\w*$")
_AFTER_NODE = re.compile(
    r"^" + re.escape(_plan.NEW_FILE) + r"::test\w*(?:\[.*\])?$")
_DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|секунд[а-я]*|s|мин|min)"
                       r"(?![A-Za-zА-Яа-яЁё])")
_STATUS_CMD = "git status --porcelain -- orchestrator/"
_PORCELAIN_LINE = re.compile(r"^\s*[ MADRCU?!]{1,2}\s+\S*orchestrator/\S*")
_BEFORE, _AFTER = "Мутации до", "Мутации после"


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _patch_names() -> dict:
    names = _plan.patch_names(
        _plan.docs_entries(DOCS_REPO, DOCS_REVISION, TASK_ID))
    assert names, "патчей mutation-<nnn>.diff в каталоге документов задачи нет"
    return names


def _section_text(plan: str, title: str) -> str:
    texts = _plan.sections(plan, title)
    assert texts, f"в PLAN нет раздела «{title}»"
    return "\n".join(texts)


def _section_tables(plan: str, title: str) -> list:
    found, errors = _plan.tables(_section_text(plan, title))
    assert not errors, f"раздел «{title}»: " + "; ".join(errors)
    assert found, (f"в разделе «{title}» нет ни одной таблицы mutation-run "
                   f"(шапка «# mutation-run №…», колонки номер/исход/узлы)")
    return found


def _base_texts(paths=(*_plan.SOURCE_FILES, _plan.SANDBOX_FILE)) -> dict:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    texts = {}
    for path in paths:
        text = _plan.show(CODE_ROOT, DIFF_BASE, path)
        assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
        texts[path] = text
    return texts


def _base_tests() -> dict:
    tests = {}
    for path, text in _base_texts(_plan.SOURCE_FILES).items():
        for test in _plan.base_tests(path, text):
            tests[test.key] = test
    return tests


def _new_text() -> str:
    text = _plan.show(CODE_ROOT, "HEAD", _plan.NEW_FILE)
    assert text is not None, f"{_plan.NEW_FILE} нет в HEAD ветки"
    return text


def _setup_lines(plan: str) -> list:
    return [line for line in _plan.prose_lines(plan)
            if "setUp" in line or "подготовк" in line.casefold()]


def _setup_before(plan: str) -> dict:
    """{номер мутации: ключи узлов «до», убитых падением подготовки}."""
    marked = defaultdict(set)
    for line in _setup_lines(plan):
        for number in _plan.refs(line):
            marked[number] |= _plan.test_keys(line)
    return marked


def _setup_after(plan: str) -> dict:
    """{номер мутации: отметки узлов «после» (функция, вариант)}."""
    marked = defaultdict(set)
    for line in _setup_lines(plan):
        for number in _plan.refs(line):
            marked[number] |= _plan.after_refs(line)
    return marked


def _mentioned_as_finding(plan: str) -> set:
    found = set()
    for line in _plan.prose_lines(plan):
        if "находк" in line.casefold():
            found |= _plan.refs(line)
    for text in _plan.sections(plan, "находк"):
        for line in _plan.prose_lines(text):
            found |= _plan.refs(line)
    return found


def _removed_duplicates(plan: str) -> dict:
    """{ключ теста: номера мутаций} из строк разделов «…дубл…»."""
    removed = defaultdict(set)
    for text in _plan.sections(plan, "дубл"):
        for line in _plan.prose_lines(text):
            for key in _plan.test_keys(line):
                removed[key] |= _plan.refs(line)
    return removed


def _collect_new_nodes() -> set:
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", _plan.NEW_FILE],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=600)
    assert res.returncode == 0, (f"сбор {_plan.NEW_FILE} не прошёл "
                                 f"(код {res.returncode}):\n{res.stdout[-3000:]}"
                                 f"\n{res.stderr[-2000:]}")
    return {line.strip() for line in res.stdout.splitlines()
            if line.strip().startswith(_plan.NEW_FILE + "::")}


def _assertion_at(tree, line: int):
    """Самый внутренний узел утверждения, охватывающий строку `line`."""
    found = [n for n in ast.walk(tree) if _plan._is_assertion_node(n)
             and n.lineno <= line <= (n.end_lineno or n.lineno)]
    return min(found, key=lambda n: (n.end_lineno or n.lineno) - n.lineno,
               default=None)


def _site_literals(node) -> set:
    """Литералы смысловой части утверждения: проверяемое выражение
    `assert` или смысловые аргументы `<что-то>.assert*`."""
    if isinstance(node, ast.Assert):
        return _plan.constants(node.test)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr.startswith("assert"):
        return set().union(*[_plan.constants(a)
                             for a in _plan.semantic_args(node)] or [set()])
    return set().union(*[_plan.constants(a) for a in node.args] or [set()])


def _site(texts: dict, path: str, line: int):
    """(цепочка функций, литералы утверждения) для ссылки `path:line`,
    указывающей на утверждение вне `setUp`, метода подготовки песочницы и
    фикстуры; иначе None."""
    text = texts.get(path)
    if text is None:
        return None
    inside, chain = _plan.assertion_site(text, line)
    if not (inside and chain) or _plan.in_preparation(chain):
        return None
    node = _assertion_at(ast.parse(text), line)
    return chain, (_site_literals(node) if node is not None else set())


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_source_file_parts_within_limit():
    """Раздел «Мутации до»: таблицы `--ref base` на исходном файле частями-диапазонами не длиннее предела.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно исходный файл,
    `# рабочих процессов: <n>`, строки «# патч … sha256 …». Патчи части —
    сплошной диапазон номеров длиной не больше 15, а при 4 рабочих
    процессах — не больше 7. У каждой строки есть строка «# патч» шапки её
    таблицы; исход — из словаря команды; у «убита» узлы непусты и имеют вид
    `tests/<исходный файл>::<Класс>::<метод>`. Каждая мутация набора есть
    строкой в таблицах раздела.

    Ловит мутацию: роль прогнала «до» одной частью `--patches 1-30` (или
    повтор при `--workers 4` частью `1-10`), перенесла вывод без строк
    части мутаций либо прогнала «до» с `--ref worktree` — длина части,
    ревизия или состав строк расходятся, тест краснеет.
    """
    plan = _plan_text()
    names = _patch_names()
    found = _section_tables(plan, _BEFORE)
    problems = []
    for table in found:
        where = f"таблица №{table.run_no}"
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != "base":
            problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась base")
        if sorted(table.tests) != sorted(_plan.SOURCE_FILES):
            problems.append(f"{where}: тесты {table.tests}, ожидались "
                            f"{list(_plan.SOURCE_FILES)}")
        if not table.workers:
            problems.append(f"{where}: в шапке нет строки «# рабочих процессов: …»")
        numbers = sorted(table.patches)
        if not numbers:
            problems.append(f"{where}: в шапке нет строк «# патч … sha256 …»")
        elif numbers != list(range(numbers[0], numbers[-1] + 1)):
            problems.append(f"{where}: патчи части не сплошной диапазон: {numbers}")
        limit = _plan.MAX_PART_WORKERS_4 if table.workers == "4" else _plan.MAX_PART
        if len(numbers) > limit:
            problems.append(f"{where}: в части {len(numbers)} патчей при "
                            f"рабочих процессах {table.workers!r} — больше {limit}")
        for number, outcome, nodes in table.rows:
            if number not in table.patches:
                problems.append(f"{where}: строка мутации {number} без строки "
                                f"«# патч {number} …» в шапке")
            if outcome not in _plan.OUTCOMES:
                problems.append(f"{where}: мутация {number} — исход «{outcome}» "
                                f"не из вывода команды")
            if outcome == _plan.KILLED:
                bad = [n for n in nodes if not _BEFORE_NODE.match(n)]
                if not nodes or bad:
                    problems.append(f"{where}: мутация {number} убита, узлы "
                                    f"не вида tests/<файл>::<Класс>::<метод>: "
                                    f"{nodes}")
    absent = sorted(set(names) - set(_plan.last_rows(found)))
    if absent:
        problems.append(f"мутаций набора нет строкой в таблицах «до»: {absent}")
    assert not problems, "\n".join(problems)


def _copy_problems(plan: str, title: str) -> list:
    """Таблицы раздела, не равные дословно своей копии `--copy-table`."""
    text = _section_text(plan, title)
    found, errors = _plan.tables(text)
    assert not errors, f"раздел «{title}»: " + "; ".join(errors)
    assert found, f"в разделе «{title}» нет таблиц mutation-run"
    problems = []
    for run_no in sorted({t.run_no for t in found}):
        name = f"mutation-run-{run_no}.tsv"
        copy = artifact_text(name)
        if copy is None:
            problems.append(f"«{title}», таблица №{run_no}: копии {name} "
                            f"(--copy-table) в каталоге документов нет")
            continue
        block = copy.rstrip("\n").split("\n")
        if not _plan.contains_block(text, block):
            problems.append(f"«{title}», таблица №{run_no}: в разделе нет "
                            f"дословного текста копии {name} (шапка и все "
                            f"{len(block)} строк подряд)")
    return problems


def test_ac2_before_tables_verbatim_equal_copy_table():
    """Каждая таблица «до» в PLAN дословно, с шапкой и всеми строками, равна своей копии `--copy-table`.

    Для каждого номера прогона таблиц раздела «Мутации до» в каталоге
    документов есть копия `mutation-run-<номер>.tsv`, и все её строки стоят
    в разделе подряд без изменений.

    Ловит мутацию: роль перенесла вывод `--wait` без части строк «# патч»
    (или переписала исход «итог неизвестен» как «убита»), либо прогнала
    часть без `--copy-table` — текст раздела расходится с копией или копии
    нет, тест краснеет с номером прогона.
    """
    problems = _copy_problems(_plan_text(), _BEFORE)
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-3

def test_ac3_each_killed_mutation_names_failed_assertion_before_and_after():
    """У каждой убитой мутации PLAN называет файл:строку упавшего утверждения «до» и «после».

    «До»: для мутации с последним исходом «до» «убита» есть строка PLAN вне
    таблиц со ссылкой на мутацию, ключом `<Класс>::<метод>` одного из её
    убийц «до» T и ссылкой `tests/<файл>.py:<строка>`, которая в базе
    ветки (исходный файл или `tests/outcome_gate_sandbox.py`) лежит внутри
    утверждения и не внутри `setUp`, метода подготовки или фикстуры.
    «После» (решение Оператора ANSWER-1, п. 2): если «после» она убита, есть
    строка со ссылкой на мутацию, узлом её убийцы «после» — функции, в
    которую перенесён T по соответствию PLAN, — и ссылкой
    `tests/test_outcome_gate_module.py:<строка>`, которая на HEAD лежит в
    утверждении этой функции или помощника исхода (`refusal`,
    `no_gate_refusal`, `assert_no_gate`, `assert_prepare`), и литералы
    проверяемой части этого утверждения содержат литералы утверждения «до»
    (двойник по тексту).

    Ловит мутацию: роль назвала строкой падения «до» утверждение
    подготовки `OutcomeGateSandbox.in_dev_task`, или «после» привела
    строку утверждения чужой функции (`assert box.state(t) == "in_dev"`
    вместо перенесённого `assertIn("стал красным", …)`), или не привела
    файл:строку из лога — у мутации нет годной строки, тест краснеет с
    номером.
    """
    plan = _plan_text()
    base_texts = _base_texts()
    head_texts = {_plan.NEW_FILE: _new_text()}
    mapping = _plan.transfer_map(plan)
    before = _plan.killed(_plan.last_rows(_section_tables(plan, _BEFORE)))
    after = _plan.killed(_plan.last_rows(_section_tables(plan, _AFTER)))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        killers = {_plan.node_key(n) for n in nodes}
        sites = []  # (T, литералы утверждения «до»)
        for line in lines:
            if number not in _plan.refs(line):
                continue
            keys = _plan.test_keys(line) & killers
            for path, n in _plan.file_lines(line):
                site = _site(base_texts, path, n)
                if site and keys:
                    sites += [(key, site[1]) for key in keys]
        if not sites:
            problems.append(f"мутация {number} «до»: нет строки PLAN с её "
                            f"убийцей из {sorted(killers)} и файл:строка "
                            f"упавшего утверждения вне подготовки")
            continue
        if number not in after:
            continue  # отсутствие убийцы «после» — предмет AC-12
        after_nodes = after[number]
        ok_after = False
        for line in lines:
            if number not in _plan.refs(line):
                continue
            named = {_plan.after_node_parts(n)[0] for n in after_nodes
                     if _plan.after_marked(n, _plan.after_refs(line))}
            for key, lits in sites:
                funcs = mapping.get(key, set()) & named
                if not funcs:
                    continue
                for path, n in _plan.file_lines(line):
                    site = _site(head_texts, path, n)
                    if site is None:
                        continue
                    chain, after_lits = site
                    owner = chain[0].name
                    if (owner in funcs or owner in _plan.OUTCOME_HELPERS) \
                            and lits <= after_lits:
                        ok_after = True
        if not ok_after:
            problems.append(f"мутация {number} «после»: нет строки PLAN с её "
                            f"убийцей из {after_nodes} — функцией, в которую "
                            f"перенесён убийца «до», — и файл:строка "
                            f"{_plan.NEW_FILE} утверждения этой функции (или "
                            f"помощника исхода) с литералами утверждения «до»")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-4

def test_ac4_collection_error_never_counted_killed():
    """Мутация с последним исходом «ошибка сбора, импорта или setup» не засчитана доказательством.

    Для мутации, чья последняя строка «до» или «после» — этот исход
    (патч не переписан), PLAN называет её находкой: в доказательство
    убитых она не входит.

    Ловит мутацию: патч ломает импорт `orchestrator.advance_gates.
    outcome_integrity`, строка таблицы — «ошибка сбора, импорта или
    setup», а роль сослалась на неё как на убитую и не переписала патч —
    мутация не убита и не находка, тест краснеет с номером.
    """
    plan = _plan_text()
    before = _plan.last_rows(_section_tables(plan, _BEFORE))
    after = _plan.last_rows(_section_tables(plan, _AFTER))
    collection = sorted({n for rows in (before, after)
                         for n, (outcome, _nodes) in rows.items()
                         if outcome == _plan.COLLECTION})
    unlisted = sorted(set(collection) - _mentioned_as_finding(plan))
    assert not unlisted, (
        f"мутации с последним исходом «{_plan.COLLECTION}» не переписаны и не "
        f"названы находками: {unlisted}")


def test_ac4_each_proof_mutation_has_killer_outside_setup_marks_before_and_after():
    """У каждой мутации доказательства есть убийца вне отметки падений подготовки — «до» и «после».

    Доказательство — мутации, чья последняя строка «до» — «убита» с узлами.
    Отметка — строки PLAN со словом `setUp`/«подготовк…» и ссылкой на
    мутацию: для «до» — ключи `<Класс>::<метод>`, для «после» — ссылки
    `test_outcome_gate_module.py::<функция>[<вариант>]`. Для каждой мутации
    доказательства хотя бы один убивший узел «до» и хотя бы один убивший
    узел «после» под отметку не попадают.

    Ловит мутацию: патч ломает `OutcomeGateSandbox.in_dev_task` (утверждение
    подготовки роняет все тесты «до»), роль честно отметила эти узлы
    падением подготовки, но не переписала патч: у мутации не остаётся
    убийцы вне отметки, тест краснеет с номером.
    """
    plan = _plan_text()
    before = _plan.killed(_plan.last_rows(_section_tables(plan, _BEFORE)))
    after = _plan.last_rows(_section_tables(plan, _AFTER))
    marked_before, marked_after = _setup_before(plan), _setup_after(plan)
    lonely = []
    for number, nodes in sorted(before.items()):
        keys = {_plan.node_key(n) for n in nodes}
        if not keys - marked_before.get(number, set()):
            lonely.append(f"мутация {number} «до»: все убийцы {sorted(keys)} — "
                          f"в отметке падений подготовки")
        outcome, after_nodes = after.get(number, ("<нет строки>", []))
        if outcome != _plan.KILLED or not after_nodes:
            continue  # отсутствие убийцы «после» — предмет AC-12
        marks = marked_after.get(number, set())
        if all(_plan.after_marked(n, marks) for n in after_nodes):
            lonely.append(f"мутация {number} «после»: все убийцы {after_nodes} — "
                          f"в отметке падений подготовки")
    assert not lonely, "\n".join(lonely)


def test_ac4_survived_before_listed_as_findings():
    """Мутации, не убитые «до» никем, перечислены в PLAN находками.

    Для каждой мутации с последним исходом «до» — «не убита» в PLAN есть
    ссылка на неё в строке со словом «находк…» либо в разделе, в заголовке
    которого это слово есть.

    Ловит мутацию: роль молча оставила в наборе патч, который «до» никто
    не убил (как 011 и 027 заготовки 2а-1), и не записала его находкой —
    номер мутации не найден среди находок, тест краснеет.
    """
    plan = _plan_text()
    rows = _plan.last_rows(_section_tables(plan, _BEFORE))
    survived = sorted(n for n, (outcome, _nodes) in rows.items()
                      if outcome == _plan.SURVIVED)
    unlisted = sorted(set(survived) - _mentioned_as_finding(plan))
    assert not unlisted, (f"мутации, не убитые «до», не перечислены "
                          f"находками: {unlisted}")


def test_ac4_limit_outcome_neither_killed_nor_survived():
    """Мутация с последним исходом «оборвана по пределу»/«не прогнана (предел)» не засчитана ни убитой, ни выжившей.

    Для мутации, чья последняя строка «до» или «после» — исход предела,
    PLAN не называет её находкой (выжившей); убитой она не считается по
    разбору таблиц (доказательство — только последний исход «убита»).

    Ловит мутацию: прогон «до» оборвался по пределу, роль записала
    оборванную мутацию находкой («никто не убил») и не перепрогнала её
    меньшим диапазоном — номер найден среди находок, тест краснеет.
    """
    plan = _plan_text()
    before = _plan.last_rows(_section_tables(plan, _BEFORE))
    after = _plan.last_rows(_section_tables(plan, _AFTER))
    limited = sorted({n for rows in (before, after)
                      for n, (outcome, _nodes) in rows.items()
                      if outcome in _plan.LIMIT_OUTCOMES})
    as_findings = sorted(set(limited) & _mentioned_as_finding(plan))
    assert not as_findings, (f"мутации с исходом предела названы находками "
                             f"(выжившими): {as_findings}")


# ------------------------------------------------------------------ AC-11

def test_ac11_removed_duplicates_killed_by_kept_test_with_its_literals():
    """Удалённый дубль: его мутации убивает сохраняемый тест с теми же утверждениями.

    Раздел «…дубл…» PLAN перечисляет удалённые тесты исходного файла с
    мутациями. Для каждого: мутаций не меньше одной; каждую по таблице «до»
    убивает и сохраняемый тест (условие (а)); среди сохраняемых есть тест,
    убивающий их все, у которого литералы и виды `self.assert*` (по базе
    ветки) покрывают литералы и виды удалённого (условие (б)). Ни одна
    мутация, сопоставленная удалённому тесту в PLAN, не осталась «до»
    неубитой.

    Ловит мутацию: удалён как дубль тест, чью мутацию «до» убивал только он
    сам, или тест с `assertIn("стал красным", …)`, литерала которого нет у
    оставленного соседа, — тест краснеет с именем дубля.
    """
    plan = _plan_text()
    rows = _plan.last_rows(_section_tables(plan, _BEFORE))
    proof = _plan.killed(rows)
    removed = _removed_duplicates(plan)
    tests = _base_tests()
    killers = {n: {_plan.node_key(x) for x in nodes} for n, nodes in proof.items()}
    claimed = defaultdict(set)
    for line in _plan.prose_lines(plan):
        for key in _plan.test_keys(line):
            claimed[key] |= _plan.refs(line)
    problems = []
    for key, numbers in sorted(removed.items()):
        if key not in tests:
            problems.append(f"{key}: в исходном файле базы такого теста нет")
            continue
        if not numbers:
            problems.append(f"{key}: удалён без перечня своих мутаций")
            continue
        unkilled = sorted(n for n in claimed[key] | numbers if n not in proof)
        if unkilled:
            problems.append(f"{key}: удалён, а его мутации {unkilled} «до» не "
                            f"убиты никем")
            continue
        kept = None
        for number in numbers:
            others = killers[number] - {key} - set(removed)
            kept = others if kept is None else kept & others
            if not others:
                problems.append(f"{key}: мутацию {number} не убивает ни один "
                                f"сохраняемый тест")
        lits = _plan.assertion_literals(tests[key].func)
        kinds = _plan.assertion_kinds(tests[key].func)
        covering = [k for k in sorted(kept or ()) if k in tests
                    and lits <= _plan.assertion_literals(tests[k].func)
                    and kinds <= _plan.assertion_kinds(tests[k].func)]
        if not covering:
            problems.append(f"{key}: среди сохраняемых тестов, убивающих "
                            f"{sorted(numbers)}, нет теста с его литералами "
                            f"{sorted(map(repr, lits))} и видами {sorted(kinds)}")
    assert not problems, "\n".join(problems)


def test_ac11_every_untransferred_test_listed_as_removed_duplicate():
    """Узлов нового файла не меньше, чем тестов модуля на базе плюс 42 исходных минус перечисленные дубли.

    Сбор `pytest --collect-only` нового файла даёт число узлов; каждый
    тест модуля на базе и каждый перенесённый исходный тест дают хотя бы
    один узел. Тест, пропавший при своде без записи в PLAN удалённым
    дублем, это число нарушает.

    Ловит мутацию: при своде тест исходного файла потерян (не перенесён и
    не записан дублем) — узлов нового файла меньше ожидаемого минимума,
    тест краснеет с обоими числами.
    """
    plan = _plan_text()
    tests = _base_tests()
    removed = set(_removed_duplicates(plan)) & set(tests)
    base_module = _plan.show(CODE_ROOT, DIFF_BASE, _plan.NEW_FILE)
    assert base_module is not None, f"{_plan.NEW_FILE} нет в базе ветки"
    base_count = len(_plan.module_tests(ast.parse(base_module)))
    nodes = _collect_new_nodes()
    expected_min = base_count + len(tests) - len(removed)
    assert len(nodes) >= expected_min, (
        f"в {_plan.NEW_FILE} узлов {len(nodes)}, а тестов модуля на базе "
        f"{base_count} плюс исходных {len(tests)} минус удалённых дублей "
        f"{len(removed)} = {expected_min}: не перенесённый тест не записан в "
        f"PLAN удалённым дублем")


# ------------------------------------------------------------------ AC-12

def test_ac12_after_tables_worktree_same_ranges_and_workers_every_mutation():
    """Раздел «Мутации после»: `--ref worktree` на модуле, те же диапазоны и рабочие процессы, что «до», каждая мутация есть.

    Каждая таблица раздела — задача, `ревизия прогона: worktree <sha>`,
    тесты — только `tests/test_outcome_gate_module.py`; пара (диапазон
    патчей шапки, `# рабочих процессов`) есть среди пар таблиц «до»; у
    строк — строка «# патч» шапки, исход из словаря команды, у «убита»
    узлы вида `tests/test_outcome_gate_module.py::<функция>[<вариант>]`.
    Каждая мутация набора есть строкой «после»; у каждой мутации, убитой
    «до», последний исход «после» — «убита» с узлами.

    Ловит мутацию: при своде из теста выпало утверждение, которое одно
    убивало мутацию, — «после» она «не убита»; или «после» прогнан одной
    частью `1-30` при частях «до» `1-15`/`16-30`, либо с `--workers 4` при
    «до» по умолчанию — тест краснеет с номером, диапазоном или ревизией.
    """
    plan = _plan_text()
    names = _patch_names()
    before_tables = _section_tables(plan, _BEFORE)
    before = _plan.last_rows(before_tables)
    after_tables = _section_tables(plan, _AFTER)
    parts = {(tuple(sorted(t.patches)), t.workers) for t in before_tables}
    problems = []
    for table in after_tables:
        where = f"таблица «после» №{table.run_no}"
        if table.task != TASK_ID:
            problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
        if table.ref != "worktree":
            problems.append(f"{where}: ревизия прогона {table.ref}, "
                            f"ожидалась worktree")
        if table.tests != [_plan.NEW_FILE]:
            problems.append(f"{where}: тесты {table.tests}, ожидался "
                            f"[{_plan.NEW_FILE!r}]")
        part = (tuple(sorted(table.patches)), table.workers)
        if part not in parts:
            problems.append(f"{where}: диапазон {list(part[0])} при рабочих "
                            f"процессах {part[1]!r} — такой части «до» нет")
        for number, outcome, nodes in table.rows:
            if number not in table.patches:
                problems.append(f"{where}: строка мутации {number} без строки "
                                f"«# патч {number} …» в шапке")
            if outcome not in _plan.OUTCOMES:
                problems.append(f"{where}: мутация {number} — исход «{outcome}» "
                                f"не из вывода команды")
            if outcome == _plan.KILLED and (
                    not nodes or any(not _AFTER_NODE.match(n) for n in nodes)):
                problems.append(f"{where}: мутация {number} убита, узлы не вида "
                                f"{_plan.NEW_FILE}::<функция>[<вариант>]: {nodes}")
    after = _plan.last_rows(after_tables)
    for number in sorted(names):
        if number not in after:
            problems.append(f"мутации {number} нет в таблицах «после»")
    for number in sorted(_plan.killed(before)):
        outcome, nodes = after.get(number, ("<нет строки>", []))
        if outcome != _plan.KILLED or not nodes:
            problems.append(f"мутация {number} убита «до», а «после» — "
                            f"«{outcome}» {nodes}")
    assert not problems, "\n".join(problems)


def test_ac12_after_tables_verbatim_equal_copy_table():
    """Каждая таблица «после» в PLAN дословно, с шапкой и всеми строками, равна своей копии `--copy-table`.

    Ловит мутацию: роль свела в PLAN две части «после» в одну таблицу с
    общей шапкой (или дописала исход руками) — текст раздела не содержит
    копии `mutation-run-<номер>.tsv` подряд, тест краснеет с номером.
    """
    problems = _copy_problems(_plan_text(), _AFTER)
    assert not problems, "\n".join(problems)


def test_ac12_mutation_killed_before_by_t_killed_after_by_function_of_t():
    """Мутацию, убитую «до» тестом T, «после» убивает функция, в которую перенесён T.

    Соответствие «до → после» — строки PLAN вне таблиц со ссылкой на тест
    исходного файла `<Класс>::<метод>` и на функцию
    `test_outcome_gate_module.py::<функция>`. Каждый тест исходного файла
    базы, не перечисленный удалённым дублем, сопоставлен хотя бы одной
    функции, и она есть в новом файле на HEAD. Для каждой мутации с
    последним исходом «до» «убита» и каждого её убийцы «до» T (вне
    отметки падений подготовки и не удалённого дублем) среди убийц
    «после» вне отметки подготовки есть узел функции, сопоставленной T.

    Ловит мутацию: тест `Ac4PrepareTest::…` при своде потерял подслучай
    «выписка головы» — мутацию, которую «до» убивал он, «после» убивает
    только соседняя функция; или PLAN не приводит соответствия имён — тест
    краснеет с номером и именем T.
    """
    plan = _plan_text()
    tests = _base_tests()
    removed = set(_removed_duplicates(plan))
    mapping = _plan.transfer_map(plan)
    new_funcs = {f.name for f in _plan.module_tests(ast.parse(_new_text()))}
    problems = []
    for key in sorted(tests):
        if key in removed:
            continue
        funcs = mapping.get(key, set())
        if not funcs:
            problems.append(f"{key}: в PLAN нет соответствия «до → после» "
                            f"(строки с ним и {_plan.NEW_FILE}::<функция>)")
        elif not funcs & new_funcs:
            problems.append(f"{key}: сопоставленных функций {sorted(funcs)} в "
                            f"{_plan.NEW_FILE} нет")
    before = _plan.killed(_plan.last_rows(_section_tables(plan, _BEFORE)))
    after = _plan.last_rows(_section_tables(plan, _AFTER))
    marked_before, marked_after = _setup_before(plan), _setup_after(plan)
    for number, nodes in sorted(before.items()):
        outcome, after_nodes = after.get(number, ("<нет строки>", []))
        marks = marked_after.get(number, set())
        killers_after = {_plan.after_node_parts(n)[0] for n in after_nodes
                         if outcome == _plan.KILLED
                         and not _plan.after_marked(n, marks)}
        for key in sorted({_plan.node_key(n) for n in nodes}):
            if key in marked_before.get(number, set()) or key in removed:
                continue
            funcs = mapping.get(key, set())
            if funcs and not funcs & killers_after:
                problems.append(f"мутация {number}: «до» её убил {key}, а "
                                f"«после» её функции {sorted(funcs)} не среди "
                                f"убийц {sorted(killers_after)}")
    assert not problems, "\n".join(problems)


def test_ac12_empty_orchestrator_status_shown_before_each_after_part():
    """Перед каждой таблицей «после» PLAN приводит пустой вывод `git status --porcelain -- orchestrator/`.

    В разделе «Мутации после» между концом предыдущей таблицы (или началом
    раздела) и шапкой каждой таблицы стоит команда `git status --porcelain
    -- orchestrator/`, и между её последним вхождением и шапкой нет ни
    одной строки вида вывода porcelain с путём `orchestrator/…`.

    Ловит мутацию: роль привела проверку только перед первой частью «после»
    (вторую прогнала, не проверив дерево), или перенесла вывод
    ` M orchestrator/advance_gates/outcome_integrity.py` — перед частью нет
    команды или вывод непуст, тест краснеет с номером таблицы.
    """
    text = _section_text(_plan_text(), _AFTER)
    found, errors = _plan.tables(text)
    assert not errors, f"раздел «{_AFTER}»: " + "; ".join(errors)
    assert found, f"в разделе «{_AFTER}» нет таблиц mutation-run"
    lines = text.split("\n")
    problems, prev_end = [], 0
    for table in sorted(found, key=lambda t: t.start):
        lead = lines[prev_end:table.start]
        at = [i for i, line in enumerate(lead) if _STATUS_CMD in line]
        if not at:
            problems.append(f"перед таблицей «после» №{table.run_no} нет "
                            f"команды «{_STATUS_CMD}»")
        else:
            dirty = [line for line in lead[at[-1] + 1:]
                     if _PORCELAIN_LINE.match(line)]
            if dirty:
                problems.append(f"перед таблицей «после» №{table.run_no} вывод "
                                f"непуст: {dirty}")
        prev_end = table.start + len(table.lines)
    assert not problems, "\n".join(problems)


def test_ac12_same_orchestrator_tree_across_all_header_revisions():
    """Дерево `orchestrator/` у ревизий всех шапок «до» и «после» одно.

    Для каждой пары различных ревизий из шапок таблиц обоих разделов
    `git diff --quiet <sha> <sha> -- orchestrator/` в рабочей копии
    завершается кодом 0.

    Ловит мутацию: «после» прогнан на ревизии с правкой `orchestrator/`
    (или «до» не повторён после подтяжки main с правкой `orchestrator/`) —
    `git diff` даёт код 1, тест краснеет с парой ревизий.
    """
    plan = _plan_text()
    shas = sorted({t.sha for t in _section_tables(plan, _BEFORE)}
                  | {t.sha for t in _section_tables(plan, _AFTER)})
    problems = []
    for i, left in enumerate(shas):
        for right in shas[i + 1:]:
            res = _plan.git(CODE_ROOT, "diff", "--quiet", left, right, "--",
                            "orchestrator/")
            if res.returncode != 0:
                problems.append(f"git diff --quiet {left} {right} -- "
                                f"orchestrator/ — код {res.returncode} "
                                f"{res.stderr.strip()}")
    assert not problems, "\n".join(problems)


def test_ac12_patch_sha256_same_in_before_and_after_headers():
    """sha256 каждого патча в шапке «до» совпадает с его sha256 в шапке «после».

    Каждый патч набора есть строкой «# патч» в шапках «до»; шапки «после»
    несут строку того же номера, и её sha256 равен sha256 «до».

    Ловит мутацию: роль переписала патч между прогонами «до» и «после» и не
    повторила «до» — sha256 номера в шапках расходится, тест краснеет с
    номером и обоими значениями.
    """
    plan = _plan_text()
    names = _patch_names()
    b_shas = _plan.last_patch_sha(_section_tables(plan, _BEFORE))
    a_shas = _plan.last_patch_sha(_section_tables(plan, _AFTER))
    assert set(names) <= set(b_shas), (
        f"патчи без строки «# патч» в шапках «до»: {sorted(set(names) - set(b_shas))}")
    problems = [f"патч {n}: sha256 «до» {b_shas[n]} ≠ «после» {a_shas.get(n)}"
                for n in sorted(b_shas) if a_shas.get(n) != b_shas[n]]
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-13

def test_ac13_plan_names_test_count_lines_and_control_run_time():
    """PLAN называет число тестов и строк до и после свода и время контрольных прогонов «до» и «после».

    «До» — по базе ветки: число тестов (42 исходного файла, либо вместе с
    тестами модуля на базе) и число строк (исходного файла, либо вместе со
    строками модуля на базе). «После» — по
    `tests/test_outcome_gate_module.py` головы ветки: число тестовых
    функций (или собранных узлов) и строк. Каждое число стоит в PLAN
    отдельным числом; в строках PLAN со словом «контрольн…» длительностей
    (`<n> с`/`мин`) не меньше двух.

    Ловит мутацию: роль записала в PLAN число тестов и строк только «до»
    (или привела строки модуля до последней правки), либо время адресного
    прогона под ролью вместо контрольных прогонов `mutation-run` — числа
    «после» или двух длительностей контрольных прогонов нет, тест краснеет.
    """
    plan = _plan_text()
    source = _base_texts(_plan.SOURCE_FILES)[_plan.OUTCOME_FILE]
    module = _plan.show(CODE_ROOT, DIFF_BASE, _plan.NEW_FILE)
    assert module is not None, f"{_plan.NEW_FILE} нет в базе ветки"
    src_tests = len(_plan.base_tests(_plan.OUTCOME_FILE, source))
    mod_tests = len(_plan.module_tests(ast.parse(module)))
    src_lines, mod_lines = source.count("\n"), module.count("\n")
    new_text = _new_text()
    new_funcs = len(_plan.module_tests(ast.parse(new_text)))
    new_nodes = len(_collect_new_nodes())

    def named(number: int) -> bool:
        return re.search(rf"(?<![\d.,]){number}(?![\d])", plan) is not None

    problems = []
    if not (named(src_tests) or named(src_tests + mod_tests)):
        problems.append(f"число тестов «до» {src_tests} (или "
                        f"{src_tests + mod_tests} с модулем) в PLAN не названо")
    if not (named(src_lines) or named(src_lines + mod_lines)):
        problems.append(f"число строк «до» {src_lines} (или "
                        f"{src_lines + mod_lines} с модулем) в PLAN не названо")
    if not (named(new_funcs) or (new_nodes and named(new_nodes))):
        problems.append(f"число тестов «после» ({new_funcs} функций / "
                        f"{new_nodes} узлов) в PLAN не названо")
    if not named(new_text.count("\n")):
        problems.append(f"число строк «после» {new_text.count(chr(10))} в PLAN "
                        f"не названо")
    control = [line for line in _plan.prose_lines(plan)
               if "контрольн" in line.casefold()]
    if sum(len(_DURATION.findall(line)) for line in control) < 2:
        problems.append("в строках PLAN о контрольных прогонах нет двух "
                        "длительностей («<n> с» / «<n> мин») — «до» и «после»")
    assert not problems, "\n".join(problems)
