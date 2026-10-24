"""AC-2, AC-3, AC-4, AC-9 (итог CI в PLAN), AC-15, AC-16, AC-17, AC-18:
таблицы `mutation-run` «до» и «после» в PLAN и их согласованность с набором
патчей, отметками падений подготовки, упавшими утверждениями, находками,
удалёнными дублями и рабочей копией; числа адресного прогона и итог CI.

Группа: разовый
Красен до реализации: PLAN.md с разделами «Мутации до»/«Мутации после», патчей и tests/test_report_outcome_module.py ещё нет — прогонов mutation-run и свода не было.

Планка сверяет форму и согласованность таблиц: каждая мутация в обеих
таблицах, у убитой «до» есть убийца «после», отметки, упавшие утверждения
и дубли перечислены с мутациями. Подлинность таблиц и верность отметки
«убита только падением подготовки» — работа независимой проверки
(требование 18 SPEC). Соглашения разбора PLAN — докстринг `_plan.py`.
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


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _patch_names() -> dict:
    names = _plan.patch_names(
        _plan.docs_entries(DOCS_REPO, DOCS_REVISION, TASK_ID))
    assert names, "патчей mutation-<nnn>.diff в каталоге документов задачи нет"
    return names


def _section_tables(plan: str, title: str) -> list:
    texts = _plan.sections(plan, title)
    assert texts, f"в PLAN нет раздела «{title}»"
    found, errors = _plan.tables("\n".join(texts))
    assert not errors, f"раздел «{title}»: " + "; ".join(errors)
    assert found, (f"в разделе «{title}» нет ни одной таблицы mutation-run "
                   f"(шапка «# mutation-run №…», колонки номер/исход/узлы)")
    return found


def _base_texts() -> dict:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    texts = {}
    for path in _plan.SOURCE_FILES:
        text = _plan.show(CODE_ROOT, DIFF_BASE, path)
        assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
        texts[path] = text
    return texts


def _base_tests() -> dict:
    tests = {}
    for path, text in _base_texts().items():
        for test in _plan.base_tests(path, text):
            tests[test.key] = test
    return tests


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
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=110)
    assert res.returncode == 0, (f"сбор {_plan.NEW_FILE} не прошёл "
                                 f"(код {res.returncode}):\n{res.stdout[-3000:]}"
                                 f"\n{res.stderr[-2000:]}")
    return {line.strip() for line in res.stdout.splitlines()
            if line.strip().startswith(_plan.NEW_FILE + "::")}


def _valid_site(texts: dict, path: str, line: int) -> bool:
    """Ссылка `path:line` указывает на утверждение вне `setUp`, метода
    подготовки песочницы и фикстуры."""
    text = texts.get(path)
    if text is None:
        return False
    inside, chain = _plan.assertion_site(text, line)
    return inside and bool(chain) and not _plan.in_preparation(chain)


# ------------------------------------------------------------------ AC-2

def test_ac2_before_tables_base_ref_source_file_parts_and_every_patch():
    """Раздел «Мутации до»: таблицы `--ref base` на исходном файле, части по ≤15 патчей, все патчи в них.

    Каждая таблица раздела несёт полную шапку: задача, источник,
    `ревизия прогона: base <sha>`, тесты — ровно исходный файл волны,
    строки «# патч … sha256 …», и не больше 15 патчей. Каждый номер набора
    патчей есть строкой хотя бы одной таблицы; у каждой строки есть строка
    «# патч» шапки её таблицы; исход — из словаря команды; у «убита» узлы
    непусты и имеют вид `tests/<файл>::<Класс>::<метод>`.

    Ловит мутацию: роль перенесла только последнюю часть деления
    `--patches` (вывод первой части потерян), прогнала часть из 20 патчей
    или прогнала «до» с `--ref worktree` либо на новом файле — номер набора
    отсутствует, часть велика, ревизия не `base` или список тестов не тот,
    тест краснеет.
    """
    plan = _plan_text()
    names = _patch_names()
    found = _section_tables(plan, "Мутации до")
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
        if not table.patches:
            problems.append(f"{where}: в шапке нет строк «# патч … sha256 …»")
        if len(table.patches) > _plan.MAX_PART:
            problems.append(f"{where}: патчей в части {len(table.patches)}, "
                            f"больше {_plan.MAX_PART}")
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
    rows = _plan.last_rows(found)
    absent = sorted(set(names) - set(rows))
    if absent:
        problems.append(f"мутаций набора нет в таблицах «до»: {absent}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-3

def test_ac3_collection_error_never_counted_killed():
    """Мутация с последним исходом «до» «ошибка сбора, импорта или setup» не засчитана доказательством.

    Такая мутация не переписана (иначе её последняя строка «до» была бы
    иной) — значит, в доказательство она не входит и PLAN называет её
    находкой.

    Ловит мутацию: патч ломает импорт `orchestrator.reporters.outcome`,
    «до» строка — «ошибка сбора, импорта или setup», а
    роль сослалась на неё как на убитую и не переписала патч — мутация «до»
    не убита и не находка, тест краснеет с номером.
    """
    plan = _plan_text()
    before = _plan.last_rows(_section_tables(plan, "Мутации до"))
    collection = sorted(n for n, (outcome, _nodes) in before.items()
                        if outcome == _plan.COLLECTION)
    unlisted = sorted(set(collection) - _mentioned_as_finding(plan))
    assert not unlisted, (
        f"мутации с последним исходом «до» «{_plan.COLLECTION}» не "
        f"переписаны и не названы находками: {unlisted}")


def test_ac3_each_proof_mutation_has_killer_outside_setup_marks_before_and_after():
    """У каждой мутации доказательства есть убийца вне отметки падений подготовки — «до» и «после».

    Доказательство — мутации, чья последняя строка «до» — «убита» с узлами.
    Отметка — строки PLAN со словом `setUp`/«подготовк…» и ссылкой на
    мутацию: для «до» — ключи `<Класс>::<метод>`, для «после» — ссылки
    `test_report_outcome_module.py::<функция>[<вариант>]`. Для каждой мутации
    доказательства хотя бы один убивший узел «до» и хотя бы один убивший
    узел «после» под отметку не попадают.

    Ловит мутацию: патч ломает таблицу версий Vitest, и тесты падают в
    методе подготовки `ReportSandbox.table`, роль честно отметила эти узлы,
    но не переписала патч: у мутации не остаётся убийцы вне отметки, тест
    краснеет с номером.
    """
    plan = _plan_text()
    before = _plan.killed(_plan.last_rows(_section_tables(plan, "Мутации до")))
    after = _plan.last_rows(_section_tables(plan, "Мутации после"))
    marked_before, marked_after = _setup_before(plan), _setup_after(plan)
    lonely = []
    for number, nodes in sorted(before.items()):
        keys = {_plan.node_key(n) for n in nodes}
        if not keys - marked_before.get(number, set()):
            lonely.append(f"мутация {number} «до»: все убийцы {sorted(keys)} — "
                          f"в отметке падений подготовки")
        outcome, after_nodes = after.get(number, ("<нет строки>", []))
        if outcome != _plan.KILLED or not after_nodes:
            continue  # отсутствие убийцы «после» — предмет AC-16
        marks = marked_after.get(number, set())
        if all(_plan.after_marked(n, marks) for n in after_nodes):
            lonely.append(f"мутация {number} «после»: все убийцы {after_nodes} — "
                          f"в отметке падений подготовки")
    assert not lonely, "\n".join(lonely)


def test_ac3_each_proof_mutation_names_failed_assertion_outside_preparation():
    """Для каждой мутации доказательства PLAN называет убивший узел и упавшее утверждение «до» и «после».

    Для мутации с последним исходом «до» «убита» в PLAN есть строка вне
    таблиц со ссылкой на мутацию, ключом `<Класс>::<метод>` одного из её
    убийц «до» и ссылкой `tests/<исходный файл>.py:<строка>`, которая в
    базе ветки лежит внутри утверждения (`assert`, `self.assert*`,
    `pytest.raises`/`fail`) и не внутри `setUp`, `profile`, `records_of`,
    `by_id`, `table`, `accepted_major`, `cache_flag`, `key_case` или
    фикстуры. Если «после» она убита — так же строка с узлом её убийцы
    «после» и ссылкой `tests/test_report_outcome_module.py:<строка>` или
    `tests/report_outcome_sandbox.py:<строка>` по тем же правилам на HEAD.

    Ловит мутацию: роль назвала убийцей узел, упавший в
    `key_case` (утверждение подготовки «дерево клона не снято»), или не привела
    файл:строку из лога прогона — у мутации нет годной ссылки, тест
    краснеет с номером.
    """
    plan = _plan_text()
    base_texts = _base_texts()
    head_texts = {p: _plan.show(CODE_ROOT, "HEAD", p) for p in _plan.AFTER_FILES}
    head_texts = {p: t for p, t in head_texts.items() if t is not None}
    before = _plan.killed(_plan.last_rows(_section_tables(plan, "Мутации до")))
    after = _plan.killed(_plan.last_rows(_section_tables(plan, "Мутации после")))
    lines = _plan.prose_lines(plan)
    problems = []
    for number, nodes in sorted(before.items()):
        killers = {_plan.node_key(n) for n in nodes}
        ok_before = any(
            number in _plan.refs(line) and _plan.test_keys(line) & killers
            and any(_valid_site(base_texts, p, n) for p, n in _plan.file_lines(line))
            for line in lines)
        if not ok_before:
            problems.append(f"мутация {number} «до»: нет строки PLAN с её "
                            f"убийцей из {sorted(killers)} и файл:строка "
                            f"упавшего утверждения вне подготовки")
        if number not in after:
            continue  # отсутствие убийцы «после» — предмет AC-16
        after_nodes = after[number]
        ok_after = any(
            number in _plan.refs(line)
            and any(_plan.after_marked(n, _plan.after_refs(line))
                    for n in after_nodes)
            and any(_valid_site(head_texts, p, n) for p, n in _plan.file_lines(line))
            for line in lines)
        if not ok_after:
            problems.append(f"мутация {number} «после»: нет строки PLAN с её "
                            f"убийцей из {after_nodes} и файл:строка упавшего "
                            f"утверждения вне подготовки")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-4

def test_ac4_survived_before_listed_as_findings_and_out_of_proof():
    """Мутации, не убитые «до» никем, перечислены в PLAN находками.

    Для каждой мутации с последним исходом «до» — «не убита» в PLAN есть
    ссылка на неё в строке со словом «находк…» либо в разделе, в заголовке
    которого это слово есть.

    Ловит мутацию: роль молча оставила в наборе патч, который «до» никто
    не убил, и не записала его находкой — номер мутации не найден среди
    находок, тест краснеет.
    """
    plan = _plan_text()
    rows = _plan.last_rows(_section_tables(plan, "Мутации до"))
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

    Ловит мутацию: часть «до» оборвалась по пределу, роль записала
    оборванную мутацию находкой («никто не убил») и не перепрогнала её
    меньшим диапазоном — номер найден среди находок, тест краснеет.
    """
    plan = _plan_text()
    before = _plan.last_rows(_section_tables(plan, "Мутации до"))
    after = _plan.last_rows(_section_tables(plan, "Мутации после"))
    limited = sorted({n for rows in (before, after)
                      for n, (outcome, _nodes) in rows.items()
                      if outcome in _plan.LIMIT_OUTCOMES})
    as_findings = sorted(set(limited) & _mentioned_as_finding(plan))
    assert not as_findings, (f"мутации с исходом предела названы находками "
                             f"(выжившими): {as_findings}")


