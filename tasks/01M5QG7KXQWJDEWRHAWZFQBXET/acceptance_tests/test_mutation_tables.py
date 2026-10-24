"""AC-2, AC-3, AC-4, AC-14, AC-15: таблицы `mutation-run` «до» и «после» в
PLAN и их согласованность с набором патчей, упавшими утверждениями,
отметками падений подготовки, находками, переносом тестов и числами
прогона.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после» и патчей ещё нет, crg не сведён в модуль — прогонов mutation-run и свода не было.

Таблица раздела — последняя таблица `mutation-run` в нём (более ранние —
история переписанных прогонов). Планка сверяет форму и согласованность:
каждая мутация в обеих таблицах, у убитой «до» тестом T есть убийца «после»
— функция, в которую перенесён T, тем же утверждением (нормальная форма —
докстринг `_plan.py`). Подлинность таблиц — работа независимой проверки
(требование 19 SPEC). Соглашения разбора PLAN — докстринг `_plan.py`.
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
    r"^" + re.escape(_plan.SOURCE_FILE) + r"::[A-Za-z_]\w*::test\w*$")
_AFTER_NODE = re.compile(
    r"^" + re.escape(_plan.NEW_FILE) + r"::test\w*(?:\[.*\])?$")
_DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|секунд[а-я]*|s|мин|min)"
                       r"(?![A-Za-zА-Яа-яЁё])")


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _patch_names() -> dict:
    names = _plan.patch_names(
        _plan.docs_entry_types(DOCS_REPO, DOCS_REVISION, TASK_ID))
    assert names, "патчей mutation-<nnn>.diff в каталоге документов задачи нет"
    return names


def _table(plan: str, title: str):
    texts = _plan.sections(plan, title)
    assert texts, f"в PLAN нет раздела «{title}»"
    found, errors = _plan.tables("\n".join(texts))
    assert not errors, f"раздел «{title}»: " + "; ".join(errors)
    assert found, (f"в разделе «{title}» нет ни одной таблицы mutation-run "
                   f"(шапка «# mutation-run №…», колонки номер/исход/узлы)")
    return found[-1]


def _rows(plan: str, title: str) -> dict:
    return _plan.last_rows([_table(plan, title)])


def _base(path: str) -> str:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, path)
    assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
    return text


def _head(path: str) -> str:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    assert text is not None, f"{path} нет в HEAD ветки"
    return text


def _base_tests() -> dict:
    return {t.key: t for t in _plan.base_tests(_base(_plan.SOURCE_FILE))}


def _transferred(plan: str) -> dict:
    return _plan.transferred(plan, _base_tests(),
                             ast.parse(_head(_plan.NEW_FILE)),
                             ast.parse(_base(_plan.NEW_FILE)))


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


def _findings(plan: str) -> set:
    found = set()
    for line in _plan.prose_lines(plan):
        if "находк" in line.casefold():
            found |= _plan.refs(line)
    for text in _plan.sections(plan, "находк"):
        for line in _plan.prose_lines(text):
            found |= _plan.refs(line)
    return found


def _removed(plan: str) -> set:
    removed = set()
    for text in _plan.sections(plan, "дубл"):
        for line in _plan.prose_lines(text):
            removed |= _plan.test_keys(line)
    return removed


def _valid_site(texts: dict, path: str, line: int) -> bool:
    """`path:line` — строка утверждения вне `setUp`, утверждения подготовки
    песочницы и фикстуры."""
    text = texts.get(path)
    if text is None:
        return False
    node, chain = _plan.site(text, line)
    return node is not None and bool(chain) and not _plan.in_preparation(chain)


def _check_header(table, ref: str, tests: list, where: str, names: dict,
                  node_form) -> list:
    problems = []
    if table.task != TASK_ID:
        problems.append(f"{where}: задача {table.task}, ожидалась {TASK_ID}")
    if table.ref != ref:
        problems.append(f"{where}: ревизия прогона {table.ref}, ожидалась {ref}")
    if table.tests != tests:
        problems.append(f"{where}: тесты {table.tests}, ожидались {tests}")
    if table.workers != _plan.WORKERS:
        problems.append(f"{where}: рабочих процессов {table.workers}, "
                        f"ожидалось {_plan.WORKERS} (--workers {_plan.WORKERS})")
    absent_head = sorted(set(names) - set(table.patches))
    if absent_head:
        problems.append(f"{where}: нет строк «# патч … sha256 …» патчей {absent_head}")
    numbers = [n for n, _o, _nodes in table.rows]
    absent_rows = sorted(set(names) - set(numbers))
    if absent_rows:
        problems.append(f"{where}: нет строк мутаций {absent_rows}")
    for number, outcome, nodes in table.rows:
        if number not in table.patches:
            problems.append(f"{where}: строка мутации {number} без строки "
                            f"«# патч {number} …» в шапке")
        if outcome not in _plan.OUTCOMES:
            problems.append(f"{where}: мутация {number} — исход «{outcome}» "
                            f"не из вывода команды")
        if outcome == _plan.KILLED and (
                not nodes or any(not node_form.match(n) for n in nodes)):
            problems.append(f"{where}: мутация {number} убита, узлы не того "
                            f"вида: {nodes}")
    return problems


def _collect_new_nodes() -> set:
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", _plan.NEW_FILE],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=110)
    assert res.returncode == 0, (f"сбор {_plan.NEW_FILE} не прошёл "
                                 f"(код {res.returncode}):\n{res.stdout[-3000:]}"
                                 f"\n{res.stderr[-2000:]}")
    return {line.strip() for line in res.stdout.splitlines()
            if line.strip().startswith(_plan.NEW_FILE + "::")}


# ------------------------------------------------------------------ AC-2

def test_ac2_before_table_base_ref_on_crg_with_workers_4_and_every_patch():
    """Раздел «Мутации до»: таблица `--ref base` на crg с `--workers 4`, каждый патч набора в ней.

    Последняя таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, `тесты: tests/test_component_report_gates.py`,
    `рабочих процессов: 4`, строки «# патч … sha256 …» каждого патча
    набора; строка колонок и строка каждого патча; исход — из словаря
    команды; у «убита» узлы вида `tests/test_component_report_gates.py::<Класс>::<метод>`.

    Ловит мутацию: роль прогнала «до» с `--ref worktree` (где crg уже
    удалён) или без `--workers 4`, либо перенесла вывод без строки одного
    патча — ревизия, число процессов или номер расходится, тест краснеет.
    """
    plan = _plan_text()
    problems = _check_header(_table(plan, "Мутации до"), "base",
                             [_plan.SOURCE_FILE], "таблица «до»",
                             _patch_names(), _BEFORE_NODE)
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-3

def test_ac3_each_killed_mutation_names_failed_assertion_before_and_after():
    """Для каждой убитой мутации PLAN называет убийцу и строку упавшего утверждения «до» и «после».

    Для мутации с исходом «убита» в таблице «до» в PLAN есть строка вне
    таблиц со ссылкой на мутацию, ключом `<Класс>::<метод>` одного из её
    убийц и ссылкой `tests/test_component_report_gates.py:<строка>` (или
    `tests/report_outcome_sandbox.py:<строка>`), которая в базе ветки лежит
    внутри утверждения и не в `setUp`, `profile`, `table`,
    `accepted_major`, `cache_flag` или фикстуре. Для мутации, убитой
    «после», — так же строка с узлом её убийцы
    `test_report_outcome_module.py::<функция>` и ссылкой
    `tests/test_report_outcome_module.py:<строка>` (или песочницы) на HEAD.

    Ловит мутацию: роль назвала убийцей узел, упавший в
    `ReportSandbox.profile` (утверждение подготовки «профиль не собран»),
    или не привела файл:строку из лога прогона — у мутации нет годной
    ссылки, тест краснеет с номером.
    """
    plan = _plan_text()
    base_texts = {p: _plan.show(CODE_ROOT, DIFF_BASE, p)
                  for p in (_plan.SOURCE_FILE, _plan.SANDBOX_FILE)}
    head_texts = {p: _plan.show(CODE_ROOT, "HEAD", p)
                  for p in (_plan.NEW_FILE, _plan.SANDBOX_FILE)}
    before = _plan.killed(_rows(plan, "Мутации до"))
    after = _plan.killed(_rows(plan, "Мутации после"))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        killers = {_plan.node_key(n) for n in nodes}
        if not any(number in _plan.refs(line) and _plan.test_keys(line) & killers
                   and any(_valid_site(base_texts, p, n)
                           for p, n in _plan.file_lines(line))
                   for line in lines):
            problems.append(f"мутация {number} «до»: нет строки PLAN с её "
                            f"убийцей из {sorted(killers)} и файл:строка "
                            f"упавшего утверждения вне подготовки")
    for number, nodes in sorted(after.items()):
        if not any(number in _plan.refs(line)
                   and any(_plan.after_marked(n, _plan.after_refs(line))
                           for n in nodes)
                   and any(_valid_site(head_texts, p, n)
                           for p, n in _plan.file_lines(line))
                   for line in lines):
            problems.append(f"мутация {number} «после»: нет строки PLAN с её "
                            f"убийцей из {nodes} и файл:строка упавшего "
                            f"утверждения вне подготовки")
    assert before, "в таблице «до» нет ни одной убитой мутации"
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-4

def test_ac4_killed_mutation_has_killer_outside_preparation_marks():
    """У каждой убитой мутации есть убийца вне отметки «убит падением подготовки» — «до» и «после».

    Отметка — строки PLAN со словом `setUp`/«подготовк…» и ссылкой на
    мутацию: для «до» — ключи `<Класс>::<метод>`, для «после» — ссылки
    `test_report_outcome_module.py::<функция>[<вариант>]`. Для каждой
    мутации с исходом «убита» хотя бы один убивший узел под отметку не
    попадает.

    Ловит мутацию: патч ломает таблицу версий Vitest, тест падает в
    `ReportSandbox.table`, роль честно отметила узел, но не переписала
    патч — у мутации не остаётся убийцы вне отметки, тест краснеет с
    номером.
    """
    plan = _plan_text()
    before = _plan.killed(_rows(plan, "Мутации до"))
    after = _plan.killed(_rows(plan, "Мутации после"))
    marked_before, marked_after = _setup_before(plan), _setup_after(plan)
    lonely = []
    for number, nodes in sorted(before.items()):
        keys = {_plan.node_key(n) for n in nodes}
        if not keys - marked_before.get(number, set()):
            lonely.append(f"мутация {number} «до»: все убийцы {sorted(keys)} — "
                          f"в отметке падений подготовки")
    for number, nodes in sorted(after.items()):
        marks = marked_after.get(number, set())
        if all(_plan.after_marked(n, marks) for n in nodes):
            lonely.append(f"мутация {number} «после»: все убийцы {nodes} — "
                          f"в отметке падений подготовки")
    assert not lonely, "\n".join(lonely)


def test_ac4_undecided_outcome_neither_killed_nor_survived():
    """Мутация с исходом «итог неизвестен», «патч не применяется», «патч трогает тесты», «не прогнана» не засчитана ни убитой, ни выжившей.

    Для мутации, чья строка в таблице «до» или «после» несёт такой исход,
    PLAN не называет её находкой (выжившей), а в таблице «до» она не
    засчитана убитой: её исход — не «убита» (по разбору таблицы).

    Ловит мутацию: патч не применился к ревизии, роль записала его
    находкой («никто не убил») и не переписала — номер найден среди
    находок, тест краснеет.
    """
    plan = _plan_text()
    rows = [_rows(plan, "Мутации до"), _rows(plan, "Мутации после")]
    undecided = sorted({n for r in rows for n, (outcome, _nodes) in r.items()
                        if outcome in _plan.UNDECIDED})
    as_findings = sorted(set(undecided) & _findings(plan))
    assert not as_findings, (f"мутации с неопределённым исходом названы "
                             f"находками (выжившими): {as_findings}")


def test_ac4_survived_before_listed_as_findings():
    """Мутации, не убитые «до» никем, перечислены в PLAN находками.

    Для каждой мутации с исходом «до» «не убита» в PLAN есть ссылка на неё
    в строке со словом «находк…» либо в разделе, в заголовке которого это
    слово есть.

    Ловит мутацию: роль молча оставила в наборе патч, который «до» никто
    не убил, и не записала его находкой — номер не найден среди находок,
    тест краснеет.
    """
    plan = _plan_text()
    survived = sorted(n for n, (outcome, _nodes) in _rows(plan, "Мутации до").items()
                      if outcome == _plan.SURVIVED)
    unlisted = sorted(set(survived) - _findings(plan))
    assert not unlisted, f"мутации, не убитые «до», не названы находками: {unlisted}"


# ------------------------------------------------------------------ AC-14

def test_ac14_after_table_worktree_on_module_with_workers_4_and_every_patch():
    """Раздел «Мутации после»: таблица `--ref worktree` на модуле с `--workers 4`, каждый патч набора в ней.

    Ловит мутацию: «после» прогнан с `--ref head` или на crg и модуле
    вместе (`--tests a,b`), или одного патча нет в выводе — ревизия,
    список тестов или номер расходится, тест краснеет.
    """
    plan = _plan_text()
    problems = _check_header(_table(plan, "Мутации после"), "worktree",
                             [_plan.NEW_FILE], "таблица «после»",
                             _patch_names(), _AFTER_NODE)
    assert not problems, "\n".join(problems)


def test_ac14_empty_orchestrator_status_before_after_table():
    """Перед таблицей «после» в PLAN — пустой вывод `git status --porcelain -- orchestrator/`.

    В разделе «Мутации после» перед шапкой последней таблицы
    (`# mutation-run №…`), после конца предыдущей таблицы, есть строка с
    командой `git status --porcelain -- orchestrator/`, и между ней и шапкой
    нет строки вывода porcelain (`XY <путь>`) с путём под `orchestrator/`.

    Ловит мутацию: роль не привела вывод `git status` (или привела
    непустой ` M orchestrator/acceptance.py` — рабочая копия с правкой
    кода) — пустого вывода перед таблицей нет, тест краснеет.
    """
    plan = _plan_text()
    texts = _plan.sections(plan, "Мутации после")
    assert texts, "в PLAN нет раздела «Мутации после»"
    lines = "\n".join(texts).split("\n")
    command = "git status --porcelain -- orchestrator/"
    porcelain = re.compile(r"^[ MADRCUT?!]{2} \"?orchestrator/")
    heads = [i for i, line in enumerate(lines) if _plan._HEAD.match(line)]
    assert heads, "в разделе «Мутации после» нет таблиц mutation-run"
    last = heads[-1]
    boundary = 0
    for i in range(last):
        if _plan._ROW.match(lines[i]) or lines[i] == _plan._COLUMNS:
            boundary = i + 1
    window = lines[boundary:last]
    marks = [k for k, w in enumerate(window) if command in w]
    assert marks, f"перед таблицей «после» нет вывода «{command}»"
    dirty = [w for w in window[marks[-1] + 1:] if porcelain.match(w.strip("`"))]
    assert not dirty, f"вывод «{command}» перед таблицей не пуст: {dirty}"


def test_ac14_mutation_killed_by_t_before_killed_by_its_function_after_same_assertion():
    """Мутацию, убитую «до» тестом T, «после» убивает функция переноса T тем же утверждением.

    Для каждой мутации с исходом «до» «убита» и каждого её убийцы T, не
    перечисленного удалённым дублем: у T есть функция переноса F (правило
    докстринга `_plan.py`); исход «после» — «убита», и F среди убийц; в PLAN
    есть строка со ссылкой на мутацию, T и `tests/test_component_report_gates.py:<строка>`
    и строка со ссылкой на мутацию, F и `tests/test_report_outcome_module.py:<строка>`
    внутри F, и нормальные формы этих двух утверждений совпадают.

    Ловит мутацию: при своде утверждение
    `self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED)` перенесено как
    `assert run.outcome != acceptance.FULL_SUITE_GREEN`, и «после» мутацию
    ловит соседнее утверждение — нормальные формы расходятся (или F нет
    среди убийц), тест краснеет с номером и T.
    """
    plan = _plan_text()
    before = _plan.killed(_rows(plan, "Мутации до"))
    after = _rows(plan, "Мутации после")
    removed = _removed(plan)
    moved = _transferred(plan)
    crg = _base(_plan.SOURCE_FILE)
    head = _head(_plan.NEW_FILE)
    head_funcs = _plan.module_functions(ast.parse(head))
    helpers = {fname: method for method, fname
               in _plan.helper_function_names(head_funcs).items()}
    lines = _plan.prose_lines(plan)
    problems = []
    assert before, "в таблице «до» нет ни одной убитой мутации"
    for number, nodes in sorted(before.items()):
        outcome, after_nodes = after.get(number, ("<нет строки>", []))
        after_funcs = {_plan.after_node_parts(n)[0] for n in after_nodes} \
            if outcome == _plan.KILLED else set()
        for key in sorted({_plan.node_key(n) for n in nodes}):
            if key in removed:
                continue
            funcs = moved.get(key, set())
            if not funcs:
                problems.append(f"мутация {number}, {key}: функции переноса нет")
                continue
            hit = funcs & after_funcs
            if not hit:
                problems.append(f"мутация {number}, {key}: «после» исход "
                                f"«{outcome}», убийцы {after_nodes} — без {sorted(funcs)}")
                continue
            before_forms = set()
            for line in lines:
                if number in _plan.refs(line) and key in _plan.test_keys(line):
                    for path, n in _plan.file_lines(line):
                        if path == _plan.SOURCE_FILE:
                            node, _chain = _plan.site(crg, n)
                            if node is not None:
                                before_forms.add(_plan.canon(node, {"self"}))
            after_forms = set()
            for line in lines:
                refs = {f for f, _v in _plan.after_refs(line)} & hit
                if number not in _plan.refs(line) or not refs:
                    continue
                for path, n in _plan.file_lines(line):
                    if path != _plan.NEW_FILE:
                        continue
                    node, chain = _plan.site(head, n)
                    if node is None or not chain or chain[0].name not in refs:
                        continue
                    stands = set(_plan.STAND_NAMES) | set(_plan.fixture_params(chain[0]))
                    after_forms.add(_plan.canon(node, stands, helpers))
            if not ((before_forms - {None}) & (after_forms - {None})):
                problems.append(f"мутация {number}, {key}: нет пары строк PLAN "
                                f"с тем же утверждением «до» (crg:строка) и "
                                f"«после» (модуль:строка в {sorted(hit)})")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-15

def test_ac15_same_orchestrator_tree_in_before_and_after_headers():
    """Дерево `orchestrator/` у ревизий шапок «до» и «после» одно.

    `git diff --quiet <sha до> <sha после> -- orchestrator/` в рабочей копии
    завершается кодом 0.

    Ловит мутацию: «после» прогнан на ревизии с правкой `orchestrator/`
    (или «до» не повторён после подтяжки main с правкой `orchestrator/`) —
    `git diff` даёт код 1, тест краснеет с парой ревизий.
    """
    plan = _plan_text()
    left = _table(plan, "Мутации до").sha
    right = _table(plan, "Мутации после").sha
    res = _plan.git(CODE_ROOT, "diff", "--quiet", left, right, "--",
                    "orchestrator/")
    assert res.returncode == 0, (f"git diff --quiet {left} {right} -- "
                                 f"orchestrator/ — код {res.returncode} "
                                 f"{res.stderr.strip()}")


def test_ac15_patch_sha256_same_in_before_and_after_headers():
    """sha256 каждого патча в шапке «до» совпадает с его sha256 в шапке «после».

    Ловит мутацию: роль переписала патч между прогонами «до» и «после» и не
    повторила «до» — sha256 номера в шапках расходится, тест краснеет с
    номером и обоими значениями.
    """
    plan = _plan_text()
    names = _patch_names()
    b_shas = _plan.last_patch_sha([_table(plan, "Мутации до")])
    a_shas = _plan.last_patch_sha([_table(plan, "Мутации после")])
    problems = [f"патч {n}: sha256 «до» {b_shas.get(n)} ≠ «после» {a_shas.get(n)}"
                for n in sorted(names) if b_shas.get(n) is None
                or a_shas.get(n) != b_shas[n]]
    assert not problems, "\n".join(problems)


def test_ac15_plan_names_test_count_lines_and_time_before_and_after():
    """PLAN называет число тестов, строк и время прогона до и после свода.

    «До» — по базе ветки: тесты crg (13) и его строки; «после» — по
    `tests/test_report_outcome_module.py` головы ветки: число тестовых
    функций (или собранных узлов) и строк. Каждое число стоит в PLAN
    отдельным числом; длительностей (`<n> с`/`мин`) в PLAN не меньше двух.

    Ловит мутацию: роль записала число тестов и строк только «до» (или
    привела строки модуля до финальной правки) — числа «после» в PLAN нет,
    тест краснеет с ним.
    """
    plan = _plan_text()
    crg = _base(_plan.SOURCE_FILE)
    new_text = _head(_plan.NEW_FILE)
    new_funcs = len(_plan.module_tests(ast.parse(new_text)))
    new_nodes = len(_collect_new_nodes())

    def named(number: int) -> bool:
        return re.search(rf"(?<![\d.,]){number}(?![\d])", plan) is not None

    problems = []
    if not named(len(_plan.base_tests(crg))):
        problems.append(f"число тестов «до» {len(_plan.base_tests(crg))} не названо")
    if not named(crg.count("\n")):
        problems.append(f"число строк «до» {crg.count(chr(10))} не названо")
    if not (named(new_funcs) or (new_nodes and named(new_nodes))):
        problems.append(f"число тестов «после» ({new_funcs} функций / "
                        f"{new_nodes} узлов) не названо")
    if not named(new_text.count("\n")):
        problems.append(f"число строк «после» {new_text.count(chr(10))} не названо")
    if len(_DURATION.findall(plan)) < 2:
        problems.append("в PLAN нет двух длительностей прогона («<n> с» / "
                        "«<n> мин») — до и после")
    assert not problems, "\n".join(problems)
