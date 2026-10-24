"""AC-1: патчи мутаций `mutation-<nnn>.diff` и их сопоставление в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md в ссылке документов задачи ещё нет — разработчик их не написал.

Источник патчей и PLAN — ссылка документов задачи (`_pult.artifact_text`,
перечень первого уровня — `git ls-tree` ревизии выкладки). Исходные файлы
волны читаются из базы ветки (`_pult.DIFF_BASE`): на ветке они удаляются.
Соглашения разбора PLAN — докстринг `_plan.py`: тест и мутация
сопоставлены, когда в одной строке PLAN (вне таблиц `mutation-run`) стоят
`<Класс>::<метод>` теста и имя патча `mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество строк «Ловит мутацию» («одинаковые по смыслу — одна
мутация») разбором не различимо; планка держит наблюдаемую часть: у
каждой заявки есть мутация, и одной мутации можно сопоставить список
тестов (в одной строке PLAN — несколько ссылок на тесты).
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, artifact_text)


def _patch_names() -> dict:
    names = _plan.patch_names(
        _plan.docs_entries(DOCS_REPO, DOCS_REVISION, TASK_ID))
    assert names, ("в каталоге документов задачи первым уровнем нет ни одного "
                   "патча mutation-<nnn>.diff")
    return names


def test_ac1_patches_numbered_in_a_row_each_one_orchestrator_mutation():
    """Патчи первого уровня: номера подряд, каждый — одна правка `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи: номера образуют непрерывный ряд; каждый патч трогает ровно один
    файл, и этот файл — под `orchestrator/`; в патче ровно один хунк с
    изменёнными строками (одна мутация — одно место кода).

    Ловит мутацию: разработчик пропустил номер при переписывании набора
    (есть 001, 002, 004) или положил в один патч две правки (второй хунк,
    второй файл) либо правку `tests/` — перечень/патч отличается, тест
    краснеет с именем патча.
    """
    names = _patch_names()
    numbers = sorted(names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), (
        f"номера патчей не подряд: {numbers}")
    problems = []
    for number, name in sorted(names.items()):
        text = artifact_text(name)
        if text is None:
            problems.append(f"{name}: не читается из ссылки документов")
            continue
        paths = _plan.patch_paths(text)
        outside = sorted(p for p in paths if not p.startswith("orchestrator/"))
        if not paths:
            problems.append(f"{name}: в патче нет ни одного пути")
        if outside:
            problems.append(f"{name}: меняет файлы вне orchestrator/: {outside}")
        if len(paths) != 1:
            problems.append(f"{name}: меняет не один файл: {sorted(paths)}")
        if _plan.hunk_count(text) != 1 or _plan.changed_line_count(text) < 1:
            problems.append(f"{name}: хунков {_plan.hunk_count(text)}, "
                            f"изменённых строк {_plan.changed_line_count(text)} "
                            f"— ожидалась одна мутация (один хунк с правкой)")
    assert not problems, "\n".join(problems)


def test_ac1_every_claim_and_unclaimed_notes_test_mapped_to_mutation():
    """Каждая заявка исходных файлов и 26 тестов без заявки сопоставлены мутации.

    Из базы ветки разбираются четыре исходных файла: тесты со строкой
    «Ловит мутацию» во всех четырёх и все тесты `tests/test_notes.py` (у
    26 из них строки нет). Для каждого в PLAN есть строка вне таблиц, где
    `<Класс>::<метод>` теста стоит рядом со ссылкой на патч набора.

    Ловит мутацию: PLAN сопоставляет мутации только тестам со строкой
    «Ловит мутацию», а 26 тестов `tests/test_notes.py` без неё пропущены
    (или забыт один файл волны) — перечень несопоставленных непуст.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    numbers = set(_patch_names())
    mapped = defaultdict(set)
    for line in _plan.prose_lines(plan):
        hit = _plan.refs(line) & numbers
        if hit:
            for key in _plan.test_keys(line):
                mapped[key] |= hit
    need, unclaimed_notes = [], 0
    for path in _plan.SOURCE_FILES:
        text = _plan.show(CODE_ROOT, DIFF_BASE, path)
        assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
        for test in _plan.base_tests(path, text):
            if test.claim or path == _plan.NOTES_FILE:
                need.append(test)
            if path == _plan.NOTES_FILE and not test.claim:
                unclaimed_notes += 1
    assert unclaimed_notes == 26, (
        f"в базе {_plan.NOTES_FILE} тестов без «Ловит мутацию» "
        f"{unclaimed_notes}, а критерий называет 26 — база прочитана не та")
    missing = [f"{t.path}::{t.key}" for t in need if not mapped.get(t.key)]
    assert not missing, ("тесты без сопоставленной мутации в PLAN:\n"
                         + "\n".join(missing))