# ------------------------------------------------------------------ AC-15

def test_ac15_removed_duplicates_killed_by_kept_test_with_its_literals():
    """Удалённый дубль: его мутации убивает сохраняемый тест с теми же утверждениями.

    Раздел «…дубл…» PLAN перечисляет удалённые тесты исходного файла с
    мутациями. Для каждого: мутаций не меньше одной; каждую по таблице «до»
    убивает и сохраняемый тест; среди сохраняемых есть тест, убивающий их
    все, у которого литералы и виды `self.assert*` (по базе ветки)
    покрывают литералы и виды удалённого. Ни одна мутация, сопоставленная
    удалённому тесту в PLAN, не осталась «до» неубитой.

    Ловит мутацию: удалён как дубль тест, чью мутацию «до» убивал только он
    сам, или тест с утверждением `assertEqual(fld(record, "outcome"), kind)`
    литерала `"outcome"` которого нет у оставленного соседа, — тест краснеет с именем
    дубля.
    """
    plan = _plan_text()
    rows = _plan.last_rows(_section_tables(plan, "Мутации до"))
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


def test_ac15_every_untransferred_test_listed_as_removed_duplicate():
    """Тестов в новом файле не меньше, чем исходных минус перечисленные дубли.

    Сбор `pytest --collect-only` нового файла даёт число узлов; каждый
    перенесённый исходный тест даёт хотя бы один узел. Поэтому узлов не
    меньше, чем исходных тестов базы без перечисленных в PLAN удалённых
    дублей: тест, пропавший при своде без записи в PLAN, это число нарушает.

    Ловит мутацию: при своде тест исходного файла потерян (не перенесён и
    не записан дублем) — узлов нового файла меньше ожидаемого минимума,
    тест краснеет с обоими числами.
    """
    plan = _plan_text()
    tests = _base_tests()
    removed = set(_removed_duplicates(plan)) & set(tests)
    nodes = _collect_new_nodes()
    expected_min = len(tests) - len(removed)
    assert len(nodes) >= expected_min, (
        f"в {_plan.NEW_FILE} узлов {len(nodes)}, а исходных тестов "
        f"{len(tests)} минус удалённых дублей {len(removed)} = {expected_min}: "
        f"не перенесённый тест не записан в PLAN удалённым дублем")


# ------------------------------------------------------------------ AC-16

def test_ac16_after_tables_kill_every_mutation_killed_before():
    """Раздел «Мутации после»: `--ref worktree` на новом файле, части по ≤15, убитые «до» убиты.

    Каждая таблица раздела — `ревизия прогона: worktree <sha>`, тесты —
    только `tests/test_report_outcome_module.py`, патчей в части не больше
    15; каждая мутация набора есть и в таблицах «до», и в таблицах
    «после»; у каждой мутации, убитой «до», последний исход «после» —
    «убита» с узлами вида
    `tests/test_report_outcome_module.py::<функция>[<вариант>]`.

    Ловит мутацию: при своде из теста выпало утверждение, которое одно
    убивало мутацию, — «после» она «не убита», тест краснеет с номером.
    """
    plan = _plan_text()
    names = _patch_names()
    before = _plan.last_rows(_section_tables(plan, "Мутации до"))
    after_tables = _section_tables(plan, "Мутации после")
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
        if len(table.patches) > _plan.MAX_PART:
            problems.append(f"{where}: патчей в части {len(table.patches)}, "
                            f"больше {_plan.MAX_PART}")
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
        if number not in before:
            problems.append(f"мутации {number} нет в таблицах «до»")
        if number not in after:
            problems.append(f"мутации {number} нет в таблицах «после»")
    for number in sorted(_plan.killed(before)):
        outcome, nodes = after.get(number, ("<нет строки>", []))
        if outcome != _plan.KILLED or not nodes:
            problems.append(f"мутация {number} убита «до», а «после» — "
                            f"«{outcome}» {nodes}")
    assert not problems, "\n".join(problems)


def test_ac16_empty_orchestrator_status_before_each_after_part():
    """Перед каждой частью «после» в PLAN — пустой вывод `git status --porcelain -- orchestrator/`.

    В разделе «Мутации после» перед строкой шапки каждой таблицы
    (`# mutation-run №…`), после конца предыдущей таблицы, есть строка с
    командой `git status --porcelain -- orchestrator/`, и между ней и шапкой
    нет ни одной строки вывода porcelain (`XY <путь>`) с путём под
    `orchestrator/`.

    Ловит мутацию: роль привела вывод `git status` только перед первой
    частью (или перед частью стоит непустой вывод ` M orchestrator/
    reporters/outcome.py` — рабочая копия с правкой кода) — у части нет
    пустого вывода, тест краснеет с номером таблицы.
    """
    plan = _plan_text()
    texts = _plan.sections(plan, "Мутации после")
    assert texts, "в PLAN нет раздела «Мутации после»"
    command = "git status --porcelain -- orchestrator/"
    porcelain = re.compile(r"^[ MADRCUT?!]{2} \"?orchestrator/")
    problems, heads = [], 0
    for text in texts:
        lines = text.split("\n")
        boundary = 0
        for i, line in enumerate(lines):
            if not _plan._HEAD.match(line):
                if _plan._ROW.match(line) or line == _plan._COLUMNS:
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


# ------------------------------------------------------------------ AC-17

def test_ac17_same_orchestrator_tree_across_all_header_revisions():
    """Дерево `orchestrator/` у ревизий всех шапок «до» и «после» одно.

    Для каждой пары различных ревизий из шапок таблиц обоих разделов
    `git diff --quiet <sha> <sha> -- orchestrator/` в рабочей копии
    завершается кодом 0.

    Ловит мутацию: «после» прогнан на ревизии с правкой `orchestrator/`
    (или «до» не повторён после подтяжки main с правкой `orchestrator/`) —
    `git diff` даёт код 1, тест краснеет с парой ревизий.
    """
    plan = _plan_text()
    shas = sorted({t.sha for t in _section_tables(plan, "Мутации до")}
                  | {t.sha for t in _section_tables(plan, "Мутации после")})
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


def test_ac17_patch_sha256_same_in_before_and_after_headers():
    """sha256 каждого патча в шапке «до» совпадает с его sha256 в шапке «после».

    Каждый патч набора есть строкой «# патч» в шапках «до»; шапки «после»
    несут строку того же номера, и её sha256 равен sha256 «до».

    Ловит мутацию: роль переписала патч между прогонами «до» и «после» и не
    повторила «до» — sha256 номера в шапках расходится, тест краснеет с
    номером и обоими значениями.
    """
    plan = _plan_text()
    names = _patch_names()
    b_shas = _plan.last_patch_sha(_section_tables(plan, "Мутации до"))
    a_shas = _plan.last_patch_sha(_section_tables(plan, "Мутации после"))
    assert set(names) <= set(b_shas), (
        f"патчи без строки «# патч» в шапках «до»: {sorted(set(names) - set(b_shas))}")
    problems = [f"патч {n}: sha256 «до» {b_shas[n]} ≠ «после» {a_shas.get(n)}"
                for n in sorted(b_shas) if a_shas.get(n) != b_shas[n]]
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-18

def test_ac18_plan_names_test_count_lines_and_time_before_and_after():
    """PLAN называет число тестов, строк и время адресного прогона до и после.

    Числа «до» считаются по базе ветки: тесты исходного файла и его
    строки; «после» — по `tests/test_report_outcome_module.py`
    головы ветки: число тестовых функций (или собранных узлов) и строк.
    Каждое число стоит в PLAN отдельным числом; длительностей
    (`<n> с`/`мин`) в PLAN не меньше двух.

    Ловит мутацию: роль записала в PLAN число тестов и строк только «до»
    (или привела строки нового файла с ошибкой) — числа «после» в PLAN нет,
    тест краснеет с ним.
    """
    plan = _plan_text()
    base_tests, base_lines = 0, 0
    for path, text in _base_texts().items():
        base_tests += len(_plan.base_tests(path, text))
        base_lines += text.count("\n")
    new_text = _plan.show(CODE_ROOT, "HEAD", _plan.NEW_FILE)
    assert new_text is not None, f"{_plan.NEW_FILE} нет в HEAD ветки"
    new_funcs = len(_plan.module_tests(ast.parse(new_text)))
    new_nodes = len(_collect_new_nodes())

    def named(number: int) -> bool:
        return re.search(rf"(?<![\d.,]){number}(?![\d])", plan) is not None

    problems = []
    if not named(base_tests):
        problems.append(f"число тестов «до» {base_tests} в PLAN не названо")
    if not named(base_lines):
        problems.append(f"число строк «до» {base_lines} в PLAN не названо")
    if not (named(new_funcs) or (new_nodes and named(new_nodes))):
        problems.append(f"число тестов «после» ({new_funcs} функций / "
                        f"{new_nodes} узлов) в PLAN не названо")
    if not named(new_text.count("\n")):
        problems.append(f"число строк «после» {new_text.count(chr(10))} в PLAN "
                        f"не названо")
    if len(_DURATION.findall(plan)) < 2:
        problems.append("в PLAN нет двух длительностей адресного прогона "
                        "(«<n> с» / «<n> мин») — до и после")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-9

def test_ac9_plan_names_ci_result_for_invariant_test_and_importer():
    """PLAN называет итог CI кодовой ветки для инварианта и для импортёра.

    Есть строка PLAN вне таблиц, где стоят `ReportedOutcomeNotGreenInvariantTest`
    и слово `CI`, и строка, где стоят имя `test_component_report_gates` и
    слово `CI`.

    Ловит мутацию: роль записала итог CI только для
    `tests/test_component_report_gates.py`, а итог
    `tests/test_invariants.py::ReportedOutcomeNotGreenInvariantTest` не
    назвала — строки с именем класса и `CI` нет, тест краснеет с ним.
    """
    plan = _plan_text()
    lines = [line for line in _plan.prose_lines(plan) if "CI" in line]
    wanted = (_plan.INVARIANT_CLASS, Path(_plan.IMPORTER).stem)
    missing = [name for name in wanted if not any(name in line for line in lines)]
    assert not missing, ("итог CI кодовой ветки не назван в PLAN (строка с "
                         "именем и «CI»): " + ", ".join(missing))
